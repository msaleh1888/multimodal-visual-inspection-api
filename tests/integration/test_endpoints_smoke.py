import io
import os
import importlib

from PIL import Image
from fastapi.testclient import TestClient


def _make_png_bytes(w: int = 64, h: int = 32) -> bytes:
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_client() -> TestClient:
    """
    Build a TestClient with mock/noop engines to avoid heavy deps (torch, etc.).
    Important: env vars must be set BEFORE importing app.main.
    """
    # --- VLM / LLM (mock) ---
    os.environ.setdefault("VLM_ENGINE", "mock")
    os.environ.setdefault("LLM_ENGINE", "mock")

    # --- Vision baseline (avoid torch import) ---
    os.environ.setdefault("VISION_ENGINE", "noop")

    # Some builds use different names; keep these as safe extras
    os.environ.setdefault("VISION_BACKEND", "noop")
    os.environ.setdefault("VISION_MODEL", "noop")

    # Reload app.main so env vars take effect even if tests are run repeatedly
    import app.main as main
    importlib.reload(main)

    return TestClient(main.app)


def test_smoke_analyze_image_vlm_returns_200_and_contract_shape():
    client = _build_client()

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "vlm"}

    resp = client.post("/analyze/image", files=files, data=data, headers={"X-Request-Id": "it-image-1"})
    assert resp.status_code == 200

    # Middleware should echo request id
    assert resp.headers.get("X-Request-Id") == "it-image-1"

    body = resp.json()
    assert "finding" in body
    assert "confidence" in body
    assert "details" in body
    assert "explanation" in body
    assert "recommendation" in body
    assert "warnings" in body

    details = body["details"]
    assert details["mode"] == "vlm"
    assert "model" in details and "name" in details["model"] and "version" in details["model"]
    assert "vlm" in details and details["vlm"] is not None

    # Grounding is expected after Issue #14; keep assertion flexible but meaningful
    assert "grounding" in details
    if details["grounding"] is not None:
        g = details["grounding"]
        assert "risk_level" in g
        assert "assumptions" in g
        assert "limitations" in g
        assert "llm_model" in g


def test_smoke_analyze_document_with_image_input_returns_200():
    """
    We test /analyze/document using an image input (PNG) to avoid PDF rendering
    dependencies in a minimal integration smoke test.
    """
    client = _build_client()

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "full", "max_pages": "2"}

    resp = client.post("/analyze/document", files=files, data=data, headers={"X-Request-Id": "it-doc-1"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id") == "it-doc-1"

    body = resp.json()
    assert "finding" in body
    assert "confidence" in body
    assert "details" in body
    assert "explanation" in body
    assert "recommendation" in body
    assert "warnings" in body

    details = body["details"]
    assert "extracted_fields" in details
    assert "tables" in details
    assert "model" in details and "name" in details["model"] and "version" in details["model"]


def test_image_invalid_mode_returns_400_and_error_shape_and_request_id():
    client = _build_client()

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "invalid"}

    resp = client.post("/analyze/image", files=files, data=data, headers={"X-Request-Id": "it-badmode-1"})
    assert resp.status_code == 400
    assert resp.headers.get("X-Request-Id") == "it-badmode-1"

    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "invalid_parameters"
    assert "message" in body["error"]
    assert body["error"]["request_id"] == "it-badmode-1"


def test_image_unsupported_file_type_returns_400():
    client = _build_client()

    files = {"file": ("x.txt", b"hello", "text/plain")}
    data = {"mode": "vlm"}

    resp = client.post("/analyze/image", files=files, data=data, headers={"X-Request-Id": "it-badfile-1"})
    assert resp.status_code == 400
    assert resp.headers.get("X-Request-Id") == "it-badfile-1"

    body = resp.json()
    assert body["error"]["code"] == "unsupported_file_type"
    assert body["error"]["request_id"] == "it-badfile-1"


def test_document_invalid_mode_returns_422():
    client = _build_client()

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "invalid", "max_pages": "2"}

    resp = client.post(
        "/analyze/document",
        files=files,
        data=data,
        headers={"X-Request-Id": "it-doc-badmode-1"},
    )

    # FastAPI rejects invalid Literal values before the route runs
    assert resp.status_code == 422

    # Request-ID header should still be present (middleware)
    assert resp.headers.get("X-Request-Id") == "it-doc-badmode-1"


def test_document_max_pages_must_be_positive_returns_400():
    client = _build_client()

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "full", "max_pages": "0"}

    resp = client.post("/analyze/document", files=files, data=data, headers={"X-Request-Id": "it-doc-pages-1"})
    assert resp.status_code == 400
    assert resp.headers.get("X-Request-Id") == "it-doc-pages-1"

    body = resp.json()
    assert body["error"]["code"] == "invalid_parameters"
    assert body["error"]["request_id"] == "it-doc-pages-1"