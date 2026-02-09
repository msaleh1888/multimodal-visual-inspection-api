import io
import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes_document


def _make_test_app() -> FastAPI:
    """
    Create a minimal FastAPI app for testing ONLY the document route.
    This avoids importing app.main (which pulls image pipeline -> torch).
    """
    app = FastAPI()
    app.include_router(routes_document.router)
    return app


client = TestClient(_make_test_app())


def _make_png_bytes(width: int = 64, height: int = 64) -> bytes:
    img = Image.new("RGB", (width, height))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_analyze_document_happy_path_returns_contract_shape_and_request_id():
    png = _make_png_bytes()

    headers = {"X-Request-Id": "req-123"}
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "full", "max_pages": "10"}

    resp = client.post("/analyze/document", headers=headers, files=files, data=data)

    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id") == "req-123"

    body = resp.json()
    assert "finding" in body
    assert "confidence" in body
    assert "details" in body
    assert "explanation" in body
    assert "recommendation" in body
    assert "warnings" in body

    assert "extracted_fields" in body["details"]
    assert "tables" in body["details"]
    assert "model" in body["details"]
    assert "name" in body["details"]["model"]
    assert "version" in body["details"]["model"]
    assert isinstance(body["warnings"], list)


def test_analyze_document_generates_request_id_when_missing():
    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "fast", "max_pages": "5"}

    resp = client.post("/analyze/document", files=files, data=data)

    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id")
    assert len(resp.headers["X-Request-Id"]) > 0


def test_analyze_document_rejects_invalid_mode():
    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "invalid", "max_pages": "10"}

    resp = client.post("/analyze/document", files=files, data=data)

    assert resp.status_code == 422


def test_analyze_document_rejects_non_positive_max_pages():
    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "full", "max_pages": "0"}

    resp = client.post("/analyze/document", files=files, data=data)

    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "invalid_parameters"


def test_analyze_document_unsupported_file_type_returns_400():
    bad = b"NOT_A_PDF_OR_IMAGE"
    files = {"file": ("file.bin", bad, "application/octet-stream")}
    data = {"mode": "full", "max_pages": "10"}

    resp = client.post("/analyze/document", files=files, data=data)

    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "unsupported_file_type"


def test_analyze_document_too_large_returns_413(monkeypatch):
    def _raise(*args, **kwargs):
        from app.preprocessing.document import DocumentTooLargeError
        raise DocumentTooLargeError("too big")

    monkeypatch.setattr(routes_document, "preprocess_document", _raise)

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "full", "max_pages": "10"}

    resp = client.post("/analyze/document", files=files, data=data)

    assert resp.status_code == 413
    body = resp.json()
    assert body["error"]["code"] == "payload_too_large"


def test_analyze_document_parse_error_returns_422(monkeypatch):
    def _raise(*args, **kwargs):
        from app.preprocessing.document import DocumentParseError
        raise DocumentParseError("encrypted pdf")

    monkeypatch.setattr(routes_document, "preprocess_document", _raise)

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "full", "max_pages": "10"}

    resp = client.post("/analyze/document", files=files, data=data)

    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "document_parse_error"