from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, List, Dict


@dataclass(frozen=True)
class VLMInput:
    prompt: str
    task: Optional[str] = None
    question: Optional[str] = None


@dataclass(frozen=True)
class VLMResult:
    finding: str
    confidence: float
    explanation: str
    recommendation: str
    warnings: List[str]
    raw_output: Optional[str]
    model_name: str
    model_version: str


class VLMImageAnalyzer(Protocol):
    def analyze(self, image_pil, vlm_input: VLMInput) -> VLMResult:
        ...