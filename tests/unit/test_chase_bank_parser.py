import json
from pathlib import Path

from bank_parser.core.models import ParseResult
from bank_parser.parsers.chase_bank import ChaseBankParser

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "parsers" / "chase_bank" / "en"


def test_chase_bank_parser_parses_fixture() -> None:
    statement_text_path = FIXTURES_DIR / "statement_text.txt"
    expected_json_path = FIXTURES_DIR / "expected_parse.json"

    normalized_text = statement_text_path.read_text(encoding="utf-8")
    expected_data = json.loads(expected_json_path.read_text(encoding="utf-8"))

    parser = ChaseBankParser()
    result = parser.parse(normalized_text)

    expected_result = ParseResult.model_validate(expected_data)
    assert result.metadata == expected_result.metadata
    assert len(result.transactions) == len(expected_result.transactions)
    for actual, expected in zip(result.transactions, expected_result.transactions):
        assert actual.transaction_date == expected.transaction_date
        assert actual.description == expected.description
        assert actual.debit == expected.debit
        assert actual.credit == expected.credit
        assert actual.amount == expected.amount
        assert actual.balance == expected.balance
        assert actual.currency == expected.currency


def test_chase_bank_parser_regression_unclear_rows() -> None:
    text = """
    CHASE BANK STATEMENT
    Account Number: 9876543210
    Currency: USD

    TRANSACTION DETAIL
    Posting Date | Description | Amount | Balance
    INVALID_DATE | Bad Row | INVALID_AMOUNT | 
    """
    parser = ChaseBankParser()
    result = parser.parse(text)

    assert len(result.transactions) == 1
    tx = result.transactions[0]
    assert tx.transaction_date is None
    codes = [flag.code for flag in tx.review_flags]
    assert "unclear_date" in codes
    assert "unclear_amount" in codes
    assert "missing_balance" in codes
