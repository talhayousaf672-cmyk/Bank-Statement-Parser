"""AI description enrichment — opt-in, always downstream of validation.

Enriches terse transaction descriptions (e.g. "TRF CR", "POS 4892") with
human-readable labels using the Claude API.

All enriched output MUST pass through validate_ai_fallback_result() before
it can reach export or the review queue. This is enforced here.
"""

from __future__ import annotations

from bank_parser.ai.fallback_gate import AiFallbackGateResult, validate_ai_fallback_result
from bank_parser.core.models import ParseResult, Transaction

_ENRICH_PROMPT = """\
You are enriching terse bank transaction descriptions to be human-readable.

For each transaction below, provide a clearer description. Keep it concise (max 60 chars).
Do NOT change amounts, dates, or references — ONLY the description text.

Return a JSON array in the same order as the input, each item being a string.
Return ONLY the JSON array. No prose.

Transactions:
{transactions}
"""


class EnrichmentUnavailableError(RuntimeError):
    """Raised when the AI enrichment service is not configured."""


def enrich_descriptions(
    parse_result: ParseResult,
    api_key: str | None = None,
) -> AiFallbackGateResult:
    """Enrich transaction descriptions using Claude (opt-in).

    The enriched result is always passed through the AI fallback gate
    — it will be REJECTED if it fails reconciliation.

    Args:
        parse_result: A validated ParseResult from validate_parse_result().
        api_key: Claude API key. If None, raises EnrichmentUnavailableError.

    Returns:
        AiFallbackGateResult with status ACCEPTED, ACCEPTED_WITH_REVIEW, or REJECTED.

    Usage:
        result = validate_parse_result(parser.parse(text))
        gate = enrich_descriptions(result, api_key=os.environ["CLAUDE_API_KEY"])
        if gate.accepted:
            write_excel(gate.parse_result, output_path)
    """
    if api_key is None:
        raise EnrichmentUnavailableError(
            "AI enrichment requires a CLAUDE_API_KEY. "
            "Set the environment variable or pass api_key= explicitly."
        )

    enriched_descriptions = _call_claude_api(parse_result.transactions, api_key)

    enriched_transactions = [
        tx.model_copy(update={"description": new_desc})
        for tx, new_desc in zip(parse_result.transactions, enriched_descriptions)
    ]
    enriched_result = parse_result.model_copy(update={"transactions": enriched_transactions})

    # Gate: always validate enriched output before returning
    return validate_ai_fallback_result(enriched_result)


def _call_claude_api(
    transactions: list[Transaction],
    api_key: str,
) -> list[str]:
    """Call Claude API to enrich transaction descriptions.

    Phase 4.5: implement using the anthropic SDK.

    Example implementation:
        from anthropic import Anthropic
        import json
        client = Anthropic(api_key=api_key)
        tx_list = [{"description": tx.description, "amount": str(tx.amount)} for tx in transactions]
        prompt = _ENRICH_PROMPT.format(transactions=json.dumps(tx_list, indent=2))
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(message.content[0].text)
    """
    raise NotImplementedError(
        "Claude API enrichment is not yet implemented (Phase 4.5). "
        "Install 'anthropic' and implement _call_claude_api() following the example above."
    )
