"""Example parser used to prove the registry shape."""

from __future__ import annotations

from bank_parser.core.models import Language, ParseResult, StatementMetadata
from bank_parser.core.parser import BaseBankParser


class ExampleBankEnglishLikeParser(BaseBankParser):
    bank_id = "example_bank"
    language = Language.SPANISH

    def parse(self, normalized_text: str) -> ParseResult:
        return ParseResult(
            metadata=StatementMetadata(bank_id=self.bank_id, language=self.language),
            transactions=[],
        )
