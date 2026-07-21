# Mohsin Phase Plan

This is the parsing-engine plan only. Mohsin owns deterministic extraction and parsing up to canonical `ParseResult` output. Validation, review acceptance, Excel export, desktop UI, and web UI stay outside this lane unless a parser test needs a small supporting change.

Current product assumption: input bank statements are English for v1. Multilingual source-PDF parsing may be added later, but selected-language export/localization is the only multilingual requirement for now. Mohsin will build a generic English statement parser first, with bank-specific parsers only when a layout cannot be handled generically.

## Mohsin Role

- [x] Own shared parsing core boundaries.
- [x] Own PDF text extraction contracts.
- [x] Own PyMuPDF extraction behavior.
- [x] Own English text normalization for parser input.
- [x] Own `BaseBankParser` interface.
- [x] Own parser registry/factory behavior.
- [ ] Own built-in parser registration.
- [ ] Own generic English statement parser.
- [ ] Own bank-specific parser overrides only when needed.
- [ ] Own parser onboarding boundaries and checklist.

## Parser Engine Flow

- [ ] Receive PDF path, optional `bank_id`, and output `language`.
- [ ] Extract positioned text blocks from the PDF.
- [ ] Convert extracted blocks into stable page text.
- [x] Normalize English statement text for parser input.
- [ ] Select a bank-specific parser if available.
- [ ] Fall back to the generic English statement parser.
- [ ] Parse deterministic text patterns into canonical Pydantic models.
- [ ] Return `ParseResult` with metadata, transactions, parser version, and parser-level flags.
- [ ] Hand result to Umer's validation layer without accepting or correcting balances.

## Phase 0: Parser Foundation

- [x] Read starter docs and current skeleton.
- [x] Confirm canonical starter models exist.
- [x] Confirm parser interface exists.
- [x] Confirm parser registry exists.
- [x] Confirm example parser exists.
- [x] Lock parser-facing canonical fields with the team.
- [x] Define parser error/review flag contract.
- [x] Define parser fixture structure.
- [x] Define supported bank onboarding checklist.

## Locked Canonical Fields

Statement-level fields:

- [x] `bank_id`
- [x] `language`
- [x] `account_number`
- [x] `account_holder`
- [x] `currency`
- [x] `statement_period_start`
- [x] `statement_period_end`
- [x] `parser_version`

Transaction-level fields:

- [x] `transaction_date`
- [x] `value_date`
- [x] `description`
- [x] `reference`
- [x] `debit`
- [x] `credit`
- [x] `amount`
- [x] `balance`

Parser quality fields:

- [x] `confidence`
- [x] `review_flags`

## Locked Parser-Side Review Flags

These flags belong to Mohsin's parsing layer. They describe extraction or parsing uncertainty only. Umer's validation layer decides final acceptance, warning, or failure.

- [x] `missing_required_field`
- [x] `unclear_date`
- [x] `unclear_amount`
- [x] `unclear_balance`
- [x] `ambiguous_debit_credit`
- [x] `unsupported_layout`
- [x] `partial_page_extraction`
- [x] `scanned_pdf_no_text`
- [x] `parser_low_confidence`

## Locked Parser Fixture Structure

Parser fixtures prove that a bank parser converts deterministic statement text into the canonical output model.

Fixture path:

```text
tests/
  fixtures/
    parsers/
      <bank_id>/
        <language>/
          statement_text.txt
          expected_parse.json
```

Fixture files:

- [x] `statement_text.txt`: normalized or extracted text used as parser input.
- [x] `expected_parse.json`: exact expected canonical `ParseResult` output.

Rules:

- [x] Start with extracted/normalized text fixtures for parser behavior.
- [x] Add PDF fixtures separately for extraction behavior.
- [x] Never use AI-generated accepted output as a fixture expectation.
- [x] Every new parser must include at least one fixture-backed test.
- [x] Fixture expectations must use locked canonical field names.

## Locked Bank Onboarding Checklist

Initial strategy: accept all bank candidates into the onboarding flow, then tighten support rules as real layouts and fixtures expose the strict requirements.

