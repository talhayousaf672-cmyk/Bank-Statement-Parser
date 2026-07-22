"""AI fallback extraction using Groq/Llama-70B.

When a deterministic parser returns zero transactions or all rows have ERROR flags,
Llama-3.3-70B attempts to extract transactions from the normalized text.

ALL output is gated through validate_ai_fallback_result() — non-negotiable.
Uses the 70B model because structured JSON extraction requires high accuracy.
"""

from __future__ import annotations

import json

from bank_parser.ai.fallback_gate import AiFallbackGateResult, validate_ai_fallback_result
from bank_parser.ai.groq_client import DEFAULT_MODEL, get_groq_client
from bank_parser.core.models import Language, ParseResult, ReviewSeverity

from pydantic import BaseModel, Field

_SCHEMA_MAPPER_PROMPT = """\
You are a precise financial data schema mapper.
Below is the header and first few rows of a bank statement Markdown table.
Your job is to identify which column index (0-indexed) corresponds to which field in our schema.

Schema fields:
- transaction_date
- value_date
- description (or particulars)
- reference (or cheque number)
- debit (withdrawals, out)
- credit (deposits, in)
- balance

Return ONLY a valid JSON object mapping the field name to the integer column index.
If a field is NOT present in the table, map it to null.
Do not guess. Do not include markdown fences.

Schema:
{{
  "transaction_date": <int or null>,
  "value_date": <int or null>,
  "description": <int or null>,
  "reference": <int or null>,
  "debit": <int or null>,
  "credit": <int or null>,
  "balance": <int or null>
}}

Markdown table (first 5 rows):
{markdown_table}
"""

class ColumnMap(BaseModel):
    transaction_date: int | None = None
    value_date: int | None = None
    description: int | None = None
    reference: int | None = None
    debit: int | None = None
    credit: int | None = None
    balance: int | None = None



class FallbackUnavailableError(RuntimeError):
    """Raised when no GROQ_API_KEY is configured."""


def _is_fallback_needed(parse_result: ParseResult) -> bool:
    if len(parse_result.transactions) == 0:
        return True
    error_count = sum(
        1 for tx in parse_result.transactions
        if any(f.severity == ReviewSeverity.ERROR for f in tx.review_flags)
    )
    return error_count == len(parse_result.transactions)


def extract_with_fallback(
    normalized_text: str,
    bank_id: str,
    language: Language,
    api_key: str | None = None,
    *,
    force: bool = False,
    existing_result: ParseResult | None = None,
) -> AiFallbackGateResult | None:
    """Attempt AI fallback extraction when deterministic parsing fails.

    Legacy path: accepts raw normalized text.
    Prefer extract_from_markdown() when the spatial engine is available.

    Args:
        normalized_text: Statement text already through text_normalizer.
        bank_id: Bank identifier for metadata.
        language: Output language for Excel headers.
        api_key: Groq API key. Falls back to GROQ_API_KEY env var.
        force: If True, run fallback even if not strictly needed.
        existing_result: Existing ParseResult to check if fallback is needed.

    Returns:
        AiFallbackGateResult if fallback ran, None if not needed and force=False.
    """
    if existing_result is not None and not force and not _is_fallback_needed(existing_result):
        return None

    try:
        client = get_groq_client(api_key)
    except ValueError as exc:
        raise FallbackUnavailableError(str(exc)) from exc

    # Fallback to the original raw extraction prompt for the legacy pipeline
    legacy_prompt = """\
You are a precise financial data extractor.
Return ONLY a valid JSON object — no prose, no markdown fences.

Schema:
{{  
  "metadata": {{
    "bank_id": "{bank_id}",
    "language": "{language}",
    "account_number": null,
    "account_holder": null,
    "currency": null,
    "statement_period_start": null,
    "statement_period_end": null,
    "parser_version": "0.2.0"
  }},
  "transactions": [],
  "review_flags": []
}}

Statement text:
{text}
"""
    prompt = legacy_prompt.format(
        bank_id=bank_id,
        language=language.value,
        text=f"```\n{normalized_text[:5000]}\n```",
    )

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0.0,  # deterministic for JSON extraction
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Llama returned invalid JSON: {exc}\n\nRaw response:\n{raw[:500]}") from exc

    parse_result = ParseResult.model_validate(data)
    return validate_ai_fallback_result(parse_result)


