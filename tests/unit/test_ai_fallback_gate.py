from decimal import Decimal

from bank_parser.ai.fallback_gate import AiFallbackStatus, validate_ai_fallback_result
from bank_parser.core.models import Language, ParseResult, StatementMetadata, Transaction


def test_ai_fallback_gate_accepts_clean_validated_output() -> None:
    result = validate_ai_fallback_result(
        ParseResult(
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
    )

    assert result.status == AiFallbackStatus.ACCEPTED
    assert result.accepted is True
    assert result.gate_flags == []


def test_ai_fallback_gate_accepts_warning_only_output_for_review() -> None:
    result = validate_ai_fallback_result(
        ParseResult(
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
    )

    assert result.status == AiFallbackStatus.ACCEPTED_WITH_REVIEW
    assert result.accepted is True
    assert result.summary.flag_counts_by_code["unclear_date"] == 1


def test_ai_fallback_gate_rejects_output_that_fails_reconciliation() -> None:
    result = validate_ai_fallback_result(
        ParseResult(
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
    )

    assert result.status == AiFallbackStatus.REJECTED
    assert result.accepted is False
    assert result.gate_flags[0].code == "ai_fallback_rejected"
