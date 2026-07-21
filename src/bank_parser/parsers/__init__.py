"""Bank-specific parser implementations."""

from __future__ import annotations

from bank_parser.core.parser import ParserRegistry
from bank_parser.parsers.bank_of_america import BankOfAmericaParser
from bank_parser.parsers.chase_bank import ChaseBankParser
from bank_parser.parsers.example_bank import ExampleBankEnglishLikeParser
from bank_parser.parsers.generic_english import GenericEnglishBankParser
from bank_parser.parsers.hbl import HBLParser
from bank_parser.parsers.meezan_bank import MeezanBankParser
from bank_parser.parsers.ubl import UBLParser
from bank_parser.parsers.wells_fargo import WellsFargoParser


def register_builtin_parsers(registry: ParserRegistry | None = None) -> ParserRegistry:
    """Register all built-in parser classes into a ParserRegistry."""
    target_registry = registry if registry is not None else ParserRegistry()
    target_registry.register(ExampleBankEnglishLikeParser)
    target_registry.register(GenericEnglishBankParser)
    target_registry.register(ChaseBankParser)
    target_registry.register(HBLParser)
    target_registry.register(UBLParser)
    target_registry.register(MeezanBankParser)
    target_registry.register(WellsFargoParser)
    target_registry.register(BankOfAmericaParser)
    return target_registry