def extract_from_markdown(
    markdown_table: str,
    bank_id: str,
    language: Language,
    api_key: str | None = None,
) -> AiFallbackGateResult:
    """Extract transactions from a pre-structured Markdown table (new spatial pipeline).

    This is the primary extraction path when the spatial engine (Camelot/Docling)
    has already isolated the transaction table as clean Markdown. The AI's job
    is purely semantic: map the Markdown rows to the Pydantic JSON schema.

    Args:
        markdown_table: Clean Markdown table from spatial_extractor.
        bank_id: Bank identifier for metadata.
        language: Output language for Excel headers.
        api_key: Groq API key. Falls back to GROQ_API_KEY env var.

    Returns:
        AiFallbackGateResult with extracted and validated transactions.
    """
    # 1. Ask AI to map the column headers (Zero-Shot Schema Mapping)
    # Only send the first 5 rows to the LLM to avoid token limits
    table_lines = markdown_table.strip().split("\n")
    sample_table = "\n".join(table_lines[:6])

    prompt = _SCHEMA_MAPPER_PROMPT.format(markdown_table=sample_table)

    try:
        client = get_groq_client(api_key)
    except ValueError as exc:
        raise FallbackUnavailableError(str(exc)) from exc

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    raw = raw.strip()

    try:
        data = json.loads(raw)
        col_map = ColumnMap.model_validate(data)
    except Exception as exc:
        raise ValueError(f"AI Schema Mapper returned invalid JSON/Schema: {exc}\n\nRaw:\n{raw}") from exc

    # 2. Deterministically parse ALL rows using the AI's column map
    from bank_parser.core.models import StatementMetadata, Transaction
    from decimal import Decimal
    from datetime import date
    import re

    def _parse_date(d_str: str) -> date | None:
        if not d_str: return None
        # Basic YYYY-MM-DD or DD-MM-YYYY parser
        m = re.search(r"(\d{2,4})[-/](\d{1,2})[-/](\d{2,4})", d_str)
        if not m: return None
        p1, p2, p3 = m.groups()
        if len(p1) == 4:
            return date(int(p1), int(p2), int(p3))
        elif len(p3) == 4:
            return date(int(p3), int(p2), int(p1))
        # Handle DD-MM-YY (assume 2000+)
        if len(p3) == 2:
            return date(2000 + int(p3), int(p2), int(p1))
        return None

    def _parse_decimal(val: str) -> Decimal | None:
        val = val.replace(",", "").strip()
        if not val or val == "-": return None
        # Find the first number or negative sign
        m = re.search(r"-?\d+(?:\.\d+)?", val)
        if not m: return None
        try:
            return Decimal(m.group(0))
        except:
            return None

    transactions = []
    
    # Skip header and separator rows (usually first 2 lines)
    data_lines = [l for l in table_lines if l.strip().startswith("|") and "---" not in l]
    if len(data_lines) > 0 and "date" in data_lines[0].lower():
        data_lines = data_lines[1:]

    for line in data_lines:
        cells = [c.strip() for c in line.split("|")[1:-1]]  # remove leading/trailing empty cells from pipes
        if not cells or all(not c for c in cells):
            continue

        def _get_cell(idx: int | None) -> str:
            if idx is None or idx < 0 or idx >= len(cells): return ""
            return cells[idx]

        desc = _get_cell(col_map.description)
        if not desc:
            continue  # Skip rows without description

        tx_date_str = _get_cell(col_map.transaction_date)
        val_date_str = _get_cell(col_map.value_date)
        ref_str = _get_cell(col_map.reference)
        debit_str = _get_cell(col_map.debit)
        credit_str = _get_cell(col_map.credit)
        balance_str = _get_cell(col_map.balance)

        debit = _parse_decimal(debit_str)
        credit = _parse_decimal(credit_str)
        balance = _parse_decimal(balance_str)

        amount = Decimal("0.0")
        if debit is not None:
            amount = -debit
        elif credit is not None:
            amount = credit

        # If both are null but we expect a transaction, maybe it's just a description overflow row
        if debit is None and credit is None and balance is None and not tx_date_str:
            # Append to previous transaction's description
            if transactions:
                transactions[-1].description += " " + desc
            continue

        tx = Transaction(
            transaction_date=_parse_date(tx_date_str),
            value_date=_parse_date(val_date_str),
            description=desc,
            reference=ref_str if ref_str else None,
            debit=debit,
            credit=credit,
            amount=amount,
            balance=balance,
        )
        transactions.append(tx)

    metadata = StatementMetadata(
        bank_id=bank_id,
        language=language,
        parser_version="0.3.0"
    )

    parse_result = ParseResult(metadata=metadata, transactions=transactions)
    return validate_ai_fallback_result(parse_result)

