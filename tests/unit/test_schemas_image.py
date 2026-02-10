import pytest
from pydantic import ValidationError

from app.api.schemas_image import AnalyzeImageResponse


def _valid_payload_with_grounding():
    return {
        "finding": "visual_summary_placeholder",
        "confidence": 0.2,
        "details": {
            "mode": "vlm",
            "model": {"name": "mock-vlm", "version": "0.1"},
            "meta": {"duration_ms": 1, "attempts_used": 1},
            "grounding": {
                "risk_level": "high",
                "assumptions": [],
                "limitations": ["LLM JSON missing required keys"],
                "llm_model": "mock-llm-v1",
            },
            "vlm": {"task": "", "prompt": "", "raw_output": "[MOCK] ..."},
            "baseline": None,
        },
        "explanation": "fallback explanation",
        "recommendation": "fallback recommendation",
        "warnings": ["empty_prompt_used_default_behavior"],
    }


def test_analyze_image_response_accepts_grounding_details():
    payload = _valid_payload_with_grounding()
    model = AnalyzeImageResponse.model_validate(payload)
    assert model.details.grounding is not None
    assert model.details.grounding.llm_model == "mock-llm-v1"


def test_analyze_image_response_rejects_extra_top_level_keys():
    payload = _valid_payload_with_grounding()
    payload["unexpected"] = "nope"

    with pytest.raises(ValidationError):
        AnalyzeImageResponse.model_validate(payload)


def test_analyze_image_response_rejects_extra_details_keys():
    payload = _valid_payload_with_grounding()
    payload["details"]["unexpected_details_key"] = 123

    with pytest.raises(ValidationError):
        AnalyzeImageResponse.model_validate(payload)