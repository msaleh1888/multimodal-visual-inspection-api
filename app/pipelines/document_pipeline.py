"""
Document analysis pipeline orchestration (Issue #10).

Responsibilities:
- Coordinate page-by-page analysis using a DocumentAnalyzer adapter.
- Aggregate page-level extractions into a document-level result.
- Apply document-level policies (warnings aggregation, doc confidence).

Non-responsibilities (intentionally not here):
- FastAPI request/response handling (Issue #11)
- Document preprocessing (Issue #8)
- Model prompting/parsing (Issue #9 VLM adapter)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, List

from app.analyzers.document_analyzer import (
    Confidence,
    DocumentExtractionResult,
    DocumentAnalyzer,
    PageExtraction,
)
from app.preprocessing.document import PreprocessedDocument


DocumentMode = Literal["fast", "full"]


@dataclass(frozen=True)
class DocumentPipelineInput:
    """
    Input contract for orchestration.

    We keep it explicit and testable: this is not tied to HTTP.
    """
    preprocessed: PreprocessedDocument
    mode: DocumentMode = "fast"
    context: Optional[Dict[str, Any]] = None


def run_document_pipeline(
    *,
    inp: DocumentPipelineInput,
    analyzer: DocumentAnalyzer,
) -> DocumentExtractionResult:
    """
    Run the document analysis pipeline:
      - Analyze each page independently
      - Collect results
      - Aggregate warnings and confidence

    Resilience policy:
      - One page failure must NOT fail the whole document.
      - If the analyzer throws unexpectedly, we convert it to an empty PageExtraction with warnings.
    """
    ctx = inp.context or {}

    page_results: List[PageExtraction] = []
    warnings: List[str] = []

    for i, page_img in enumerate(inp.preprocessed.pages):
        try:
            page_result = analyzer.analyze_page(
                page_image=page_img,
                page_index=i,
                mode=inp.mode,
                context=ctx,
            )
        except Exception as e:
            # Strong safety: orchestration never lets an analyzer crash the whole pipeline.
            page_result = PageExtraction(
                page_index=i,
                fields=[],
                tables=[],
                page_confidence=None,
                warnings=[f"Analyzer exception: {type(e).__name__}: {e}"],
                engine_meta={"name": "unknown", "mode": inp.mode},
            )

        page_results.append(page_result)

        # Collect warnings (doc-level union)
        if page_result.warnings:
            warnings.extend([f"page[{i}]: {w}" for w in page_result.warnings])

    doc_confidence = _aggregate_doc_confidence(page_results)

    engine_meta = {
        "pipeline": "document",
        "mode": inp.mode,
        "pages_processed": len(page_results),
        "input_file_type": inp.preprocessed.doc_meta.file_type,
    }

    return DocumentExtractionResult(
        pages=page_results,
        doc_confidence=doc_confidence,
        warnings=warnings,
        engine_meta=engine_meta,
    )


def _aggregate_doc_confidence(pages: List[PageExtraction]) -> Optional[Confidence]:
    """
    Simple document-level confidence policy.

    Why this exists:
    - Consumers want a single signal for the whole document.
    - But page-level confidence may be missing or heterogeneous across engines.

    Policy (simple + safe):
    - If we have numeric scores for some pages: doc score = average of available scores.
    - If no numeric scores exist but levels exist: doc level = minimum (worst) level across pages.
    - If nothing exists: return None.
    """
    scores: List[float] = []
    levels: List[str] = []

    for p in pages:
        c = p.page_confidence
        if c is None:
            continue
        if c.score is not None:
            scores.append(c.score)
        if c.level is not None:
            levels.append(c.level)

    if scores:
        avg = sum(scores) / len(scores)
        # No level assigned here; we keep it numeric to avoid fake precision.
        return Confidence(score=avg, level=None)

    if levels:
        # Define an ordering: low < medium < high, choose worst-case
        rank = {"low": 0, "medium": 1, "high": 2}
        worst = min(levels, key=lambda lv: rank.get(lv, 0))
        return Confidence(score=None, level=worst)  # type: ignore[arg-type]

    return None