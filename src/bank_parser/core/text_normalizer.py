"""Language-aware text normalization boundary."""

from __future__ import annotations

import unicodedata

from bank_parser.core.models import Language


RTL_LANGUAGES = {Language.ARABIC, Language.URDU}


def normalize_text(text: str, language: Language) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    if language in RTL_LANGUAGES:
        return normalized
    return normalized
