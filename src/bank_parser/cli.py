"""CLI entry point — parse a bank statement PDF into a validated Excel file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bank_parser.core.models import Language
from bank_parser.core.pdf_extractor import PdfExtractionError, extract_text_blocks
from bank_parser.core.text_normalizer import normalize_text
from bank_parser.export.excel_writer import write_excel
from bank_parser.parsers import register_builtin_parsers
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.summary import summarize_validation


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Parse a bank statement PDF and export a validated Excel file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  bank-parser statement.pdf --bank-id chase_bank --language en --output out.xlsx\n"
            "  bank-parser statement.pdf --bank-id generic_english --language ar --output out.xlsx\n"
        ),
    )
    p.add_argument("input_pdf", help="Path to the bank statement PDF.")
    p.add_argument("--bank-id", required=True, help="Bank identifier registered in the parser factory.")
    p.add_argument(
        "--language",
        required=True,
        choices=[lang.value for lang in Language],
        help="Output Excel header language code (ar, ur, ru, es, hi).",
    )
    p.add_argument("--output", required=True, help="Output XLSX file path.")
    return p


def main() -> int:
    args = build_parser().parse_args()

    input_pdf = Path(args.input_pdf)
    if not input_pdf.exists():
        print(f"ERROR: Input file not found: {input_pdf}", file=sys.stderr)
        return 1

    try:
        language = Language(args.language)
    except ValueError:
        print(f"ERROR: Unsupported language code: {args.language}", file=sys.stderr)
        return 1

    # 1. Extract text from PDF
    print(f"Extracting text from {input_pdf.name} ...")
    try:
        blocks = extract_text_blocks(input_pdf)
    except PdfExtractionError as exc:
        print(f"ERROR: PDF extraction failed — {exc}", file=sys.stderr)
        return 1

    raw_text = "\n".join(block.text for block in blocks)
    normalized = normalize_text(raw_text)

    # 2. Parse
    registry = register_builtin_parsers()
    print(f"Parsing with bank_id='{args.bank_id}' ...")
    try:
        parser = registry.create(args.bank_id, language)
    except LookupError:
        available = registry.list_parsers()
        print(
            f"ERROR: No parser registered for bank_id='{args.bank_id}', language='{language.value}'.\n"
            f"Available: {available}",
            file=sys.stderr,
        )
        return 1

    parse_result = parser.parse(normalized)
    print(f"  Parsed {len(parse_result.transactions)} transactions.")

    # 3. Validate
    print("Validating ...")
    parse_result = validate_parse_result(parse_result)

    # 4. Summarise
    summary = summarize_validation(parse_result)
    print(
        f"  Summary: {summary.total_rows} rows — "
        f"{summary.clean_rows} clean, "
        f"{summary.warning_rows} warning, "
        f"{summary.error_rows} error."
    )
    print(f"  Export readiness: {summary.export_readiness.value.upper()}")

    if not summary.export_ready:
        print(
            "ERROR: Statement has validation errors and cannot be exported.",
            file=sys.stderr,
        )
        _print_flags(parse_result)
        return 1

    if summary.warning_rows or summary.statement_flag_count:
        print("WARNING: Statement has review flags — check the 'Review Flags' sheet in the output.")

    # 5. Export
    output_path = Path(args.output)
    print(f"Exporting to {output_path} ...")
    write_excel(parse_result, output_path, language=language)
    print(f"Done. File saved: {output_path.resolve()}")
    return 0


def _print_flags(parse_result) -> None:
    for flag in parse_result.review_flags:
        loc = f"[row {flag.row_number}] " if flag.row_number else "[statement] "
        print(f"  {loc}{flag.severity.value.upper()}: {flag.code} — {flag.message}", file=sys.stderr)
    for row_num, tx in enumerate(parse_result.transactions, start=1):
        for flag in tx.review_flags:
            print(
                f"  [row {row_num}] {flag.severity.value.upper()}: {flag.code} — {flag.message}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    raise SystemExit(main())
