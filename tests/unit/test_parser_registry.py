from bank_parser.core.models import Language
from bank_parser.core.parser import ParserRegistry
from bank_parser.parsers.example_bank import ExampleBankEnglishLikeParser


def test_registry_creates_registered_parser() -> None:
    registry = ParserRegistry()
    registry.register(ExampleBankEnglishLikeParser)

    parser = registry.create("example_bank", Language.SPANISH)

    assert isinstance(parser, ExampleBankEnglishLikeParser)
