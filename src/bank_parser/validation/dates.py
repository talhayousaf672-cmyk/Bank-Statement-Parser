"""Date consistency validation."""

from __future__ import annotations

from datetime import date

from bank_parser.core.models import ParseResult, ReviewFlag, ReviewSeverity, Transaction


def validate_dates(parse_result: ParseResult) -> list[ReviewFlag]:
    """Validate transaction dates against value dates and statement period."""
    flags: list[ReviewFlag] = []
    period_start = parse_result.metadata.statement_period_start
    period_end = parse_result.metadata.statement_period_end

    if period_start is not None and period_end is not None and period_start > period_end:
        flags.append(
            ReviewFlag(
                code="invalid_statement_period",
                message="Statement period start date is after the end date.",
                severity=ReviewSeverity.ERROR,
            )
        )

    for row_number, transaction in enumerate(parse_result.transactions, start=1):
        flags.extend(_validate_transaction_dates(transaction, row_number, period_start, period_end))

    return flags


def _validate_transaction_dates(
    transaction: Transaction,
    row_number: int,
    period_start: date | None,
    period_end: date | None,
) -> list[ReviewFlag]:
    flags: list[ReviewFlag] = []

    if transaction.transaction_date is None:
        return flags

    if transaction.value_date is not None and transaction.value_date < transaction.transaction_date:
        flags.append(
            ReviewFlag(
                code="value_date_before_transaction_date",
                message="Value date is before the transaction date.",
                severity=ReviewSeverity.WARNING,
                row_number=row_number,
            )
        )

    if period_start is not None and transaction.transaction_date < period_start:
        flags.append(
            ReviewFlag(
                code="transaction_date_outside_period",
                message="Transaction date is before the statement period.",
                severity=ReviewSeverity.WARNING,
                row_number=row_number,
            )
        )

    if period_end is not None and transaction.transaction_date > period_end:
        flags.append(
            ReviewFlag(
                code="transaction_date_outside_period",
                message="Transaction date is after the statement period.",
                severity=ReviewSeverity.WARNING,
                row_number=row_number,
            )
        )

    return flags
