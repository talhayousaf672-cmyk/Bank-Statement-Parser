from decimal import Decimal

from bank_parser.core.models import Language, ParseResult, StatementMetadata, Transaction
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.review_queue import ReviewStatus, build_review_queue
from bank_parser.validation.sqlite_review_store import SQLiteReviewQueueStore


def test_sqlite_review_store_saves_and_loads_review_items(tmp_path) -> None:
    store = SQLiteReviewQueueStore(tmp_path / "review_queue.sqlite")
    store.initialize()
    items = _review_items()

    store.save_items(items)
    loaded = store.list_items_for_statement("stmt_001")

    assert len(loaded) == 1
    assert loaded[0].id == items[0].id
    assert loaded[0].statement_id == "stmt_001"
    assert loaded[0].flag.code == "balance_mismatch"
    assert loaded[0].transaction is not None
    assert loaded[0].transaction.description == "bad row"


def test_sqlite_review_store_filters_by_status(tmp_path) -> None:
    store = SQLiteReviewQueueStore(tmp_path / "review_queue.sqlite")
    store.initialize()
    items = _review_items()
    store.save_items(items)

    store.update_status(items[0].id, ReviewStatus.RESOLVED, notes=["Fixed manually"])

    open_items = store.list_items(status=ReviewStatus.OPEN)
    resolved_items = store.list_items(status=ReviewStatus.RESOLVED)

    assert open_items == []
    assert len(resolved_items) == 1
    assert resolved_items[0].status == ReviewStatus.RESOLVED
    assert resolved_items[0].notes == ["Fixed manually"]


def _review_items():
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
    return build_review_queue(validate_parse_result(parse_result), statement_id="stmt_001")
