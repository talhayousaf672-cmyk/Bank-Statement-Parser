from decimal import Decimal

from bank_parser.core.models import Language, ParseResult, StatementMetadata, Transaction
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.review_queue import build_review_queue


def test_build_review_queue_creates_items_from_validation_flags() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            account_number="123456789",
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
    queue = build_review_queue(validated, statement_id="stmt_001")

    assert len(queue) == 1
    assert queue[0].statement_id == "stmt_001"
    assert queue[0].bank_id == "hbl"
    assert queue[0].account_number == "123456789"
    assert queue[0].row_number == 2
    assert queue[0].flag.code == "balance_mismatch"
