"""Fixture-based QA helpers for parser accuracy checks."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from bank_parser.core.models import ParseResult


class FieldMismatch(BaseModel):
    row_number: int | None = None
    field_name: str
    expected: str | None
    actual: str | None


class AccuracyReport(BaseModel):
    total_fields: int
    matched_fields: int
    mismatches: list[FieldMismatch] = Field(default_factory=list)

    @property
    def accuracy(self) -> float:
        if self.total_fields == 0:
            return 1.0
        return round(self.matched_fields / self.total_fields, 4)

    @property
    def passed(self) -> bool:
        return not self.mismatches


STATEMENT_FIELDS = [
    "bank_id",
    "language",
    "account_number",
    "account_holder",
    "currency",
    "statement_period_start",
    "statement_period_end",
    "parser_version",
]

TRANSACTION_FIELDS = [
    "transaction_date",
    "value_date",
    "description",
    "reference",
    "debit",
    "credit",
    "amount",
    "balance",
]


def compare_parse_results(expected: ParseResult, actual: ParseResult) -> AccuracyReport:
    mismatches: list[FieldMismatch] = []
    total_fields = 0
    matched_fields = 0

    for field_name in STATEMENT_FIELDS:
        total_fields += 1
        expected_value = getattr(expected.metadata, field_name)
        actual_value = getattr(actual.metadata, field_name)
        if _normalized(expected_value) == _normalized(actual_value):
            matched_fields += 1
        else:
            mismatches.append(
                FieldMismatch(
                    field_name=field_name,
                    expected=_normalized(expected_value),
                    actual=_normalized(actual_value),
                )
            )

    max_rows = max(len(expected.transactions), len(actual.transactions))
    for index in range(max_rows):
        expected_transaction = _get_row(expected, index)
        actual_transaction = _get_row(actual, index)
        for field_name in TRANSACTION_FIELDS:
            total_fields += 1
            expected_value = getattr(expected_transaction, field_name, None)
            actual_value = getattr(actual_transaction, field_name, None)
            if _normalized(expected_value) == _normalized(actual_value):
                matched_fields += 1
            else:
                mismatches.append(
                    FieldMismatch(
                        row_number=index + 1,
                        field_name=field_name,
                        expected=_normalized(expected_value),
                        actual=_normalized(actual_value),
                    )
                )

    return AccuracyReport(
        total_fields=total_fields,
        matched_fields=matched_fields,
        mismatches=mismatches,
    )


def _get_row(parse_result: ParseResult, index: int) -> object | None:
    if index >= len(parse_result.transactions):
        return None
    return parse_result.transactions[index]


def _normalized(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.01")))
    return str(value)
