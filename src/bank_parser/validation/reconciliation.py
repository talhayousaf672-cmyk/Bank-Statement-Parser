"""Balance reconciliation boundary."""

from __future__ import annotations

from decimal import Decimal

from bank_parser.core.models import ReviewFlag, ReviewSeverity, Transaction


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
