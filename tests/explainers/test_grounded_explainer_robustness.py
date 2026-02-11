import json
from dataclasses import dataclass
from typing import Any, Optional

import pytest

from app.explainers.grounded_explainer import generate_grounded_explanation


# -----------------------------
# Test doubles (fake LLM client)
# -----------------------------

@dataclass
class _FakeLLMResponse:
    raw_text: str


class _FakeLLM:
    """
    Minimal test double for LLMClient.

    We don't need the full implementation — only:
      - generate(request) -> response with raw_text
    We also capture the last request to assert temperature/request_id/prompt content.
    """

    def __init__(self, raw_text: str, *, raise_exc: Optional[Exception] = None):
        self._raw_text = raw_text
        self._raise_exc = raise_exc
        self.last_request = None

    def generate(self, req: Any) -> _FakeLLMResponse:
        self.last_request = req
        if self._raise_exc is not None:
            raise self._raise_exc
        return _FakeLLMResponse(raw_text=self._raw_text)


# -----------------------------
# Helpers
# -----------------------------

def _facts(with_warnings: bool = False) -> dict:
    return {
        "finding": "something",
        "confidence": 0.2,
        "details": {"extracted_fields": {"invoice_total": {"value": "100", "confidence": 0.4}}},
        "warnings": ["some_warning"] if with_warnings else [],
    }


# -----------------------------
# Tests
# -----------------------------

def test_llm_request_is_deterministic_and_prompt_is_grounded():
    llm_ok_json = json.dumps(
        {
            "explanation": "Based only on input.",
            "recommendation": "Verify.",
            "risk_level": "medium",
            "assumptions": [],
            "limitations": [],
        }
    )
    llm = _FakeLLM(llm_ok_json)

    facts = _facts(with_warnings=True)
    out = generate_grounded_explanation(
        llm=llm,
        task_type="document",
        mode="full",
        facts=facts,
        request_id="rid-123",
    )

    # Returned JSON is the model output (because it's valid and matches schema)
    assert out["risk_level"] == "medium"

    # Verify request settings that reduce hallucinations / increase determinism
    assert llm.last_request is not None
    assert getattr(llm.last_request, "temperature", None) == 0.0
    assert getattr(llm.last_request, "max_tokens", None) == 600
    assert getattr(llm.last_request, "request_id", None) == "rid-123"

    # Prompt grounding rules must be present
    prompt = getattr(llm.last_request, "prompt", "")
    assert "Use ONLY the information provided in the INPUT JSON" in prompt
    assert "Output MUST be valid JSON" in prompt
    assert "No extra keys" in prompt

    # Prompt must actually contain the facts JSON (so the LLM is forced to reference it)
    assert "INPUT JSON:" in prompt
    assert '"finding": "something"' in prompt
    assert '"warnings"' in prompt


def test_invalid_json_returns_fallback_and_mentions_reason():
    llm = _FakeLLM("NOT JSON AT ALL")

    out = generate_grounded_explanation(
        llm=llm,
        task_type="image",
        mode="fast",
        facts=_facts(with_warnings=False),
        request_id="rid-badjson",
    )

    # Fallback contract should be stable
    assert out["risk_level"] in {"medium", "high"}
    assert out["assumptions"] == []
    assert isinstance(out["limitations"], list)
    assert any("Invalid JSON" in s for s in out["limitations"])


def test_missing_required_keys_returns_fallback():
    # Missing "limitations"
    bad = json.dumps(
        {
            "explanation": "x",
            "recommendation": "y",
            "risk_level": "low",
            "assumptions": [],
        }
    )
    llm = _FakeLLM(bad)

    out = generate_grounded_explanation(
        llm=llm,
        task_type="image",
        mode="fast",
        facts=_facts(with_warnings=False),
    )

    assert out["risk_level"] in {"medium", "high"}
    assert any("missing required keys" in s.lower() for s in out["limitations"])


def test_extra_keys_returns_fallback_because_schema_requires_exact_keys():
    # Your validator checks: set(obj.keys()) == _REQUIRED_KEYS
    # So extra keys must trigger fallback (this is a robustness test + docs for behavior).
    bad = json.dumps(
        {
            "explanation": "x",
            "recommendation": "y",
            "risk_level": "low",
            "assumptions": [],
            "limitations": [],
            "extra_field": "should not be here",
        }
    )
    llm = _FakeLLM(bad)

    out = generate_grounded_explanation(
        llm=llm,
        task_type="document",
        mode="full",
        facts=_facts(with_warnings=False),
    )

    assert out["risk_level"] in {"medium", "high"}
    assert any("missing required keys" in s.lower() for s in out["limitations"])


def test_llm_exception_returns_fallback_and_sets_high_risk_if_warnings_present():
    llm = _FakeLLM("", raise_exc=RuntimeError("LLM down"))

    out = generate_grounded_explanation(
        llm=llm,
        task_type="document",
        mode="full",
        facts=_facts(with_warnings=True),
        request_id="rid-err",
    )

    # Warnings present -> fallback marks risk high
    assert out["risk_level"] == "high"
    assert any("LLM error" in s for s in out["limitations"])
    assert any("warnings" in s.lower() for s in out["limitations"])