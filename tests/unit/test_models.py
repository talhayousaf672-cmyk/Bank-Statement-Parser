from decimal import Decimal

from bank_parser.core.models import Language, StatementMetadata, Transaction


def test_statement_metadata_matches_output_model_fields() -> None:
    metadata = StatementMetadata(
        bank_id="hbl",
        language=Language.URDU,
        account_number="123456789",
        account_holder="Talha",
        currency="PKR",
        statement_period_start="2026-01-01",
        statement_period_end="2026-01-31",
        parser_version="0.1.0",
    )

    assert metadata.bank_id == "hbl"
    assert metadata.language == Language.URDU
    assert metadata.account_holder == "Talha"
    assert metadata.statement_period_start.isoformat() == "2026-01-01"
    assert metadata.statement_period_end.isoformat() == "2026-01-31"


def test_transaction_adds_unclear_date_review_flag() -> None:
    transaction = Transaction(description="ATM withdrawal", amount=Decimal("-100.00"))

    assert "unclear_date" in {flag.code for flag in transaction.review_flags}


def test_transaction_accepts_optional_row_currency() -> None:
    transaction = Transaction(
        transaction_date="2026-01-01",
        description="card settlement",
        amount=Decimal("10.00"),
        currency="USD",
    )

    assert transaction.currency == "USD"


def test_transaction_flags_debit_positive_amount() -> None:
    transaction = Transaction(
        transaction_date="2026-01-01",
        description="ATM withdrawal",
        debit=Decimal("100.00"),
        amount=Decimal("100.00"),
    )

    assert "amount_sign_mismatch" in {flag.code for flag in transaction.review_flags}


def test_transaction_flags_both_debit_and_credit() -> None:
    transaction = Transaction(
        transaction_date="2026-01-01",
        description="ambiguous row",
        debit=Decimal("100.00"),
        credit=Decimal("100.00"),
        amount=Decimal("100.00"),
    )

    assert "ambiguous_amount" in {flag.code for flag in transaction.review_flags}
