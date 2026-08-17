"""Compatibility parser used by registry tests and starter examples."""

from __future__ import annotations

from bank_parser.parsers.generic_english import GenericEnglishBankParser


class ExampleBankEnglishLikeParser(GenericEnglishBankParser):
    bank_id = "example_bank"
