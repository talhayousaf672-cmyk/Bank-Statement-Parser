"""Grid Cropper — Phase 1 preprocessing for layout-aware extraction.

Scans each PDF page for transaction table anchor words and records the
Y-axis bounding coordinates of the table region. The cropped region
coordinates are then passed to the spatial extractor.

This module does NOT extract text. It only returns coordinate bounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Anchor words that mark the TOP of a transaction table
_TABLE_TOP_ANCHORS: list[str] = [
    "transaction date",
    "txn date",
    "value date",
    "date",
    "posting date",
    "trans. date",
    "trans date",
]

# Anchor words that mark the BOTTOM of a transaction table
_TABLE_BOTTOM_ANCHORS: list[str] = [
    "closing balance",
    "closing bal",
    "total debit",
    "total credit",
    "end of statement",
    "statement total",
    "brought forward",
]

# Fallback: use 85% of the page height as the bottom boundary
_DEFAULT_BOTTOM_FRACTION = 0.90


@dataclass
class CroppedRegion:
    """Represents the bounding box of the transaction table on one page."""

    page_index: int  # 0-based
    x0: float
    y_top: float
    x1: float
    y_bottom: float

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y_top, self.x1, self.y_bottom)


def get_cropped_regions(pdf_path: str | Path) -> list[CroppedRegion]:
    """Detect transaction table regions on each page of a PDF.

    Uses PyMuPDF (fitz) bounding-box coordinates to find anchor words
    and calculate the Y-axis slice that contains only transaction rows.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        A list of CroppedRegion objects, one per page that contains table data.
        If no anchors are found on a page, the full page bounds are returned
        so that the spatial extractor can still attempt extraction.
    """
    try:
        import fitz
    except ImportError as exc:
        raise ImportError("PyMuPDF (fitz) is required. Install with: pip install pymupdf") from exc

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    regions: list[CroppedRegion] = []

    try:
        for page_idx, page in enumerate(doc):
            region = _detect_table_region(page, page_idx)
            regions.append(region)
    finally:
        doc.close()

    return regions


def _detect_table_region(page: Any, page_idx: int) -> CroppedRegion:
    """Detect the Y-axis bounds of the transaction table on a single page."""
    page_rect = page.rect
    page_width = page_rect.width
    page_height = page_rect.height

    words = page.get_text("words")  # returns list of (x0, y0, x1, y1, word, ...)
    if not words:
        # No text on page — return full page
        return CroppedRegion(
            page_index=page_idx,
            x0=0.0,
            y_top=0.0,
            x1=page_width,
            y_bottom=page_height,
        )

    y_top = _find_top_anchor(words, page_height)
    y_bottom = _find_bottom_anchor(words, page_height, y_top)

    return CroppedRegion(
        page_index=page_idx,
        x0=0.0,
        y_top=y_top,
        x1=page_width,
        y_bottom=y_bottom,
    )


def _find_top_anchor(words: list[tuple], page_height: float) -> float:
    """Find the Y-coordinate of the first table header anchor word."""
    # Build 3-word sliding windows to match multi-word anchors
    word_positions: list[tuple[float, str]] = [
        (float(w[1]), w[4].lower().strip()) for w in words if len(w) >= 5
    ]

    # Try sliding windows of 1, 2, 3 words to find anchors
    for window in range(3, 0, -1):
        for i in range(len(word_positions) - window + 1):
            phrase = " ".join(wp[1] for wp in word_positions[i : i + window])
            if any(phrase == anchor for anchor in _TABLE_TOP_ANCHORS):
                # Return the y0 of the first word in this phrase
                return word_positions[i][0]

    # Fallback: top 20% of page
    return page_height * 0.20


def _find_bottom_anchor(words: list[tuple], page_height: float, y_top: float) -> float:
    """Find the Y-coordinate of the last table row (closing balance etc)."""
    word_positions: list[tuple[float, str]] = [
        (float(w[1]), w[4].lower().strip()) for w in words if len(w) >= 5 and float(w[1]) > y_top
    ]

    for window in range(3, 0, -1):
        for i in range(len(word_positions) - window + 1):
            phrase = " ".join(wp[1] for wp in word_positions[i : i + window])
            if any(anchor in phrase for anchor in _TABLE_BOTTOM_ANCHORS):
                return min(word_positions[i][0] + 20, page_height)

    return page_height * _DEFAULT_BOTTOM_FRACTION
