from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.config import settings

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

logger = logging.getLogger(__name__)

_vlm = create_vlm_analyzer()
_vision = create_vision_analyzer()


@dataclass(frozen=True)
class ImagePipelineResult:
    """
    Normalized output boundary for the image analysis pipeline.
    The API layer should be able to return this directly as JSON.
    """
    finding: str
    confidence: float
    details: Dict[str, Any]
    explanation: str
    recommendation: str
    warnings: List[str]

    mode: str
    model_name: str
    model_version: str

    # Optional meta for debugging/observability (not required by clients)
    duration_ms: Optional[int] = None
    attempts_used: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "finding": self.finding,
            "confidence": float(self.confidence),
            "details": {
                **(self.details or {}),
                "mode": self.mode,
                "model": {"name": self.model_name, "version": self.model_version},
            },
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "warnings": self.warnings or [],
        }
        # Keep meta inside details so the contract stays stable
        meta: Dict[str, Any] = {}
        if self.duration_ms is not None:
            meta["duration_ms"] = self.duration_ms
        if self.attempts_used is not None:
            meta["attempts_used"] = self.attempts_used
        if meta:
            payload["details"]["meta"] = meta
        return payload


def _tighten_prompt(vlm_input: VLMInput) -> VLMInput:
    """
    Used on retries for invalid output to push the model toward a strict format.
    (We keep it small and deterministic.)
    """
    extra = "IMPORTANT: Return ONLY valid JSON. No markdown. No extra text."
    base = (vlm_input.prompt or "").strip()
    new_prompt = f"{base}\n\n{extra}".strip() if base else extra
    return VLMInput(prompt=new_prompt, task=vlm_input.task, question=vlm_input.question)


async def _run_vlm_with_retries(img_pil, vlm_input: VLMInput) -> Tuple[Any, int, float]:
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


class ImageAnalysisPipeline:
    """
    Orchestrates image analysis for both:
    - VLM mode (multimodal reasoning)
    - Baseline mode (vision-only debug/fallback)

    Keeps routing, retries/timeouts, metrics and normalized output out of the API layer.
    """

    async def run(
        self,
        image_pil,
        mode: str,
        prompt: str = "",
        task: str = "",
        question: str = "",
        baseline_top_k: int = 5,
        baseline_return_embedding: bool = True,
        baseline_embedding_preview_len: int = 16,
    ) -> ImagePipelineResult:
        m = (mode or "").strip().lower() or "vlm"
        if m not in {"vlm", "baseline"}:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_parameters", "message": "mode must be 'vlm' or 'baseline'"},
            )

        if m == "baseline":
            return self._run_baseline(
                image_pil=image_pil,
                top_k=baseline_top_k,
                return_embedding=baseline_return_embedding,
                embedding_preview_len=baseline_embedding_preview_len,
            )

        # VLM mode
        vlm_input = VLMInput(prompt=prompt, task=(task or None), question=(question or None))
        return await self._run_vlm(image_pil=image_pil, vlm_input=vlm_input)

    def _run_baseline(
        self,
        image_pil,
        top_k: int,
        return_embedding: bool,
        embedding_preview_len: int,
    ) -> ImagePipelineResult:
        model_label = getattr(_vision, "model_name", "unknown")

        t0 = time.perf_counter()
        try:
            v_in = VisionInput(
                top_k=max(1, int(top_k)),
                return_embedding=bool(return_embedding),
                embedding_preview_len=max(0, int(embedding_preview_len)),
            )
            v_res = _vision.analyze(image_pil, v_in)
            duration_s = time.perf_counter() - t0

            VISION_REQUESTS_TOTAL.labels(result="ok", model=model_label).inc()
            VISION_INFERENCE_SECONDS.labels(model=model_label).observe(duration_s)

        except Exception as e:
            duration_s = time.perf_counter() - t0
            VISION_REQUESTS_TOTAL.labels(result="failed", model=model_label).inc()
            VISION_INFERENCE_SECONDS.labels(model=model_label).observe(duration_s)
            logger.exception("baseline_failed model=%s", model_label)
            raise HTTPException(status_code=502, detail={"code": "baseline_failed", "message": str(e)})

        top1 = v_res.top_k[0] if v_res.top_k else None
        finding = f"baseline_top1: {top1.label}" if top1 else "baseline_no_prediction"
        confidence = float(top1.prob) if top1 else 0.0

        logger.info(
            "baseline_ok model=%s top1=%s conf=%.3f duration_ms=%d",
            v_res.model_name,
            top1.label if top1 else "n/a",
            confidence,
            int(duration_s * 1000),
        )

        details = {
            "baseline": {
                "top_k": [{"label": p.label, "prob": float(p.prob)} for p in v_res.top_k],
                "embedding": (
                    {"dim": v_res.embedding.dim, "preview": v_res.embedding.preview}
                    if v_res.embedding is not None
                    else None
                ),
            }
        }

        return ImagePipelineResult(
            finding=finding,
            confidence=confidence,
            details=details,
            explanation=(
                "Vision-only baseline output (ImageNet pretrained). "
                "Useful for fast sanity checks and debugging; not multimodal reasoning."
            ),
            recommendation="Use mode=vlm for grounded multimodal explanations and recommendations.",
            warnings=["baseline_imagenet_labels_may_not_match_domain"],
            mode="baseline",
            model_name=v_res.model_name,
            model_version=v_res.model_version,
            duration_ms=int(duration_s * 1000),
        )

    async def _run_vlm(self, image_pil, vlm_input: VLMInput) -> ImagePipelineResult:
        result, attempts_used, duration_s = await _run_vlm_with_retries(image_pil, vlm_input)

        logger.info(
            "vlm_ok model=%s attempts=%d duration_ms=%d has_prompt=%s has_task=%s",
            getattr(_vlm, "model_name", "unknown"),
            attempts_used,
            int(duration_s * 1000),
            bool((vlm_input.prompt or "").strip()),
            bool((vlm_input.task or "").strip()),
        )

        details = {
            "vlm": {
                "task": vlm_input.task or "",
                "prompt": vlm_input.prompt or "",
                "raw_output": getattr(result, "raw_output", None),
            }
        }

        return ImagePipelineResult(
            finding=getattr(result, "finding", ""),
            confidence=float(getattr(result, "confidence", 0.0)),
            details=details,
            explanation=getattr(result, "explanation", ""),
            recommendation=getattr(result, "recommendation", ""),
            warnings=list(getattr(result, "warnings", []) or []),
            mode="vlm",
            model_name=getattr(result, "model_name", "unknown"),
            model_version=getattr(result, "model_version", "unknown"),
            duration_ms=int(duration_s * 1000),
            attempts_used=attempts_used,
        )