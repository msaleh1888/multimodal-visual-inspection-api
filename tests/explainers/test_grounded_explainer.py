import json

from app.explainers.grounded_explainer import generate_grounded_explanation
from app.llm.llm_client import LLMClient, LLMRequest, LLMResult


class _GoodJSONLLM(LLMClient):
    @property
    def model_id(self) -> str:
        return "good-json-llm"

    def generate(self, req: LLMRequest) -> LLMResult:
        payload = {
            "explanation": "Based only on the provided facts, some fields may be missing.",
            "recommendation": "Verify low-confidence items and re-upload clearer inputs if needed.",
            "risk_level": "medium",
            "assumptions": ["Document type inferred from available field names."],
            "limitations": ["Some fields were not present in the extracted facts."],
        }
        return LLMResult(
            raw_text=json.dumps(payload),
            model_id=self.model_id,
            latency_ms=1,
            attempts=1,
            meta={"mock": True},
        )


class _InvalidJSONLLM(LLMClient):
    @property
    def model_id(self) -> str:
        return "invalid-json-llm"

    def generate(self, req: LLMRequest) -> LLMResult:
        # Not JSON
        return LLMResult(
            raw_text="Here is your answer: explanation=..., recommendation=...",
            model_id=self.model_id,
            latency_ms=1,
            attempts=1,
            meta={"mock": True},
        )


class _MissingKeysLLM(LLMClient):
    @property
    def model_id(self) -> str:
        return "missing-keys-llm"

    def generate(self, req: LLMRequest) -> LLMResult:
        # JSON but missing required keys
        payload = {
            "explanation": "ok",
            "recommendation": "ok",
            # missing risk_level, assumptions, limitations
        }
        return LLMResult(
            raw_text=json.dumps(payload),
            model_id=self.model_id,
            latency_ms=1,
            attempts=1,
            meta={"mock": True},
        )


class _BadRiskLevelLLM(LLMClient):
    @property
    def model_id(self) -> str:
        return "bad-risk-llm"

    def generate(self, req: LLMRequest) -> LLMResult:
        payload = {
            "explanation": "ok",
            "recommendation": "ok",
            "risk_level": "critical",  # invalid
            "assumptions": [],
            "limitations": [],
        }
        return LLMResult(
            raw_text=json.dumps(payload),
            model_id=self.model_id,
            latency_ms=1,
            attempts=1,
            meta={"mock": True},
        )


class _RaisingLLM(LLMClient):
    @property
    def model_id(self) -> str:
        return "raising-llm"

    def generate(self, req: LLMRequest) -> LLMResult:
        raise RuntimeError("boom")


def test_grounded_explainer_returns_valid_json_when_llm_obeys_contract():
    llm = _GoodJSONLLM()

    facts = {
        "overall_confidence": 0.6,
        "warnings": ["page[0]: low_confidence"],
        "extracted_fields": {"invoice_number": {"value": "INV-123", "confidence": 0.9}},
        "tables": [],
    }

    out = generate_grounded_explanation(
        llm=llm,
        task_type="document",
        mode="full",
        facts=facts,
        request_id="rid-1",
    )

    # Schema keys
    assert set(out.keys()) == {"explanation", "recommendation", "risk_level", "assumptions", "limitations"}
    assert out["risk_level"] in {"low", "medium", "high"}
    assert isinstance(out["assumptions"], list)
    assert isinstance(out["limitations"], list)


def test_grounded_explainer_falls_back_on_invalid_json():
    llm = _InvalidJSONLLM()

    facts = {
        "overall_confidence": 0.8,
        "warnings": [],
        "extracted_fields": {},
        "tables": [],
    }

    out = generate_grounded_explanation(
        llm=llm,
        task_type="image",
        mode="fast",
        facts=facts,
        request_id="rid-2",
    )

    assert set(out.keys()) == {"explanation", "recommendation", "risk_level", "assumptions", "limitations"}
    # No warnings -> fallback uses medium risk by default
    assert out["risk_level"] in {"medium", "high"}
    assert any("Invalid JSON" in s or "Invalid" in s or "JSON" in s for s in out["limitations"])


def test_grounded_explainer_falls_back_on_missing_required_keys():
    llm = _MissingKeysLLM()

    facts = {
        "overall_confidence": 0.9,
        "warnings": [],
        "extracted_fields": {"x": {"value": "y", "confidence": 0.9}},
        "tables": [],
    }

    out = generate_grounded_explanation(
        llm=llm,
        task_type="document",
        mode="full",
        facts=facts,
        request_id="rid-3",
    )

    assert set(out.keys()) == {"explanation", "recommendation", "risk_level", "assumptions", "limitations"}
    assert any("missing required keys" in s.lower() for s in out["limitations"])


def test_grounded_explainer_falls_back_on_invalid_risk_level():
    llm = _BadRiskLevelLLM()

    facts = {
        "overall_confidence": 0.9,
        "warnings": [],
        "extracted_fields": {},
        "tables": [],
    }

    out = generate_grounded_explanation(
        llm=llm,
        task_type="image",
        mode="full",
        facts=facts,
        request_id="rid-4",
    )

    assert set(out.keys()) == {"explanation", "recommendation", "risk_level", "assumptions", "limitations"}
    assert out["risk_level"] in {"medium", "high"}  # fallback


def test_grounded_explainer_raises_llm_errors_as_fallback_and_marks_high_when_warnings_exist():
    llm = _RaisingLLM()

    facts = {
        "overall_confidence": 0.2,
        "warnings": ["page[0]: Model output is not valid JSON; using empty extraction."],
        "extracted_fields": {},
        "tables": [],
    }

    out = generate_grounded_explanation(
        llm=llm,
        task_type="document",
        mode="full",
        facts=facts,
        request_id="rid-5",
    )

    assert set(out.keys()) == {"explanation", "recommendation", "risk_level", "assumptions", "limitations"}
    # With warnings, fallback should be high risk (per our current fallback logic)
    assert out["risk_level"] == "high"
    assert any("LLM error" in s for s in out["limitations"])