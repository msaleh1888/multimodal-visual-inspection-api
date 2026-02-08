from fastapi import APIRouter, File, UploadFile, Form

from app.config import settings
from app.preprocessing.image_preprocess import load_and_preprocess_image
from app.analyzers.vlm_base import VLMInput
from app.analyzers.vlm_mock import MockVLMAnalyzer

router = APIRouter(prefix="/analyze", tags=["analyze"])


# Start with mock to guarantee it runs everywhere.
_vlm = MockVLMAnalyzer()

@router.post("/image")
async def analyze_image(
    file: UploadFile = File(...),
    mode: str = Form("vlm"),          # "vlm" or "baseline"
    prompt: str = Form(""),
    task: str = Form(""),
    question: str = Form(""),
):
    img = await load_and_preprocess_image(
        file,
        max_mb=settings.max_image_mb,
        target_size=None,     # let the VLM adapter decide
        return_array=False,   # VLM uses PIL
    )

    if mode != "vlm":
        # Baseline not implemented yet; we’ll do it in Issue #5b.
        return {
            "finding": "baseline_not_implemented",
            "confidence": 0.0,
            "details": {"mode": mode},
            "explanation": "Baseline mode is not implemented yet. Use mode=vlm.",
            "recommendation": "Use mode=vlm with an optional prompt/task.",
            "warnings": ["baseline_mode_not_available"],
        }

    vlm_input = VLMInput(prompt=prompt, task=task or None, question=question or None)
    result = _vlm.analyze(img.pil, vlm_input)

    return {
        "finding": result.finding,
        "confidence": result.confidence,
        "details": {
            "mode": "vlm",
            "vlm": {"task": task, "prompt": prompt, "raw_output": result.raw_output},
            "model": {"name": result.model_name, "version": result.model_version},
        },
        "explanation": result.explanation,
        "recommendation": result.recommendation,
        "warnings": result.warnings,
    }