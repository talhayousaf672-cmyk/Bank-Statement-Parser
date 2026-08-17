# Security Checklist

> Phase 6 hardening — reviewed before v1.0.0 launch.

## 1. Input Validation

- [x] **PDF file type check** — `extract_text_blocks()` uses PyMuPDF which will raise `PdfOpenError` on non-PDF bytes. CLI and web API surface this as a 422 error.
- [x] **File path traversal** — all paths go through `Path()` and are never interpolated into shell commands or SQL.
- [ ] **Max file size enforcement** — web API (`api.py`) does NOT currently reject oversized uploads. **Action:** add `UploadFile` size check (`< 10 MB`) before writing to temp file.
- [ ] **File extension whitelist** — web API currently accepts any extension. **Action:** reject if `file.content_type != "application/pdf"`.

## 2. Data Handling / PII

- [x] **No PII in logs** — parsers and validators do not call `print()` or `logging` with transaction data. CLI prints only counts and flag codes.
- [x] **Temp file cleanup** — `extract_text_blocks()` receives a `Path` and does not create temp files. CLI and web API are responsible for cleanup (implemented with `unlink(missing_ok=True)`).
- [ ] **Web API temp XLSX files** — `export_statement()` writes XLSX to `tempfile.mktemp()` and returns a `FileResponse`. The file is NOT deleted after the response. **Action:** use `BackgroundTask` to delete the file after response.
- [x] **No API keys in logs** — `enrichment.py`, `fallback_extractor.py`, and `onboarding_assist.py` never log the `api_key` argument.

## 3. AI Integration

- [x] **Enrichment gated** — `enrich_descriptions()` always calls `validate_ai_fallback_result()`. AI output cannot bypass validation.
- [x] **Fallback gated** — `extract_with_fallback()` always calls `validate_ai_fallback_result()`. AI output cannot bypass validation.
- [x] **Onboarding assist never auto-saves** — `draft_parser_from_sample()` returns a string. Caller must explicitly write to disk.
- [ ] **Claude API rate limiting** — no retry/backoff logic yet. **Action:** wrap API calls in `tenacity` retry with exponential backoff.

## 4. Web API

- [ ] **CORS policy** — FastAPI app does not set `CORSMiddleware`. **Action:** add `CORSMiddleware` with explicit allowed origins before exposing publicly.
- [ ] **Auth / multi-tenant isolation** — in-memory `_statement_store` is global. Any caller can access any `statement_id`. **Action:** scope by session token before Phase 5B launch.
- [x] **Temp statement store** — `_statement_store` is in-memory and resets on restart. This is documented; Supabase persistence is Phase 5B.
- [ ] **Input size limits** — FastAPI does not limit request body size by default. **Action:** configure `uvicorn` with `--limit-concurrency` and add `MAX_UPLOAD_BYTES` guard.

## 5. Dependencies

- [x] **Pinned versions** — `pyproject.toml` uses `>=` lower bounds. For production, consider generating a `requirements.lock` with exact pinned versions.
- [ ] **Dependency audit** — run `pip-audit` or `safety check` before launch to identify known CVEs in pinned packages.

## 6. Release Gate

Before tagging v1.0.0:
- [ ] All items marked `[ ]` above are resolved or explicitly accepted as known risks.
- [ ] `ruff check src/ tests/` passes with zero errors.
- [ ] All 82+ unit tests pass.
- [ ] All integration tests pass.
- [ ] Accuracy report shows 100% fixture pass rate.
