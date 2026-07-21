from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from bank_parser.core.pdf_extractor import (
    PdfEncryptedError,
    PdfExtractionError,
    PdfNoExtractableTextError,
    PdfOpenError,
    extract_text_blocks,
)


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


class FakePage:
    def __init__(self, blocks: list[tuple[object, ...]]) -> None:
        self._blocks = blocks

    def get_text(self, mode: str) -> list[tuple[object, ...]]:
        assert mode == "blocks"
        return self._blocks


class FakeDocument:
    def __init__(self, pages: list[FakePage] | None = None) -> None:
        self.closed = False
        self.pages = pages or [
            FakePage(
                [
                    (100, 50, 180, 70, "second on line", 0, 0),
                    (10, 10, 90, 30, "first block", 0, 0),
                    (10, 10, 90, 30, "   ", 0, 0),
                    (10, 50, 90, 70, "first on line", 0, 0),
                ]
            ),
            FakePage([(10, 10, 90, 30, "next page", 0, 0)]),
        ]

    def __iter__(self):
        return iter(self.pages)

    def close(self) -> None:
        self.closed = True


def test_extract_text_blocks_uses_pymupdf_in_reading_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = FIXTURES_DIR / "pdfs" / "english_statement.pdf"
    document = FakeDocument()
    fake_fitz = ModuleType("fitz")
    fake_fitz.open = lambda path: document
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    blocks = extract_text_blocks(pdf_path)

    assert [block.text for block in blocks] == [
        "first block",
        "first on line",
        "second on line",
        "next page",
    ]
    assert [block.page_number for block in blocks] == [1, 1, 1, 2]
    assert blocks[0].bbox == (10.0, 10.0, 90.0, 30.0)
    assert document.closed is True


def test_extract_text_blocks_reads_committed_pdf_fixture() -> None:
    pytest.importorskip("fitz")
    pdf_path = FIXTURES_DIR / "pdfs" / "english_statement.pdf"

    blocks = extract_text_blocks(pdf_path)
    extracted_text = "\n".join(block.text for block in blocks)

    assert "Statement Date Description Debit Credit Balance" in extracted_text
    assert "2026-01-02 ATM Withdrawal 100.00 900.00" in extracted_text
    assert "2026-01-03 Salary Credit 500.00 1400.00" in extracted_text
    assert {block.page_number for block in blocks} == {1}
    assert all(block.bbox is not None for block in blocks)


def test_extract_text_blocks_reports_scanned_or_image_only_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = FIXTURES_DIR / "pdfs" / "english_statement.pdf"
    document = FakeDocument(pages=[FakePage([]), FakePage([(10, 10, 90, 30, "   ", 0, 0)])])
    fake_fitz = ModuleType("fitz")
    fake_fitz.open = lambda path: document
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    with pytest.raises(PdfNoExtractableTextError, match="no extractable text"):
        extract_text_blocks(pdf_path)

    assert PdfNoExtractableTextError.code == "scanned_pdf_no_text"
    assert document.closed is True


def test_extract_text_blocks_requires_existing_pdf() -> None:
    with pytest.raises(FileNotFoundError):
        extract_text_blocks(FIXTURES_DIR / "pdfs" / "missing.pdf")


def test_extract_text_blocks_reports_missing_pymupdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = FIXTURES_DIR / "pdfs" / "english_statement.pdf"
    monkeypatch.setitem(sys.modules, "fitz", None)

    with pytest.raises(PdfExtractionError, match="PyMuPDF is required"):
        extract_text_blocks(pdf_path)


def test_extract_text_blocks_reports_encrypted_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = FIXTURES_DIR / "pdfs" / "english_statement.pdf"
    fake_fitz = ModuleType("fitz")

    def raise_encrypted_error(path: Path) -> None:
        raise RuntimeError("cannot authenticate encrypted document without password")

    fake_fitz.open = raise_encrypted_error
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    with pytest.raises(PdfEncryptedError, match="encrypted"):
        extract_text_blocks(pdf_path)

    assert PdfEncryptedError.code == "encrypted_pdf"


def test_extract_text_blocks_reports_corrupt_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = FIXTURES_DIR / "pdfs" / "english_statement.pdf"
    fake_fitz = ModuleType("fitz")

    def raise_corrupt_error(path: Path) -> None:
        raise RuntimeError("cannot open broken document")

    fake_fitz.open = raise_corrupt_error
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    with pytest.raises(PdfOpenError, match="Could not open PDF"):
        extract_text_blocks(pdf_path)

    assert PdfOpenError.code == "corrupt_pdf"
