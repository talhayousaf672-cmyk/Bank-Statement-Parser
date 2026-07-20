from bank_parser.core.models import ReviewFlag, ReviewSeverity
from bank_parser.validation.policy import ExportDecision, ValidationPolicy


def test_policy_blocks_known_financial_correctness_flags() -> None:
    policy = ValidationPolicy()
    flag = ReviewFlag(
        code="balance_mismatch",
        message="Balance does not reconcile.",
        severity=ReviewSeverity.ERROR,
    )

    assert policy.decision_for_flag(flag) == ExportDecision.BLOCK


def test_policy_allows_known_reviewable_flags_with_warnings() -> None:
    policy = ValidationPolicy()
    flag = ReviewFlag(
        code="missing_balance",
        message="Balance missing.",
        severity=ReviewSeverity.WARNING,
    )

    assert policy.decision_for_flag(flag) == ExportDecision.ALLOW_WITH_WARNINGS


def test_policy_can_override_error_flag_as_warning() -> None:
    policy = ValidationPolicy(
        blocking_flag_codes=set(),
        warning_flag_codes={"custom_error"},
    )
    flag = ReviewFlag(
        code="custom_error",
        message="Configured as warning.",
        severity=ReviewSeverity.ERROR,
    )

    assert policy.decision_for_flag(flag) == ExportDecision.ALLOW_WITH_WARNINGS


def test_policy_blocks_invalid_statement_period() -> None:
    policy = ValidationPolicy()
    flag = ReviewFlag(
        code="invalid_statement_period",
        message="Bad period.",
        severity=ReviewSeverity.ERROR,
    )

    assert policy.decision_for_flag(flag) == ExportDecision.BLOCK
