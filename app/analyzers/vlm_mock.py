from __future__ import annotations

from typing import List
from app.analyzers.vlm_base import VLMImageAnalyzer, VLMInput, VLMResult


class MockVLMAnalyzer(VLMImageAnalyzer):
    def __init__(self):
        self.model_name = "mock-vlm"
        self.model_version = "0.1"

    def analyze(self, image_pil, vlm_input: VLMInput) -> VLMResult:
        prompt = (vlm_input.prompt or "").strip()
        task = (vlm_input.task or "").strip()

        # Pretend we "reasoned" over image+prompt. This is for dev/testing only.
        warnings: List[str] = []
        if not prompt and not task:
            warnings.append("empty_prompt_used_default_behavior")

        finding = "visual_summary_placeholder"
        explanation = "Mock VLM output (dev mode). Replace with real VLM adapter."
        recommendation = "Enable a real VLM provider/model for multimodal reasoning."
        confidence = 0.2

        return VLMResult(
            finding=finding,
            confidence=confidence,
            explanation=explanation,
            recommendation=recommendation,
            warnings=warnings,
            raw_output=f"[MOCK] prompt={prompt} task={task} question={vlm_input.question}",
            model_name=self.model_name,
            model_version=self.model_version,
        )