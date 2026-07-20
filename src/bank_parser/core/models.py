"""Canonical data models shared by all parser adapters."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Language(str, Enum):
    ARABIC = "ar"
    URDU = "ur"
    RUSSIAN = "ru"
    SPANISH = "es"
    HINDI = "hi"


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
    currency: str | None = None
    statement_period: str | None = None


class Transaction(BaseModel):
    transaction_date: str | None = None
    value_date: str | None = None
    description: str
    reference: str | None = None
    debit: Decimal | None = None
    credit: Decimal | None = None
    amount: Decimal
    balance: Decimal | None = None
    currency: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    review_flags: list[ReviewFlag] = Field(default_factory=list)


class ParseResult(BaseModel):
    metadata: StatementMetadata
    transactions: list[Transaction] = Field(default_factory=list)
    review_flags: list[ReviewFlag] = Field(default_factory=list)
    parser_version: str = "0.1.0"
