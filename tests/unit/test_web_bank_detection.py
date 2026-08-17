from __future__ import annotations

from pathlib import Path

import openpyxl

from bank_parser.core.bank_detector import detect_bank_id_from_header
from bank_parser.export.excel_writer import write_excel
from bank_parser.parsers.ubl import UBLParser
from bank_parser.web.api import _resolve_bank_id


FIXTURE_BASE = Path("tests/fixtures/parsers")


def test_meezan_header_overrides_stale_ubl_selection() -> None:
    text = (FIXTURE_BASE / "meezan_bank" / "en" / "statement_text.txt").read_text(
        encoding="utf-8"
    )

    assert _resolve_bank_id("ubl", text) == "meezan_bank"


def test_transaction_acronym_does_not_override_strong_header_marker() -> None:
    text = """\
MEEZAN BANK LIMITED
CURRENT ACCOUNT STATEMENT
Account No: 01010123456789

Date | Narration | Cheque/Ref No | Debit | Credit | Balance
02/01/2026 | ATM CASH WITHDRAWAL UBL 0123 | REF-1 | 100.00 | | 900.00
"""

    assert _resolve_bank_id("generic_english", text) == "meezan_bank"


def test_header_detector_ignores_transaction_table_acronyms() -> None:
    text = """\
HABIB BANK LIMITED
ACCOUNT STATEMENT

Date | Description | Debit | Credit | Balance
02/01/2026 | ATM CASH WITHDRAWAL UBL 0123 | 100.00 | | 900.00
"""

    assert detect_bank_id_from_header(text) == "hbl"


def test_ubl_parser_does_not_export_meezan_statement_as_ubl(tmp_path: Path) -> None:
    text = (FIXTURE_BASE / "meezan_bank" / "en" / "statement_text.txt").read_text(
        encoding="utf-8"
    )

    result = UBLParser().parse(text)
    out = write_excel(result, tmp_path / "out.xlsx")
    wb = openpyxl.load_workbook(out)

    assert result.metadata.bank_id == "meezan_bank"
    assert result.metadata.account_number == "01010123456789"
    assert str(result.metadata.statement_period_start) == "2026-01-01"
    assert wb["Statement"].cell(row=2, column=1).value == "meezan_bank"


def test_ubl_parser_delegates_headerless_meezan_layout_to_meezan_parser() -> None:
    text = """\
Date | Narration | Cheque/Ref No | Debit | Credit | Balance
02/01/2026 | MUSHARAKAH PROFIT | PRF-20260102 | | 1500.00 | 201500.00
09/01/2026 | TAKAFUL PREMIUM | TKF-2026009 | 8000.00 | | 193500.00
"""

    result = UBLParser().parse(text)

    assert result.metadata.bank_id == "meezan_bank"
    assert result.transactions[0].description == "MUSHARAKAH PROFIT"
