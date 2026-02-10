from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------
# Shared
# ---------

class ModelInfo(BaseModel):
    name: str
    version: str


class MetaInfo(BaseModel):
    duration_ms: Optional[int] = None
    attempts_used: Optional[int] = None


# ---------
# VLM details
# ---------

class VLMDetails(BaseModel):
    task: str = ""
    prompt: str = ""
    raw_output: Optional[Any] = None  # keep flexible; mock returns string, real models may return dict


# ---------
# Baseline details
# ---------

class BaselinePrediction(BaseModel):
    label: str
    prob: float


class BaselineEmbedding(BaseModel):
    dim: int
    preview: List[float] = Field(default_factory=list)


class BaselineDetails(BaseModel):
    top_k: List[BaselinePrediction] = Field(default_factory=list)
    embedding: Optional[BaselineEmbedding] = None


# ---------
# Grounding details (LLM explainer metadata)
# ---------

class GroundingDetails(BaseModel):
    risk_level: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    llm_model: Optional[str] = None


# ---------
# Details union (mode + model always present)
# ---------

class AnalyzeImageDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["vlm", "baseline"]
    model: ModelInfo
    meta: Optional[MetaInfo] = None
    grounding: Optional[GroundingDetails] = None

    # exactly one of these should exist depending on mode
    vlm: Optional[VLMDetails] = None
    baseline: Optional[BaselineDetails] = None


# ---------
# Top-level response
# ---------

class AnalyzeImageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding: str
    confidence: float
    details: AnalyzeImageDetails
    explanation: str
    recommendation: str
    warnings: List[str] = Field(default_factory=list)


# ---------
# Optional: consistent error payload (matches your contract)
# ---------

class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody