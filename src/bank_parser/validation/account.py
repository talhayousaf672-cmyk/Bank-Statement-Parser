"""Account metadata consistency validation."""

from __future__ import annotations

import re

from bank_parser.core.models import ParseResult, ReviewFlag, ReviewSeverity


ACCOUNT_NUMBER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\- ]{3,33}[A-Z0-9]$")


def validate_account_metadata(parse_result: ParseResult) -> list[ReviewFlag]:
    """Validate account metadata required to trust a statement."""
    flags: list[ReviewFlag] = []
    account_number = _normalize_account_number(parse_result.metadata.account_number)

    if account_number is None:
        flags.append(
            ReviewFlag(
                code="missing_account_number",
                message="Statement account number is missing.",
                severity=ReviewSeverity.WARNING,
            )
        )
        return flags

    if not ACCOUNT_NUMBER_PATTERN.fullmatch(account_number):
        flags.append(
            ReviewFlag(
                code="invalid_account_number",
                message="Statement account number has an invalid format.",
                severity=ReviewSeverity.WARNING,
            )
        )

    return flags


def _normalize_account_number(account_number: str | None) -> str | None:
    if account_number is None:
        return None
    normalized = account_number.strip().upper()
    return normalized or None
