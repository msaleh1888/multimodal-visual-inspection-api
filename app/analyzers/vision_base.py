from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol


@dataclass(frozen=True)
class VisionInput:
    """
    Optional knobs for baseline vision analysis.

    For now we keep it minimal, but having an input object lets us extend later:
    - top_k
    - whether to return embeddings
    - normalization options
    """
    top_k: int = 5
    return_embedding: bool = True
    embedding_preview_len: int = 16  # don't return full vector by default


@dataclass(frozen=True)
class TopKPrediction:
    label: str
    prob: float


@dataclass(frozen=True)
class EmbeddingInfo:
    dim: int
    preview: List[float]  # only first N values, not the full embedding


@dataclass(frozen=True)
class VisionResult:
    """
    Output of the vision-only baseline analyzer.

    This is intentionally simple and API-friendly.
    """
    top_k: List[TopKPrediction]
    embedding: Optional[EmbeddingInfo]
    model_name: str
    model_version: str  # e.g., "torchvision-imagenet"
    raw_debug: Optional[dict] = None  # keep optional; useful for debugging


class VisionImageAnalyzer(Protocol):
    """
    Contract for any vision-only analyzer implementation.
    This mirrors the style of VLMImageAnalyzer.
    """
    model_name: str
    model_version: str

    def analyze(self, image_pil, inputs: VisionInput) -> VisionResult:
        ...