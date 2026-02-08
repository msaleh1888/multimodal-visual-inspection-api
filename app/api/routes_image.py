import logging
from fastapi import APIRouter, File, UploadFile, Form, HTTPException

from app.config import settings
from app.preprocessing.image_preprocess import load_and_preprocess_image
from app.analyzers.vlm_base import VLMInput
from app.analyzers.vlm_factory import create_vlm_analyzer
from app.analyzers.vlm_errors import VLMTimeout, VLMInvalidOutput
from app.analyzers.vlm_runner import run_with_timeout
from app.observability.metrics import VLM_REQUESTS_TOTAL, VLM_INFERENCE_SECONDS

router = APIRouter(prefix="/analyze", tags=["analyze"])

# Instantiate once (safe + production style)
_vlm = create_vlm_analyzer()

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
        # Basic log: baseline requested
        logger.info(
            "image_analyze baseline_not_implemented filename=%s content_type=%s",
            file.filename,
            file.content_type,
        )
        return {
            "finding": "baseline_not_implemented",
            "confidence": 0.0,
            "details": {
                "mode": "baseline",
                "model": {"name": "n/a", "version": "n/a"},
            },
            "explanation": "Baseline mode is not implemented yet. Use mode=vlm.",
            "recommendation": "Use mode=vlm with an optional prompt/task.",
            "warnings": ["baseline_mode_not_available"],
        }

    vlm_input = VLMInput(
        prompt=prompt,
        task=task or None,
        question=question or None,
    )

    result, attempts_used, duration_s = await _run_vlm_with_retries(img.pil, vlm_input)

    # Basic log: VLM success
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