"""PDF text extraction boundary."""

from __future__ import annotations

from pydantic import BaseModel


class TextBlock(BaseModel):
    page_number: int
    text: str
    bbox: tuple[float, float, float, float] | None = None


def extract_text_blocks(pdf_path: str) -> list[TextBlock]:
    """Extract positioned text blocks from a PDF.

    Implementation will use PyMuPDF in the first parsing sprint.
    """
    raise NotImplementedError("PDF extraction is not implemented yet.")
