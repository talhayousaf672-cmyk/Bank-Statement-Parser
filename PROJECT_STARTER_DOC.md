# Bank Statement Parser - Project Starter Doc

## Wholemap

Build one shared parsing core that can power both a desktop app and a web app.

The core job is to extract transactions from PDF bank statements, normalize them into one canonical 16-field model, validate the math, and export clean Excel files in the selected language. The deterministic parser is the source of truth. AI is only an assistant for onboarding new banks, fallback extraction after parser failure, and optional description enrichment.

### Product Tracks

| Track | Purpose | Main Stack |
|---|---|---|
| Shared Core | PDF extraction, RTL/LTR normalization, parser factory, validation, export | Python, PyMuPDF, Pydantic, openpyxl |
| Desktop App | Fully local Windows tool for sensitive PDFs | PySide6, SQLite, PyInstaller |
| Web App | Multi-user upload, review, export workflow | FastAPI, Supabase, React, Mantine |

### Team Ownership

| Person | Role | Primary Areas |
|---|---|---|
| Mohsin | Dev A - Parsing Engine Lead | PDF extraction, language ordering, parser interface, bank-specific parsers, AI onboarding assist |
| Talha | Dev B - Validation & Data Lead | Reconciliation, confidence scoring, QA harness, review queue schemas, Supabase/Postgres models |
| Umer | Dev C - App & Localization Lead | Excel export, translated headers, desktop UI, web UI, packaging/deployment, AI enrichment integration |

### Architecture Map

```text
PDF statement
  -> pdf_extractor
  -> text normalizer
  -> parser factory
  -> bank parser
  -> canonical statement model
  -> reconciliation validator
  -> review queue if needed
  -> Excel export
  -> desktop UI or web API
```

### Repository Map

```text
bank-statement-parser/
  docs/
    prompts/
    roadmap.md
  src/
    bank_parser/
      ai/
      core/
      desktop/
      export/
      parsers/
      validation/
      web/
  tests/
    fixtures/
    unit/
    integration/
  scripts/
```

### Canonical Data Goal

Every parser must output the same internal model, regardless of bank, language, or app.

Statement-level fields:

| Field | Purpose |
|---|---|
| bank_id | Bank/parser identifier, for example hbl, meezan, example_bank |
| language | Statement language: ar, ur, ru, es, hi |
| account_number | Customer account number, if available |
| account_holder | Account holder/customer name, if available |
| currency | Main statement currency, for example PKR, SAR, USD |
| statement_period_start | Start date of the statement period |
| statement_period_end | End date of the statement period |
| parser_version | Version of the parser that produced the result |

Transaction-level fields:

| Field | Purpose |
|---|---|
| transaction_date | Date the transaction happened |
| value_date | Date the bank applies value/settlement, if shown |
| description | Transaction description/narration |
| reference | Cheque number, transfer ID, transaction ID, or other reference |
| debit | Money out; null if not a debit row |
| credit | Money in; null if not a credit row |
| amount | Signed transaction amount; debit is negative, credit is positive |
| balance | Running balance after the transaction |
| currency | Transaction currency if shown; otherwise inherits statement currency |
| confidence | Parser confidence for the row, from 0.0 to 1.0 |
| review_flags | Issues like missing_balance, unclear_date, ambiguous_amount |

### Phase Plan

| Phase | Weeks | Owner | Output |
|---|---:|---|---|
| 0. Foundation | 1-2 | All | Repo setup, canonical schema, parser interface, fixtures, initial CI |
| 1. Extraction | 2-5 | Mohsin | PDF extraction, RTL/LTR normalization, pilot bank parsers |
| 2. Validation | 3-6 | Talha | Reconciliation engine, confidence scoring, test harness |
| 3. Export & Localization | 5-7 | Umer | Excel writer, translated headers, RTL sheet handling |
| 4. Multi-Bank Expansion | 6-12 | Mohsin + Umer | Additional bank parser classes |
| 4.5. AI Assist | 9-13 | Mohsin + Umer | Onboarding draft, fallback extraction, enrichment |
| 5A. Desktop | 8-11 | Umer | PySide6 app, SQLite review queue, packaged exe |
| 5B. Web | 8-13 | Umer + Talha | FastAPI, Supabase, React UI, async jobs |
| 6. Hardening | 10-14 | Talha + All | Accuracy pass, edge cases, load/security checks |
| 7. Launch | 14+ | All | v1 release and bank expansion backlog |

### Definition of Done

- Parser output conforms to the canonical Pydantic models.
- Reconciliation passes or the statement is flagged for review.
- Excel export preserves 16 required fields and selected-language headers.
- Tests include at least one fixture per supported bank/language combination.
- AI output never bypasses validation.
- Web uploads use short-lived storage and tenant-isolated data.

## Initial IDE Prompts

