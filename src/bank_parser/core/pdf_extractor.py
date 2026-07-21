"""PDF text extraction boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel


class TextBlock(BaseModel):
    page_number: int
    text: str
    bbox: tuple[float, float, float, float] | None = None


class PdfExtractionError(RuntimeError):
    """Raised when statement text cannot be extracted from a PDF."""


class PdfNoExtractableTextError(PdfExtractionError):
    """Raised when a PDF has no extractable text blocks."""

    code = "scanned_pdf_no_text"


class PdfEncryptedError(PdfExtractionError):
    """Raised when a PDF is encrypted or password protected."""

    code = "encrypted_pdf"


class PdfOpenError(PdfExtractionError):
    """Raised when a PDF cannot be opened for text extraction."""

    code = "corrupt_pdf"


def extract_text_blocks(pdf_path: str | Path) -> list[TextBlock]:
    """Extract positioned text blocks from a PDF.

    Blocks are returned in deterministic page, vertical, then horizontal order.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(path)

    try:
        import fitz
    except ImportError as exc:
        raise PdfExtractionError("PyMuPDF is required for PDF text extraction.") from exc

    try:
        document = fitz.open(path)
    except Exception as exc:  # pragma: no cover - exact PyMuPDF errors vary by version.
        _raise_pdf_open_error(path, exc)

    blocks: list[TextBlock] = []
    try:
        for page_index, page in enumerate(document, start=1):
            page_blocks = _extract_page_blocks(page)
            for block in sorted(page_blocks, key=_block_sort_key):
                text = str(block[4]).strip()
                if not text:
                    continue

                blocks.append(
                    TextBlock(
                        page_number=page_index,
                        text=text,
                        bbox=(
                            float(block[0]),
                            float(block[1]),
                            float(block[2]),
                            float(block[3]),
                        ),
                    )
                )
    finally:
        close = getattr(document, "close", None)
        if callable(close):
            close()

    if not blocks:
        raise PdfNoExtractableTextError(
            "PDF contains no extractable text blocks. It may be scanned or image-only."
        )

    return blocks


def _extract_page_blocks(page: Any) -> list[tuple[Any, ...]]:
    try:
        raw_blocks = page.get_text("blocks")
    except Exception as exc:  # pragma: no cover - exact PyMuPDF errors vary by version.
        raise PdfExtractionError("Could not extract text blocks from PDF page.") from exc

    return [block for block in raw_blocks if len(block) >= 5]


def _block_sort_key(block: tuple[Any, ...]) -> tuple[float, float]:
    return (float(block[1]), float(block[0]))


def _raise_pdf_open_error(path: Path, exc: Exception) -> None:
    error_text = str(exc).lower()
    if "encrypt" in error_text or "password" in error_text:
        raise PdfEncryptedError(f"PDF is encrypted or password protected: {path}") from exc

    raise PdfOpenError(f"Could not open PDF for extraction: {path}") from exc
