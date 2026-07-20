"""Statement-level validation summary reporting."""

from __future__ import annotations

from collections import Counter
from enum import Enum

from pydantic import BaseModel, Field

from bank_parser.core.models import ParseResult, ReviewFlag, ReviewSeverity, Transaction
from bank_parser.validation.policy import DEFAULT_VALIDATION_POLICY, ValidationPolicy


class ExportReadiness(str, Enum):
    READY = "ready"
    READY_WITH_WARNINGS = "ready_with_warnings"
    BLOCKED = "blocked"


class ValidationSummary(BaseModel):
    total_rows: int
    clean_rows: int
    info_rows: int
    warning_rows: int
    error_rows: int
    statement_flag_count: int
    row_flag_count: int
    flag_counts_by_code: dict[str, int] = Field(default_factory=dict)
    severity_counts: dict[ReviewSeverity, int] = Field(default_factory=dict)
    export_readiness: ExportReadiness

    @property
    def export_ready(self) -> bool:
        return self.export_readiness in {
            ExportReadiness.READY,
            ExportReadiness.READY_WITH_WARNINGS,
        }


def summarize_validation(
    parse_result: ParseResult,
    policy: ValidationPolicy = DEFAULT_VALIDATION_POLICY,
) -> ValidationSummary:
    """Summarize statement and row review flags for app/export decisions."""
    statement_flags = parse_result.review_flags
    row_flags = [flag for transaction in parse_result.transactions for flag in transaction.review_flags]
    all_flags = statement_flags + row_flags
    row_severities = [_highest_row_severity(transaction) for transaction in parse_result.transactions]

    severity_counts = Counter(flag.severity for flag in all_flags)
    flag_counts_by_code = Counter(flag.code for flag in all_flags)

    return ValidationSummary(
        total_rows=len(parse_result.transactions),
        clean_rows=sum(1 for severity in row_severities if severity is None),
        info_rows=sum(1 for severity in row_severities if severity == ReviewSeverity.INFO),
        warning_rows=sum(1 for severity in row_severities if severity == ReviewSeverity.WARNING),
        error_rows=sum(1 for severity in row_severities if severity == ReviewSeverity.ERROR),
        statement_flag_count=len(statement_flags),
        row_flag_count=len(row_flags),
        flag_counts_by_code=dict(flag_counts_by_code),
        severity_counts=dict(severity_counts),
        export_readiness=_export_readiness(all_flags, policy),
    )


def _highest_row_severity(transaction: Transaction) -> ReviewSeverity | None:
    if not transaction.review_flags:
        return None

    severities = {flag.severity for flag in transaction.review_flags}
    if ReviewSeverity.ERROR in severities:
        return ReviewSeverity.ERROR
    if ReviewSeverity.WARNING in severities:
        return ReviewSeverity.WARNING
    return ReviewSeverity.INFO


def _export_readiness(flags: list[ReviewFlag], policy: ValidationPolicy) -> ExportReadiness:
    if policy.should_block_export(flags):
        return ExportReadiness.BLOCKED
    if policy.has_export_warnings(flags):
        return ExportReadiness.READY_WITH_WARNINGS
    return ExportReadiness.READY
