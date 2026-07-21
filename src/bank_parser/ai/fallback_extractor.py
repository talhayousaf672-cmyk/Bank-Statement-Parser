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

    prompt = _FALLBACK_PROMPT.format(
        bank_id=bank_id,
        text=normalized_text[:5000],  # cap to stay within context
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
