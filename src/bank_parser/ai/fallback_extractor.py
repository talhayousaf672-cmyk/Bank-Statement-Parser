"""AI fallback extraction — used when deterministic parsers fail.

When a parser returns zero transactions or all rows have ERROR flags,
Claude attempts to extract transactions from the raw text.

ALL output is gated through validate_ai_fallback_result() before
it can reach export or the review queue. This is non-negotiable.
"""

from __future__ import annotations

import json

from bank_parser.ai.fallback_gate import AiFallbackGateResult, validate_ai_fallback_result
from bank_parser.core.models import Language, ParseResult, StatementMetadata


_FALLBACK_PROMPT = """\
Extract bank transactions from this bank statement text. Return a JSON object matching this schema:

{{
  "metadata": {{
    "bank_id": "<bank_id>",
    "language": "<language_code>",
    "account_number": "<string or null>",
    "account_holder": "<string or null>",
    "currency": "<3-letter ISO code or null>",
    "statement_period_start": "<YYYY-MM-DD or null>",
    "statement_period_end": "<YYYY-MM-DD or null>"
  }},
  "transactions": [
    {{
      "transaction_date": "<YYYY-MM-DD or null>",
      "value_date": "<YYYY-MM-DD or null>",
      "description": "<string>",
      "reference": "<string or null>",
      "debit": "<decimal string or null>",
      "credit": "<decimal string or null>",
      "amount": "<signed decimal string — negative for debits>",
      "balance": "<decimal string or null>",
      "currency": "<3-letter code or null>"
    }}
  ]
}}

Rules:
- Use YYYY-MM-DD for all dates. If a date is ambiguous, use null.
- amount must be negative for debits, positive for credits.
- Do NOT include debit AND credit for the same row.
- Return ONLY the JSON. No prose, no markdown fences.

Statement text:
---
{text}
---
"""


class FallbackUnavailableError(RuntimeError):
    """Raised when the AI fallback service is not configured."""


def _is_fallback_needed(parse_result: ParseResult) -> bool:
    """Determine if AI fallback should be triggered."""
    if len(parse_result.transactions) == 0:
        return True
    from bank_parser.core.models import ReviewSeverity
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
) -> AiFallbackGateResult | None:
    """Attempt AI fallback extraction when deterministic parsing fails.

    Args:
        normalized_text: Statement text already through text_normalizer.
        bank_id: Bank identifier for metadata.
        language: Output language for Excel headers.
        api_key: Claude API key.
        force: If True, run fallback even if not strictly needed.

    Returns:
        AiFallbackGateResult if fallback ran, None if not needed and force=False.

    Raises:
        FallbackUnavailableError: if api_key is None.
    """
    if api_key is None:
        raise FallbackUnavailableError(
            "AI fallback extraction requires a CLAUDE_API_KEY."
        )

    prompt = _FALLBACK_PROMPT.format(text=normalized_text[:4000])

    # Phase 4.5: implement using the anthropic SDK.
    # from anthropic import Anthropic
    # client = Anthropic(api_key=api_key)
    # message = client.messages.create(
    #     model="claude-opus-4-5",
    #     max_tokens=4096,
    #     messages=[{"role": "user", "content": prompt}],
    # )
    # raw_json = message.content[0].text
    # data = json.loads(raw_json)
    # parse_result = ParseResult.model_validate(data)
    # return validate_ai_fallback_result(parse_result)

    raise NotImplementedError(
        "Claude API fallback extraction is not yet implemented. "
        "Install 'anthropic' and uncomment the API call in extract_with_fallback()."
    )
