import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image


def _make_png_bytes(w: int = 64, h: int = 64) -> bytes:
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def client() -> TestClient:
    """
    Important:
    - Set providers to MOCK before importing the app, so we don't import heavy torch/transformers.
    - This also keeps the test deterministic.
    """
    os.environ.setdefault("VLM_PROVIDER", "mock")
    os.environ.setdefault("LLM_PROVIDER", "mock")

    # Windows OpenMP workaround (harmless on non-Windows)
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")

    from app.main import app  # import after env vars

    return TestClient(app)


def test_analyze_image_includes_grounding_details(client: TestClient):
    png = _make_png_bytes()
    files = {"file": ("scan.png", png, "image/png")}
    data = {"mode": "vlm"}

    resp = client.post("/analyze/image", files=files, data=data)

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Grounding is attached under details.grounding
    details = body.get("details") or {}
    grounding = details.get("grounding") or {}

    assert isinstance(grounding, dict)
    assert grounding.get("llm_model") == "mock-llm-v1"