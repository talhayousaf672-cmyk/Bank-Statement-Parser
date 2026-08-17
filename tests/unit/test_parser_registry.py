import pytest

from bank_parser.core.models import Language
from bank_parser.core.parser import DuplicateParserRegistrationError, ParserRegistry
from bank_parser.parsers.example_bank import ExampleBankEnglishLikeParser


def test_registry_creates_registered_parser() -> None:
    registry = ParserRegistry()
    registry.register(ExampleBankEnglishLikeParser)

    parser = registry.create("example_bank", Language.SPANISH)

    assert isinstance(parser, ExampleBankEnglishLikeParser)


def test_registry_rejects_duplicate_parser_registration() -> None:
    registry = ParserRegistry()
    registry.register(ExampleBankEnglishLikeParser)

    with pytest.raises(DuplicateParserRegistrationError, match="example_bank"):
        registry.register(ExampleBankEnglishLikeParser)


def test_registry_raises_lookup_error_for_unregistered_parser() -> None:
    registry = ParserRegistry()

    with pytest.raises(LookupError, match="No parser registered for bank_id=unknown_bank, language=Language.SPANISH"):
        registry.create("unknown_bank", Language.SPANISH)


def test_registry_list_parsers() -> None:
    registry = ParserRegistry()
    assert registry.list_parsers() == []

    registry.register(ExampleBankEnglishLikeParser)
    assert registry.list_parsers() == [("example_bank", Language.SPANISH)]


def test_register_builtin_parsers_populates_registry() -> None:
    from bank_parser.parsers import register_builtin_parsers

    registry = register_builtin_parsers()
    parsers = registry.list_parsers()

    assert ("example_bank", Language.SPANISH) in parsers
    assert isinstance(registry.create("example_bank", Language.SPANISH), ExampleBankEnglishLikeParser)

