"""Text normalization for parser input."""

from __future__ import annotations

import re
import unicodedata


DEFAULT_SOURCE_LANGUAGE = "en"
FUTURE_MULTILINGUAL_SOURCE_LANGUAGES = {"ar", "ur", "ru", "es", "hi"}

_HORIZONTAL_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_PAGE_NUMBER_RE = re.compile(r"^Page\s+\d+(\s+of\s+\d+)?$", re.IGNORECASE)


def normalize_text(text: str, source_language: str = DEFAULT_SOURCE_LANGUAGE) -> str:
    """Normalize extracted statement text before deterministic parsing.

    The v1 parser input language is English. Selected export language is handled
    downstream and should not be passed here as a parser input language.
    """
    if source_language != DEFAULT_SOURCE_LANGUAGE:
        if source_language in FUTURE_MULTILINGUAL_SOURCE_LANGUAGES:
            return _normalize_basic_text(text)
        raise ValueError(f"Unsupported parser input language: {source_language}")

    return _normalize_basic_text(text)


def _normalize_basic_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    lines = []
    for line in normalized.split("\n"):
        compacted = _HORIZONTAL_WHITESPACE_RE.sub(" ", line).strip()
        if compacted and not _PAGE_NUMBER_RE.match(compacted):
            lines.append(compacted)

    return "\n".join(lines)

