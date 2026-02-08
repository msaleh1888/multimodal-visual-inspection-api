from __future__ import annotations

import torch
from transformers import AutoProcessor, AutoModelForVision2Seq

from app.analyzers.vlm_base import VLMImageAnalyzer, VLMInput, VLMResult


class TransformersVLMAnalyzer(VLMImageAnalyzer):
    """
    Generic VLM adapter using HuggingFace Transformers.
    Works with models that support Vision2Seq (image + text -> text).
    """

    def __init__(self, model_id: str, device: str | None = None, max_new_tokens: int = 200):
        self.model_id = model_id
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.max_new_tokens = max_new_tokens

        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForVision2Seq.from_pretrained(model_id)
        self.model.to(self.device)
        self.model.eval()

        self.model_name = model_id
        self.model_version = "hf"

    def _build_prompt(self, vlm_input: VLMInput) -> str:
        # Minimal prompt builder; we can improve later.
        if vlm_input.prompt and vlm_input.prompt.strip():
            return vlm_input.prompt.strip()

        if vlm_input.task == "qa" and vlm_input.question:
            return f"Answer the question based on the image: {vlm_input.question.strip()}"

        if vlm_input.task == "describe":
            return "Describe what you see in the image."

        return "Describe what you see and suggest next steps."

    @torch.no_grad()
    def analyze(self, image_pil, vlm_input: VLMInput) -> VLMResult:
        prompt = self._build_prompt(vlm_input)

        inputs = self.processor(images=image_pil, text=prompt, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        output_ids = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens)
        text = self.processor.batch_decode(output_ids, skip_special_tokens=True)[0].strip()

        # For now: simple parsing. Later we’ll enforce JSON schema.
        finding = text.split(".")[0][:120] if text else "unknown"
        confidence = 0.5  # Many open-source VLMs don't provide calibrated confidence.

        warnings = []
        if not text:
            warnings.append("empty_vlm_output")

        return VLMResult(
            finding=finding,
            confidence=confidence,
            explanation=text or "No explanation produced.",
            recommendation="If output is unclear, try a clearer photo or a more specific prompt.",
            warnings=warnings,
            raw_output=text,
            model_name=self.model_name,
            model_version=self.model_version,
        )