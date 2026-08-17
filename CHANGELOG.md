# Changelog

All notable changes to the Bank Statement Parser project.

---

## [1.0.0] — 2026-07-21

### Added

#### Parsing Engine (Mohsin)
- PDF text extraction using PyMuPDF with reading-order preservation
- RTL/LTR text normalization (`normalize_text`)
- Parser interface (`BaseBankParser`) and `ParserRegistry` with duplicate detection
- `GenericEnglishBankParser` — generic English layout parser
- `ChaseBankParser` — Chase Bank (US, pipe-delimited, MM/DD/YYYY)
- `HBLParser` — Habib Bank Limited (Pakistan, pipe-delimited, DD-Mon-YYYY, PKR)
- `UBLParser` — United Bank Limited (Pakistan, pipe-delimited, DD/MM/YYYY, PKR)
- `MeezanBankParser` — Meezan Bank (Pakistan, Islamic bank, pipe-delimited, PKR)
- `WellsFargoParser` — Wells Fargo (US, pipe-delimited, MM/DD/YYYY, USD)
- `BankOfAmericaParser` — Bank of America (US, MM/DD short dates, USD)
- Bank onboarding guide and fixture contract (`docs/bank_onboarding_guide.md`)

#### Validation & Data (Talha)
- Balance reconciliation with configurable tolerance (`reconcile_transactions`)
- Confidence scoring based on review flag severity
- Date validation (period, value date, transaction date)
- Currency validation (ISO codes, mixed-currency detection)
- Account metadata validation
- Validation policy system (`ValidationPolicy`) with flag override support
- `ValidationSummary` with `ExportReadiness` (READY / READY_WITH_WARNINGS / BLOCKED)
- `ReviewQueueItem` model and `build_review_queue()` builder
- `SQLiteReviewQueueStore` — persistent review queue for desktop use
- QA harness (`compare_parse_results`) for fixture-based accuracy testing
- AI fallback gate (`validate_ai_fallback_result`) — all AI output is gated here

#### Export & Localization (Umer)
- 16-field Excel export with `openpyxl` (`write_excel`)
- Translated header maps for 5 languages: Arabic, Urdu, Russian, Spanish, Hindi
- RTL sheet direction for Arabic and Urdu workbooks
- Styled headers (bold, dark blue, white text), frozen pane, auto-sized columns
- Separate "Review Flags" sheet per workbook
- Full CLI pipeline: `bank-parser <pdf> --bank-id <id> --language <code> --output <xlsx>`
- FastAPI web adapter with parse/validate/export/review endpoints
- 10 MB upload limit and temp file cleanup on web API
- PDF content-type enforcement on web API
- PySide6 desktop app skeleton (Phase 5A)
- AI enrichment module with Claude API stub and validation gate
- AI fallback extractor with Claude API stub and validation gate
- AI onboarding assist with Claude API stub (never auto-saves output)

#### Quality & Documentation
- 82+ unit tests, 14+ integration tests across all parsers and export layers
- Integration pipeline tests: fixture → parse → validate → XLSX verification
- Accuracy report script (`scripts/run_accuracy_report.py`)
- Security checklist (`docs/security_checklist.md`)
- Roadmap (`docs/roadmap.md`)

### Supported Banks (v1.0.0)

| Bank | Country | Currency | Layout |
|---|---|---|---|
| `chase_bank` | USA | USD | Pipe-delimited |
| `generic_english` | Any | Any | Generic English |
| `hbl` | Pakistan | PKR | Pipe-delimited |
| `ubl` | Pakistan | PKR | Pipe-delimited |
| `meezan_bank` | Pakistan | PKR | Pipe-delimited |
| `wells_fargo` | USA | USD | Pipe-delimited |
| `bank_of_america` | USA | USD | Short-date tabular |

### Supported Export Languages

Arabic, Urdu, Russian, Spanish, Hindi (RTL enabled for Arabic and Urdu)

### Known Limitations

- AI integrations (enrichment, fallback, onboarding) require a `CLAUDE_API_KEY` — stubs raise `NotImplementedError`.
- Web app frontend (Phase 5B) is not included in v1.0.0.
- Desktop app (Phase 5A) skeleton exists but is not packaged as a standalone `.exe`.
- CORS and auth/multi-tenant isolation are deferred to Phase 5B.

---

## [0.1.0] — 2026-07-01 (Initial)

- Initial repository setup
- Canonical Pydantic models (`ParseResult`, `Transaction`, `StatementMetadata`)
- Validation data workflow (Phase 0)
