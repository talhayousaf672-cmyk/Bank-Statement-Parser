"""Confidence scoring for parsed transactions."""

from __future__ import annotations

from bank_parser.core.models import ReviewSeverity, Transaction


SEVERITY_PENALTIES: dict[ReviewSeverity, float] = {
    ReviewSeverity.INFO: 0.05,
    ReviewSeverity.WARNING: 0.20,
    ReviewSeverity.ERROR: 0.45,
}


def score_transaction_confidence(transaction: Transaction) -> float:
    """Return a bounded confidence score based on transaction review flags."""
    penalty = sum(SEVERITY_PENALTIES[flag.severity] for flag in transaction.review_flags)
    return max(0.0, round(1.0 - penalty, 2))


def apply_confidence_scores(transactions: list[Transaction]) -> list[Transaction]:
    for transaction in transactions:
        transaction.confidence = score_transaction_confidence(transaction)
    return transactions
