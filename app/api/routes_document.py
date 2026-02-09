from __future__ import annotations

import base64
import io
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

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
)

router = APIRouter(prefix="/analyze", tags=["analyze"])

DocumentMode = Literal["fast", "full"]


def get_document_analyzer() -> DocumentAnalyzer:
    """
    Dependency provider for document analysis.

    ✅ Fix: use VLM for document extraction instead of NoOp.
    We reuse the SAME VLM factory used by the image pipeline, so the provider/model
    stays configurable via settings (mock vs transformers).

    Note:
    - VLMDocumentAnalyzer expects JSON-only outputs. If the underlying VLM returns
      non-JSON, the analyzer will fall back to empty extraction + warnings (safe behavior).
    """
    # Local imports to avoid heavy import-time side effects and keep startup flexible.
    from app.analyzers.vlm_factory import create_vlm_analyzer
    from app.analyzers.vlm_document_analyzer import VLMDocumentAnalyzer

    # Some repos have VLMInput in different places; keep this import inside and explicit.
    from app.analyzers.vlm_base import VLMInput  # used by the image VLM analyzers
    from app.config import settings

    class VLMClientAdapter:
        """
        Adapter to bridge:
          - existing image VLM interface: vlm.analyze(PIL.Image, VLMInput) -> result.raw_output
        into:
          - document VLM client interface expected by VLMDocumentAnalyzer:
              analyze_image(prompt, image_b64, mime_type, model) -> (text, meta)
        """

        def __init__(self, vlm_analyzer: Any):
            self._vlm = vlm_analyzer

        def analyze_image(
            self,
            *,
            prompt: str,
            image_b64: str,
            mime_type: str,
            model: Optional[str] = None,
        ) -> Tuple[str, Dict[str, Any]]:
            # Decode base64 image to PIL
            img_bytes = base64.b64decode(image_b64.encode("utf-8"))
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            # Call the underlying VLM analyzer
            vlm_input = VLMInput(prompt=prompt, task=None, question=None)
            res = self._vlm.analyze(img, vlm_input)

            # VLMDocumentAnalyzer expects the model to return JSON-only text.
            # Our internal normalizer will validate/parse; if invalid -> safe fallback.
            text = getattr(res, "raw_output", None) or ""

            meta = {
                "model": getattr(res, "model_name", None)
                or getattr(self._vlm, "model_name", None)
                or (model or "unknown"),
                "version": getattr(res, "model_version", None)
                or getattr(self._vlm, "model_version", None)
                or "unknown",
            }
            return text, meta

    vlm = create_vlm_analyzer()
    client = VLMClientAdapter(vlm)

    # This is just a label passed through; actual model selection is handled inside create_vlm_analyzer()
    model_label = getattr(settings, "vlm_model_id", None)

    return VLMDocumentAnalyzer(client=client, model_name=model_label)


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