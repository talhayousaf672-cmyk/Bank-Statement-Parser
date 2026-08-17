from bank_parser.core.models import Language, ParseResult
from bank_parser.core.onboarding import (
    validate_bank_onboarding_fixtures,
    validate_parser_naming_convention,
)
from bank_parser.core.parser import BaseBankParser
from bank_parser.parsers.chase_bank import ChaseBankParser
from bank_parser.parsers.generic_english import GenericEnglishBankParser


def test_validate_bank_onboarding_fixtures_success() -> None:
    assert validate_bank_onboarding_fixtures("generic_english", "en") is True
    assert validate_bank_onboarding_fixtures("chase_bank", "en") is True


def test_validate_bank_onboarding_fixtures_failure() -> None:
    assert validate_bank_onboarding_fixtures("non_existent_bank", "en") is False


def test_validate_parser_naming_convention_success() -> None:
    assert validate_parser_naming_convention(ChaseBankParser) is True
    assert validate_parser_naming_convention(GenericEnglishBankParser) is True


def test_validate_parser_naming_convention_failure() -> None:
    class BadNameParser(BaseBankParser):
        bank_id = "bad_name"

        def parse(self, normalized_text: str) -> ParseResult:
            raise NotImplementedError

    class InvalidBankIdBankParser(BaseBankParser):
        bank_id = "Invalid-Bank-Id!"

        def parse(self, normalized_text: str) -> ParseResult:
            raise NotImplementedError

    assert validate_parser_naming_convention(BadNameParser) is False
    assert validate_parser_naming_convention(InvalidBankIdBankParser) is False
