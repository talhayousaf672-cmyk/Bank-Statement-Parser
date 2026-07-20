from decimal import Decimal

from bank_parser.core.models import Language, ParseResult, StatementMetadata, Transaction
from bank_parser.validation.dates import validate_dates


def test_validate_dates_flags_invalid_statement_period() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            statement_period_start="2026-02-01",
            statement_period_end="2026-01-01",
        )
    )

    flags = validate_dates(parse_result)

    assert flags[0].code == "invalid_statement_period"


def test_validate_dates_flags_value_date_before_transaction_date() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(bank_id="hbl", language=Language.URDU),
        transactions=[
            Transaction(
                transaction_date="2026-01-05",
                value_date="2026-01-04",
                description="settlement issue",
                amount=Decimal("10.00"),
            )
        ],
    )

    flags = validate_dates(parse_result)

    assert flags[0].code == "value_date_before_transaction_date"
    assert flags[0].row_number == 1


def test_validate_dates_flags_transaction_before_statement_period() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            statement_period_start="2026-01-01",
            statement_period_end="2026-01-31",
        ),
        transactions=[
            Transaction(
                transaction_date="2025-12-31",
                description="old row",
                amount=Decimal("10.00"),
            )
        ],
    )

    flags = validate_dates(parse_result)

    assert flags[0].code == "transaction_date_outside_period"


def test_validate_dates_flags_transaction_after_statement_period() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            statement_period_start="2026-01-01",
            statement_period_end="2026-01-31",
        ),
        transactions=[
            Transaction(
                transaction_date="2026-02-01",
                description="future row",
                amount=Decimal("10.00"),
            )
        ],
    )

    flags = validate_dates(parse_result)

    assert flags[0].code == "transaction_date_outside_period"


def test_validate_dates_accepts_dates_inside_period() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            statement_period_start="2026-01-01",
            statement_period_end="2026-01-31",
        ),
        transactions=[
            Transaction(
                transaction_date="2026-01-15",
                value_date="2026-01-16",
                description="good row",
                amount=Decimal("10.00"),
            )
        ],
    )

    assert validate_dates(parse_result) == []
