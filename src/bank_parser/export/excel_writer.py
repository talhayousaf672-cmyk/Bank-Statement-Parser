"""Excel export boundary."""

from __future__ import annotations

from pathlib import Path

from bank_parser.core.models import Language, ParseResult


HEADERS: dict[Language, list[str]] = {
    Language.ARABIC: ["transaction_date", "value_date", "description", "amount", "balance"],
    Language.URDU: ["transaction_date", "value_date", "description", "amount", "balance"],
    Language.RUSSIAN: ["transaction_date", "value_date", "description", "amount", "balance"],
    Language.SPANISH: ["transaction_date", "value_date", "description", "amount", "balance"],
    Language.HINDI: ["transaction_date", "value_date", "description", "amount", "balance"],
}


def write_excel(parse_result: ParseResult, output_path: str | Path) -> Path:
    """Write parse result to XLSX.

    Implementation will use openpyxl in the export sprint.
    """
    raise NotImplementedError("Excel export is not implemented yet.")
