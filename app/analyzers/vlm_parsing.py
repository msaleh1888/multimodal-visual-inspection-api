from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import ValidationError
from app.analyzers.vlm_schema import VLMStructuredOutput


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)

def extract_json_object(text: str) -> Optional[str]:
    """
    Attempts to extract the first JSON object from a model output.
    """
    if not text:
        return None
    m = _JSON_OBJ_RE.search(text)
    return m.group(0) if m else None


def parse_structured_output(text: str) -> VLMStructuredOutput:
    raw = extract_json_object(text)
    if raw is None:
        raise ValueError("No JSON object found in model output")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e

    try:
        return VLMStructuredOutput.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"JSON does not match schema: {e}") from e