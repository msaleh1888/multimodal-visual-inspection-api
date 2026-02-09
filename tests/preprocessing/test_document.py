import io

import pytest
from PIL import Image

from app.preprocessing.document import (
    preprocess_document,
    UnsupportedDocumentTypeError,
    DocumentTooLargeError,
)


def _make_png_bytes(width: int, height: int, mode: str = "RGB") -> bytes:
    img = Image.new(mode, (width, height))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_pdf_bytes_with_pages(num_pages: int = 2) -> bytes:
    """
    Create a small in-memory PDF with `num_pages` pages using reportlab.
    This avoids needing any fixture files in the repo.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    for i in range(num_pages):
        c.drawString(100, 750, f"Hello page {i+1}")
        c.showPage()
    c.save()
    return buf.getvalue()


def test_rejects_too_large_document():
    # Arrange
    data = b"x" * 101

    # Act + Assert
    with pytest.raises(DocumentTooLargeError):
        preprocess_document(
            file_bytes=data,
            filename="big.pdf",
            max_doc_bytes=100,  # tiny limit for test
        )


def test_rejects_unsupported_type():
    # Arrange: random bytes that are not an image and not a PDF
    data = b"NOT_A_PDF_OR_IMAGE"

    # Act + Assert
    with pytest.raises(UnsupportedDocumentTypeError):
        preprocess_document(
            file_bytes=data,
            filename="weird.bin",
        )


def test_image_becomes_single_rgb_page():
    # Arrange: grayscale image ("L") to confirm conversion to RGB
    png_bytes = _make_png_bytes(200, 100, mode="L")

    # Act
    result = preprocess_document(
        file_bytes=png_bytes,
        filename="scan.png",
        mode="fast",
        max_pixels_per_page=1_000_000,
    )

    # Assert
    assert result.doc_meta.file_type == "image"
    assert result.doc_meta.total_pages == 1
    assert result.doc_meta.processed_pages == 1
    assert len(result.pages) == 1
    assert result.pages[0].mode == "RGB"
    assert result.page_meta[0].page_index == 0
    assert result.page_meta[0].width == 200
    assert result.page_meta[0].height == 100


def test_huge_image_is_downscaled_and_warns():
    # Arrange: 4000x4000 = 16M pixels
    png_bytes = _make_png_bytes(4000, 4000, mode="RGB")

    # Act: cap at 1M pixels to force resizing
    result = preprocess_document(
        file_bytes=png_bytes,
        filename="huge.png",
        max_pixels_per_page=1_000_000,
    )

    # Assert: should resize down and warn
    assert result.page_meta[0].resized is True
    assert result.page_meta[0].original_size == (4000, 4000)
    assert result.pages[0].size[0] * result.pages[0].size[1] <= 1_000_000
    assert any("downscaled" in w.lower() for w in result.doc_meta.warnings)


def test_pdf_respects_max_pages_and_sets_metadata():
    # Arrange: a 3-page PDF
    pdf_bytes = _make_pdf_bytes_with_pages(num_pages=3)

    # Act: process only 2 pages
    result = preprocess_document(
        file_bytes=pdf_bytes,
        filename="doc.pdf",
        mode="fast",
        max_pages=2,
        max_pixels_per_page=6_000_000,
    )

    # Assert
    assert result.doc_meta.file_type == "pdf"
    assert result.doc_meta.total_pages == 3
    assert result.doc_meta.processed_pages == 2
    assert len(result.pages) == 2
    assert result.page_meta[0].page_index == 0
    assert result.page_meta[1].page_index == 1
    assert any("processed only first 2 page" in w.lower() for w in result.doc_meta.warnings)