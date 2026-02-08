import time
import logging
from fastapi import APIRouter, File, UploadFile, Form, HTTPException

from app.config import settings
from app.preprocessing.image_preprocess import load_and_preprocess_image

from app.analyzers.vlm_base import VLMInput
from app.analyzers.vlm_factory import create_vlm_analyzer
from app.analyzers.vlm_errors import VLMTimeout, VLMInvalidOutput
from app.analyzers.vlm_runner import run_with_timeout

from app.analyzers.vision_base import VisionInput
from app.analyzers.vision_factory import create_vision_analyzer

from app.observability.metrics import (
    VLM_REQUESTS_TOTAL,
    VLM_INFERENCE_SECONDS,
    VISION_REQUESTS_TOTAL,
    VISION_INFERENCE_SECONDS,
)

router = APIRouter(prefix="/analyze", tags=["analyze"])

# Instantiate once (safe + production style)
_vlm = create_vlm_analyzer()
_vision = create_vision_analyzer()

logger = logging.getLogger(__name__)


def _normalize_mode(mode: str) -> str:
    m = (mode or "").strip().lower()
    if not m:
        return "vlm"
    if m not in {"vlm", "baseline"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_parameters", "message": "mode must be 'vlm' or 'baseline'"},
        )
    return m


def _tighten_prompt(vlm_input: VLMInput) -> VLMInput:
    extra = "IMPORTANT: Return ONLY valid JSON. No markdown. No extra text."
    base = (vlm_input.prompt or "").strip()
    new_prompt = f"{base}\n\n{extra}".strip() if base else extra
    return VLMInput(
        prompt=new_prompt,
        task=vlm_input.task,
        question=vlm_input.question,
    )


async def _run_vlm_with_retries(img_pil, vlm_input: VLMInput):
    """
    Runs the VLM with:
    - timeout mapping to 504
    - retries on invalid output
    - metrics emitted for ok/timeout/invalid_output/failed
    Returns: (VLMResult, attempts_used, duration_seconds)
    """
    retries = int(getattr(settings, "vlm_max_retries", 0))
    model_label = getattr(_vlm, "model_name", "unknown")

    last_invalid = None

    for attempt in range(retries + 1):
        try:
            result, duration_s = await run_with_timeout(_vlm.analyze, img_pil, vlm_input)

            # Metrics for successful inference
            VLM_REQUESTS_TOTAL.labels(mode="vlm", result="ok", model=model_label).inc()
            VLM_INFERENCE_SECONDS.labels(model=model_label).observe(duration_s)

            return result, (attempt + 1), duration_s

        except VLMTimeout as e:
            VLM_REQUESTS_TOTAL.labels(mode="vlm", result="timeout", model=model_label).inc()
            raise HTTPException(status_code=504, detail={"code": "timeout", "message": str(e)})

        except VLMInvalidOutput as e:
            last_invalid = e
            VLM_REQUESTS_TOTAL.labels(mode="vlm", result="invalid_output", model=model_label).inc()

            if attempt < retries:
                vlm_input = _tighten_prompt(vlm_input)
                continue

            raise HTTPException(status_code=502, detail={"code": "invalid_vlm_output", "message": str(e)})

        except Exception as e:
            VLM_REQUESTS_TOTAL.labels(mode="vlm", result="failed", model=model_label).inc()
            raise HTTPException(status_code=502, detail={"code": "vlm_failed", "message": str(e)})

    raise HTTPException(
        status_code=502,
        detail={"code": "invalid_vlm_output", "message": str(last_invalid) if last_invalid else "Invalid VLM output"},
    )


@router.post("/image")
async def analyze_image(
    file: UploadFile = File(...),
    mode: str = Form("vlm"),
    prompt: str = Form(""),
    task: str = Form(""),
    question: str = Form(""),
):
    mode = _normalize_mode(mode)

    img = await load_and_preprocess_image(
        file,
        max_mb=settings.max_image_mb,
        target_size=None,
        return_array=False,
    )

    if mode == "baseline":
        v_in = VisionInput(top_k=5, return_embedding=True, embedding_preview_len=16)

        model_label = getattr(_vision, "model_name", "unknown")
        t0 = time.perf_counter()

        try:
            v_res = _vision.analyze(img.pil, v_in)
            duration_s = time.perf_counter() - t0

            VISION_REQUESTS_TOTAL.labels(result="ok", model=model_label).inc()
            VISION_INFERENCE_SECONDS.labels(model=model_label).observe(duration_s)

        except Exception as e:
            duration_s = time.perf_counter() - t0
            VISION_REQUESTS_TOTAL.labels(result="failed", model=model_label).inc()
            VISION_INFERENCE_SECONDS.labels(model=model_label).observe(duration_s)

            logger.exception("image_analyze baseline_failed filename=%s", file.filename)
            raise HTTPException(
                status_code=502,
                detail={"code": "baseline_failed", "message": str(e)},
            )

        top1 = v_res.top_k[0] if v_res.top_k else None
        finding = f"baseline_top1: {top1.label}" if top1 else "baseline_no_prediction"
        confidence = float(top1.prob) if top1 else 0.0

        logger.info(
            "image_analyze baseline_ok model=%s top1=%s conf=%.3f duration_ms=%d filename=%s",
            v_res.model_name,
            top1.label if top1 else "n/a",
            confidence,
            int(duration_s * 1000),
            file.filename,
        )

        return {
            "finding": finding,
            "confidence": confidence,
            "details": {
                "mode": "baseline",
                "baseline": {
                    "top_k": [{"label": p.label, "prob": float(p.prob)} for p in v_res.top_k],
                    "embedding": (
                        {"dim": v_res.embedding.dim, "preview": v_res.embedding.preview}
                        if v_res.embedding is not None
                        else None
                    ),
                },
                "model": {"name": v_res.model_name, "version": v_res.model_version},
            },
            "explanation": (
                "Vision-only baseline output (ImageNet pretrained). "
                "Useful for fast sanity checks and debugging; not multimodal reasoning."
            ),
            "recommendation": "Use mode=vlm for grounded multimodal explanations and recommendations.",
            "warnings": ["baseline_imagenet_labels_may_not_match_domain"],
        }

    # --- VLM path ---
    vlm_input = VLMInput(
        prompt=prompt,
        task=task or None,
        question=question or None,
    )

    result, attempts_used, duration_s = await _run_vlm_with_retries(img.pil, vlm_input)

    logger.info(
        "image_analyze vlm_ok model=%s attempts=%d duration_ms=%d filename=%s has_prompt=%s has_task=%s",
        getattr(_vlm, "model_name", "unknown"),
        attempts_used,
        int(duration_s * 1000),
        file.filename,
        bool((prompt or "").strip()),
        bool((task or "").strip()),
    )

    return {
        "finding": result.finding,
        "confidence": float(result.confidence),
        "details": {
            "mode": "vlm",
            "vlm": {
                "task": vlm_input.task or "",
                "prompt": vlm_input.prompt or "",
                "raw_output": result.raw_output,
            },
            "model": {
                "name": result.model_name,
                "version": result.model_version,
            },
        },
        "explanation": result.explanation,
        "recommendation": result.recommendation,
        "warnings": result.warnings or [],
    }