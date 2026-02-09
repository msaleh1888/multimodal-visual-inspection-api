import pytest
from PIL import Image

from app.pipelines.document_pipeline import (
    DocumentPipelineInput,
    run_document_pipeline,
)
from app.analyzers.document_analyzer import (
    Confidence,
    PageExtraction,
)
from app.preprocessing.document import (
    PreprocessedDocument,
    DocumentMeta,
)


class FakeAnalyzer:
    """
    Deterministic fake analyzer for orchestration tests.
    Can optionally fail on a given page index.
    """

    def __init__(self, *, fail_on_page: int | None = None):
        self.fail_on_page = fail_on_page

    def analyze_page(self, *, page_image, page_index, mode, context=None):
        if self.fail_on_page == page_index:
            raise RuntimeError("boom")

        return PageExtraction(
            page_index=page_index,
            fields=[],
            tables=[],
            page_confidence=Confidence(score=0.5 + 0.1 * page_index, level=None),
            warnings=[f"warning from page {page_index}"],
            engine_meta={"name": "fake"},
        )


def _fake_preprocessed_doc(num_pages: int) -> PreprocessedDocument:
    pages = [Image.new("RGB", (32, 32)) for _ in range(num_pages)]
    meta = DocumentMeta(
        file_type="pdf",
        filename="test.pdf",
        input_bytes=123,
        total_pages=num_pages,
        processed_pages=num_pages,
        mode="fast",
        warnings=[],
    )
    return PreprocessedDocument(pages=pages, doc_meta=meta, page_meta=[])


def test_pipeline_happy_path_aggregates_pages_and_confidence():
    inp = DocumentPipelineInput(
        preprocessed=_fake_preprocessed_doc(3),
        mode="fast",
    )
    analyzer = FakeAnalyzer()

    result = run_document_pipeline(inp=inp, analyzer=analyzer)

    assert len(result.pages) == 3
    assert [p.page_index for p in result.pages] == [0, 1, 2]

    # Confidence: average of [0.5, 0.6, 0.7] = 0.6
    assert result.doc_confidence is not None
    assert result.doc_confidence.score == pytest.approx(0.6)

    # Warnings are prefixed with page index
    assert "page[0]: warning from page 0" in result.warnings
    assert "page[1]: warning from page 1" in result.warnings
    assert "page[2]: warning from page 2" in result.warnings


def test_pipeline_recovers_from_analyzer_exception():
    inp = DocumentPipelineInput(
        preprocessed=_fake_preprocessed_doc(3),
        mode="fast",
    )
    analyzer = FakeAnalyzer(fail_on_page=1)

    result = run_document_pipeline(inp=inp, analyzer=analyzer)

    assert len(result.pages) == 3

    # Page 1 should be empty but present
    p1 = result.pages[1]
    assert p1.page_index == 1
    assert p1.fields == []
    assert p1.tables == []
    assert p1.page_confidence is None
    assert any("Analyzer exception" in w for w in p1.warnings)

    # Other pages still succeeded
    assert result.pages[0].page_confidence is not None
    assert result.pages[2].page_confidence is not None