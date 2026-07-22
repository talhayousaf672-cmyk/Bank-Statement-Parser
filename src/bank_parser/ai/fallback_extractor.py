"""AI fallback extraction using Groq/Llama-70B.

When a deterministic parser returns zero transactions or all rows have ERROR flags,
Llama-3.3-70B attempts to extract transactions from the normalized text.

ALL output is gated through validate_ai_fallback_result() — non-negotiable.
Uses the 70B model because structured JSON extraction requires high accuracy.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from bank_parser.ai.fallback_gate import AiFallbackGateResult, validate_ai_fallback_result
from bank_parser.ai.groq_client import DEFAULT_MODEL, get_groq_client
from bank_parser.core.models import Language, ParseResult, ReviewSeverity

_FALLBACK_PROMPT = """\
Extract all bank transactions from the statement text below.

Return ONLY a valid JSON object — no prose, no markdown fences.

Schema:
{{
  "metadata": {{
    "bank_id": "{bank_id}",
    "language": "es",
    "account_number": "<string or null>",
    "account_holder": "<string or null>",
    "currency": "<3-letter ISO code, e.g. PKR or USD, or null>",
    "statement_period_start": "<YYYY-MM-DD or null>",
    "statement_period_end": "<YYYY-MM-DD or null>",
    "parser_version": "0.1.0"
  }},
  "transactions": [
    {{
      "transaction_date": "<YYYY-MM-DD or null>",
      "value_date": "<YYYY-MM-DD or null>",
      "description": "<string>",
      "reference": "<string or null>",
      "debit": "<decimal string e.g. 1500.00, or null>",
      "credit": "<decimal string e.g. 5000.00, or null>",
      "amount": "<signed decimal — negative for debits, positive for credits>",
      "balance": "<decimal string or null>",
      "currency": "<3-letter code or null>",
      "confidence": 0.7,
      "review_flags": []
    }}
  ],
  "review_flags": []
}}

Rules:
- Dates MUST be YYYY-MM-DD. If unclear, use null.
- amount is NEGATIVE for debits, POSITIVE for credits.
- Do NOT include both debit AND credit on the same row.
- Skip header/footer rows and opening/closing balance rows.
- If a field is missing, use null. Never guess amounts.

Statement text:
---
{text}
---
"""

_COMPACT_FALLBACK_PROMPT = """\
Extract bank transactions from the statement text below.

Return ONLY a valid JSON object with this compact schema:
{{
  "metadata": {{
    "account_number": "<string or null>",
    "account_holder": "<string or null>",
    "currency": "PKR",
    "statement_period_start": "<YYYY-MM-DD or null>",
    "statement_period_end": "<YYYY-MM-DD or null>"
  }},
  "transactions": [
    {{
      "transaction_date": "<YYYY-MM-DD or null>",
      "description": "<clear string preserving names, merchant, transfer channel, and reference text>",
      "debit": "<positive decimal string or null>",
      "credit": "<positive decimal string or null>",
      "balance": "<decimal string or null>"
    }}
  ]
}}

Rules:
- Use null, not blank strings, for missing numeric values.
- Do not include both debit and credit for one transaction.
- Skip opening balance, closing balance, totals, headers, and footers.
- Preserve visible names, merchant names, phone/account fragments, channels, and references in descriptions.
- Keep descriptions under 140 characters.
- Return every visible transaction row you can identify.

Statement text:
---
{text}
---
"""


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

    first_error: Exception | None = None
    rejected_gate: AiFallbackGateResult | None = None

    try:
        data = _request_json(
            client,
            _FALLBACK_PROMPT.format(
                bank_id=bank_id,
                text=normalized_text[:5000],  # cap to stay within context
            ),
            max_completion_tokens=12000,
        )
        gate = validate_ai_fallback_result(ParseResult.model_validate(data))
        if gate.accepted and gate.parse_result.transactions:
            return gate
        rejected_gate = gate
    except Exception as exc:
        first_error = exc

    try:
        data = _request_json(
            client,
            _COMPACT_FALLBACK_PROMPT.format(text=normalized_text[:7000]),
            max_completion_tokens=8000,
        )
        compact_result = _compact_parse_result(data, bank_id, language)
        compact_gate = validate_ai_fallback_result(compact_result)
        if compact_gate.parse_result.transactions:
            return compact_gate
        raise ValueError("AI compact fallback returned no transactions.")
    except Exception as exc:
        if rejected_gate is not None and rejected_gate.parse_result.transactions:
            return rejected_gate
        if first_error is not None:
            raise ValueError(f"AI fallback failed after compact retry: {first_error}; {exc}") from exc
        raise


def _request_json(client, prompt: str, max_completion_tokens: int) -> dict:
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=max_completion_tokens,
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    raw = raw.strip()

    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Llama returned invalid JSON: {exc}\n\nRaw response:\n{raw[:500]}") from exc
    if not isinstance(loaded, dict):
        raise ValueError("Llama returned JSON, but it was not an object.")
    return loaded


def _compact_parse_result(data: dict, bank_id: str, language: Language) -> ParseResult:
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    transactions = []
    for row in data.get("transactions", []):
        if not isinstance(row, dict):
            continue

        description = str(row.get("description") or "").strip()
        if not description:
            continue

        debit = _positive_decimal_or_none(row.get("debit"))
        credit = _positive_decimal_or_none(row.get("credit"))
        if debit is not None and credit is not None:
            credit = None

        if debit is not None:
            amount = -debit
        elif credit is not None:
            amount = credit
        else:
            amount = Decimal("0.00")

        transactions.append(
            {
                "transaction_date": _blank_to_none(row.get("transaction_date") or row.get("date")),
                "value_date": None,
                "description": description[:140],
                "reference": None,
                "debit": str(debit) if debit is not None else None,
                "credit": str(credit) if credit is not None else None,
                "amount": str(amount),
                "balance": _decimal_string_or_none(row.get("balance")),
                "currency": _blank_to_none(row.get("currency") or metadata.get("currency")),
                "confidence": 0.7,
                "review_flags": [],
            }
        )

    return ParseResult.model_validate(
        {
            "metadata": {
                "bank_id": bank_id,
                "language": language.value,
                "account_number": _blank_to_none(metadata.get("account_number")),
                "account_holder": _blank_to_none(metadata.get("account_holder")),
                "currency": _blank_to_none(metadata.get("currency")),
                "statement_period_start": _blank_to_none(metadata.get("statement_period_start")),
                "statement_period_end": _blank_to_none(metadata.get("statement_period_end")),
                "parser_version": "0.1.0",
            },
            "transactions": transactions,
            "review_flags": [],
        }
    )


def _blank_to_none(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal_string_or_none(value) -> str | None:
    parsed = _decimal_or_none(value)
    return str(parsed) if parsed is not None else None


def _positive_decimal_or_none(value) -> Decimal | None:
    parsed = _decimal_or_none(value)
    return abs(parsed) if parsed is not None else None


def _decimal_or_none(value) -> Decimal | None:
    text = _blank_to_none(value)
    if text is None:
        return None
    cleaned = text.replace(",", "").replace("PKR", "").strip()
    if cleaned in {"-", "--"}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
