from decimal import Decimal

from bank_parser.core.models import Language, ParseResult, StatementMetadata, Transaction
from bank_parser.validation.reconciliation import reconcile_transactions, validate_parse_result


def test_reconcile_transactions_flags_balance_mismatch() -> None:
    transactions = [
        Transaction(
            transaction_date="2026-01-01",
            description="opening",
            amount=Decimal("10.00"),
            balance=Decimal("10.00"),
        ),
        Transaction(
            transaction_date="2026-01-02",
            description="bad row",
            amount=Decimal("5.00"),
            balance=Decimal("20.00"),
        ),
    ]

    flags = reconcile_transactions(transactions)

    assert flags[0].code == "balance_mismatch"


def test_reconcile_transactions_allows_decimal_tolerance() -> None:
    transactions = [
        Transaction(
            transaction_date="2026-01-01",
            description="opening",
            amount=Decimal("10.00"),
            balance=Decimal("10.00"),
        ),
        Transaction(
            transaction_date="2026-01-02",
            description="fee",
            amount=Decimal("-1.005"),
            balance=Decimal("9.00"),
        ),
    ]

    flags = reconcile_transactions(transactions, tolerance=Decimal("0.01"))

    assert flags == []


def test_reconcile_transactions_flags_missing_balance() -> None:
    transactions = [
        Transaction(
            transaction_date="2026-01-01",
            description="missing balance",
            amount=Decimal("10.00"),
            balance=None,
        )
    ]

    flags = reconcile_transactions(transactions)

    assert flags[0].code == "missing_balance"


def test_validate_parse_result_attaches_row_flags() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="example_bank",
            language=Language.SPANISH,
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
                description="bad row",
                amount=Decimal("5.00"),
                balance=Decimal("20.00"),
            ),
        ],
    )

    validated = validate_parse_result(parse_result)

    assert validated.review_flags[0].code == "balance_mismatch"
    assert validated.transactions[1].review_flags[0].code == "balance_mismatch"


def test_reconcile_transactions_flags_mixed_currency_balance() -> None:
    transactions = [
        Transaction(
            transaction_date="2026-01-01",
            description="pkr row",
            amount=Decimal("10.00"),
            balance=Decimal("10.00"),
            currency="PKR",
        ),
        Transaction(
            transaction_date="2026-01-02",
            description="usd row",
            amount=Decimal("5.00"),
            balance=Decimal("5.00"),
            currency="USD",
        ),
    ]

    flags = reconcile_transactions(transactions)

    assert flags[0].code == "mixed_currency_balance"
