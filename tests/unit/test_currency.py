from decimal import Decimal

from bank_parser.core.models import Language, ParseResult, StatementMetadata, Transaction
from bank_parser.validation.currency import validate_currencies


def test_validate_currencies_flags_missing_statement_and_row_currency() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(bank_id="hbl", language=Language.URDU),
        transactions=[Transaction(description="row", amount=Decimal("10.00"))],
    )

    flags = validate_currencies(parse_result)

    assert [flag.code for flag in flags] == ["missing_currency", "missing_currency"]
    assert flags[1].row_number == 1


def test_validate_currencies_allows_rows_to_inherit_statement_currency() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(bank_id="hbl", language=Language.URDU, currency="PKR"),
        transactions=[Transaction(description="row", amount=Decimal("10.00"))],
    )

    assert validate_currencies(parse_result) == []


def test_validate_currencies_flags_transaction_currency_mismatch() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(bank_id="hbl", language=Language.URDU, currency="PKR"),
        transactions=[Transaction(description="row", amount=Decimal("10.00"), currency="USD")],
    )

    flags = validate_currencies(parse_result)

    assert flags[0].code == "currency_mismatch"
    assert flags[0].row_number == 1


def test_validate_currencies_flags_unsupported_currency() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(bank_id="hbl", language=Language.URDU, currency="XYZ"),
        transactions=[],
    )

    flags = validate_currencies(parse_result)

    assert flags[0].code == "unsupported_currency"
