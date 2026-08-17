"""Canonical data models shared by all parser adapters."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, model_validator, field_validator


class Language(str, Enum):
    ARABIC = "ar"
    URDU = "ur"
    RUSSIAN = "ru"
    SPANISH = "es"
    HINDI = "hi"
    ENGLISH = "en"


class ReviewSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ReviewFlag(BaseModel):
    code: str
    message: str
    severity: ReviewSeverity = ReviewSeverity.WARNING
    row_number: int | None = None


class StatementMetadata(BaseModel):
    bank_id: str
    language: Language
    account_number: str | None = None
    account_holder: str | None = None
    currency: str | None = None
    statement_period_start: date | None = None
    statement_period_end: date | None = None
    parser_version: str = "0.1.0"


class Transaction(BaseModel):
    transaction_date: date | None = None
    value_date: date | None = None
    description: str
    reference: str | None = None
    debit: Decimal | None = None
    credit: Decimal | None = None
    amount: Decimal
    balance: Decimal | None = None
    currency: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    review_flags: list[ReviewFlag] = Field(default_factory=list)

    @field_validator("debit", "credit", "amount", "balance", mode="before")
    @classmethod
    def strip_commas(cls, v: str | Decimal | None) -> str | Decimal | None:
        if isinstance(v, str):
            return v.replace(",", "")
        return v

    @model_validator(mode="after")
    def add_quality_flags(self) -> "Transaction":
        if self.transaction_date is None:
            self._add_review_flag(
                code="unclear_date",
                message="Transaction date is missing or unclear.",
                severity=ReviewSeverity.WARNING,
            )

        if self.debit is not None and self.credit is not None:
            self._add_review_flag(
                code="ambiguous_amount",
                message="Both debit and credit are populated for one transaction.",
                severity=ReviewSeverity.ERROR,
            )

        if self.debit is not None and self.amount > 0:
            self._add_review_flag(
                code="amount_sign_mismatch",
                message="Debit rows must use a negative signed amount.",
                severity=ReviewSeverity.ERROR,
            )

        if self.credit is not None and self.amount < 0:
            self._add_review_flag(
                code="amount_sign_mismatch",
                message="Credit rows must use a positive signed amount.",
                severity=ReviewSeverity.ERROR,
            )

        return self

    def _add_review_flag(
        self,
        code: str,
        message: str,
        severity: ReviewSeverity,
    ) -> None:
        if any(flag.code == code for flag in self.review_flags):
            return
        self.review_flags.append(ReviewFlag(code=code, message=message, severity=severity))


class ParseResult(BaseModel):
    metadata: StatementMetadata
    transactions: list[Transaction] = Field(default_factory=list)
    review_flags: list[ReviewFlag] = Field(default_factory=list)
