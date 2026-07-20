from decimal import Decimal

from bank_parser.core.models import Transaction
from bank_parser.validation.reconciliation import reconcile_transactions


def test_reconcile_transactions_flags_balance_mismatch() -> None:
    transactions = [
        Transaction(description="opening", amount=Decimal("10.00"), balance=Decimal("10.00")),
        Transaction(description="bad row", amount=Decimal("5.00"), balance=Decimal("20.00")),
    ]

    flags = reconcile_transactions(transactions)

    assert flags[0].code == "balance_mismatch"
