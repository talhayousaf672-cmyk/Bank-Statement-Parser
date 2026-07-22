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
    """Use Camelot stream mode to extract the best transaction table."""
    try:
        import camelot
    except ImportError:
        logger.warning("camelot-py not installed. Skipping Camelot extraction.")
        return ""

    try:
        clean_path = _get_unrestricted_copy(path)
        
        # Pass 1: Fast scan of first 3 pages to find the best table structure
        tables_pass1 = camelot.read_pdf(
            str(clean_path),
            pages="1-3",
            flavor="stream",
            edge_tol=50,
            row_tol=10,
        )
        
        if not tables_pass1:
            return ""

        # Score tables to find the primary transaction grid
        scored = []
        for table in tables_pass1:
            df = table.df
            if df.empty:
                continue
            all_text = " ".join(str(v).lower() for v in df.values.flatten())
            score = 0
            for keyword in ["date", "debit", "credit", "balance", "description", "amount", "particulars", "value"]:
                if keyword in all_text:
                    score += 1
            score += min(len(df), 50) * 0.05
            scored.append((score, table))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)
        best_table = scored[0][1]
        expected_cols = best_table.df.shape[1]

        # Extract the x-coordinates of the column boundaries from the best table
        # camelot table.cols is a list of (x0, x1). We need a comma-separated string of x1's for the columns arg.
        if len(best_table.cols) > 1:
            x_coords = [str(x1) for x0, x1 in best_table.cols[:-1]]
            cols_str = ",".join(x_coords)
            
            # Pass 2: Extract ALL pages forcing the exact column boundaries
            tables = camelot.read_pdf(
                str(clean_path),
                pages="all",
                flavor="stream",
                columns=[cols_str],
                edge_tol=50,
                row_tol=10,
            )
        else:
            # Fallback if no columns detected
            tables = camelot.read_pdf(str(clean_path), pages="all", flavor="stream", edge_tol=50, row_tol=10)

    except Exception as exc:
        logger.warning("Camelot failed: %s", exc)
        return ""
    finally:
        if 'clean_path' in dir() and clean_path != path:
            try:
                clean_path.unlink(missing_ok=True)
            except Exception:
                pass

    # Since we forced columns, all tables should have expected_cols
    # but we'll still score them to weed out random text blocks
    scored_pass2 = []
    for table in tables:
        df = table.df
        if df.shape[1] != expected_cols:
            continue
        all_text = " ".join(str(v).lower() for v in df.values.flatten())
        score = 0
        for keyword in ["date", "debit", "credit", "balance", "description", "amount", "particulars", "value"]:
            if keyword in all_text:
                score += 1
        score += min(len(df), 50) * 0.05
        scored_pass2.append((score, table))

    if not scored_pass2:
        return ""
        
    scored_pass2.sort(key=lambda x: x[0], reverse=True)
    best_pass2_table = scored_pass2[0][1]

    # Find the header row in the best table
    header_idx = _find_header_row(best_pass2_table.df.values.tolist())
    if header_idx < 0:
        header_idx = 0

    header = best_pass2_table.df.values.tolist()[header_idx]
    clean_header = [str(c).strip().replace("\n", " ") for c in header]
    
    markdown_rows: list[str] = []
    markdown_rows.append("| " + " | ".join(clean_header) + " |")
    markdown_rows.append("|" + "|".join(["---"] * len(clean_header)) + "|")

    # Extract data from all matching tables
    for _score, table in scored_pass2:
        rows = table.df.values.tolist()
        
        start_idx = 0
        if table is best_pass2_table:
            start_idx = header_idx + 1
        else:
            first_row_text = " ".join(str(c).lower() for c in rows[0])
            if any(w in first_row_text for w in ["date", "debit", "credit", "balance"]):
                start_idx = 1
                
        for row in rows[start_idx:]:
            clean_row = [str(c).strip().replace("\n", " ") for c in row]
            if any(c for c in clean_row):
                markdown_rows.append("| " + " | ".join(clean_row) + " |")

    return "\n".join(markdown_rows)

def _find_header_row(rows: list[list]) -> int:
    """Find the row index containing the column headers."""
    target_words = {"date", "debit", "credit", "balance", "description", "amount", "value"}
    for i, row in enumerate(rows[:10]):  # only search first 10 rows
        row_text = " ".join(str(c).lower() for c in row)
        matches = sum(1 for w in target_words if w in row_text)
        if matches >= 2:
            return i
    return -1


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


def _get_unrestricted_copy(path: Path) -> Path:
    """Return a path to a copy of the PDF with copy-restriction flags removed.

    Some banks (e.g. Meezan) set the PDF copy-text permission bit to False
    even though the text is fully extractable. Camelot's underlying parser
    (`playa`) strictly respects this flag and raises PDFTextExtractionNotAllowed.

    PyMuPDF ignores this flag and can re-save the file without it.
    If no restriction is present, returns the original path unchanged.
    """
    try:
        import fitz
        import tempfile

        doc = fitz.open(str(path))
        # Check if copy permission is blocked (bit 4 of permissions)
        copy_allowed = bool(doc.permissions & (1 << 4))
        doc.close()

        if copy_allowed:
            return path  # No restriction — use original

        # Re-save without restrictions
        doc = fitz.open(str(path))
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = Path(tmp.name)
        doc.save(str(tmp_path), encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close()
        logger.info("Stripped copy-restriction flags from %s", path.name)
        return tmp_path

    except Exception as exc:
        logger.warning("Could not strip PDF restrictions: %s", exc)
        return path  # Fall back to original
