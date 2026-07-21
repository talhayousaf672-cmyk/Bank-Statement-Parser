"""FastAPI web adapter — exposes the shared core as a REST API."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from bank_parser.core.models import Language, ParseResult
from bank_parser.core.pdf_extractor import PdfExtractionError, extract_text_blocks
from bank_parser.core.text_normalizer import normalize_text
from bank_parser.export.excel_writer import write_excel
from bank_parser.parsers import register_builtin_parsers
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.review_queue import ReviewQueueItem, build_review_queue
from bank_parser.validation.summary import ValidationSummary, summarize_validation

app = FastAPI(
    title="Bank Statement Parser API",
    description=(
        "Parse, validate, and export multilingual bank statement PDFs. "
        "All AI output is gated through validation before export."
    ),
    version="0.1.0",
)

_registry = register_builtin_parsers()

# In-memory store: statement_id -> ParseResult (replace with Supabase in Phase 5B)
_statement_store: dict[str, ParseResult] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/parsers")
def list_parsers() -> dict[str, list[dict]]:
    """List all registered bank parsers."""
    parsers = [
        {"bank_id": bank_id, "language": lang.value}
        for bank_id, lang in _registry.list_parsers()
    ]
    return {"parsers": parsers}


@app.post("/api/parse")
async def parse_statement(
    file: UploadFile = File(...),
    bank_id: str = "generic_english",
    language: str = "en",
) -> dict:
    """Upload a PDF and parse it. Returns a statement_id for downstream calls."""
    # Validate language
    try:
        lang = Language(language)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unsupported language: {language}")

    # Validate bank_id
    try:
        parser = _registry.create(bank_id, lang)
    except LookupError:
        available = [f"{b}/{l.value}" for b, l in _registry.list_parsers()]
        raise HTTPException(
            status_code=422,
            detail=f"No parser for bank_id='{bank_id}', language='{language}'. Available: {available}",
        )

    # Save upload to temp file
    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    # Extract + normalize
    try:
        blocks = extract_text_blocks(tmp_path)
    except PdfExtractionError as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"PDF extraction failed: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)

    normalized = normalize_text("\n".join(b.text for b in blocks))
    parse_result = parser.parse(normalized)

    # Validate and store
    parse_result = validate_parse_result(parse_result)
    statement_id = str(uuid.uuid4())
    _statement_store[statement_id] = parse_result

    summary = summarize_validation(parse_result)
    return {
        "statement_id": statement_id,
        "transaction_count": len(parse_result.transactions),
        "export_readiness": summary.export_readiness.value,
        "warning_rows": summary.warning_rows,
        "error_rows": summary.error_rows,
    }


@app.get("/api/validate/{statement_id}")
def validate_statement(statement_id: str) -> ValidationSummary:
    """Return the validation summary for a parsed statement."""
    result = _get_statement(statement_id)
    return summarize_validation(result)


@app.post("/api/export/{statement_id}")
def export_statement(statement_id: str, language: str = "en") -> FileResponse:
    """Export a validated statement to XLSX. Returns the file as a download."""
    result = _get_statement(statement_id)

    summary = summarize_validation(result)
    if not summary.export_ready:
        raise HTTPException(
            status_code=422,
            detail="Statement has blocking validation errors and cannot be exported.",
        )

    try:
        lang = Language(language)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unsupported language: {language}")

    out_path = Path(tempfile.mktemp(suffix=".xlsx"))
    write_excel(result, out_path, language=lang)

    bank_id = result.metadata.bank_id
    filename = f"{bank_id}_{statement_id[:8]}.xlsx"
    return FileResponse(
        path=str(out_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@app.get("/api/review/{statement_id}")
def get_review_queue(statement_id: str) -> dict:
    """Return all review queue items for a parsed statement."""
    result = _get_statement(statement_id)
    items = build_review_queue(result, statement_id)
    return {
        "statement_id": statement_id,
        "item_count": len(items),
        "items": [item.model_dump() for item in items],
    }


@app.patch("/api/review/{statement_id}/{item_id}")
def update_review_item(
    statement_id: str,
    item_id: str,
    status: str,
    notes: str = "",
) -> dict:
    """Update the status of a review queue item (stub — wire to SQLiteReviewQueueStore for desktop)."""
    _get_statement(statement_id)  # ensure statement exists
    # In the desktop app this calls SQLiteReviewQueueStore.update_status()
    return {
        "statement_id": statement_id,
        "item_id": item_id,
        "updated_status": status,
        "notes": notes,
        "message": "Status updated (in-memory only; connect SQLiteReviewQueueStore for persistence).",
    }


def _get_statement(statement_id: str) -> ParseResult:
    result = _statement_store.get(statement_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Statement not found: {statement_id}")
    return result
