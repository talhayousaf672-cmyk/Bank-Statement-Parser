"""Background workers for the PySide6 desktop app."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QThread, Signal

from bank_parser.ai.enrichment import EnrichmentUnavailableError, enrich_descriptions
from bank_parser.ai.fallback_extractor import (
    FallbackUnavailableError,
    extract_from_markdown,
    extract_with_fallback,
)
from bank_parser.core.bank_detector import detect_bank_id_from_header
from bank_parser.core.grid_cropper import get_cropped_regions
from bank_parser.core.models import Language, ParseResult
from bank_parser.core.pdf_extractor import PdfExtractionError, extract_text_blocks
from bank_parser.core.spatial_extractor import extract_markdown
from bank_parser.core.text_normalizer import normalize_text
from bank_parser.parsers import register_builtin_parsers
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.summary import ValidationSummary, summarize_validation

_REGISTRY = register_builtin_parsers()
_PARSER_LANGUAGE = Language.SPANISH


def parse_pdf_statement(
    pdf_path: Path,
    selected_bank_id: str = "generic_english",
    language: Language = _PARSER_LANGUAGE,
) -> tuple[ParseResult, ValidationSummary]:
    """Extract, parse, and validate a PDF statement via spatial and fallback pipelines."""
    # 1. Quick text extraction for bank ID detection and legacy fallback
    try:
        blocks = extract_text_blocks(pdf_path)
        normalized = normalize_text("\n".join(block.text for block in blocks))
        bank_id = _resolve_bank_id(selected_bank_id, normalized)
    except Exception:
        normalized = ""
        bank_id = selected_bank_id

    # 2. Try Spatial Pipeline (Camelot/Docling Grid Cropper -> Clean Markdown Table)
    try:
        regions = get_cropped_regions(pdf_path)
        markdown_table = extract_markdown(pdf_path, regions)
        if markdown_table:
            gate = extract_from_markdown(
                markdown_table,
                bank_id,
                language=language,
            )
            if gate and len(gate.parse_result.transactions) > 0:
                result = validate_parse_result(gate.parse_result)
                summary = summarize_validation(result)
                return result, summary
    except Exception:
        pass  # Fall through to legacy regex parser

    # 3. Fallback to built-in regex parser / legacy extraction
    try:
        parser = _REGISTRY.create(bank_id, language)
    except LookupError as exc:
        raise ValueError(f"No parser available for bank '{bank_id}': {exc}") from exc

    result = parser.parse(normalized)
    result = validate_parse_result(result)
    result = _apply_fallback_if_needed(normalized, bank_id, result)
    summary = summarize_validation(result)
    return result, summary


class ParseWorker(QThread):
    """Extract, parse, and validate a single PDF without blocking the UI."""

    finished = Signal(object, object)
    error = Signal(str)

    def __init__(self, pdf_path: Path, selected_bank_id: str) -> None:
        super().__init__()
        self._pdf_path = pdf_path
        self._selected_bank_id = selected_bank_id

    def run(self) -> None:
        try:
            result, summary = parse_pdf_statement(self._pdf_path, self._selected_bank_id)
            self.finished.emit(result, summary)
        except Exception as exc:
            self.error.emit(str(exc))


class BatchParseWorker(QThread):
    """Parse multiple PDF statements in sequence without blocking the UI."""

    file_started = Signal(object, int, int)  # (Path, current_index, total_count)
    file_finished = Signal(object, object, object)  # (Path, ParseResult, ValidationSummary)
    file_error = Signal(object, str)  # (Path, error_message)
    all_finished = Signal(dict)  # {Path: (ParseResult, ValidationSummary)}

    def __init__(self, pdf_paths: Sequence[Path], selected_bank_id: str) -> None:
        super().__init__()
        self._pdf_paths = list(pdf_paths)
        self._selected_bank_id = selected_bank_id
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def run(self) -> None:
        results: dict[Path, tuple[ParseResult, ValidationSummary]] = {}
        total = len(self._pdf_paths)

        for idx, pdf_path in enumerate(self._pdf_paths):
            if self._is_cancelled:
                break
            self.file_started.emit(pdf_path, idx + 1, total)
            try:
                result, summary = parse_pdf_statement(pdf_path, self._selected_bank_id)
                results[pdf_path] = (result, summary)
                self.file_finished.emit(pdf_path, result, summary)
            except Exception as exc:
                self.file_error.emit(pdf_path, str(exc))

        self.all_finished.emit(results)


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
