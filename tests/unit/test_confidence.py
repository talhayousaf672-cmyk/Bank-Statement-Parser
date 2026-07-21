from decimal import Decimal

from bank_parser.core.models import ReviewFlag, ReviewSeverity, Transaction
from bank_parser.validation.confidence import apply_confidence_scores, score_transaction_confidence


def test_score_transaction_confidence_uses_review_flag_severity() -> None:
    transaction = Transaction(
        transaction_date="2026-01-01",
        description="uncertain row",
        amount=Decimal("10.00"),
        review_flags=[
            ReviewFlag(code="manual_review", message="Needs review", severity=ReviewSeverity.WARNING)
        ],
    )

    assert score_transaction_confidence(transaction) == 0.8


def test_apply_confidence_scores_updates_transactions() -> None:
    transactions = [
        Transaction(
            transaction_date="2026-01-01",
            description="ok row",
            amount=Decimal("10.00"),
        ),
        Transaction(
            transaction_date="2026-01-02",
            description="bad row",
            amount=Decimal("10.00"),
            review_flags=[
                ReviewFlag(code="balance_mismatch", message="Mismatch", severity=ReviewSeverity.ERROR)
            ],
        ),
    ]

    scored = apply_confidence_scores(transactions)

    assert scored[0].confidence == 1.0
    assert scored[1].confidence == 0.55
