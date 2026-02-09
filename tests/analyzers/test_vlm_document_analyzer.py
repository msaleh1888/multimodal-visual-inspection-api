import pytest
from PIL import Image

from app.analyzers.vlm_document_analyzer import VLMDocumentAnalyzer


class FakeVLMClient:
    """
    Deterministic fake VLM client for unit tests.
    We can inject desired model outputs without calling any real API.
    """

    def __init__(self, *, text: str, meta=None, raise_exc: Exception | None = None):
        self._text = text
        self._meta = meta or {"model": "fake-vlm-1"}
        self._raise = raise_exc

    def analyze_image(self, *, prompt: str, image_b64: str, mime_type: str, model=None):
        if self._raise is not None:
            raise self._raise
        # We ignore prompt/image content here; unit tests focus on adapter normalization behavior.
        return self._text, self._meta


def _blank_image():
    # Small deterministic image
    return Image.new("RGB", (64, 64))


def test_valid_json_normalizes_fields_tables_and_confidence():
    client = FakeVLMClient(
        text="""
        {
          "fields": [
            {"name": "InvoiceNumber", "value": "INV-001",
             "confidence": {"score": 0.91, "level": "high"}}
          ],
          "tables": [
            {
              "table_index": 0,
              "n_rows": 2,
              "n_cols": 2,
              "confidence": {"score": 0.80, "level": "medium"},
              "cells": [
                {"row": 0, "col": 0, "text": "Item", "confidence": {"score": 0.9, "level": "high"}},
                {"row": 0, "col": 1, "text": "Price", "confidence": {"score": 0.9, "level": "high"}},
                {"row": 1, "col": 0, "text": "A", "confidence": {"score": 0.7, "level": "medium"}},
                {"row": 1, "col": 1, "text": "10", "confidence": {"score": 0.7, "level": "medium"}}
              ]
            }
          ],
          "page_confidence": {"score": 0.85, "level": "high"},
          "warnings": ["low contrast"]
        }
        """
    )
    analyzer = VLMDocumentAnalyzer(client=client, model_name="fake-model")

    result = analyzer.analyze_page(
        page_image=_blank_image(),
        page_index=0,
        mode="fast",
        context={"document_type": "invoice"},
    )

    # Fields
    assert result.page_index == 0
    assert len(result.fields) == 1
    assert result.fields[0].name == "InvoiceNumber"
    assert result.fields[0].value == "INV-001"
    assert result.fields[0].confidence is not None
    assert result.fields[0].confidence.score == pytest.approx(0.91)
    assert result.fields[0].confidence.level == "high"

    # Tables
    assert len(result.tables) == 1
    t0 = result.tables[0]
    assert t0.table_index == 0
    assert t0.n_rows == 2
    assert t0.n_cols == 2
    assert t0.confidence is not None
    assert t0.confidence.score == pytest.approx(0.80)

    assert len(t0.cells) == 4
    assert any(c.row == 1 and c.col == 1 and c.text == "10" for c in t0.cells)

    # Page confidence + warnings
    assert result.page_confidence is not None
    assert result.page_confidence.score == pytest.approx(0.85)
    assert "low contrast" in [w.lower() for w in result.warnings]

    # Engine meta
    assert result.engine_meta["name"] == "vlm"
    assert result.engine_meta["mode"] == "fast"


def test_invalid_json_returns_empty_extraction_with_warning():
    client = FakeVLMClient(text="NOT JSON AT ALL")
    analyzer = VLMDocumentAnalyzer(client=client)

    result = analyzer.analyze_page(
        page_image=_blank_image(),
        page_index=2,
        mode="full",
    )

    assert result.page_index == 2
    assert result.fields == []
    assert result.tables == []
    assert result.page_confidence is None
    assert any("not valid json" in w.lower() for w in result.warnings)


def test_missing_keys_are_handled_gracefully():
    # No fields/tables/page_confidence keys
    client = FakeVLMClient(text='{"warnings":["ok"]}')
    analyzer = VLMDocumentAnalyzer(client=client)

    result = analyzer.analyze_page(
        page_image=_blank_image(),
        page_index=1,
        mode="fast",
    )

    assert result.fields == []
    assert result.tables == []
    assert result.page_confidence is None
    assert any("ok" == w.lower() for w in result.warnings)


def test_client_exception_returns_empty_extraction_with_warning():
    client = FakeVLMClient(text="{}", raise_exc=TimeoutError("timeout"))
    analyzer = VLMDocumentAnalyzer(client=client)

    result = analyzer.analyze_page(
        page_image=_blank_image(),
        page_index=0,
        mode="fast",
    )

    assert result.fields == []
    assert result.tables == []
    assert result.page_confidence is None
    assert any("vlm call failed" in w.lower() for w in result.warnings)