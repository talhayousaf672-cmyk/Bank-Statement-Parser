"""Validation policy for export-readiness decisions."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from bank_parser.core.models import ReviewFlag, ReviewSeverity


class ExportDecision(str, Enum):
    ALLOW = "allow"
    ALLOW_WITH_WARNINGS = "allow_with_warnings"
    BLOCK = "block"


class ValidationPolicy(BaseModel):
    blocking_flag_codes: set[str] = Field(
        default_factory=lambda: {
            "ambiguous_amount",
            "amount_sign_mismatch",
            "balance_mismatch",
            "currency_mismatch",
            "invalid_statement_period",
            "mixed_currency_balance",
            "unsupported_currency",
        }
    )
    warning_flag_codes: set[str] = Field(
        default_factory=lambda: {
            "missing_balance",
            "missing_account_number",
            "missing_currency",
            "invalid_account_number",
            "transaction_date_outside_period",
            "unclear_date",
            "value_date_before_transaction_date",
        }
    )

    def decision_for_flag(self, flag: ReviewFlag) -> ExportDecision:
        if flag.code in self.blocking_flag_codes:
            return ExportDecision.BLOCK
        if flag.code in self.warning_flag_codes:
            return ExportDecision.ALLOW_WITH_WARNINGS
        if flag.severity == ReviewSeverity.ERROR:
            return ExportDecision.BLOCK
        if flag.severity in {ReviewSeverity.WARNING, ReviewSeverity.INFO}:
            return ExportDecision.ALLOW_WITH_WARNINGS
        return ExportDecision.ALLOW

    def should_block_export(self, flags: list[ReviewFlag]) -> bool:
        return any(self.decision_for_flag(flag) == ExportDecision.BLOCK for flag in flags)

    def has_export_warnings(self, flags: list[ReviewFlag]) -> bool:
        return any(
            self.decision_for_flag(flag) == ExportDecision.ALLOW_WITH_WARNINGS for flag in flags
        )


DEFAULT_VALIDATION_POLICY = ValidationPolicy()
