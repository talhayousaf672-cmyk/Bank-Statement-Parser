"""Currency consistency validation."""

from __future__ import annotations

from bank_parser.core.models import ParseResult, ReviewFlag, ReviewSeverity, Transaction


DEFAULT_SUPPORTED_CURRENCIES = {
    "AED",
    "EUR",
    "GBP",
    "INR",
    "PKR",
    "RUB",
    "SAR",
    "USD",
}


def validate_currencies(
    parse_result: ParseResult,
    supported_currencies: set[str] | None = None,
    allow_transaction_currency_override: bool = False,
) -> list[ReviewFlag]:
    """Validate statement and row currency consistency."""
    supported = {_normalize_currency(currency) for currency in supported_currencies} if supported_currencies else DEFAULT_SUPPORTED_CURRENCIES
    flags: list[ReviewFlag] = []
    statement_currency = _normalize_currency(parse_result.metadata.currency)

    if statement_currency is None:
        flags.append(
            ReviewFlag(
                code="missing_currency",
                message="Statement currency is missing.",
                severity=ReviewSeverity.WARNING,
            )
        )
    elif statement_currency not in supported:
        flags.append(
            ReviewFlag(
                code="unsupported_currency",
                message="Statement currency is not in the supported currency list.",
                severity=ReviewSeverity.ERROR,
            )
        )

    for row_number, transaction in enumerate(parse_result.transactions, start=1):
        flags.extend(
            _validate_transaction_currency(
                transaction=transaction,
                row_number=row_number,
                statement_currency=statement_currency,
                supported_currencies=supported,
                allow_transaction_currency_override=allow_transaction_currency_override,
            )
        )

    return flags


def _validate_transaction_currency(
    transaction: Transaction,
    row_number: int,
    statement_currency: str | None,
    supported_currencies: set[str],
    allow_transaction_currency_override: bool,
) -> list[ReviewFlag]:
    flags: list[ReviewFlag] = []
    transaction_currency = _normalize_currency(transaction.currency)

    if statement_currency is None and transaction_currency is None:
        flags.append(
            ReviewFlag(
                code="missing_currency",
                message="Transaction currency is missing and no statement currency is available.",
                severity=ReviewSeverity.WARNING,
                row_number=row_number,
            )
        )
        return flags

    if transaction_currency is None:
        return flags

    if transaction_currency not in supported_currencies:
        flags.append(
            ReviewFlag(
                code="unsupported_currency",
                message="Transaction currency is not in the supported currency list.",
                severity=ReviewSeverity.ERROR,
                row_number=row_number,
            )
        )

    if (
        statement_currency is not None
        and transaction_currency != statement_currency
        and not allow_transaction_currency_override
    ):
        flags.append(
            ReviewFlag(
                code="currency_mismatch",
                message="Transaction currency does not match the statement currency.",
                severity=ReviewSeverity.ERROR,
                row_number=row_number,
            )
        )

    return flags


def _normalize_currency(currency: str | None) -> str | None:
    if currency is None:
        return None
    normalized = currency.strip().upper()
    return normalized or None
