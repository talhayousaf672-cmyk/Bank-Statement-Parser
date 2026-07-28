"""Background workers for the PySide6 desktop app."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from bank_parser.ai.enrichment import EnrichmentUnavailableError, enrich_descriptions
from bank_parser.ai.fallback_extractor import FallbackUnavailableError, extract_with_fallback
from bank_parser.core.bank_detector import detect_bank_id_from_header
from bank_parser.core.models import Language, ParseResult
from bank_parser.core.pdf_extractor import PdfExtractionError, extract_text_blocks
from bank_parser.core.text_normalizer import normalize_text
from bank_parser.parsers import register_builtin_parsers
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.summary import ValidationSummary, summarize_validation

_REGISTRY = register_builtin_parsers()
_PARSER_LANGUAGE = Language.SPANISH


class ParseWorker(QThread):
    """Extract, parse, and validate a PDF without blocking the UI."""

    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, pdf_path: Path, selected_bank_id: str) -> None:
        super().__init__()
        self._pdf_path = pdf_path
        self._selected_bank_id = selected_bank_id

    def run(self) -> None:
        try:
            blocks = extract_text_blocks(self._pdf_path)
        except PdfExtractionError as exc:
            self.error.emit(str(exc))
            return

        normalized = normalize_text("\n".join(block.text for block in blocks))
        bank_id = _resolve_bank_id(self._selected_bank_id, normalized)

        try:
            parser = _REGISTRY.create(bank_id, _PARSER_LANGUAGE)
        except LookupError as exc:
            self.error.emit(str(exc))
            return

        try:
            result = parser.parse(normalized)
            result = validate_parse_result(result)
            result = _apply_fallback_if_needed(normalized, bank_id, result)
            summary = summarize_validation(result)
        except Exception as exc:
            self.error.emit(str(exc))
            return

        self.finished.emit(result, summary)


class EnrichWorker(QThread):
    """Enrich transaction descriptions without blocking the UI."""

    finished = Signal(object)
    error = Signal(str)

    def __init__(self, parse_result: ParseResult, language: Language) -> None:
        super().__init__()
        self._parse_result = parse_result
        self._language = language if isinstance(language, Language) else Language(str(language))

    def run(self) -> None:
        try:
            enriched = enrich_descriptions(self._parse_result, self._language)
        except EnrichmentUnavailableError as exc:
            self.error.emit(str(exc))
            return
        except Exception as exc:
            self.error.emit(f"AI enrichment failed: {exc}")
            return

        self.finished.emit(enriched)


def list_bank_ids() -> list[str]:
    return sorted({bank_id for bank_id, _language in _REGISTRY.list_parsers()})


def _resolve_bank_id(selected_bank_id: str, normalized_text: str) -> str:
    detected_bank_id = detect_bank_id_from_header(normalized_text)
    if detected_bank_id:
        return detected_bank_id
    return selected_bank_id


def _apply_fallback_if_needed(
    normalized_text: str,
    bank_id: str,
    result: ParseResult,
) -> ParseResult:
    try:
        fallback_gate = extract_with_fallback(
            normalized_text,
            bank_id,
            language=_PARSER_LANGUAGE,
            existing_result=result,
        )
    except FallbackUnavailableError:
        return result
    except Exception:
        return result

    if fallback_gate is None:
        return result
    return fallback_gate.parse_result
