# Bank Parser Onboarding Guide & Boundaries

This guide documents the strict rules, naming conventions, fixture contracts, and AI assist boundaries for onboarding new bank statement parsers into the parsing engine core.

---

## 1. Bank Onboarding Checklist

A bank parser candidate moves through two formal states: **Onboarding** and **Supported**.

### Onboarding State Requirements
- [x] Unique `bank_id` is assigned (lowercase, snake_case).
- [x] Input statement language is confirmed (v1 input is English).
- [x] Selected target export language is specified.
- [x] Sample raw or normalized text is extracted from a sample PDF.
- [x] Expected `ParseResult` JSON is defined matching canonical schema fields.

### Supported State Requirements
- [x] Parser implementation class exists under `src/bank_parser/parsers/<bank_id>.py`.
- [x] Class inherits from `BaseBankParser` and implements `.parse(normalized_text)`.
- [x] Parser class is registered in `register_builtin_parsers()` within `src/bank_parser/parsers/__init__.py`.
- [x] Fixture files exist under `tests/fixtures/parsers/<bank_id>/<language>/`.
- [x] Unit/fixture test exists under `tests/unit/test_<bank_id>_parser.py`.
- [x] Parser output conforms strictly to canonical Pydantic models.
- [x] Parser emits parser-side `ReviewFlag`s for ambiguous rows without attempting balance reconciliation.

---

## 2. Required Fixture Structure

Every supported bank parser must have a dedicated fixture directory:

```text
tests/
  fixtures/
    parsers/
      <bank_id>/
        <language>/
          statement_text.txt
          expected_parse.json
```

### Fixture Contracts
* **`statement_text.txt`**: Normalized text extracted from representative statement PDFs.
* **`expected_parse.json`**: Complete canonical `ParseResult` JSON payload matching the expected output.

---

## 3. Parser Naming Conventions

* **Module Filename**: `src/bank_parser/parsers/<bank_id>.py` (all lowercase, snake_case).
* **Class Name**: `<BankName>BankParser` (PascalCase, ending with `BankParser`).
* **Bank ID Attribute**: `bank_id = "<bank_id>"` matching the module filename.

Example:
```python
# src/bank_parser/parsers/chase_bank.py
class ChaseBankParser(BaseBankParser):
    bank_id = "chase_bank"
    language = Language.SPANISH
```

---

## 4. Bank Layout Versioning Rules

When a bank changes its PDF statement layout:

1. **Minor Layout Shifts** (same columns, altered spacing/headers):
   * Update the existing parser class regex patterns.
   * Ensure all existing fixture tests continue to pass.
2. **Major Layout Breaks** (column order changes, date format changes, section restructure):
   * Do NOT break backward compatibility of the existing parser if older statements are still processed.
   * Create a new versioned bank parser: `bank_id = "<bank_id>_v2"` and class `<BankName>V2BankParser`.
   * Add a new fixture directory: `tests/fixtures/parsers/<bank_id>_v2/<language>/`.

---

## 5. Decision Matrix: Update vs. New Parser Class

| Scenario | Action |
|---|---|
| Minor header text change or extra whitespace | **Update** existing parser regexes |
| Additional non-critical header field | **Update** existing parser class |
| Date format changed (e.g. `YYYY-MM-DD` to `DD/MM/YYYY`) in same bank layout | **Update** date parsing helper in existing class |
| Completely restructured column order or multi-column layout shift | **Create** new `<bank_id>_v2` parser class |
| Completely different institution or brand subsidiary | **Create** new `<bank_id>` parser class |

---

## 6. AI Assist Boundary Specification

AI capabilities (e.g., Claude API / LLM integrations) must adhere to the following strict boundaries:

1. **Draft Generation Only**:
   * AI can assist developers in drafting initial regex patterns or generating boilerplate parser classes during onboarding.
2. **Fallback Candidate Extraction**:
   * If a deterministic parser fails (`unsupported_layout`), AI may propose candidate text blocks for human review.
3. **No Direct Unvalidated Output**:
   * AI output **MUST NEVER** bypass the deterministic parser schema validation or Umer's balance reconciliation engine.
   * All transaction data must pass canonical Pydantic model validation and reconciliation before final export or database persistence.
