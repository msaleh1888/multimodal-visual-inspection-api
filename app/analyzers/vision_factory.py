from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, List, Optional


def _get_vision_engine() -> str:
    """
    Read configured vision engine.

    We support multiple env var names to keep tests robust across refactors.
    """
    for key in ("VISION_ENGINE", "VISION_BACKEND", "VISION_MODEL"):
        val = os.getenv(key)
        if val:
            return val.strip().lower()
    return "resnet"  # default


# --------
# NoOp runtime-compatible analyzer (no torch import)
# --------

@dataclass(frozen=True)
class _NoOpTop1:
    label: str
    prob: float


@dataclass(frozen=True)
class _NoOpEmbedding:
    dim: int
    preview: List[float]


@dataclass(frozen=True)
class _NoOpVisionResult:
    model_name: str
    model_version: str
    top_k: List[_NoOpTop1]
    embedding: Optional[_NoOpEmbedding]


@dataclass(frozen=True)
class NoOpVisionAnalyzer:
    """
    Lightweight analyzer used for integration tests and environments without torch.

    Contract (runtime):
    - has model_name, model_version
    - has analyze(image_pil, inp) -> result with:
        model_name, model_version, top_k[{label, prob}], embedding{dim, preview}|None
    """
    model_name: str = "noop-vision"
    model_version: str = "0"

    def analyze(self, image_pil: Any, inp: Any) -> _NoOpVisionResult:
        # The pipeline reads these fields from VisionInput.
        top_k = max(1, int(getattr(inp, "top_k", 1)))
        return_embedding = bool(getattr(inp, "return_embedding", False))
        preview_len = max(0, int(getattr(inp, "embedding_preview_len", 0)))

        preds = [_NoOpTop1(label="noop", prob=1.0)]
        preds = preds[:top_k]

        emb = None
        if return_embedding:
            emb = _NoOpEmbedding(dim=preview_len, preview=[0.0 for _ in range(preview_len)])

        return _NoOpVisionResult(
            model_name=self.model_name,
            model_version=self.model_version,
            top_k=preds,
            embedding=emb,
        )


def create_vision_analyzer() -> Any:
    """
    Factory for the vision analyzer.

    Critical rule:
    - Do NOT import torch-based implementations unless the selected engine needs them.
    """
    engine = _get_vision_engine()

    if engine in {"noop", "none", "disabled"}:
        return NoOpVisionAnalyzer()

    if engine in {"resnet", "resnet50", "imagenet"}:
        # Lazy import to avoid importing torch in test environments
        from app.analyzers.vision_resnet import ResNetVisionAnalyzer

        return ResNetVisionAnalyzer()

    # Safe default: keep service alive and explicit
    return NoOpVisionAnalyzer()
