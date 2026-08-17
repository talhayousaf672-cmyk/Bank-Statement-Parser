"""Unit tests for HBL, UBL, Meezan Bank, Wells Fargo, and Bank of America parsers."""

from __future__ import annotations

from pathlib import Path
import json

import pytest

from bank_parser.parsers.bank_of_america import BankOfAmericaParser
from bank_parser.parsers.hbl import HBLParser
from bank_parser.parsers.meezan_bank import MeezanBankParser
from bank_parser.parsers.ubl import UBLParser
from bank_parser.parsers.wells_fargo import WellsFargoParser
from bank_parser.core.models import ParseResult

FIXTURE_BASE = Path("tests/fixtures/parsers")


def _load_fixture(bank_id: str) -> tuple[str, dict]:
    text = (FIXTURE_BASE / bank_id / "en" / "statement_text.txt").read_text(encoding="utf-8")
    expected = json.loads((FIXTURE_BASE / bank_id / "en" / "expected_parse.json").read_text(encoding="utf-8"))
    return text, expected


# ---------------------------------------------------------------------------
# HBL
# ---------------------------------------------------------------------------

class TestHBLParser:
    def test_hbl_parses_fixture(self):
        text, expected = _load_fixture("hbl")
        result = HBLParser().parse(text)
        assert len(result.transactions) == len(expected["transactions"])

    def test_hbl_metadata(self):
        text, _ = _load_fixture("hbl")
        result = HBLParser().parse(text)
        assert result.metadata.bank_id == "hbl"
        assert result.metadata.account_number == "PK36HABB0000123456789012"
        assert result.metadata.account_holder == "JOHN DOE"
        assert result.metadata.currency == "PKR"
        assert str(result.metadata.statement_period_start) == "2026-01-01"
        assert str(result.metadata.statement_period_end) == "2026-01-31"

    def test_hbl_first_transaction_is_credit(self):
        text, _ = _load_fixture("hbl")
        result = HBLParser().parse(text)
        tx = result.transactions[0]
        assert tx.description == "SALARY CREDIT"
        assert tx.credit is not None
        assert tx.debit is None
        assert tx.amount > 0

    def test_hbl_debit_transactions_have_negative_amount(self):
        text, _ = _load_fixture("hbl")
        result = HBLParser().parse(text)
        for tx in result.transactions:
            if tx.debit is not None:
                assert tx.amount < 0, f"Debit tx {tx.description!r} should have negative amount"

    def test_hbl_no_review_flags_on_clean_fixture(self):
        text, _ = _load_fixture("hbl")
        result = HBLParser().parse(text)
        assert all(len(tx.review_flags) == 0 for tx in result.transactions)


# ---------------------------------------------------------------------------
# UBL
# ---------------------------------------------------------------------------

class TestUBLParser:
    def test_ubl_parses_fixture(self):
        text, expected = _load_fixture("ubl")
        result = UBLParser().parse(text)
        assert len(result.transactions) == len(expected["transactions"])

    def test_ubl_metadata(self):
        text, _ = _load_fixture("ubl")
        result = UBLParser().parse(text)
        assert result.metadata.bank_id == "ubl"
        assert result.metadata.currency == "PKR"
        assert str(result.metadata.statement_period_start) == "2026-01-01"
        assert str(result.metadata.statement_period_end) == "2026-01-31"

    def test_ubl_skips_opening_balance_row(self):
        text, _ = _load_fixture("ubl")
        result = UBLParser().parse(text)
        descriptions = [tx.description for tx in result.transactions]
        assert not any("OPENING BALANCE" in d.upper() for d in descriptions)

    def test_ubl_credit_transactions_have_positive_amount(self):
        text, _ = _load_fixture("ubl")
        result = UBLParser().parse(text)
        for tx in result.transactions:
            if tx.credit is not None:
                assert tx.amount > 0

    def test_ubl_withdrawal_transactions_have_negative_amount(self):
        text, _ = _load_fixture("ubl")
        result = UBLParser().parse(text)
        for tx in result.transactions:
            if tx.debit is not None:
                assert tx.amount < 0


# ---------------------------------------------------------------------------
# Meezan Bank
# ---------------------------------------------------------------------------

