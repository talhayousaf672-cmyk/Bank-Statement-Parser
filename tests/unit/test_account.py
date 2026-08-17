from bank_parser.core.models import Language, ParseResult, StatementMetadata
from bank_parser.validation.account import validate_account_metadata


def test_validate_account_metadata_flags_missing_account_number() -> None:
    parse_result = ParseResult(metadata=StatementMetadata(bank_id="hbl", language=Language.URDU))

    flags = validate_account_metadata(parse_result)

    assert flags[0].code == "missing_account_number"


def test_validate_account_metadata_flags_invalid_account_number() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            account_number="@@@",
        )
    )

    flags = validate_account_metadata(parse_result)

    assert flags[0].code == "invalid_account_number"


def test_validate_account_metadata_accepts_common_account_number_formats() -> None:
    parse_result = ParseResult(
        metadata=StatementMetadata(
            bank_id="hbl",
            language=Language.URDU,
            account_number="PK12 HABB 0000 1234 5678",
        )
    )

    assert validate_account_metadata(parse_result) == []
