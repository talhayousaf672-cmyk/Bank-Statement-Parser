"""Balance reconciliation boundary."""

from __future__ import annotations

from decimal import Decimal

from bank_parser.core.models import ParseResult, ReviewFlag, ReviewSeverity, Transaction
from bank_parser.validation.confidence import apply_confidence_scores


def reconcile_transactions(
    transactions: list[Transaction],
    tolerance: Decimal = Decimal("0.01"),
) -> list[ReviewFlag]:
    flags: list[ReviewFlag] = []
    previous_balance: Decimal | None = None

    for index, transaction in enumerate(transactions, start=1):
        if transaction.balance is None:
            flags.append(
                ReviewFlag(
                    code="missing_balance",
                    message="Transaction balance is missing.",
                    severity=ReviewSeverity.WARNING,
                    row_number=index,
                )
            )
            previous_balance = None
            continue

        if previous_balance is not None:
            expected = previous_balance + transaction.amount
            if abs(expected - transaction.balance) > tolerance:
                flags.append(
                    ReviewFlag(
                        code="balance_mismatch",
                        message="Transaction balance does not reconcile.",
                        severity=ReviewSeverity.ERROR,
                        row_number=index,
                    )
                )

        previous_balance = transaction.balance

    return flags


def validate_parse_result(
    parse_result: ParseResult,
    tolerance: Decimal = Decimal("0.01"),
) -> ParseResult:
    """Attach validation review flags to a parse result.

    Normal statement quality issues are recorded as review flags so UI layers can
    show them without the parser silently accepting uncertain rows.
    """
    reconciliation_flags = reconcile_transactions(parse_result.transactions, tolerance=tolerance)
    parse_result.review_flags.extend(reconciliation_flags)

    for flag in reconciliation_flags:
        if flag.row_number is None:
            continue
        transaction_index = flag.row_number - 1
        if transaction_index < len(parse_result.transactions):
            transaction = parse_result.transactions[transaction_index]
            if not any(existing.code == flag.code for existing in transaction.review_flags):
                transaction.review_flags.append(flag)

    apply_confidence_scores(parse_result.transactions)
    return parse_result
