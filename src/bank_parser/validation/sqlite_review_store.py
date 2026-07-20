"""SQLite persistence for desktop review queue items."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from bank_parser.core.models import ReviewFlag, Transaction
from bank_parser.validation.review_queue import ReviewQueueItem, ReviewStatus


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS review_queue (
    id TEXT PRIMARY KEY,
    statement_id TEXT NOT NULL,
    bank_id TEXT NOT NULL,
    account_number TEXT,
    row_number INTEGER,
    flag_code TEXT NOT NULL,
    flag_message TEXT NOT NULL,
    flag_severity TEXT NOT NULL,
    transaction_snapshot TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    assigned_to TEXT,
    notes TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SQLiteReviewQueueStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(SCHEMA_SQL)

    def save_items(self, items: list[ReviewQueueItem]) -> None:
        if not items:
            return

        now = _utc_now()
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO review_queue (
                    id,
                    statement_id,
                    bank_id,
                    account_number,
                    row_number,
                    flag_code,
                    flag_message,
                    flag_severity,
                    transaction_snapshot,
                    status,
                    assigned_to,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [self._item_to_row(item, now) for item in items],
            )

    def list_items(self, status: ReviewStatus | None = None) -> list[ReviewQueueItem]:
        query = "SELECT * FROM review_queue"
        params: list[str] = []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status.value)
        query += " ORDER BY created_at, row_number"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_item(row) for row in rows]

    def list_items_for_statement(self, statement_id: str) -> list[ReviewQueueItem]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM review_queue
                WHERE statement_id = ?
                ORDER BY row_number, created_at
                """,
                (statement_id,),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def update_status(
        self,
        item_id: str,
        status: ReviewStatus,
        notes: list[str] | None = None,
    ) -> None:
        updated_at = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE review_queue
                SET status = ?, notes = COALESCE(?, notes), updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    json.dumps(notes) if notes is not None else None,
                    updated_at,
                    item_id,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _item_to_row(self, item: ReviewQueueItem, now: str) -> tuple[object, ...]:
        return (
            item.id,
            item.statement_id,
            item.bank_id,
            item.account_number,
            item.row_number,
            item.flag.code,
            item.flag.message,
            item.flag.severity.value,
            _dump_transaction(item.transaction),
            item.status.value,
            item.assigned_to,
            json.dumps(item.notes),
            now,
            now,
        )

    def _row_to_item(self, row: sqlite3.Row) -> ReviewQueueItem:
        return ReviewQueueItem(
            id=row["id"],
            statement_id=row["statement_id"],
            bank_id=row["bank_id"],
            account_number=row["account_number"],
            row_number=row["row_number"],
            flag=ReviewFlag(
                code=row["flag_code"],
                message=row["flag_message"],
                severity=row["flag_severity"],
                row_number=row["row_number"],
            ),
            transaction=_load_transaction(row["transaction_snapshot"]),
            status=row["status"],
            assigned_to=row["assigned_to"],
            notes=json.loads(row["notes"]),
        )


def _dump_transaction(transaction: Transaction | None) -> str | None:
    if transaction is None:
        return None
    return transaction.model_dump_json()


def _load_transaction(snapshot: str | None) -> Transaction | None:
    if snapshot is None:
        return None
    return Transaction.model_validate_json(snapshot)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
