"""Benchmark spatial extraction engines on real bank statement PDFs.

Run this script from the project root:
    .venv\\Scripts\\python scripts\\benchmark_spatial.py

It will test Camelot and Docling on all PDFs in statements/ and print
a comparison table showing extracted row counts and column detection quality.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Make sure bank_parser is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bank_parser.core.grid_cropper import get_cropped_regions
from bank_parser.core.spatial_extractor import _extract_with_camelot, _extract_with_docling, _count_data_rows

STATEMENTS_DIR = Path(__file__).parent.parent / "statements"
EXPECTED_COLUMNS = {"date", "description", "debit", "credit", "balance"}


def score_markdown(markdown: str, pdf_name: str) -> dict:
    """Score a Markdown table output for quality."""
    if not markdown:
        return {"rows": 0, "columns_detected": 0, "has_date_col": False, "has_amount_col": False, "raw_preview": ""}

    lines = [l for l in markdown.strip().split("\n") if l.strip().startswith("|")]
    rows = max(0, len(lines) - 2)  # exclude header + separator

    header_line = lines[0] if lines else ""
    header_cells = [c.strip().lower() for c in header_line.split("|") if c.strip()]

    has_date = any("date" in c for c in header_cells)
    has_amount = any(w in c for c in header_cells for w in ["debit", "credit", "amount", "balance"])
    cols_found = len([c for c in header_cells if c])

    preview = "\n".join(lines[:5]) if lines else "(empty)"

    return {
        "rows": rows,
        "columns_detected": cols_found,
        "has_date_col": has_date,
        "has_amount_col": has_amount,
        "raw_preview": preview,
    }


def run_benchmark():
    pdfs = sorted(STATEMENTS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {STATEMENTS_DIR}")
        return

    print(f"\n{'='*80}")
    print(f"{'SPATIAL ENGINE BENCHMARK':^80}")
    print(f"{'='*80}")
    print(f"Found {len(pdfs)} PDFs: {[p.name for p in pdfs]}\n")

    results = []

    for pdf in pdfs:
        print(f"\n--- {pdf.name} ---")
        row = {"pdf": pdf.name}

        try:
            regions = get_cropped_regions(pdf)
            print(f"  Grid cropper: detected {len(regions)} page(s)")
        except Exception as e:
            print(f"  Grid cropper FAILED: {e}")
            regions = []

        # Camelot
        t0 = time.time()
        try:
            camelot_md = _extract_with_camelot(pdf, regions) if regions else ""
        except Exception as e:
            print(f"  Camelot ERROR: {e}")
            camelot_md = ""
        camelot_time = time.time() - t0
        camelot_score = score_markdown(camelot_md, pdf.name)
        row["camelot"] = {**camelot_score, "time_s": round(camelot_time, 2)}
        print(f"  Camelot:  {camelot_score['rows']} rows | {camelot_score['columns_detected']} cols | "
              f"date={camelot_score['has_date_col']} | amount={camelot_score['has_amount_col']} | "
              f"{camelot_time:.2f}s")

        # Docling
        t0 = time.time()
        try:
            docling_md = _extract_with_docling(pdf)
        except Exception as e:
            print(f"  Docling ERROR: {e}")
            docling_md = ""
        docling_time = time.time() - t0
        docling_score = score_markdown(docling_md, pdf.name)
        row["docling"] = {**docling_score, "time_s": round(docling_time, 2)}
        print(f"  Docling:  {docling_score['rows']} rows | {docling_score['columns_detected']} cols | "
              f"date={docling_score['has_date_col']} | amount={docling_score['has_amount_col']} | "
              f"{docling_time:.2f}s")

        results.append(row)

    # Summary table
    print(f"\n{'='*80}")
    print(f"{'SUMMARY':^80}")
    print(f"{'='*80}")
    print(f"{'PDF':<20} {'Camelot Rows':>13} {'Docling Rows':>13} {'Winner':>10}")
    print("-" * 60)
    for r in results:
        c_rows = r["camelot"]["rows"]
        d_rows = r["docling"]["rows"]
        winner = "Camelot" if c_rows >= d_rows else "Docling"
        print(f"{r['pdf']:<20} {c_rows:>13} {d_rows:>13} {winner:>10}")

    camelot_wins = sum(1 for r in results if r["camelot"]["rows"] >= r["docling"]["rows"])
    docling_wins = len(results) - camelot_wins
    print(f"\nOverall: Camelot wins {camelot_wins}/{len(results)} | Docling wins {docling_wins}/{len(results)}")

    if camelot_wins >= docling_wins:
        print("\n✓ RECOMMENDATION: Use Camelot as primary, Docling as fallback.")
    else:
        print("\n✓ RECOMMENDATION: Use Docling as primary, Camelot as fallback.")

    print(f"{'='*80}\n")


if __name__ == "__main__":
    run_benchmark()
