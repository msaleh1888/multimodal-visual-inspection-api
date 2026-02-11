import io
import os
import importlib
import sys
from types import SimpleNamespace

import pytest

from PIL import Image
from fastapi.testclient import TestClient
from app.analyzers.vlm_errors import VLMTimeout, VLMInvalidOutput
from app.analyzers.document_analyzer import PageExtraction, ExtractedField

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


class _FakeVLM:
    """
    Async fake VLM that can simulate:
    - timeout
    - invalid output
    """

    def __init__(self, behavior: str):
        self.behavior = behavior
        self.model_name = "fake-vlm"
        self.model_version = "test"

    def analyze(self, image_pil, vlm_input):
        if self.behavior == "timeout":
            raise VLMTimeout("simulated timeout")
        if self.behavior == "invalid_output":
            raise VLMInvalidOutput("simulated invalid json")
        raise RuntimeError(f"unknown behavior: {self.behavior}")


def _build_client_with_fake_vlm(monkeypatch, *, behavior: str) -> TestClient:
    """
    Patch the VLM factory BEFORE importing/reloading the pipeline module that instantiates _vlm.

    Key: app.pipelines.image_pipeline creates _vlm at import time.
    So we must reload that module (and routes/main) after patching.
    """
    os.environ.setdefault("LLM_ENGINE", "mock")
    os.environ.setdefault("VISION_ENGINE", "noop")
    os.environ.setdefault("VISION_BACKEND", "noop")
    os.environ.setdefault("VISION_MODEL", "noop")

    # Patch factory
    import app.analyzers.vlm_factory as vf
    monkeypatch.setattr(vf, "create_vlm_analyzer", lambda: _FakeVLM(behavior))

    # Force-reload modules that cache _vlm at import time
    for mod in (
        "app.pipelines.image_pipeline",
        "app.api.routes_image",
        "app.main",
    ):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])

    import app.main as main
    return TestClient(main.app)


def test_image_vlm_timeout_maps_to_504_and_error_schema(monkeypatch):
    client = _build_client_with_fake_vlm(monkeypatch, behavior="timeout")

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "vlm"}

    resp = client.post("/analyze/image", files=files, data=data, headers={"X-Request-Id": "it-timeout-1"})
    assert resp.status_code == 504
    assert resp.headers.get("X-Request-Id") == "it-timeout-1"

    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "timeout"
    assert body["error"]["request_id"] == "it-timeout-1"


def test_image_vlm_invalid_output_maps_to_502(monkeypatch):
    client = _build_client_with_fake_vlm(monkeypatch, behavior="invalid_output")

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "vlm"}

    resp = client.post("/analyze/image", files=files, data=data, headers={"X-Request-Id": "it-invalid-1"})
    assert resp.status_code == 502
    assert resp.headers.get("X-Request-Id") == "it-invalid-1"

    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] in {"invalid_vlm_output", "vlm_failed"}
    assert body["error"]["request_id"] == "it-invalid-1"


def _build_client_with_doc_partial_failure(monkeypatch) -> TestClient:
    """
    Build a client where:
      - preprocessing returns 2 pages (from one PNG)
      - analyzer fails on page 0 and succeeds on page 1
    This lets us test the pipeline resilience policy without PDF deps.
    """
    os.environ.setdefault("VLM_ENGINE", "mock")
    os.environ.setdefault("LLM_ENGINE", "mock")
    os.environ.setdefault("VISION_ENGINE", "noop")
    os.environ.setdefault("VISION_BACKEND", "noop")
    os.environ.setdefault("VISION_MODEL", "noop")

    # Patch preprocess_document (routes_document imports it directly)
    import app.api.routes_document as rd

    def _fake_preprocess_document(*, file_bytes: bytes, filename: str, mode: str, max_pages: int):
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        # Fake 2 pages
        pages = [img, img]
        doc_meta = SimpleNamespace(file_type="image")
        return SimpleNamespace(pages=pages, doc_meta=doc_meta)

    monkeypatch.setattr(rd, "preprocess_document", _fake_preprocess_document)

    # Build app + override dependency the FastAPI way (works even when Depends captured the function)
    import app.main as main
    importlib.reload(main)

    class _FakeDocAnalyzer:
        def analyze_page(self, *, page_image, page_index: int, mode: str, context=None):
            if page_index == 0:
                raise RuntimeError("simulated page failure")
            return PageExtraction(
                page_index=page_index,
                fields=[ExtractedField(name="invoice_total", value="100", confidence=None)],
                tables=[],
                page_confidence=None,
                warnings=[],
                engine_meta={"name": "fake-doc-analyzer", "mode": mode},
            )

    # Override the dependency in the FastAPI app
    main.app.dependency_overrides[rd.get_document_analyzer] = lambda: _FakeDocAnalyzer()

    return TestClient(main.app)

    # Reload main so the route module uses patched symbols consistently
    import app.main as main
    importlib.reload(main)

    return TestClient(main.app)

def test_document_partial_page_failure_still_returns_200_and_warnings_point_to_page(monkeypatch):
    client = _build_client_with_doc_partial_failure(monkeypatch)

    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "full", "max_pages": "2"}

    resp = client.post("/analyze/document", files=files, data=data, headers={"X-Request-Id": "it-doc-partial-1"})
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id") == "it-doc-partial-1"

    body = resp.json()
    details = body["details"]

    # Page 1 succeeded → field should appear in aggregated extracted_fields
    assert "invoice_total" in details["extracted_fields"]
    assert details["extracted_fields"]["invoice_total"]["value"] == "100"

    # Page 0 failed → warning should clearly reference page[0]
    warnings = body.get("warnings") or []
    assert any(w.startswith("page[0]:") for w in warnings)
    assert any("Analyzer exception" in w for w in warnings)