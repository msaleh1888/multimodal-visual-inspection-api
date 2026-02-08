from __future__ import annotations

from pydantic import BaseModel, Field, conlist
from typing import List, Optional


class VLMStructuredOutput(BaseModel):
    finding: str = Field(..., min_length=1, max_length=160)
    explanation: str = Field(..., min_length=1, max_length=2000)
    recommendation: str = Field(..., min_length=1, max_length=600)
    warnings: List[str] = Field(default_factory=list)