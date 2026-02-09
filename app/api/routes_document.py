from __future__ import annotations

import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse

from app.preprocessing.document import (
    preprocess_document,
    DocumentTooLargeError,
    DocumentParseError,
    UnsupportedDocumentTypeError,
)
from app.pipelines.document_pipeline import DocumentPipelineInput, run_document_pipeline
from app.analyzers.document_analyzer import (
    Confidence,
    DocumentAnalyzer,
    DocumentExtractionResult,
    ExtractedTable,
    PageExtraction,
    NoOpDocumentAnalyzer,
)

router = APIRouter(prefix="/analyze", tags=["analyze"])

DocumentMode = Literal["fast", "full"]


def get_document_analyzer() -> DocumentAnalyzer:
    """
    Dependency provider.
    For now: NoOp analyzer so endpoint works without external VLM config.
    Replace later with VLMDocumentAnalyzer wired to your real VLM client.
    """
    return NoOpDocumentAnalyzer(engine_name="noop", engine_version="0")


@router.post("/document")
async def analyze_document(
    file: UploadFile = File(...),
    mode: DocumentMode = Form("full"),
    max_pages: int = Form(10),
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
    analyzer: DocumentAnalyzer = Depends(get_document_analyzer),
):
    """
    Analyze an uploaded document (PDF or image).

    Flow:
    - read file bytes
    - preprocess into page images (Issue #8)
    - run document pipeline orchestration (Issue #10)
    - map result to API contract response
    """
    request_id = x_request_id or str(uuid.uuid4())

    try:
        # Basic param validation
        if mode not in ("fast", "full"):
            return _error(400, "invalid_parameters", "mode must be one of: fast, full", request_id)

        if max_pages <= 0:
            return _error(400, "invalid_parameters", "max_pages must be a positive integer", request_id)

        file_bytes = await file.read()
        filename = file.filename or "uploaded"

        preprocessed = preprocess_document(
            file_bytes=file_bytes,
            filename=filename,
            mode=mode,
            max_pages=max_pages,
        )

        pipeline_inp = DocumentPipelineInput(preprocessed=preprocessed, mode=mode, context={})
        result = run_document_pipeline(inp=pipeline_inp, analyzer=analyzer)

        payload = _to_api_contract_document_response(result)
        resp = JSONResponse(status_code=200, content=payload)
        resp.headers["X-Request-Id"] = request_id
        return resp

    except DocumentTooLargeError as e:
        return _error(413, "payload_too_large", str(e), request_id)
    except UnsupportedDocumentTypeError as e:
        # Your contract currently uses 400 for unsupported files
        return _error(400, "unsupported_file_type", str(e), request_id)
    except DocumentParseError as e:
        return _error(422, "document_parse_error", str(e), request_id)
    except TimeoutError as e:
        return _error(504, "timeout", str(e), request_id)
    except Exception as e:
        # Conservative mapping for unexpected downstream failures
        return _error(502, "downstream_failure", f"{type(e).__name__}: {e}", request_id)


# -----------------------------
# Mapping: internal -> API contract
# -----------------------------

def _to_api_contract_document_response(result: DocumentExtractionResult) -> Dict[str, Any]:
    extracted_fields = _aggregate_fields(result.pages)
    tables = _flatten_tables(result.pages)

    doc_conf = _confidence_to_number(result.doc_confidence)

    finding = f"Extracted {len(extracted_fields)} field(s) and {len(tables)} table(s) from the document."
    explanation = (
        "The system processed the document page-by-page and extracted visible fields and tables. "
        "Low-confidence or unreadable content is surfaced in warnings."
    )
    recommendation = (
        "Review extracted values and validate items with low confidence. "
        "If the scan is blurry or incomplete, re-upload a higher-quality document."
    )

    model_name = str(result.engine_meta.get("pipeline", "document_pipeline"))
    model_version = str(result.engine_meta.get("version", "v1"))

    return {
        "finding": finding,
        "confidence": doc_conf,
        "details": {
            "extracted_fields": extracted_fields,
            "tables": tables,
            "model": {"name": model_name, "version": model_version},
        },
        "explanation": explanation,
        "recommendation": recommendation,
        "warnings": result.warnings or [],
    }


def _aggregate_fields(pages: List[PageExtraction]) -> Dict[str, Dict[str, Any]]:
    best: Dict[str, Dict[str, Any]] = {}

    for p in pages:
        for f in p.fields:
            if not f.name or f.value is None:
                continue
            cand_score = _confidence_to_number(f.confidence)

            if f.name not in best:
                best[f.name] = {"value": f.value, "confidence": cand_score}
                continue

            prev_score = float(best[f.name].get("confidence", 0.0) or 0.0)
            if cand_score > prev_score:
                best[f.name] = {"value": f.value, "confidence": cand_score}

    return best


def _flatten_tables(pages: List[PageExtraction]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    table_counter = 0

    for p in pages:
        for t in p.tables:
            out.append(_table_to_contract(t, name=f"table_{table_counter}"))
            table_counter += 1

    return out


def _table_to_contract(t: ExtractedTable, *, name: str) -> Dict[str, Any]:
    grid: List[List[Optional[str]]] = [
        [None for _ in range(max(t.n_cols, 0))] for _ in range(max(t.n_rows, 0))
    ]

    for c in t.cells:
        if c.row < 0 or c.col < 0:
            continue
        if c.row >= len(grid) or (len(grid) > 0 and c.col >= len(grid[0])):
            continue
        grid[c.row][c.col] = c.text

    rows: List[Dict[str, Any]] = []
    for r in grid:
        rows.append({f"col_{i}": (val if val is not None else "") for i, val in enumerate(r)})

    return {"name": name, "rows": rows}


def _confidence_to_number(c: Optional[Confidence]) -> float:
    if c is None:
        return 0.0
    if c.score is not None:
        return float(c.score)
    if c.level == "high":
        return 0.85
    if c.level == "medium":
        return 0.60
    if c.level == "low":
        return 0.30
    return 0.0


# -----------------------------
# Error response (global schema)
# -----------------------------

def _error(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    payload = {"error": {"code": code, "message": message, "request_id": request_id}}
    resp = JSONResponse(status_code=status_code, content=payload)
    resp.headers["X-Request-Id"] = request_id
    return resp