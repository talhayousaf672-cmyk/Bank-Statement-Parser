from decimal import Decimal

from bank_parser.core.models import Language, ParseResult, StatementMetadata, Transaction
from bank_parser.validation.qa_harness import compare_parse_results


def test_compare_parse_results_passes_for_matching_results() -> None:
    expected = _parse_result(balance=Decimal("10.00"))
    actual = _parse_result(balance=Decimal("10.00"))

    report = compare_parse_results(expected, actual)

    assert report.passed is True
    assert report.accuracy == 1.0


def test_compare_parse_results_reports_field_mismatch() -> None:
    expected = _parse_result(balance=Decimal("10.00"))
    actual = _parse_result(balance=Decimal("11.00"))

    report = compare_parse_results(expected, actual)

    assert report.passed is False
    assert report.mismatches[0].row_number == 1
    assert report.mismatches[0].field_name == "balance"


def _parse_result(balance: Decimal) -> ParseResult:
    return ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            account_number="123456789",
            account_holder="Talha",
            currency="PKR",
            statement_period_start="2026-01-01",
            statement_period_end="2026-01-31",
        ),
        transactions=[
            Transaction(
                transaction_date="2026-01-01",
                description="opening",
                amount=Decimal("10.00"),
                balance=balance,
            )
        ],
    )
