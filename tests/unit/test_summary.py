from decimal import Decimal

from bank_parser.core.models import Language, ParseResult, StatementMetadata, Transaction
from bank_parser.validation.policy import ValidationPolicy
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.summary import ExportReadiness, summarize_validation


def test_summarize_validation_reports_ready_clean_statement() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            account_number="123456789",
            currency="PKR",
        ),
        transactions=[
            Transaction(
                transaction_date="2026-01-01",
                description="opening",
                amount=Decimal("10.00"),
                balance=Decimal("10.00"),
            )
        ],
    )

    summary = summarize_validation(validate_parse_result(parse_result))

    assert summary.total_rows == 1
    assert summary.clean_rows == 1
    assert summary.export_readiness == ExportReadiness.READY
    assert summary.export_ready is True


def test_summarize_validation_reports_warning_only_statement() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            account_number="123456789",
            currency="PKR",
        ),
        transactions=[
            Transaction(
                description="missing date",
                amount=Decimal("10.00"),
                balance=Decimal("10.00"),
            )
        ],
    )

    summary = summarize_validation(validate_parse_result(parse_result))

    assert summary.warning_rows == 1
    assert summary.flag_counts_by_code["unclear_date"] == 1
    assert summary.export_readiness == ExportReadiness.READY_WITH_WARNINGS
    assert summary.export_ready is True


def test_summarize_validation_blocks_statement_with_errors() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            account_number="123456789",
            currency="PKR",
        ),
        transactions=[
            Transaction(
                transaction_date="2026-01-01",
                description="opening",
                amount=Decimal("10.00"),
                balance=Decimal("10.00"),
            ),
            Transaction(
                transaction_date="2026-01-02",
                description="bad balance",
                amount=Decimal("5.00"),
                balance=Decimal("20.00"),
            ),
        ],
    )

    summary = summarize_validation(validate_parse_result(parse_result))

    assert summary.error_rows == 1
    assert summary.statement_flag_count == 1
    assert summary.row_flag_count == 1
    assert summary.flag_counts_by_code["balance_mismatch"] == 2
    assert summary.export_readiness == ExportReadiness.BLOCKED
    assert summary.export_ready is False


def test_summarize_validation_uses_configurable_policy() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            account_number="123456789",
            currency="PKR",
        ),
        transactions=[
            Transaction(
                transaction_date="2026-01-01",
                description="opening",
                amount=Decimal("10.00"),
                balance=Decimal("10.00"),
            ),
            Transaction(
                transaction_date="2026-01-02",
                description="bad balance",
                amount=Decimal("5.00"),
                balance=Decimal("20.00"),
            ),
        ],
    )
    warning_only_policy = ValidationPolicy(
        blocking_flag_codes=set(),
        warning_flag_codes={"balance_mismatch"},
    )

    summary = summarize_validation(validate_parse_result(parse_result), policy=warning_only_policy)

    assert summary.export_readiness == ExportReadiness.READY_WITH_WARNINGS
    assert summary.export_ready is True


def test_summarize_validation_reports_date_warning() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            account_number="123456789",
            currency="PKR",
            statement_period_start="2026-01-01",
            statement_period_end="2026-01-31",
        ),
        transactions=[
            Transaction(
                transaction_date="2026-02-01",
                description="outside period",
                amount=Decimal("10.00"),
                balance=Decimal("10.00"),
            )
        ],
    )

    summary = summarize_validation(validate_parse_result(parse_result))

    assert summary.flag_counts_by_code["transaction_date_outside_period"] == 2
    assert summary.export_readiness == ExportReadiness.READY_WITH_WARNINGS
