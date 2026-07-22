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
You are a precise financial data extractor. A bank statement table has already been parsed
from a PDF into the Markdown table below. Your job is to convert it into structured JSON.

Do NOT guess or hallucinate missing values. If a field is absent, use null.
Do NOT include both debit AND credit on the same row.
Dates MUST be formatted as YYYY-MM-DD.
amount is NEGATIVE for debits, POSITIVE for credits.
Skip any row that is a header, footer, or subtotal — only include actual transaction rows.

Return ONLY a valid JSON object — no prose, no markdown fences.

Schema:
{{  
  "metadata": {{
    "bank_id": "{bank_id}",
    "account_number": "<string or null>",
    "account_holder": "<string or null>",
    "currency": "<3-letter ISO code e.g. PKR or USD, or null>",
    "statement_period_start": "<YYYY-MM-DD or null>",
    "statement_period_end": "<YYYY-MM-DD or null>",
    "parser_version": "0.2.0"
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
      "confidence": 0.9,
      "review_flags": []
    }}
  ],
  "review_flags": []
}}

Markdown table to parse:
{markdown_table}
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

    prompt = _FALLBACK_PROMPT.format(
        bank_id=bank_id,
        markdown_table=f"```\n{normalized_text[:5000]}\n```",
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
    try:
        client = get_groq_client(api_key)
    except ValueError as exc:
        raise FallbackUnavailableError(str(exc)) from exc

    prompt = _FALLBACK_PROMPT.format(
        bank_id=bank_id,
        markdown_table=markdown_table,
    )

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0.0,
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
