from __future__ import annotations

import json
from typing import Any, Dict, List

from app.llm.llm_client import LLMClient, LLMRequest


# -----------------------------
# Public API
# -----------------------------

def generate_grounded_explanation(
    *,
    llm: LLMClient,
    task_type: str,  # "image" | "document"
    mode: str,       # "fast" | "full"
    facts: Dict[str, Any],
    request_id: str | None = None,
) -> Dict[str, Any]:
    """
    Generate a grounded explanation and recommendation from structured facts.

    This function:
    - builds a grounded prompt
    - calls the LLM
    - parses and validates JSON
    - falls back safely on errors

    It NEVER sees raw images or documents.
    """

    prompt = _build_prompt(
        task_type=task_type,
        mode=mode,
        facts=facts,
    )

    req = LLMRequest(
        prompt=prompt,
        temperature=0.0,      # deterministic by default
        max_tokens=600,
        request_id=request_id,
    )

    try:
        res = llm.generate(req)
    except Exception as e:
        # Hard failure: LLM unavailable
        return _fallback_explanation(
            reason=f"LLM error: {type(e).__name__}",
            facts=facts,
        )

    parsed = _parse_llm_json(res.raw_text)
    if parsed is None:
        return _fallback_explanation(
            reason="Invalid JSON returned by LLM",
            facts=facts,
        )

    if not _validate_schema(parsed):
        return _fallback_explanation(
            reason="LLM JSON missing required keys",
            facts=facts,
        )

    return parsed


# -----------------------------
# Prompt construction
# -----------------------------

def _build_prompt(*, task_type: str, mode: str, facts: Dict[str, Any]) -> str:
    facts_json = json.dumps(facts, indent=2, ensure_ascii=False)

    return f"""
You are an assistant generating a grounded explanation of an automated visual inspection result.

You MUST follow these rules:
1) Use ONLY the information provided in the INPUT JSON. Do NOT invent new fields, values, numbers, entities, or conclusions.
2) If the INPUT JSON lacks enough evidence for a statement, write it as an assumption (in "assumptions") or a limitation (in "limitations").
3) If overall confidence is low OR there are warnings, you MUST mention uncertainty and recommend verification.
4) Output MUST be valid JSON matching exactly the OUTPUT SCHEMA below. No markdown. No extra keys. No extra text.

OUTPUT SCHEMA (exact keys):
{{
  "explanation": string,
  "recommendation": string,
  "risk_level": "low" | "medium" | "high",
  "assumptions": [string, ...],
  "limitations": [string, ...]
}}

RISK LEVEL GUIDANCE:
- "low": high confidence, few/no warnings, key fields present
- "medium": mixed confidence or some missing info/warnings
- "high": low confidence, many warnings, or critical info missing

TASK TYPE: {task_type}
MODE: {mode}

INPUT JSON:
{facts_json}
""".strip()


# -----------------------------
# JSON parsing & validation
# -----------------------------

_REQUIRED_KEYS = {
    "explanation",
    "recommendation",
    "risk_level",
    "assumptions",
    "limitations",
}


def _parse_llm_json(text: str) -> Dict[str, Any] | None:
    """
    Parse raw LLM output as JSON.

    We do NOT try to "fix" malformed JSON here.
    If the model violates the contract, we fail fast and fall back.
    """
    try:
        return json.loads(text)
    except Exception:
        return None


def _validate_schema(obj: Dict[str, Any]) -> bool:
    if not isinstance(obj, dict):
        return False

    if set(obj.keys()) != _REQUIRED_KEYS:
        return False

    if obj["risk_level"] not in {"low", "medium", "high"}:
        return False

    if not isinstance(obj["assumptions"], list):
        return False

    if not isinstance(obj["limitations"], list):
        return False

    return True


# -----------------------------
# Safe fallback
# -----------------------------

def _fallback_explanation(*, reason: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Conservative fallback when LLM fails or violates grounding rules.
    """

    warnings = facts.get("warnings") or []
    has_warnings = bool(warnings)

    risk = "high" if has_warnings else "medium"

    limitations: List[str] = []
    if has_warnings:
        limitations.append("The analysis contains warnings that reduce confidence.")
    limitations.append(reason)

    return {
        "explanation": (
            "A detailed explanation could not be generated reliably from the available "
            "analysis results."
        ),
        "recommendation": (
            "Review the extracted results manually and verify low-confidence items. "
            "If issues persist, re-upload higher-quality inputs."
        ),
        "risk_level": risk,
        "assumptions": [],
        "limitations": limitations,
    }