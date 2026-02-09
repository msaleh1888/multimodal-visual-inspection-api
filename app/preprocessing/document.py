"""
Document preprocessing.

Purpose (boundary layer):
- Accept uploaded document bytes (PDF or image)
- Normalize into a bounded list of RGB page images + metadata
- Enforce safety limits (bytes/pages/pixels)
- Raise domain errors that the API can map to your global error schema

Key idea:
Everything becomes "pages" (even a single PNG is treated as 1-page document).
That keeps downstream document analysis consistent and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Literal

from PIL import Image, ImageOps


# =============================================================================
# Domain Exceptions (API layer maps these to HTTP errors)
# =============================================================================

class DocumentPreprocessingError(Exception):
    """Base error for document preprocessing failures."""


class UnsupportedDocumentTypeError(DocumentPreprocessingError):
    """Uploaded file type is not supported (not PDF, not a readable image)."""


class DocumentTooLargeError(DocumentPreprocessingError):
    """Uploaded document exceeds configured byte limits."""


class DocumentParseError(DocumentPreprocessingError):
    """Failed to parse/render document (corrupt, encrypted PDF, unreadable image, missing deps)."""


# =============================================================================
# Output Contracts (what downstream pipeline consumes)
# =============================================================================

DocumentMode = Literal["fast", "full"]


@dataclass(frozen=True)
class DocumentMeta:
    file_type: Literal["pdf", "image"]
    filename: str
    input_bytes: int
    total_pages: int
    processed_pages: int
    mode: DocumentMode
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PageMeta:
    page_index: int  # 0-based
    width: int
    height: int
    resized: bool
    original_size: Optional[Tuple[int, int]] = None


@dataclass(frozen=True)
class PreprocessedDocument:
    pages: List[Image.Image]          # Always RGB
    doc_meta: DocumentMeta
    page_meta: List[PageMeta]


# =============================================================================
# Defaults (safe, overridable by callers / config later)
# =============================================================================

DEFAULT_MAX_DOC_BYTES = 20 * 1024 * 1024      # 20 MB
DEFAULT_MAX_PAGES = 10                        # Process at most 10 pages of a PDF by default
DEFAULT_MAX_PIXELS_PER_PAGE = 6_000_000       # Prevent huge scans from blowing memory

FAST_DPI = 120
FULL_DPI = 200


# =============================================================================
# Public API
# =============================================================================

def preprocess_document(
    *,
    file_bytes: bytes,
    filename: str,
    mode: DocumentMode = "fast",
    max_pages: Optional[int] = None,
    max_doc_bytes: int = DEFAULT_MAX_DOC_BYTES,
    max_pixels_per_page: int = DEFAULT_MAX_PIXELS_PER_PAGE,
) -> PreprocessedDocument:
    """
    Entry point: bytes + filename -> normalized pages + metadata.

    Raises:
      - DocumentTooLargeError
      - UnsupportedDocumentTypeError
      - DocumentParseError
    """
    _enforce_size_limit(file_bytes=file_bytes, max_doc_bytes=max_doc_bytes)

    doc_type = _detect_type(file_bytes=file_bytes, filename=filename)
    pages_limit = DEFAULT_MAX_PAGES if max_pages is None else max_pages

    if doc_type == "pdf":
        return _preprocess_pdf(
            file_bytes=file_bytes,
            filename=filename,
            mode=mode,
            max_pages=pages_limit,
            max_pixels_per_page=max_pixels_per_page,
        )

    # doc_type == "image"
    return _preprocess_image_document(
        file_bytes=file_bytes,
        filename=filename,
        mode=mode,
        max_pixels_per_page=max_pixels_per_page,
    )


# =============================================================================
# Stage 1: Validation
# =============================================================================

def _enforce_size_limit(*, file_bytes: bytes, max_doc_bytes: int) -> None:
    if len(file_bytes) > max_doc_bytes:
        raise DocumentTooLargeError(
            f"Document too large: {len(file_bytes)} bytes exceeds limit {max_doc_bytes} bytes."
        )


# =============================================================================
# Stage 2: Type detection
# =============================================================================

def _detect_type(*, file_bytes: bytes, filename: str) -> Literal["pdf", "image"]:
    """
    Detect supported types using magic bytes + Pillow verification.

    - PDF: magic bytes %PDF- (or .pdf extension fallback)
    - Image: anything Pillow can verify (png/jpg/webp/bmp/...)
    """
    name = (filename or "").lower().strip()

    if file_bytes[:5] == b"%PDF-":
        return "pdf"

    if name.endswith(".pdf"):
        # Some PDFs might not start with %PDF- exactly at byte 0 (rare/odd),
        # but we allow the renderer to decide.
        return "pdf"

    if _is_pillow_readable_image(file_bytes):
        return "image"

    raise UnsupportedDocumentTypeError(
        f"Unsupported document type for filename='{filename}'. Only PDF or image files are supported."
    )


def _is_pillow_readable_image(file_bytes: bytes) -> bool:
    from io import BytesIO
    try:
        with Image.open(BytesIO(file_bytes)) as im:
            im.verify()  # verifies header integrity
        return True
    except Exception:
        return False


# =============================================================================
# Stage 3A: PDF path
# =============================================================================

def _preprocess_pdf(
    *,
    file_bytes: bytes,
    filename: str,
    mode: DocumentMode,
    max_pages: int,
    max_pixels_per_page: int,
) -> PreprocessedDocument:
    """
    PDF -> list of rendered page images (RGB), limited by max_pages.
    """
    pages, metas, total_pages, warnings = _render_pdf_to_pages(
        file_bytes=file_bytes,
        mode=mode,
        max_pages=max_pages,
        max_pixels_per_page=max_pixels_per_page,
    )

    doc_meta = DocumentMeta(
        file_type="pdf",
        filename=filename,
        input_bytes=len(file_bytes),
        total_pages=total_pages,
        processed_pages=len(pages),
        mode=mode,
        warnings=warnings,
    )
    return PreprocessedDocument(pages=pages, doc_meta=doc_meta, page_meta=metas)


def _render_pdf_to_pages(
    *,
    file_bytes: bytes,
    mode: DocumentMode,
    max_pages: int,
    max_pixels_per_page: int,
) -> Tuple[List[Image.Image], List[PageMeta], int, List[str]]:
    """
    Render a PDF into RGB images.

    Uses PyMuPDF (fitz):
      - fast server-side rendering
      - DPI control

    Returns:
      pages, page_meta, total_pages, warnings
    """
    warnings: List[str] = []

    fitz = _import_pymupdf()

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise DocumentParseError("Failed to open PDF (corrupt or unsupported).") from e

    try:
        _reject_encrypted_pdf(doc)

        total_pages = doc.page_count
        if total_pages <= 0:
            raise DocumentParseError("PDF has no pages.")

        pages_to_process = min(total_pages, max_pages)
        if total_pages > max_pages:
            warnings.append(f"PDF has {total_pages} pages; processed only first {pages_to_process} page(s).")

        dpi = FAST_DPI if mode == "fast" else FULL_DPI
        scale = dpi / 72.0
        matrix = fitz.Matrix(scale, scale)

        pages: List[Image.Image] = []
        metas: List[PageMeta] = []

        for i in range(pages_to_process):
            img = _render_one_pdf_page(doc, page_index=i, matrix=matrix)
            img, pm, page_warnings = _normalize_page_image(
                img=img,
                page_index=i,
                max_pixels_per_page=max_pixels_per_page,
                label_prefix=f"Page {i}",
            )
            warnings.extend(page_warnings)
            pages.append(img)
            metas.append(pm)

        return pages, metas, total_pages, warnings

    except DocumentPreprocessingError:
        # re-raise our domain errors as-is
        raise
    except Exception as e:
        # any unexpected rendering failure -> DocumentParseError
        raise DocumentParseError("Failed while rendering PDF pages.") from e
    finally:
        doc.close()


def _import_pymupdf():
    try:
        import fitz  # PyMuPDF
        return fitz
    except Exception as e:
        raise DocumentParseError("PDF rendering dependency (PyMuPDF) is not available.") from e


def _reject_encrypted_pdf(doc) -> None:
    # PyMuPDF uses needs_pass for password-protected PDFs
    if getattr(doc, "needs_pass", False):
        raise DocumentParseError("PDF is encrypted/password-protected and cannot be processed.")


def _render_one_pdf_page(doc, *, page_index: int, matrix) -> Image.Image:
    """
    Render a single PDF page -> PIL RGB image (no alpha).
    """
    page = doc.load_page(page_index)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


# =============================================================================
# Stage 3B: Image-document path (single "page")
# =============================================================================

def _preprocess_image_document(
    *,
    file_bytes: bytes,
    filename: str,
    mode: DocumentMode,
    max_pixels_per_page: int,
) -> PreprocessedDocument:
    """
    Image -> 1-page document.
    """
    img = _load_image(file_bytes=file_bytes)
    img, pm, warnings = _normalize_page_image(
        img=img,
        page_index=0,
        max_pixels_per_page=max_pixels_per_page,
        label_prefix="Image",
    )

    doc_meta = DocumentMeta(
        file_type="image",
        filename=filename,
        input_bytes=len(file_bytes),
        total_pages=1,
        processed_pages=1,
        mode=mode,
        warnings=warnings,
    )
    return PreprocessedDocument(pages=[img], doc_meta=doc_meta, page_meta=[pm])


def _load_image(*, file_bytes: bytes) -> Image.Image:
    from io import BytesIO
    try:
        img = Image.open(BytesIO(file_bytes))
        return img
    except Exception as e:
        raise DocumentParseError("Failed to open image document.") from e


# =============================================================================
# Stage 4: Normalization (shared by PDF pages and image documents)
# =============================================================================

def _normalize_page_image(
    *,
    img: Image.Image,
    page_index: int,
    max_pixels_per_page: int,
    label_prefix: str,
) -> Tuple[Image.Image, PageMeta, List[str]]:
    """
    Normalize a page image:
      - apply EXIF rotation (important for scans/photos)
      - convert to RGB
      - downscale if pixel limit exceeded
      - return PageMeta + warnings
    """
    warnings: List[str] = []

    # 1) Fix EXIF orientation (no-op if no EXIF)
    img = ImageOps.exif_transpose(img)

    # 2) Normalize to RGB
    if img.mode != "RGB":
        img = img.convert("RGB")

    # 3) Downscale if too large
    img, resized, orig_size = _downscale_if_needed(img, max_pixels=max_pixels_per_page)
    if resized and orig_size is not None:
        warnings.append(
            f"{label_prefix} downscaled from {orig_size[0]}x{orig_size[1]} to {img.size[0]}x{img.size[1]}."
        )

    pm = PageMeta(
        page_index=page_index,
        width=img.size[0],
        height=img.size[1],
        resized=resized,
        original_size=orig_size if resized else None,
    )
    return img, pm, warnings


def _downscale_if_needed(img: Image.Image, *, max_pixels: int) -> Tuple[Image.Image, bool, Optional[Tuple[int, int]]]:
    """
    Ensure image <= max_pixels while preserving aspect ratio.
    Deterministic and testable.
    """
    w, h = img.size
    pixels = w * h
    if pixels <= max_pixels:
        return img, False, None

    # Scale both dims by sqrt(max_pixels / current_pixels)
    scale = (max_pixels / float(pixels)) ** 0.5
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    resized_img = img.resize((new_w, new_h), resample=Image.BILINEAR)
    return resized_img, True, (w, h)