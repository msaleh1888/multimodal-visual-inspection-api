from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageOps
from fastapi import UploadFile, HTTPException


SUPPORTED_IMAGE_MIME = {"image/jpeg", "image/png"}


@dataclass(frozen=True)
class PreprocessedImage:
    width: int
    height: int
    pil: Image.Image
    array: Optional[np.ndarray] = None  # float32 [0,1], (H,W,3) if requested


def _mb_to_bytes(mb: int) -> int:
    return mb * 1024 * 1024


async def load_and_preprocess_image(
    file: UploadFile,
    *,
    max_mb: int = 10,
    target_size: Optional[Tuple[int, int]] = None,
    return_array: bool = False,
) -> PreprocessedImage:
    if file.content_type not in SUPPORTED_IMAGE_MIME:
        raise HTTPException(
            status_code=400,
            detail={"code": "unsupported_file_type", "message": f"Unsupported content_type={file.content_type}"},
        )

    data = await file.read()
    if len(data) > _mb_to_bytes(max_mb):
        raise HTTPException(
            status_code=413,
            detail={"code": "payload_too_large", "message": f"Image exceeds max size of {max_mb}MB"},
        )

    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={"code": "unprocessable_input", "message": "Invalid or corrupted image"},
        )

    if target_size is not None:
        img = img.resize(target_size, Image.BILINEAR)

    arr = None
    if return_array:
        arr = np.asarray(img).astype(np.float32) / 255.0
        h, w = arr.shape[:2]
        return PreprocessedImage(width=w, height=h, pil=img, array=arr)

    return PreprocessedImage(width=img.size[0], height=img.size[1], pil=img, array=None)