"""CSV export — turns validated ParseResult objects into standard CSV files."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Sequence

from bank_parser.core.models import Language, ParseResult
from bank_parser.export.excel_writer import _bank_label
from bank_parser.export.header_map import HEADER_MAP, HEADER_MAP_EN


def write_csv(
    parse_result: ParseResult,
    output_path: str | Path,
    language: Language | None = None,
) -> Path:
    """Write a single validated ParseResult to a CSV file.

    Uses the standard 16-column header layout matching Excel export.
    """
    lang = language or parse_result.metadata.language
    headers = HEADER_MAP.get(lang, HEADER_MAP_EN)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        meta = parse_result.metadata
        bank_label = _bank_label(meta.bank_id)

        for tx in parse_result.transactions:
            row = [
                bank_label,
                meta.account_number or "",
                meta.account_holder or "",
                str(meta.statement_period_start) if meta.statement_period_start else "",
                str(meta.statement_period_end) if meta.statement_period_end else "",
                meta.parser_version,
                meta.language.value,
                str(tx.transaction_date) if tx.transaction_date else "",
                str(tx.value_date) if tx.value_date else "",
                tx.description,
                tx.reference or "",
                float(tx.debit) if tx.debit is not None else "",
                float(tx.credit) if tx.credit is not None else "",
                float(tx.amount),
                float(tx.balance) if tx.balance is not None else "",
                tx.currency or meta.currency or "",
            ]
            writer.writerow(row)

    return output


def write_bulk_csv(
    parse_results: Sequence[ParseResult],
    output_path: str | Path,
    language: Language = Language.ENGLISH,
) -> Path:
    """Write multiple validated ParseResult objects into a single consolidated CSV file."""
    headers = HEADER_MAP.get(language, HEADER_MAP_EN)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for parse_result in parse_results:
            meta = parse_result.metadata
            bank_label = _bank_label(meta.bank_id)

            for tx in parse_result.transactions:
                row = [
                    bank_label,
                    meta.account_number or "",
                    meta.account_holder or "",
                    str(meta.statement_period_start) if meta.statement_period_start else "",
                    str(meta.statement_period_end) if meta.statement_period_end else "",
                    meta.parser_version,
                    meta.language.value,
                    str(tx.transaction_date) if tx.transaction_date else "",
                    str(tx.value_date) if tx.value_date else "",
                    tx.description,
                    tx.reference or "",
                    float(tx.debit) if tx.debit is not None else "",
                    float(tx.credit) if tx.credit is not None else "",
                    float(tx.amount),
                    float(tx.balance) if tx.balance is not None else "",
                    tx.currency or meta.currency or "",
                ]
                writer.writerow(row)

    return output
