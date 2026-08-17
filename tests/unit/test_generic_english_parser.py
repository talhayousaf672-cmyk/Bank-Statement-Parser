import json
from pathlib import Path
from decimal import Decimal

from bank_parser.core.models import Language, ParseResult
from bank_parser.parsers.generic_english import GenericEnglishBankParser

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "parsers" / "generic_english" / "en"


def test_generic_english_parser_parses_fixture() -> None:
    statement_text_path = FIXTURES_DIR / "statement_text.txt"
    expected_json_path = FIXTURES_DIR / "expected_parse.json"

    normalized_text = statement_text_path.read_text(encoding="utf-8")
    expected_data = json.loads(expected_json_path.read_text(encoding="utf-8"))

    parser = GenericEnglishBankParser()
    result = parser.parse(normalized_text)

    expected_result = ParseResult.model_validate(expected_data)
    assert result.metadata == expected_result.metadata
    assert len(result.transactions) == len(expected_result.transactions)
    for actual, expected in zip(result.transactions, expected_result.transactions):
        assert actual.transaction_date == expected.transaction_date
        assert actual.description == expected.description
        assert actual.reference == expected.reference
        assert actual.debit == expected.debit
        assert actual.credit == expected.credit
        assert actual.amount == expected.amount
        assert actual.balance == expected.balance
        assert actual.currency == expected.currency


def test_generic_english_parser_handles_missing_metadata() -> None:
    text = """
    Currency: USD

    2026-01-05 | Opening Deposit | REF1001 | | 100.00 | 100.00
    """
    parser = GenericEnglishBankParser()
    result = parser.parse(text)

    assert result.metadata.account_number is None
    assert result.metadata.currency == "USD"
    assert any(flag.code == "missing_required_field" for flag in result.review_flags)


def test_generic_english_parser_emits_review_flags_for_ambiguous_rows() -> None:
    text = """
    Account Number: ACC123
    Currency: USD

    BAD_DATE | Unknown Row | REF99 | | | 100.00
    """
    parser = GenericEnglishBankParser()
    result = parser.parse(text)

    assert len(result.transactions) == 1
    tx = result.transactions[0]
    assert tx.transaction_date is None
    codes = [flag.code for flag in tx.review_flags]
    assert "unclear_date" in codes
    assert "unclear_amount" in codes
