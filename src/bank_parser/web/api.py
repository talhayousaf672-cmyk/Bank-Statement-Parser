"""FastAPI web adapter — exposes the shared core as a REST API."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from bank_parser.core.models import Language, ParseResult
from bank_parser.core.pdf_extractor import PdfExtractionError, extract_text_blocks
from bank_parser.core.text_normalizer import normalize_text
from bank_parser.export.excel_writer import write_excel
from bank_parser.parsers import register_builtin_parsers
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.review_queue import ReviewQueueItem, build_review_queue
from bank_parser.validation.summary import ValidationSummary, summarize_validation
from bank_parser.ai.fallback_extractor import extract_from_markdown, extract_with_fallback
from bank_parser.core.grid_cropper import get_cropped_regions
from bank_parser.core.spatial_extractor import extract_markdown

app = FastAPI(
    title="Bank Statement Parser API",
    description=(
        "Parse, validate, and export multilingual bank statement PDFs. "
        "All AI output is gated through validation before export."
    ),
    version="1.0.0",
)

# CORS — allow the frontend (same origin or dev localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict to specific domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(exist_ok=True)
if (_STATIC_DIR / "index.html").exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

_registry = register_builtin_parsers()

# In-memory store: statement_id -> ParseResult (replace with Supabase in Phase 5B)
_statement_store: dict[str, ParseResult] = {}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root():
    """Serve the frontend."""
    html_path = _STATIC_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<p>Frontend not found. Run the API at <a href='/docs'>/docs</a>.</p>")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


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
) -> dict:
    """Upload a PDF and parse it. Returns a statement_id for downstream calls."""
    # Find the parser for this bank_id, ignoring input language for now
    parser = None
    for b, l in _registry.list_parsers():
        if b == bank_id:
            parser = _registry.create(bank_id, l)
            break

    if not parser:
        available = list(set([b for b, l in _registry.list_parsers()]))
        raise HTTPException(
            status_code=422,
            detail=f"No parser for bank_id='{bank_id}'. Available: {available}",
        )

    # Security: enforce PDF content type and max file size (10 MB)
    _MAX_UPLOAD_BYTES = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum upload size is 10 MB.")
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted.")

    # Save upload to temp file
    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    # Extract text blocks (for legacy pipeline fallback)
    try:
        blocks = extract_text_blocks(tmp_path)
    except PdfExtractionError as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"PDF extraction failed: {exc}")

    # -----------------------------------------------------------------------
    # New Spatial Pipeline: Grid Crop → Spatial Engine → AI (Markdown path)
    # -----------------------------------------------------------------------
    markdown_table: str = ""
    try:
        regions = get_cropped_regions(tmp_path)
        markdown_table = extract_markdown(tmp_path, regions)
    except Exception:
        pass  # Spatial engine unavailable or failed — fall through to legacy path
    finally:
        tmp_path.unlink(missing_ok=True)  # PDF no longer needed after extraction

    if markdown_table:
        # New path: clean Markdown table → AI structures it
        try:
            fallback_gate = extract_from_markdown(
                markdown_table,
                bank_id,
                language=Language.SPANISH,
            )
            if fallback_gate:
                parse_result = fallback_gate.parse_result
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
                    "pipeline": "spatial",
                }
        except Exception:
            pass  # Spatial+AI path failed — fall through to legacy

    # -----------------------------------------------------------------------
    # Legacy Pipeline: Raw Text → Regex Parser → AI Fallback
    # -----------------------------------------------------------------------
    normalized = normalize_text("\n".join(b.text for b in blocks))
    parse_result = parser.parse(normalized)
    parse_result = validate_parse_result(parse_result)

    # Try AI Fallback if needed
    try:
        fallback_gate = extract_with_fallback(
            normalized,
            bank_id,
            language=Language.SPANISH,
            existing_result=parse_result,
        )
        if fallback_gate:
            parse_result = fallback_gate.parse_result
    except Exception as exc:
        import traceback
        trace_str = "".join(traceback.format_exception(None, exc, exc.__traceback__))
        raise HTTPException(
            status_code=500,
            detail=f"AI Fallback failed: {str(exc)}\n\nTraceback:\n{trace_str}"
        )
    statement_id = str(uuid.uuid4())
    _statement_store[statement_id] = parse_result

    summary = summarize_validation(parse_result)
    return {
        "statement_id": statement_id,
        "transaction_count": len(parse_result.transactions),
        "export_readiness": summary.export_readiness.value,
        "warning_rows": summary.warning_rows,
        "error_rows": summary.error_rows,
        "pipeline": "legacy",
    }


@app.get("/api/validate/{statement_id}")
def validate_statement(statement_id: str) -> ValidationSummary:
    """Return the validation summary for a parsed statement."""
    result = _get_statement(statement_id)
    return summarize_validation(result)


@app.post("/api/export/{statement_id}")
def export_statement(
    statement_id: str,
    background_tasks: BackgroundTasks,
    language: str = "en",
) -> FileResponse:
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
    # Security: delete temp file after response is sent
    background_tasks.add_task(out_path.unlink, missing_ok=True)
    return FileResponse(
        path=str(out_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@app.get("/api/transactions/{statement_id}")
def get_transactions(statement_id: str) -> dict:
    """Return all parsed transactions for a statement."""
    result = _get_statement(statement_id)
    return {
        "statement_id": statement_id,
        "metadata": result.metadata.model_dump(mode="json"),
        "transactions": [
            {
                "row": i + 1,
                "date": str(tx.transaction_date) if tx.transaction_date else None,
                "description": tx.description,
                "reference": tx.reference,
                "debit": str(tx.debit) if tx.debit is not None else None,
                "credit": str(tx.credit) if tx.credit is not None else None,
                "balance": str(tx.balance) if tx.balance is not None else None,
                "currency": tx.currency,
                "confidence": tx.confidence,
                "flags": len(tx.review_flags),
            }
            for i, tx in enumerate(result.transactions)
        ],
    }


@app.post("/api/enrich/{statement_id}")
def enrich_statement(statement_id: str, language: str = "en") -> dict:
    """Enrich transaction descriptions using Groq/Llama."""
    result = _get_statement(statement_id)
    
    try:
        lang = Language(language)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unsupported language: {language}")

    try:
        from bank_parser.ai.enrichment import enrich_descriptions
        enriched_result = enrich_descriptions(result, lang)
        _statement_store[statement_id] = enriched_result
        return {"status": "enriched", "transaction_count": len(enriched_result.transactions)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))



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
