"""Unit tests for CSV export, batch parsing, and HITL interactive editing reconciliation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from bank_parser.core.models import (
    Language,
    ParseResult,
    ReviewFlag,
    ReviewSeverity,
    StatementMetadata,
    Transaction,
)
from bank_parser.export.csv_writer import write_bulk_csv, write_csv
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.summary import summarize_validation


def _sample_parse_result(bank_id: str = "hbl") -> ParseResult:
    tx1 = Transaction(
        transaction_date=date(2026, 1, 1),
        description="Salary Deposit",
        credit=Decimal("5000.00"),
        amount=Decimal("5000.00"),
        balance=Decimal("5000.00"),
        currency="PKR",
    )
    tx2 = Transaction(
        transaction_date=date(2026, 1, 5),
        description="Grocery Store",
        debit=Decimal("1200.00"),
        amount=Decimal("-1200.00"),
        balance=Decimal("3800.00"),
        currency="PKR",
    )
    meta = StatementMetadata(
        bank_id=bank_id,
        language=Language.ENGLISH,
        account_number="12345678",
        account_holder="Test User",
        currency="PKR",
        statement_period_start=date(2026, 1, 1),
        statement_period_end=date(2026, 1, 31),
    )
    return ParseResult(metadata=meta, transactions=[tx1, tx2])


def test_write_csv_creates_valid_file(tmp_path: Path) -> None:
    result = _sample_parse_result()
    out_file = write_csv(result, tmp_path / "test.csv")

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8-sig")
    lines = content.strip().splitlines()

    assert len(lines) == 3  # Header + 2 rows
    assert "Salary Deposit" in lines[1]
    assert "Grocery Store" in lines[2]


def test_write_bulk_csv_consolidates_multiple_statements(tmp_path: Path) -> None:
    res1 = _sample_parse_result("hbl")
    res2 = _sample_parse_result("meezan_bank")

    out_file = write_bulk_csv([res1, res2], tmp_path / "consolidated.csv")
    assert out_file.exists()

    content = out_file.read_text(encoding="utf-8-sig")
    lines = content.strip().splitlines()

    assert len(lines) == 5  # Header + 2 rows from res1 + 2 rows from res2
    assert "HBL" in lines[1]
    assert "Meezan Bank" in lines[3]


def test_hitl_inline_editing_reconciles_automatically() -> None:
    result = _sample_parse_result()

    # User modifies grocery debit from 1200 to 1000 and balance from 3800 to 4000
    tx2 = result.transactions[1]
    tx2.debit = Decimal("1000.00")
    tx2.amount = -Decimal("1000.00")
    tx2.balance = Decimal("4000.00")

    validated = validate_parse_result(result)
    summary = summarize_validation(validated)

    assert summary.total_rows == 2
    assert summary.clean_rows == 2
    assert summary.error_rows == 0
    assert summary.export_ready is True


def test_hitl_row_deletion_updates_summary() -> None:
    result = _sample_parse_result()
    assert len(result.transactions) == 2

    # User deletes transaction 2
    result.transactions.pop(1)

    validated = validate_parse_result(result)
    summary = summarize_validation(validated)

    assert summary.total_rows == 1
    assert summary.clean_rows == 1
