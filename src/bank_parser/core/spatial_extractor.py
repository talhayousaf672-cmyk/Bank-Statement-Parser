"""Spatial Extractor — Phase 2 layout-aware table extraction.

Extracts a Markdown-formatted table string from a cropped PDF page region.
Uses Camelot (classical whitespace clustering) as primary, with Docling
(IBM deep-learning layout parser) as fallback.

The output is a clean Markdown table string ready to be passed to the AI.
"""

from __future__ import annotations

import logging
from pathlib import Path

from bank_parser.core.grid_cropper import CroppedRegion

logger = logging.getLogger(__name__)

_MIN_ROWS_THRESHOLD = 1  # Min rows extracted to be considered a valid result


def extract_markdown(
    pdf_path: str | Path,
    regions: list[CroppedRegion],
) -> str:
    """Extract a Markdown table from the transaction regions of a PDF.

    Tries Camelot first (classical spatial parser, zero ML).
    Falls back to Docling if Camelot finds no tables.

    Args:
        pdf_path: Original PDF path.
        regions: Cropped bounding regions from grid_cropper.

    Returns:
        A Markdown-formatted table string, e.g.:
        | Date | Description | Debit | Credit | Balance |
        |------|-------------|-------|--------|---------|
        | 2026-01-10 | IBFT Transfer | 500.00 | | 9000.00 |
    """
    path = Path(pdf_path)

    # Try Camelot first
    markdown = _extract_with_camelot(path, regions)
    if markdown and _count_data_rows(markdown) >= _MIN_ROWS_THRESHOLD:
        logger.info("Spatial extraction: Camelot succeeded.")
        return markdown

    logger.warning("Camelot returned no tables. Falling back to Docling.")

    # Fallback: Docling
    markdown = _extract_with_docling(path)
    if markdown and _count_data_rows(markdown) >= _MIN_ROWS_THRESHOLD:
        logger.info("Spatial extraction: Docling fallback succeeded.")
        return markdown

    logger.error("Both Camelot and Docling returned no table data.")
    return ""


def _extract_with_camelot(path: Path, regions: list[CroppedRegion]) -> str:
    """Use Camelot stream mode to extract tables from cropped regions."""
    try:
        import camelot
    except ImportError:
        logger.warning("camelot-py not installed. Skipping Camelot extraction.")
        return ""

    all_markdown_rows: list[str] = []
    header_written = False

    for region in regions:
        page_num = region.page_index + 1  # camelot is 1-indexed
        table_area = f"{region.x0},{region.y_bottom},{region.x1},{region.y_top}"

        try:
            tables = camelot.read_pdf(
                str(path),
                pages=str(page_num),
                flavor="stream",
                table_areas=[table_area],
                edge_tol=50,
                row_tol=10,
            )
        except Exception as exc:
            logger.warning("Camelot failed on page %d: %s", page_num, exc)
            continue

        for table in tables:
            df = table.df
            if df.empty or len(df) < 2:
                continue

            rows = df.values.tolist()

            if not header_written:
                header = rows[0]
                clean_header = [str(c).strip().replace("\n", " ") for c in header]
                all_markdown_rows.append("| " + " | ".join(clean_header) + " |")
                all_markdown_rows.append("|" + "|".join(["---"] * len(clean_header)) + "|")
                header_written = True
                data_rows = rows[1:]
            else:
                data_rows = rows

            for row in data_rows:
                clean_row = [str(c).strip().replace("\n", " ") for c in row]
                all_markdown_rows.append("| " + " | ".join(clean_row) + " |")

    return "\n".join(all_markdown_rows)


def _extract_with_docling(path: Path) -> str:
    """Use Docling to extract the first table found in the PDF as Markdown."""
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        logger.warning("docling not installed. Skipping Docling extraction.")
        return ""

    try:
        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document
    except Exception as exc:
        logger.warning("Docling failed to convert PDF: %s", exc)
        return ""

    # Export the whole document as Markdown and return it
    try:
        markdown = doc.export_to_markdown()
        # Filter to only lines that look like table rows (contain pipes)
        table_lines = [line for line in markdown.split("\n") if "|" in line]
        if table_lines:
            return "\n".join(table_lines)
    except Exception as exc:
        logger.warning("Docling Markdown export failed: %s", exc)

    return ""


def _count_data_rows(markdown: str) -> int:
    """Count non-header rows in a Markdown table string."""
    lines = [l for l in markdown.strip().split("\n") if l.strip().startswith("|")]
    # Subtract header row and separator row
    return max(0, len(lines) - 2)
