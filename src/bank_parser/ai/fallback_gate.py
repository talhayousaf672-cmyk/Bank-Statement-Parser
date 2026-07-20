"""Validation gate for AI fallback extraction results."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from bank_parser.core.models import ParseResult, ReviewFlag, ReviewSeverity
from bank_parser.validation.policy import DEFAULT_VALIDATION_POLICY, ValidationPolicy
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.summary import ValidationSummary, summarize_validation


class AiFallbackStatus(str, Enum):
    ACCEPTED = "accepted"
    ACCEPTED_WITH_REVIEW = "accepted_with_review"
    REJECTED = "rejected"


class AiFallbackGateResult(BaseModel):
    status: AiFallbackStatus
    parse_result: ParseResult
    summary: ValidationSummary
    gate_flags: list[ReviewFlag]

    @property
    def accepted(self) -> bool:
        return self.status in {
            AiFallbackStatus.ACCEPTED,
            AiFallbackStatus.ACCEPTED_WITH_REVIEW,
        }


def validate_ai_fallback_result(
    ai_parse_result: ParseResult,
    policy: ValidationPolicy = DEFAULT_VALIDATION_POLICY,
) -> AiFallbackGateResult:
    """Validate AI fallback output before it can enter export or review flows."""
    validated = validate_parse_result(ai_parse_result)
    summary = summarize_validation(validated, policy=policy)
    gate_flags = _gate_flags(summary)

    return AiFallbackGateResult(
        status=_status_from_summary(summary),
        parse_result=validated,
        summary=summary,
        gate_flags=gate_flags,
    )


def _status_from_summary(summary: ValidationSummary) -> AiFallbackStatus:
    if not summary.export_ready:
        return AiFallbackStatus.REJECTED
    if summary.row_flag_count or summary.statement_flag_count:
        return AiFallbackStatus.ACCEPTED_WITH_REVIEW
    return AiFallbackStatus.ACCEPTED


def _gate_flags(summary: ValidationSummary) -> list[ReviewFlag]:
    if summary.export_ready:
        return []

    return [
        ReviewFlag(
            code="ai_fallback_rejected",
            message="AI fallback output failed validation and cannot be exported.",
            severity=ReviewSeverity.ERROR,
        )
    ]
