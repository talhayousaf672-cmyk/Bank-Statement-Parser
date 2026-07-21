"""Onboarding validation helpers for bank parsers."""

from __future__ import annotations

from pathlib import Path
import re

from bank_parser.core.parser import BaseBankParser

_SNAKE_CASE_RE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")


def validate_bank_onboarding_fixtures(
    bank_id: str,
    language: str = "en",
    fixtures_root: str | Path | None = None,
) -> bool:
    """Validate that the required fixture directory and files exist for a bank parser."""
    if fixtures_root is None:
        # Default to repo structure tests/fixtures/parsers
        fixtures_root = Path(__file__).parents[3] / "tests" / "fixtures" / "parsers"
    else:
        fixtures_root = Path(fixtures_root)

    bank_fixture_dir = fixtures_root / bank_id / language
    if not bank_fixture_dir.is_dir():
        return False

    statement_text_file = bank_fixture_dir / "statement_text.txt"
    expected_parse_file = bank_fixture_dir / "expected_parse.json"

    return statement_text_file.is_file() and expected_parse_file.is_file()


def validate_parser_naming_convention(parser_cls: type[BaseBankParser]) -> bool:
    """Validate that a parser class conforms to the bank onboarding naming standards."""
    if not issubclass(parser_cls, BaseBankParser):
        return False

    class_name = parser_cls.__name__
    if not class_name.endswith("BankParser"):
        return False

    bank_id = getattr(parser_cls, "bank_id", "")
    if not bank_id or not _SNAKE_CASE_RE.match(bank_id):
        return False

    return True
