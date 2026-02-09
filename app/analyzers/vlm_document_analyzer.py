"""
VLM-first Document Analyzer Adapter.

Why this file exists:
- Implements DocumentAnalyzer using a multimodal LLM (VLM).
- Extracts fields, tables, and confidence from a page image.
- Normalizes output into the stable internal schema defined in document_analyzer.py.
- Handles missing fields and malformed model output gracefully.

Design principles:
- VLM must return JSON ONLY (no markdown, no prose).
- Adapter never crashes on bad model output; it returns empty structured output + warnings.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Protocol, Tuple

from PIL import Image

from app.analyzers.document_analyzer import (
    Confidence,
    ExtractedField,
    ExtractedTable,
    PageExtraction,
    TableCell,
)


# =============================================================================
# Minimal VLM client interface (Issue #12 will likely replace/expand this)
# =============================================================================

class VLMClient(Protocol):
    """
    Minimal interface for a multimodal LLM client.

    The adapter sends:
      - prompt (string)
      - image bytes (base64 or raw depending on your client)
      - mime type

    The client returns:
      - model_text: expected to be JSON-only string
      - model_meta: optional model metadata (name/version/latency/tokens)
    """

    def analyze_image(
        self,
        *,
        prompt: str,
        image_b64: str,
        mime_type: str,
        model: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        ...


# =============================================================================
# Adapter implementation
# =============================================================================

DocumentMode = Literal["fast", "full"]


@dataclass
class VLMDocumentAnalyzer:
    """
    VLM-first analyzer that extracts:
      - fields (key-value)
      - tables (cells)
      - confidence (overall + per field/cell if available)

    Notes:
    - mode affects the strictness and verbosity of the prompt (fast vs full).
    - context can include optional hints like document type, expected fields, etc.
    """
    client: VLMClient
    model_name: Optional[str] = None

    def analyze_page(
        self,
        *,
        page_image: Image.Image,
        page_index: int,
        mode: DocumentMode,
        context: Optional[Dict[str, Any]] = None,
    ) -> PageExtraction:
        prompt = _build_vlm_prompt(mode=mode, context=context or {})

        image_b64 = _pil_to_base64_png(page_image)
        mime_type = "image/png"

        try:
            model_text, model_meta = self.client.analyze_image(
                prompt=prompt,
                image_b64=image_b64,
                mime_type=mime_type,
                model=self.model_name,
            )
        except Exception as e:
            # Engine failure should not kill the pipeline.
            return PageExtraction(
                page_index=page_index,
                fields=[],
                tables=[],
                page_confidence=None,
                warnings=[f"VLM call failed: {type(e).__name__}: {e}"],
                engine_meta={"name": "vlm", "model": self.model_name or "default", "mode": mode},
            )

        # Parse + normalize
        parsed, parse_warnings = _safe_parse_json(model_text)

        fields = _normalize_fields(parsed.get("fields"))
        tables = _normalize_tables(parsed.get("tables"))
        page_conf = _normalize_confidence(parsed.get("page_confidence"))

        warnings: List[str] = []
        warnings.extend(parse_warnings)

        # Optional warnings returned by the model (we accept but don't trust blindly)
        model_warnings = parsed.get("warnings")
        if isinstance(model_warnings, list):
            warnings.extend([str(w) for w in model_warnings if w is not None])

        engine_meta = {
            "name": "vlm",
            "model": model_meta.get("model", self.model_name or "default"),
            "mode": mode,
        }
        # Keep any extra meta (tokens/latency) if present
        engine_meta.update({k: v for k, v in model_meta.items() if k not in engine_meta})

        return PageExtraction(
            page_index=page_index,
            fields=fields,
            tables=tables,
            page_confidence=page_conf,
            warnings=warnings,
            engine_meta=engine_meta,
        )


# =============================================================================
# Prompting (grounded, strict JSON)
# =============================================================================

def _build_vlm_prompt(*, mode: DocumentMode, context: Dict[str, Any]) -> str:
    """
    Build a strict JSON-only prompt.

    We ask for:
      - fields: [{name, value, confidence:{score,level}}]
      - tables: [{table_index, n_rows, n_cols, confidence, cells:[{row,col,text,confidence}]}]
      - page_confidence: {score, level}
      - warnings: [string]

    Guardrails:
      - Do not invent values.
      - If unsure, use null and lower confidence.
      - Return JSON only.
    """
    doc_hint = context.get("document_type")  # optional hint like "invoice", "report", "form"
    expected_fields = context.get("expected_fields")  # optional list of field names

    verbosity = "minimal" if mode == "fast" else "detailed"

    return f"""
