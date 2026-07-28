"""AI fallback extraction using Groq/Llama-70B.

When a deterministic parser returns zero transactions or all rows have ERROR flags,
Llama-3.3-70B attempts to extract transactions from the normalized text.

ALL output is gated through validate_ai_fallback_result() — non-negotiable.
Uses the 70B model because structured JSON extraction requires high accuracy.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

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
- amount (use this INSTEAD of debit/credit ONLY IF they are combined in a single column with +/- signs)
- balance

Return ONLY a valid JSON object mapping the field name to the integer column index.
If a field is NOT present in the table, map it to null.
For the "currency" field, return the 3-letter ISO currency code (e.g., PKR, USD) if you see currency symbols like Rs. or $ in the table. Otherwise return null.
Do not guess. Do not include markdown fences.

Schema:
{{
  "transaction_date": <int or null>,
  "value_date": <int or null>,
  "description": <int or null>,
  "reference": <int or null>,
  "debit": <int or null>,
  "credit": <int or null>,
  "amount": <int or null>,
  "balance": <int or null>,
  "currency": "<3-letter ISO code or null>"
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
    amount: int | None = None
    balance: int | None = None
    currency: str | None = None



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

    parse_result = ParseResult.model_validate(_normalize_legacy_ai_payload(data, bank_id, language))
    return validate_ai_fallback_result(parse_result)


def _normalize_legacy_ai_payload(
    data: dict[str, Any],
    bank_id: str,
    language: Language,
) -> dict[str, Any]:
    """Coerce common AI output aliases into the canonical ParseResult schema."""
    normalized = dict(data)
    metadata = dict(normalized.get("metadata") or {})
    metadata["bank_id"] = bank_id
    metadata["language"] = language.value
    metadata.setdefault("parser_version", "0.2.0")
    metadata["statement_period_start"] = _normalize_legacy_date(
        metadata.get("statement_period_start")
    )
    metadata["statement_period_end"] = _normalize_legacy_date(
        metadata.get("statement_period_end")
    )
    normalized["metadata"] = metadata

    normalized["transactions"] = [
        _normalize_legacy_ai_transaction(tx, metadata)
        for tx in normalized.get("transactions") or []
        if isinstance(tx, dict)
    ]
    normalized.setdefault("review_flags", [])
    return normalized


def _normalize_legacy_ai_transaction(
    tx: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(tx)

    _copy_first_present(normalized, "transaction_date", ("date", "txn_date", "posting_date"))
    _copy_first_present(normalized, "value_date", ("val_date",))
    _copy_first_present(
        normalized,
        "description",
        ("details", "particulars", "narration", "transaction_details", "transaction_description"),
    )
    _copy_first_present(normalized, "reference", ("ref", "cheque_no", "instrument_no"))
    _copy_first_present(normalized, "balance", ("available_balance", "closing_balance", "running_balance"))
    normalized["transaction_date"] = _normalize_legacy_date(normalized.get("transaction_date"))
    normalized["value_date"] = _normalize_legacy_date(normalized.get("value_date"))

    debit = _parse_decimal(normalized.get("debit"))
    credit = _parse_decimal(normalized.get("credit"))
    amount = _parse_decimal(normalized.get("amount"))

    if amount is None:
        if debit is not None:
            amount = -abs(debit)
            normalized["debit"] = abs(debit)
        elif credit is not None:
            amount = abs(credit)
            normalized["credit"] = abs(credit)
        else:
            amount = Decimal("0.00")
    normalized["amount"] = amount

    if debit is None:
        normalized.pop("debit", None)
    if credit is None:
        normalized.pop("credit", None)

    normalized.setdefault("description", "")
    normalized.setdefault("currency", metadata.get("currency"))
    return normalized


def _copy_first_present(target: dict[str, Any], canonical_key: str, aliases: tuple[str, ...]) -> None:
    if target.get(canonical_key) not in (None, ""):
        return
    for alias in aliases:
        value = target.get(alias)
        if value not in (None, ""):
            target[canonical_key] = value
            return


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    cleaned = str(value).replace(",", "").strip()
    if not cleaned or cleaned == "-":
        return None
    is_negative = (
        "-" in cleaned
        or cleaned.startswith("(") and cleaned.endswith(")")
        or cleaned.upper().endswith("DR")
    )
    cleaned = cleaned.strip("()")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        number = Decimal(match.group(0))
    except InvalidOperation:
        return None
    return -number if is_negative else number


def _normalize_legacy_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()

    raw = str(value).strip()
    cleaned = re.sub(r"\s+", " ", raw.replace(",", " ")).upper()
    formats = (
        "%Y-%m-%d",
        "%d/%m/%y",
        "%d/%m/%Y",
        "%d-%m-%y",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%d %b %y",
        "%d %B %y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            pass
    return None


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
    
    try:
        from dateutil.parser import parse as parse_dt
    except ImportError:
        parse_dt = None

    def _parse_date(d_str: str) -> date | None:
        if not d_str: return None
        # Clean up weird markdown artifacts if any
        d_str = re.sub(r'[^a-zA-Z0-9\s:/-]', '', d_str).strip()
        
        # Try dateutil first since it handles "10 Jul 2025" automatically
        if parse_dt:
            try:
                # fuzzy=True ignores random words like "AM/PM" if it can find a date
                return parse_dt(d_str, fuzzy=True).date()
            except Exception:
                pass

        # Fallback to simple regex
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
        # Strip out commas
        val = val.replace(",", "").strip()
        if not val or val == "-": return None
        
        # Check for negative signs anywhere in the string, or accounting parentheses
        is_negative = "-" in val or (val.startswith("(") and val.endswith(")"))
        
        # Extract just the float, ignoring currencies like "Rs."
        m = re.search(r"(\d+(?:\.\d+)?)", val)
        if not m: return None
        try:
            d = Decimal(m.group(1))
            return -d if is_negative else d
        except:
            return None

    transactions = []
    
    # Skip header and separator rows
    data_lines = [l for l in table_lines if l.strip().startswith("|")]
    if len(data_lines) >= 2 and "---" in data_lines[1]:
        data_lines = data_lines[2:]

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
        amt_str = _get_cell(col_map.amount)
        balance_str = _get_cell(col_map.balance)

        debit = _parse_decimal(debit_str)
        credit = _parse_decimal(credit_str)
        amt_val = _parse_decimal(amt_str)
        balance = _parse_decimal(balance_str)

        amount = Decimal("0.0")
        
        # Resolve combined Amount column vs separate Debit/Credit
        if amt_val is not None:
            # It's a combined column (+ for credit, - for debit)
            amount = amt_val
            if amount < 0:
                debit = abs(amount)
            elif amount > 0:
                credit = amount
        else:
            # Separate columns
            if debit is not None:
                amount = -debit
            elif credit is not None:
                amount = credit

        # If all amounts are null, it's definitely a description overflow/continuation row
        # (Even if there's text in the date column like a time "10:33 PM", it belongs to the previous row)
        if debit is None and credit is None and amt_val is None and balance is None:
            if transactions:
                # Append any available text from the row to the previous transaction's description
                extra_text = []
                if tx_date_str: extra_text.append(tx_date_str)
                if desc: extra_text.append(desc)
                if ref_str: extra_text.append(ref_str)
                
                if extra_text:
                    transactions[-1].description += " \n " + " ".join(extra_text)
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
        currency=col_map.currency,
        parser_version="0.3.0"
    )

    parse_result = ParseResult(metadata=metadata, transactions=transactions)
    return validate_ai_fallback_result(parse_result)

