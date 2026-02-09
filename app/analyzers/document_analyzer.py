from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Protocol, Sequence, Tuple

from PIL import Image


# =============================================================================
# Normalized schema (engine-agnostic)
# =============================================================================

ConfidenceLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Confidence:
    """
    Normalized confidence container.

    We keep both:
      - score: optional numeric confidence in [0, 1] when an engine provides it
      - level: optional coarse bucket when only qualitative confidence is available

    Why both:
      Some engines return a float, others return "high/medium/low", and some return nothing.
    """
    score: Optional[float] = None
    level: Optional[ConfidenceLevel] = None

    def __post_init__(self) -> None:
        if self.score is not None and not (0.0 <= self.score <= 1.0):
            raise ValueError("Confidence.score must be in [0, 1].")


@dataclass(frozen=True)
class ExtractedField:
    """
    One extracted key/value pair.
    """
    name: str
    value: Optional[str] = None
    confidence: Optional[Confidence] = None


@dataclass(frozen=True)
class TableCell:
    """
    A single table cell, with optional confidence.
    """
    row: int
    col: int
    text: str
    confidence: Optional[Confidence] = None


@dataclass(frozen=True)
class ExtractedTable:
    """
    A normalized table representation.

    We store cells in a flat list to keep it engine-agnostic.
    Engines vary a lot: some output HTML-like tables, others output row arrays.
    Flat cells is the lowest common denominator.
    """
    table_index: int
    n_rows: int
    n_cols: int
    cells: List[TableCell] = field(default_factory=list)
    confidence: Optional[Confidence] = None


@dataclass(frozen=True)
class PageExtraction:
    """
    Extraction result for a single page image.
    """
    page_index: int
    fields: List[ExtractedField] = field(default_factory=list)
    tables: List[ExtractedTable] = field(default_factory=list)
    page_confidence: Optional[Confidence] = None
    warnings: List[str] = field(default_factory=list)
    engine_meta: Dict[str, Any] = field(default_factory=dict)  # engine name/version/latency/etc.


@dataclass(frozen=True)
class DocumentExtractionResult:
    """
    Document-level extraction output.

    Note: Issue #10 will aggregate pages into this and can later add doc-level summary.
    """
    pages: List[PageExtraction] = field(default_factory=list)
    doc_confidence: Optional[Confidence] = None
    warnings: List[str] = field(default_factory=list)
    engine_meta: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Adapter interface
# =============================================================================

class DocumentAnalyzer(Protocol):
    """
    Adapter interface for a document understanding engine (managed or local).

    This operates on normalized page images (from preprocessing module).
    """

    def analyze_page(
        self,
        *,
        page_image: Image.Image,
        page_index: int,
        mode: Literal["fast", "full"],
        context: Optional[Dict[str, Any]] = None,
    ) -> PageExtraction:
        """
        Analyze a single page and return normalized extraction.
        """


# =============================================================================
# Starter implementation (placeholder adapter)
# =============================================================================

@dataclass
class NoOpDocumentAnalyzer:
    """
    A safe default analyzer that returns an empty structured output.

    Why keep this:
    - Lets orchestration/API be built without depending on a real engine.
    - Useful for integration tests and for "engine not configured" behavior.
    """
    engine_name: str = "noop"
    engine_version: str = "0"

    def analyze_page(
        self,
        *,
        page_image: Image.Image,
        page_index: int,
        mode: Literal["fast", "full"],
        context: Optional[Dict[str, Any]] = None,
    ) -> PageExtraction:
        # We intentionally do nothing but keep the schema stable.
        return PageExtraction(
            page_index=page_index,
            fields=[],
            tables=[],
            page_confidence=None,
            warnings=["No document understanding engine configured; returned empty extraction."],
            engine_meta={"name": self.engine_name, "version": self.engine_version, "mode": mode},
        )


# =============================================================================
# Utilities (optional, but helpful for "missing fields handled gracefully")
# =============================================================================

def normalize_fields(raw: Optional[Sequence[Tuple[str, Any]]]) -> List[ExtractedField]:
    """
    Convert raw key/value pairs into normalized ExtractedField list.
    Missing values become None; caller can pass confidence later.
    """
    if not raw:
        return []
    out: List[ExtractedField] = []
    for k, v in raw:
        out.append(ExtractedField(name=str(k), value=None if v is None else str(v)))
    return out