You are a document extraction engine. Extract information ONLY if it is visible in the image.
Do NOT guess. Do NOT invent. If information is not visible, set value to null.

Return JSON ONLY (no markdown, no extra text).
Schema:
{{
  "fields": [
    {{
      "name": "string",
      "value": "string|null",
      "confidence": {{"score": 0.0-1.0|null, "level": "low|medium|high|null"}} | null
    }}
  ],
  "tables": [
    {{
      "table_index": 0,
      "n_rows": 0,
      "n_cols": 0,
      "confidence": {{"score": 0.0-1.0|null, "level": "low|medium|high|null"}} | null,
      "cells": [
        {{
          "row": 0,
          "col": 0,
          "text": "string",
          "confidence": {{"score": 0.0-1.0|null, "level": "low|medium|high|null"}} | null
        }}
      ]
    }}
  ],
  "page_confidence": {{"score": 0.0-1.0|null, "level": "low|medium|high|null"}} | null,
  "warnings": ["string"]
}}

Extraction style: {verbosity}
Document hint (optional): {doc_hint}
Expected fields (optional): {expected_fields}

Important rules:
- Keep "fields" and "tables" as empty lists if none are found.
- "n_rows" and "n_cols" should reflect the table grid you detect; if uncertain, approximate but do not invent cells.
- Confidence.score must be between 0 and 1 if provided.
- Include warnings for low-quality scans, blur, occlusion, or unreadable text.
""".strip()


# =============================================================================
# Robust parsing + normalization helpers
# =============================================================================

def _safe_parse_json(text: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parse model output as JSON.
    If parsing fails, return empty structure + warnings.

    We do NOT attempt aggressive "JSON repair" here (that can hide issues).
    We'll keep it simple and observable.
    """
    warnings: List[str] = []

    if not text or not isinstance(text, str):
        return {"fields": [], "tables": [], "page_confidence": None, "warnings": []}, ["Empty model output."]

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            warnings.append("Model output JSON is not an object; using empty extraction.")
            return {"fields": [], "tables": [], "page_confidence": None, "warnings": []}, warnings
        # Ensure keys exist (graceful handling)
        data.setdefault("fields", [])
        data.setdefault("tables", [])
        data.setdefault("page_confidence", None)
        data.setdefault("warnings", [])
        return data, warnings
    except json.JSONDecodeError:
        warnings.append("Model output is not valid JSON; using empty extraction.")
        return {"fields": [], "tables": [], "page_confidence": None, "warnings": []}, warnings


def _normalize_confidence(raw: Any) -> Optional[Confidence]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        score = raw.get("score")
        level = raw.get("level")
        try:
            score_f = float(score) if score is not None else None
        except Exception:
            score_f = None
        level_s = str(level) if level is not None else None
        # Validate level only if it matches allowed values
        if level_s not in ("low", "medium", "high"):
            level_s = None
        try:
            return Confidence(score=score_f, level=level_s)  # validates range if score present
        except Exception:
            return Confidence(score=None, level=level_s)
    return None


def _normalize_fields(raw: Any) -> List[ExtractedField]:
    if not isinstance(raw, list):
        return []
    out: List[ExtractedField] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        value = item.get("value")
        conf = _normalize_confidence(item.get("confidence"))
        out.append(ExtractedField(name=str(name), value=None if value is None else str(value), confidence=conf))
    return out


def _normalize_tables(raw: Any) -> List[ExtractedTable]:
    if not isinstance(raw, list):
        return []
    out: List[ExtractedTable] = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        table_index = _safe_int(t.get("table_index"), default=len(out))
        n_rows = _safe_int(t.get("n_rows"), default=0)
        n_cols = _safe_int(t.get("n_cols"), default=0)
        conf = _normalize_confidence(t.get("confidence"))

        cells_raw = t.get("cells")
        cells: List[TableCell] = []
        if isinstance(cells_raw, list):
            for c in cells_raw:
                if not isinstance(c, dict):
                    continue
                row = _safe_int(c.get("row"), default=0)
                col = _safe_int(c.get("col"), default=0)
                text = c.get("text")
                if text is None:
                    continue
                cell_conf = _normalize_confidence(c.get("confidence"))
                cells.append(TableCell(row=row, col=col, text=str(text), confidence=cell_conf))

        out.append(
            ExtractedTable(
                table_index=table_index,
                n_rows=n_rows,
                n_cols=n_cols,
                cells=cells,
                confidence=conf,
            )
        )
    return out


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _pil_to_base64_png(img: Image.Image) -> str:
    """
    Convert PIL image to base64 PNG for VLM transport.
    We use PNG because it's lossless and predictable for OCR-ish tasks.
    """
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")