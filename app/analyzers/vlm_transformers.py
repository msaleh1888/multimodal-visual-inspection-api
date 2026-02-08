from __future__ import annotations

import torch
from transformers import AutoProcessor, AutoConfig

from app.analyzers.vlm_base import VLMImageAnalyzer, VLMInput, VLMResult
from app.analyzers.vlm_errors import VLMInvalidOutput


def _load_vlm_model(model_id: str):
    """
    Load a VLM model in a way that works across transformers versions.

    Priority:
    1) AutoModelForVision2Seq (best generic option, if available)
    2) LlavaForConditionalGeneration (LLaVA-specific fallback)
    3) Otherwise: raise actionable error
    """
    cfg = AutoConfig.from_pretrained(model_id)

    # 1) Preferred: generic Vision2Seq auto class (newer transformers)
    try:
        from transformers import AutoModelForVision2Seq
        return AutoModelForVision2Seq.from_pretrained(model_id)
    except Exception:
        pass

    # 2) LLaVA-specific fallback (older transformers often have this even if Vision2Seq is missing)
    if cfg.__class__.__name__.lower().startswith("llavaconfig"):
        try:
            from transformers import LlavaForConditionalGeneration
            return LlavaForConditionalGeneration.from_pretrained(model_id)
        except Exception as e:
            raise RuntimeError(
                "Your transformers installation cannot load LLaVA. "
                "Try upgrading: pip install -U 'transformers>=4.45' 'accelerate>=0.33'"
            ) from e

    # 3) If we reached here, we don't know how to load this model in this transformers version
    raise RuntimeError(
        f"Cannot load model '{model_id}' with your current transformers version. "
        "Please upgrade transformers (recommended) or choose a supported model."
    )


class TransformersVLMAnalyzer(VLMImageAnalyzer):
    """
    Generic VLM adapter using HuggingFace Transformers.

    Supports:
    - Newer transformers: AutoModelForVision2Seq
    - LLaVA fallback: LlavaForConditionalGeneration
    """

    def __init__(self, model_id: str, device: str | None = None, max_new_tokens: int = 200):
        self.model_id = model_id
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.max_new_tokens = max_new_tokens

        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = _load_vlm_model(model_id)

        self.model.to(self.device)
        self.model.eval()

        self.model_name = model_id
        self.model_version = "hf"

    def _build_prompt(self, vlm_input: VLMInput) -> str:
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

        try:
            output_ids = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens)
            text = self.processor.batch_decode(output_ids, skip_special_tokens=True)[0].strip()
        except Exception as e:
            raise VLMInvalidOutput(f"VLM generation failed: {e}") from e

        if not text:
            raise VLMInvalidOutput("Empty VLM output")

        finding = text.split(".")[0][:160]
        confidence = 0.5  # placeholder (no calibrated confidence)

        return VLMResult(
            finding=finding,
            confidence=confidence,
            explanation=text,
            recommendation="If unclear, try a clearer photo or a more specific prompt.",
            warnings=[],
            raw_output=text,
            model_name=self.model_name,
            model_version=self.model_version,
        )