A bank parser can enter onboarding when:

- [x] `bank_id` is chosen.
- [x] Input statement is English.
- [x] Output `language` is chosen for downstream export/localization.
- [x] Sample extracted or normalized statement text is available.
- [x] Expected parser output can be written using canonical fields.

A bank parser becomes supported when:

- [x] Parser class exists under `src/bank_parser/parsers/`.
- [x] Parser is registered or discoverable by the parser factory.
- [x] Fixture exists under `tests/fixtures/parsers/<bank_id>/<language>/`.
- [x] Parser-focused test exists.
- [x] Parser returns canonical `ParseResult`.
- [x] Parser uses deterministic rules only.
- [x] Parser attaches parser-side review flags for unclear text.
- [x] Parser does not run reconciliation.
- [x] Parser does not decide final acceptance.
- [x] Parser does not accept AI output as truth.

## Phase 1: PDF Extraction

- [x] Define `TextBlock` model.
- [x] Implement PyMuPDF extraction adapter.
- [x] Return page numbers and optional bounding boxes.
- [x] Sort extracted blocks deterministically.
- [x] Skip empty text blocks.
- [x] Add generated or committed PDF fixture.
- [x] Add extraction test using a real fixture PDF.
- [x] Add scanned/image-only PDF behavior.
- [x] Add encrypted/corrupt PDF behavior.

## Phase 2: Text Normalization

- [x] Normalize Unicode with `NFKC`.
- [x] Normalize whitespace consistently.
- [x] Preserve numeric values and decimal separators.
- [x] Normalize English statement headers and repeated spacing.
- [x] Preserve original descriptions where possible.
- [x] Keep output language separate from parser input language.
- [x] Defer Arabic/Urdu/Russian/Spanish/Hindi source-PDF normalization until a future multilingual parser phase.
- [x] Add focused tests for English parser input normalization.

## Phase 3: Parser Factory

- [x] Register parser classes by `bank_id` and `language`.
- [x] Create registered parser instances.
- [x] Reject duplicate parser registrations explicitly.
- [x] Add built-in parser registry helper.
- [x] Add list/discovery method for supported parsers.
- [x] Add focused tests for missing and duplicate parsers.


## Phase 4: Generic English Parser

- [x] Keep example parser deterministic.
- [x] Return canonical `ParseResult`.
- [x] Add fixture-backed generic English statement text.
- [x] Parse statement metadata.
- [x] Parse transaction rows.
- [x] Parse debit, credit, amount, balance, currency, dates, description, and reference.
- [x] Add parser-focused tests for the generic fixture.
- [x] Ensure parser does not run reconciliation.


## Phase 5: Bank Parser Overrides

- [x] Start with generic parser for all English bank statements.
- [x] Choose first bank only when generic parser misses a real layout.
- [x] Add raw extracted text fixture.
- [x] Document layout assumptions.
- [x] Implement deterministic override behavior.
- [x] Add regression tests for normal rows.
- [x] Add regression tests for missing balance or unclear rows.
- [x] Return review flags for parser uncertainty only.


## Phase 6: Bank Onboarding Boundary

- [x] Create parser onboarding checklist.
- [x] Define required fixtures for a new bank.
- [x] Define parser naming convention.
- [x] Define bank/layout versioning rule.
- [x] Define when to create a new parser class vs update an existing one.
- [x] Define AI assist boundary: drafts only, never accepted output.


## Phase 7: Hardening

- [x] Add multilingual fixture coverage.
- [x] Add multiline description behavior.
- [x] Add page-break transaction behavior.
- [x] Add repeated header/footer removal strategy.
- [x] Add large statement performance smoke test.
- [x] Add unsupported layout failure behavior.


## Mohsin Discussion Points

- [x] Input PDFs are English for v1; multilingual source parsing may come later.
- [x] Selected output language belongs downstream to localization/export.
- [x] Generic English parser comes first; bank-specific overrides come later only when needed.
- [ ] Should parser fixtures store raw PDF, extracted text, or both?
- [ ] Which parser flags belong in parsing vs validation?
- [ ] How strict should duplicate parser registration be?
