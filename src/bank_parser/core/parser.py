"""Parser contracts and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod

from bank_parser.core.models import Language, ParseResult


class BaseBankParser(ABC):
    bank_id: str
    language: Language

    @abstractmethod
    def parse(self, normalized_text: str) -> ParseResult:
        """Parse normalized statement text into the canonical model."""


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[tuple[str, Language], type[BaseBankParser]] = {}

    def register(self, parser_cls: type[BaseBankParser]) -> None:
        key = (parser_cls.bank_id, parser_cls.language)
        self._parsers[key] = parser_cls

    def create(self, bank_id: str, language: Language) -> BaseBankParser:
        key = (bank_id, language)
        try:
            parser_cls = self._parsers[key]
        except KeyError as exc:
            raise LookupError(f"No parser registered for bank_id={bank_id}, language={language}") from exc
        return parser_cls()
