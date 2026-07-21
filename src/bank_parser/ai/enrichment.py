"""AI description enrichment using Groq/Llama.

Enriches terse transaction descriptions (e.g. "TRF CR", "POS 4892", "IBFT")
with human-readable labels.

Uses llama-3.1-8b-instant (fast, sufficient for simple text enrichment).
All output is gated through validate_ai_fallback_result() before export.
"""

from __future__ import annotations

import json
import os
import re

from bank_parser.ai.fallback_gate import AiFallbackGateResult, validate_ai_fallback_result
from bank_parser.ai.groq_client import DEFAULT_MODEL, get_groq_client
from bank_parser.core.models import ParseResult, Transaction, Language

_ENRICH_PROMPT = """\
You are an expert financial translator. Your task is to enrich terse Pakistani and international bank transaction descriptions and translate them into {language}.

Rules:
1. Enlarge and clarify abbreviations (e.g. IBFT=Inter-Bank Fund Transfer, TRF=Transfer, POS=Point of Sale, ATM=ATM Withdrawal).
2. Keep descriptions concise (max 60 characters).
3. CRITICAL: The final output MUST be translated entirely into {language}. Do not output English unless {language} is English.

Return ONLY a flat JSON array of strings. Do NOT return JSON objects or dicts.
Example Output:
[
  "Translated description 1",
  "Translated description 2"
]

No prose, no markdown.

Transactions to enrich:
{transactions}
"""


class EnrichmentUnavailableError(RuntimeError):
    """Raised when no GROQ_API_KEY is configured."""


def enrich_descriptions(
    parse_result: ParseResult,
    language: Language,
    api_key: str | None = None,
) -> ParseResult:
    """Enrich transaction descriptions using Llama via Groq.

    Returns:
        The updated ParseResult with enriched descriptions.
    """
    try:
        client = get_groq_client(api_key)
    except ValueError as exc:
        raise EnrichmentUnavailableError(str(exc)) from exc

    enriched_descriptions = _call_llama(client, parse_result.transactions, language)

    enriched_transactions = [
        tx.model_copy(update={"description": new_desc})
        for tx, new_desc in zip(parse_result.transactions, enriched_descriptions)
    ]
    enriched_result = parse_result.model_copy(update={"transactions": enriched_transactions})
    return enriched_result


def _call_llama(client, transactions: list[Transaction], language: Language) -> list[str]:
    """Call Llama-3.1-8B via Groq to enrich descriptions."""
    tx_list = [
        {"description": tx.description, "amount": str(tx.amount)}
        for tx in transactions
    ]
    prompt = _ENRICH_PROMPT.format(
        transactions=json.dumps(tx_list, indent=2, ensure_ascii=False),
        language=language.name,
    )

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.1,  # low temp for deterministic output
    )

    raw = response.choices[0].message.content.strip()

    # Extract JSON array using regex in case LLM added conversational text or markdown fences
    match = re.search(r'\[\s*.*?\s*\]', raw, re.DOTALL)
    if match:
        raw = match.group(0)
    else:
        raw = raw.strip()

    try:
        enriched = json.loads(raw)
        if isinstance(enriched, list) and len(enriched) == len(transactions):
            parsed_strings = []
            for d in enriched:
                if isinstance(d, dict):
                    # If it still returns a dict, grab the translated value (usually the last or most relevant key)
                    val = list(d.values())[-1]
                    parsed_strings.append(str(val))
                else:
                    parsed_strings.append(str(d))
            return parsed_strings
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: return original descriptions unchanged
    return [tx.description for tx in transactions]
