"""AI description enrichment using Groq/Llama.

Enriches terse transaction descriptions (e.g. "TRF CR", "POS 4892", "IBFT")
with human-readable labels.

Uses llama-3.1-8b-instant (fast, sufficient for simple text enrichment).
All output is gated through validate_ai_fallback_result() before export.
"""

from __future__ import annotations

import json
import os

from bank_parser.ai.fallback_gate import AiFallbackGateResult, validate_ai_fallback_result
from bank_parser.ai.groq_client import FAST_MODEL, get_groq_client
from bank_parser.core.models import ParseResult, Transaction, Language

_ENRICH_PROMPT = """\
You are enriching and translating terse Pakistani and international bank transaction descriptions.

For each transaction below, provide a clearer, more descriptive label. Rules:
- Keep descriptions concise (max 60 characters)
- Do NOT change meaning — only clarify abbreviations
- Common abbreviations: IBFT=Inter-Bank Fund Transfer, TRF=Transfer, CR=Credit, DR=Debit,
  POS=Point of Sale, ATM=ATM Withdrawal, SAL=Salary, UTIL=Utility, INS=Insurance,
  KEPTA=KESC/K-Electric, LESCO=Lahore Electric Supply, SNGPL=Sui Northern Gas,
  PTCL=Pakistan Telecom, MCB=MCB Bank, HBL=HBL Bank, UBL=United Bank
- TRANSLATE the final human-readable description into {language}.

Return ONLY a JSON array of strings, in the same order as the input. No prose, no markdown.

Transactions to enrich:
{transactions}
"""


class EnrichmentUnavailableError(RuntimeError):
    """Raised when no GROQ_API_KEY is configured."""


def enrich_descriptions(
    parse_result: ParseResult,
    language: Language,
    api_key: str | None = None,
) -> AiFallbackGateResult:
    """Enrich transaction descriptions using Llama via Groq.

    The enriched result is always gated through validate_ai_fallback_result()
    — it will be REJECTED if reconciliation fails after enrichment.

    Args:
        parse_result: A validated ParseResult from validate_parse_result().
        api_key: Groq API key. Falls back to GROQ_API_KEY env var.

    Returns:
        AiFallbackGateResult (ACCEPTED / ACCEPTED_WITH_REVIEW / REJECTED).
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
    return validate_ai_fallback_result(enriched_result)


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
        model=FAST_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0.1,  # low temp for deterministic output
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        enriched = json.loads(raw)
        if isinstance(enriched, list) and len(enriched) == len(transactions):
            return [str(d) for d in enriched]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: return original descriptions unchanged
    return [tx.description for tx in transactions]