class TestMeezanBankParser:
    def test_meezan_parses_fixture(self):
        text, expected = _load_fixture("meezan_bank")
        result = MeezanBankParser().parse(text)
        assert len(result.transactions) == len(expected["transactions"])

    def test_meezan_metadata(self):
        text, _ = _load_fixture("meezan_bank")
        result = MeezanBankParser().parse(text)
        assert result.metadata.bank_id == "meezan_bank"
        assert result.metadata.account_number == "01010123456789"
        assert result.metadata.currency == "PKR"
        assert str(result.metadata.statement_period_start) == "2026-01-01"
        assert str(result.metadata.statement_period_end) == "2026-01-31"

    def test_meezan_skips_opening_balance_row(self):
        text, _ = _load_fixture("meezan_bank")
        result = MeezanBankParser().parse(text)
        descriptions = [tx.description for tx in result.transactions]
        assert not any("OPENING BALANCE" in d.upper() for d in descriptions)

    def test_meezan_profit_transaction_is_credit(self):
        text, _ = _load_fixture("meezan_bank")
        result = MeezanBankParser().parse(text)
        profit_tx = next((tx for tx in result.transactions if "PROFIT" in tx.description), None)
        assert profit_tx is not None
        assert profit_tx.credit is not None
        assert profit_tx.amount > 0


# ---------------------------------------------------------------------------
# Wells Fargo
# ---------------------------------------------------------------------------

class TestWellsFargoParser:
    def test_wf_parses_fixture(self):
        text, expected = _load_fixture("wells_fargo")
        result = WellsFargoParser().parse(text)
        assert len(result.transactions) == len(expected["transactions"])

    def test_wf_metadata(self):
        text, _ = _load_fixture("wells_fargo")
        result = WellsFargoParser().parse(text)
        assert result.metadata.bank_id == "wells_fargo"
        assert result.metadata.currency == "USD"
        assert str(result.metadata.statement_period_start) == "2026-01-01"
        assert str(result.metadata.statement_period_end) == "2026-01-31"

    def test_wf_skips_beginning_balance(self):
        text, _ = _load_fixture("wells_fargo")
        result = WellsFargoParser().parse(text)
        descriptions = [tx.description for tx in result.transactions]
        assert not any("BEGINNING BALANCE" in d.upper() for d in descriptions)

    def test_wf_deposit_transactions_have_positive_amount(self):
        text, _ = _load_fixture("wells_fargo")
        result = WellsFargoParser().parse(text)
        for tx in result.transactions:
            if tx.credit is not None:
                assert tx.amount > 0

    def test_wf_withdrawal_transactions_have_negative_amount(self):
        text, _ = _load_fixture("wells_fargo")
        result = WellsFargoParser().parse(text)
        for tx in result.transactions:
            if tx.debit is not None:
                assert tx.amount < 0


# ---------------------------------------------------------------------------
# Bank of America
# ---------------------------------------------------------------------------

class TestBankOfAmericaParser:
    def test_bofa_parses_fixture(self):
        text, expected = _load_fixture("bank_of_america")
        result = BankOfAmericaParser().parse(text)
        assert len(result.transactions) == len(expected["transactions"])

    def test_bofa_metadata(self):
        text, _ = _load_fixture("bank_of_america")
        result = BankOfAmericaParser().parse(text)
        assert result.metadata.bank_id == "bank_of_america"
        assert result.metadata.currency == "USD"
        assert str(result.metadata.statement_period_start) == "2026-01-01"
        assert str(result.metadata.statement_period_end) == "2026-01-31"

    def test_bofa_skips_beginning_balance(self):
        text, _ = _load_fixture("bank_of_america")
        result = BankOfAmericaParser().parse(text)
        descriptions = [tx.description for tx in result.transactions]
        assert not any("BEGINNING BALANCE" in d.upper() for d in descriptions)

    def test_bofa_direct_deposit_is_credit(self):
        text, _ = _load_fixture("bank_of_america")
        result = BankOfAmericaParser().parse(text)
        deposit_tx = next((tx for tx in result.transactions if "Direct Deposit" in tx.description), None)
        assert deposit_tx is not None
        assert deposit_tx.credit is not None
        assert deposit_tx.amount > 0

    def test_bofa_debit_card_purchase_is_debit(self):
        text, _ = _load_fixture("bank_of_america")
        result = BankOfAmericaParser().parse(text)
        debit_tx = next((tx for tx in result.transactions if "Debit Card Purchase" in tx.description), None)
        assert debit_tx is not None
        assert debit_tx.debit is not None
        assert debit_tx.amount < 0


# ---------------------------------------------------------------------------
# Cross-bank registry smoke test
# ---------------------------------------------------------------------------

def test_all_new_parsers_registered():
    from bank_parser.parsers import register_builtin_parsers
    registry = register_builtin_parsers()
    bank_ids = {bank_id for bank_id, _ in registry.list_parsers()}
    for expected_id in ("hbl", "ubl", "meezan_bank", "wells_fargo", "bank_of_america"):
        assert expected_id in bank_ids, f"{expected_id} not registered"
