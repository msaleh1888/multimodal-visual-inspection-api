from __future__ import annotations

import json

SYSTEM_INSTRUCTION = (
    "You are a careful visual inspection assistant. "
    "You must be conservative, grounded, and avoid speculation."
)

OUTPUT_SCHEMA_HINT = {
    "finding": "short summary (<=160 chars)",
    "explanation": "grounded explanation based only on what is visible",
    "recommendation": "next steps, safe and general",
    "warnings": ["list of uncertainty notes, if any"]
}

def build_vlm_prompt(user_prompt: str) -> str:
    # Important: keep it short + strict.
    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        "Return ONLY valid JSON. No markdown, no extra text.\n"
        f"JSON keys must be exactly: finding, explanation, recommendation, warnings.\n"
        f"Schema example: {json.dumps(OUTPUT_SCHEMA_HINT)}\n\n"
        f"Task:\n{user_prompt.strip() if user_prompt.strip() else 'Describe what you see and suggest next steps.'}"
    )