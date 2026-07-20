"""Review queue models and builders."""

from __future__ import annotations

from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from bank_parser.core.models import ParseResult, ReviewFlag, Transaction


class ReviewStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ReviewQueueItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    statement_id: str
    bank_id: str
    account_number: str | None = None
    row_number: int | None = None
    flag: ReviewFlag
    transaction: Transaction | None = None
    status: ReviewStatus = ReviewStatus.OPEN
    assigned_to: str | None = None
    notes: list[str] = Field(default_factory=list)


def build_review_queue(
    parse_result: ParseResult,
    statement_id: str,
) -> list[ReviewQueueItem]:
    """Create UI-ready review items from statement-level and row-level flags."""
    items: list[ReviewQueueItem] = []
    metadata = parse_result.metadata

    for flag in parse_result.review_flags:
        transaction = _transaction_for_flag(parse_result.transactions, flag)
        items.append(
            ReviewQueueItem(
                statement_id=statement_id,
                bank_id=metadata.bank_id,
                account_number=metadata.account_number,
                row_number=flag.row_number,
                flag=flag,
                transaction=transaction,
            )
        )

    for row_number, transaction in enumerate(parse_result.transactions, start=1):
        for flag in transaction.review_flags:
            if _already_added(items, flag, row_number):
                continue
            items.append(
                ReviewQueueItem(
                    statement_id=statement_id,
                    bank_id=metadata.bank_id,
                    account_number=metadata.account_number,
                    row_number=row_number,
                    flag=flag,
                    transaction=transaction,
                )
            )

    return items


def _transaction_for_flag(
    transactions: list[Transaction],
    flag: ReviewFlag,
) -> Transaction | None:
    if flag.row_number is None:
        return None

    transaction_index = flag.row_number - 1
    if transaction_index < 0 or transaction_index >= len(transactions):
        return None

    return transactions[transaction_index]


def _already_added(items: list[ReviewQueueItem], flag: ReviewFlag, row_number: int) -> bool:
    return any(item.row_number == row_number and item.flag.code == flag.code for item in items)
