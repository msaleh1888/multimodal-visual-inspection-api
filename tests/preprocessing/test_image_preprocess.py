import asyncio
import io

import numpy as np
import pytest
from PIL import Image
from starlette.datastructures import UploadFile

from app.preprocessing.image_preprocess import load_and_preprocess_image


def _make_png_bytes(w: int = 32, h: int = 16) -> bytes:
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_rejects_unsupported_content_type():
    f = UploadFile(
        filename="x.txt",
        file=io.BytesIO(b"hello"),
        headers={"content-type": "text/plain"},
    )

    with pytest.raises(Exception) as e:
        asyncio.run(load_and_preprocess_image(f))

    exc = e.value
    assert getattr(exc, "status_code", None) == 400
    assert exc.detail["code"] == "unsupported_file_type"


def test_rejects_too_large_payload():
    big = b"\x00" * (1 * 1024 * 1024 + 1)
    f = UploadFile(
        filename="big.png",
        file=io.BytesIO(big),
        headers={"content-type": "image/png"},
    )

    with pytest.raises(Exception) as e:
        asyncio.run(load_and_preprocess_image(f, max_mb=1))

    exc = e.value
    assert getattr(exc, "status_code", None) == 413
    assert exc.detail["code"] == "payload_too_large"


def test_rejects_corrupted_image_bytes():
    f = UploadFile(
        filename="scan.png",
        file=io.BytesIO(b"not-a-real-image"),
        headers={"content-type": "image/png"},
    )

    with pytest.raises(Exception) as e:
        asyncio.run(load_and_preprocess_image(f))

    exc = e.value
    assert getattr(exc, "status_code", None) == 422
    assert exc.detail["code"] == "unprocessable_input"


def test_valid_image_returns_rgb_and_dimensions():
    png = _make_png_bytes(40, 20)
    f = UploadFile(
        filename="scan.png",
        file=io.BytesIO(png),
        headers={"content-type": "image/png"},
    )

    out = asyncio.run(load_and_preprocess_image(f))

    assert out.width == 40
    assert out.height == 20
    assert out.pil.mode == "RGB"
    assert out.array is None


def test_resize_and_return_array_normalized():
    png = _make_png_bytes(10, 10)
    f = UploadFile(
        filename="scan.png",
        file=io.BytesIO(png),
        headers={"content-type": "image/png"},
    )

    out = asyncio.run(load_and_preprocess_image(f, target_size=(64, 32), return_array=True))

    assert out.width == 64
    assert out.height == 32
    assert out.pil.size == (64, 32)

    assert isinstance(out.array, np.ndarray)
    assert out.array.dtype == np.float32
    assert out.array.shape == (32, 64, 3)

    assert float(out.array.min()) >= 0.0
    assert float(out.array.max()) <= 1.0