"""AI description enrichment — opt-in, always downstream of validation.

This module enriches transaction descriptions using an external AI API (Claude).
All enriched output MUST pass through validate_ai_fallback_result() before
it can reach export or the review queue.
"""

from __future__ import annotations

from bank_parser.core.models import ParseResult, Transaction
from bank_parser.ai.fallback_gate import AiFallbackGateResult, validate_ai_fallback_result


class EnrichmentUnavailableError(RuntimeError):
    """Raised when the AI enrichment service is not configured."""


def enrich_descriptions(
    parse_result: ParseResult,
    api_key: str | None = None,
) -> AiFallbackGateResult:
    """Enrich transaction descriptions using AI (opt-in).

    The enriched result is always passed through the AI fallback gate before
    being returned — it will be REJECTED if it fails reconciliation.

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

    # Stub: in Phase 4.5, call the Claude API here to enrich descriptions.
    # The enriched transactions must be reconstructed into a new ParseResult
    # and then passed through validate_ai_fallback_result() below.
    #
    # Example Phase 4.5 implementation:
    #   enriched_txs = _call_claude_api(parse_result.transactions, api_key)
    #   enriched_result = parse_result.model_copy(update={"transactions": enriched_txs})
    #   return validate_ai_fallback_result(enriched_result)

    # For now, pass through unchanged (no-op enrichment) so the gate can be tested.
    return validate_ai_fallback_result(parse_result)


def _call_claude_api(
    transactions: list[Transaction],
    api_key: str,
) -> list[Transaction]:
    """Placeholder — call Claude API to enrich transaction descriptions.

    Phase 4.5: implement using the anthropic SDK.
    Each enriched description must preserve the original amount, date, and
    reference — only description text may change.
    """
    raise NotImplementedError(
        "Claude API enrichment is not yet implemented (Phase 4.5). "
        "Install anthropic and implement _call_claude_api."
    )
