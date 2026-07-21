"""Balance reconciliation boundary."""

from __future__ import annotations

from decimal import Decimal

from bank_parser.core.models import ParseResult, ReviewFlag, ReviewSeverity, Transaction
from bank_parser.validation.account import validate_account_metadata
from bank_parser.validation.confidence import apply_confidence_scores
from bank_parser.validation.currency import validate_currencies
from bank_parser.validation.dates import validate_dates


def reconcile_transactions(
    transactions: list[Transaction],
    tolerance: Decimal = Decimal("0.01"),
) -> list[ReviewFlag]:
    flags: list[ReviewFlag] = []
    previous_balance: Decimal | None = None
    previous_currency: str | None = None

    for index, transaction in enumerate(transactions, start=1):
        current_currency = _effective_currency(transaction)
        if previous_currency is not None and current_currency is not None and current_currency != previous_currency:
            flags.append(
                ReviewFlag(
                    code="mixed_currency_balance",
                    message="Balance reconciliation crossed different transaction currencies.",
                    severity=ReviewSeverity.ERROR,
                    row_number=index,
                )
            )
            previous_balance = None

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
            previous_currency = current_currency
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
        previous_currency = current_currency

    return flags


def validate_parse_result(
    parse_result: ParseResult,
    tolerance: Decimal = Decimal("0.01"),
) -> ParseResult:
    """Attach validation review flags to a parse result.

    Normal statement quality issues are recorded as review flags so UI layers can
    show them without the parser silently accepting uncertain rows.
    """
    if _is_reverse_chronological(parse_result.transactions, tolerance):
        parse_result.transactions.reverse()
        parse_result.review_flags.append(
            ReviewFlag(
                code="reversed_chronological",
                message="Statement was detected as reverse chronological and reordered to chronological.",
                severity=ReviewSeverity.INFO,
            )
        )

    validation_flags = validate_account_metadata(parse_result)
    validation_flags.extend(validate_currencies(parse_result))
    validation_flags.extend(validate_dates(parse_result))
    validation_flags.extend(reconcile_transactions(parse_result.transactions, tolerance=tolerance))
    parse_result.review_flags.extend(validation_flags)

    for flag in validation_flags:
        if flag.row_number is None:
            continue
        transaction_index = flag.row_number - 1
        if transaction_index < len(parse_result.transactions):
            transaction = parse_result.transactions[transaction_index]
            if not any(existing.code == flag.code for existing in transaction.review_flags):
                transaction.review_flags.append(flag)

    apply_confidence_scores(parse_result.transactions)
    return parse_result


def _effective_currency(transaction: Transaction) -> str | None:
    if transaction.currency is None:
        return None
    return transaction.currency.strip().upper() or None

def _is_reverse_chronological(transactions: list[Transaction], tolerance: Decimal) -> bool:
    if len(transactions) < 2:
        return False
        
    standard_matches = 0
    reverse_matches = 0
    
    for i in range(len(transactions) - 1):
        tx1 = transactions[i]
        tx2 = transactions[i+1]
        if tx1.balance is not None and tx2.balance is not None:
            if abs((tx1.balance + tx2.amount) - tx2.balance) <= tolerance:
                standard_matches += 1
            if abs((tx2.balance + tx1.amount) - tx1.balance) <= tolerance:
                reverse_matches += 1
                
    return reverse_matches > 0 and reverse_matches > standard_matches