Use these prompts in Cursor, Windsurf, VS Code Copilot Chat, or any coding IDE. Each person gets one broad role prompt instead of separate prompts for every feature. Start with the combined team prompt once, then each person should use their own prompt in a separate IDE chat.

### Combined Team Prompt - Project Orientation

```text
You are helping build a multilingual bank statement PDF parser. Read PROJECT_STARTER_DOC.md, docs/roadmap.md, pyproject.toml, README.md, and the src/bank_parser package. Understand the wholemap: one shared Python core powers both desktop and web apps. The deterministic parser is the source of truth; AI can only assist onboarding, fallback extraction, and description enrichment after validation boundaries are respected.

Team roles:
- Mohsin owns the parsing engine: PDF extraction, RTL/LTR text handling, parser factory, bank-specific parsers, and AI onboarding assist boundaries.
- Talha owns validation and data: reconciliation, confidence scoring, review flags, QA harness, SQLite/Supabase review data models, and security checks.
- Umer owns apps and localization: Excel export, translated headers, RTL workbook behavior, desktop UI, web UI, packaging, deployment, and AI enrichment integration.

First, summarize the architecture and current skeleton. Then propose a short Phase 0 implementation order that avoids role conflicts. Do not make code changes until the team agrees on the order.
```

### Mohsin - Parsing Engine

```text
You are Mohsin, the Parsing Engine Lead for this bank statement parser. Work only in the shared parsing core unless a test requires a small supporting change.

Read PROJECT_STARTER_DOC.md, docs/roadmap.md, src/bank_parser/core, and src/bank_parser/parsers. Your responsibility is to make the parser engine ready for real bank layouts. That includes PDF text extraction contracts, PyMuPDF extraction, RTL/LTR normalization for Arabic, Urdu, Russian, Spanish, and Hindi, BaseBankParser, parser factory registration, example parser behavior, bank onboarding boundaries, and parser-focused tests.

Keep the parser deterministic. Do not let AI write accepted output. Every parser must output the canonical Pydantic models and leave validation decisions to Talha's validation layer.

Start by checking the current skeleton, then implement the next safest parsing-engine step with focused tests. Keep changes scoped to parsing engine files.
```

### Talha - Validation And Data

```text
You are Talha, the Validation and Data Lead for this bank statement parser. Work mainly in validation, review data, QA harness, and security/data-boundary files.

Read PROJECT_STARTER_DOC.md, docs/roadmap.md, src/bank_parser/core/models.py, and src/bank_parser/validation. Your responsibility is to make parsed output trustworthy. That includes balance reconciliation, decimal tolerance rules, confidence scoring, structured review flags, fixture-based accuracy tests, review queue schemas for desktop SQLite and web Supabase/Postgres, and web data-handling/security checklists.

Validation must never silently accept uncertain rows. Normal failures should produce structured review flags that Umer can display in desktop and web screens. AI fallback data must pass the same reconciliation path before export.

Start by checking the current skeleton, then implement the next safest validation/data step with focused tests. Keep changes scoped to validation and data boundaries.
```

### Umer - Apps And Localization

```text
You are Umer, the App and Localization Lead for this bank statement parser. Work mainly in export, localization, desktop UI, web UI, packaging, deployment, and app integration boundaries.

Read PROJECT_STARTER_DOC.md, docs/roadmap.md, src/bank_parser/export, src/bank_parser/desktop, and src/bank_parser/web. Your responsibility is to turn validated parse results into usable app workflows. That includes openpyxl Excel export, the 16-field translated header sets, RTL sheet direction for Arabic/Urdu, PySide6 desktop shell, FastAPI/React web shell, download/export flows, packaging/deployment setup, and optional AI description enrichment UI.

Keep UI code thin. Do not duplicate parsing or validation logic in app layers. Desktop and web should call shared services and display review flags produced by Talha's validation layer.

Start by checking the current skeleton, then implement the next safest app/localization step with focused tests or smoke checks. Keep changes scoped to export and app adapter files.
```

## First Sprint Backlog

| Task | Owner | Priority |
|---|---|---|
| Finalize canonical Pydantic models | All | P0 |
| Implement parser interface and registry | Mohsin | P0 |
| Implement reconciliation validator | Talha | P0 |
| Implement Excel header map and writer skeleton | Umer | P0 |
| Add example parser and test fixture | Mohsin | P1 |
| Add CLI smoke command | Mohsin + Talha | P1 |
| Add desktop/web placeholder adapters | Umer | P1 |
| Draft security checklist | Talha + Umer | P2 |

## Working Rules

- Shared core must stay independent of desktop and web frameworks.
- Parser classes can be bank-specific, but their output must be canonical.
- Validation failures produce review flags, not hidden corrections.
- AI is opt-in, reviewable, and always downstream of deterministic checks.
- Tests should grow with every supported bank and language.
