"""Bank-specific parser implementations."""

from __future__ import annotations

from bank_parser.core.parser import ParserRegistry
from bank_parser.parsers.chase_bank import ChaseBankParser
from bank_parser.parsers.example_bank import ExampleBankEnglishLikeParser
from bank_parser.parsers.generic_english import GenericEnglishBankParser


def register_builtin_parsers(registry: ParserRegistry | None = None) -> ParserRegistry:
    """Register all built-in parser classes into a ParserRegistry."""
    target_registry = registry if registry is not None else ParserRegistry()
    target_registry.register(ExampleBankEnglishLikeParser)
    target_registry.register(GenericEnglishBankParser)
    target_registry.register(ChaseBankParser)
    return target_registry


