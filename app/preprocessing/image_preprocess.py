from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image, ImageOps
from fastapi import UploadFile, HTTPException


SUPPORTED_IMAGE_MIME = {"image/jpeg", "image/png"}
SUPPORTED_EXT = {".jpg", ".jpeg", ".png"}


@dataclass(frozen=True)
class PreprocessedImage:
    """Model-ready image representation."""
    width: int
    height: int
    array: np.ndarray  # float32, shape (H, W, 3), range [0, 1]


def _mb_to_bytes(mb: int) -> int:
    return mb * 1024 * 1024


async def load_and_preprocess_image(
    file: UploadFile,
    *,
    max_mb: int = 10,
    target_size: Tuple[int, int] = (224, 224),
) -> PreprocessedImage:
    """
    Validate and preprocess an uploaded image into a normalized numpy array.
    - Validates MIME type (best-effort)
    - Enforces size limit
    - Decodes with PIL
    - Fixes EXIF orientation
    - Converts to RGB
    - Resizes to target_size
    - Normalizes to float32 [0,1]
    """
    # 1) Basic type check (header-based, but not fully trustworthy)
    if file.content_type not in SUPPORTED_IMAGE_MIME:
        raise HTTPException(
            status_code=400,
            detail={"code": "unsupported_file_type", "message": f"Unsupported content_type={file.content_type}"},
        )

    # 2) Read bytes and enforce size limit
    data = await file.read()
    if len(data) > _mb_to_bytes(max_mb):
        raise HTTPException(
            status_code=413,
            detail={"code": "payload_too_large", "message": f"Image exceeds max size of {max_mb}MB"},
        )

    # 3) Decode image safely
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)  # fix orientation if EXIF present
        img = img.convert("RGB")            # standardize channels
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={"code": "unprocessable_input", "message": "Invalid or corrupted image"},
        )

    # 4) Resize
    try:
        img = img.resize(target_size, Image.BILINEAR)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={"code": "preprocessing_failed", "message": "Failed to resize image"},
        )

    # 5) Convert to normalized numpy
    arr = np.asarray(img).astype(np.float32) / 255.0  # (H, W, 3)
    h, w = arr.shape[:2]

    return PreprocessedImage(width=w, height=h, array=arr)