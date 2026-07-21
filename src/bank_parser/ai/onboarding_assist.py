"""AI-assisted bank parser onboarding.

Given a sample of raw/normalized statement text, this module calls the Claude API
to draft a parser skeleton following the project's BaseBankParser contract.

The output is Python source code (string) — it is NEVER auto-saved or auto-registered.
A human MUST review and adapt the draft before using it.
"""

from __future__ import annotations

_PROMPT_TEMPLATE = """\
You are helping onboard a new bank's statement parser into a Python project.

The project uses this base class:

```python
class BaseBankParser(ABC):
    bank_id: str        # e.g. "acme_bank"
    language: Language  # e.g. Language.SPANISH (output language, not input)

    @abstractmethod
    def parse(self, normalized_text: str) -> ParseResult:
        ...
```

ParseResult contains:
- metadata: StatementMetadata (bank_id, language, account_number, account_holder,
  currency, statement_period_start: date, statement_period_end: date, parser_version)
- transactions: list[Transaction] (transaction_date, value_date, description, reference,
  debit, credit, amount, balance, currency, confidence, review_flags)
- review_flags: list[ReviewFlag]

Rules:
1. Parsers ONLY parse English-input text. Language field controls output Excel headers.
2. Use Decimal (never float) for all monetary values.
3. Debit rows: amount is NEGATIVE; credit rows: amount is POSITIVE.
4. Emit ReviewFlag for unclear/missing fields. Never silently skip.
5. Do NOT attempt balance reconciliation (that's Talha's validation layer).
6. Class name must be <BankName>Parser, file name <bank_id>.py.

Sample statement text (normalized):
---
{sample_text}
---

Bank ID to assign: {bank_id}

Draft a complete, working parser implementation. Include docstring with layout assumptions.
"""


class OnboardingUnavailableError(RuntimeError):
    """Raised when the AI onboarding service is not configured."""


def draft_parser_from_sample(
    sample_text: str,
    bank_id: str,
    api_key: str | None = None,
) -> str:
    """Ask Claude to draft a parser skeleton for a new bank.

    Returns:
        Python source code as a string. DO NOT auto-save or auto-register.
        Review and adapt before use.

    Raises:
        OnboardingUnavailableError: if api_key is None.
    """
    if api_key is None:
        raise OnboardingUnavailableError(
            "AI onboarding requires a CLAUDE_API_KEY. "
            "Set the environment variable or pass api_key= explicitly."
        )

    prompt = _PROMPT_TEMPLATE.format(
        sample_text=sample_text[:3000],  # cap to avoid token overflow
        bank_id=bank_id,
    )

    # Phase 4.5: implement using the anthropic SDK.
    # from anthropic import Anthropic
    # client = Anthropic(api_key=api_key)
    # message = client.messages.create(
    #     model="claude-opus-4-5",
    #     max_tokens=2048,
    #     messages=[{"role": "user", "content": prompt}],
    # )
    # return message.content[0].text

    raise NotImplementedError(
        "Claude API onboarding assist is not yet implemented. "
        "Install 'anthropic' and uncomment the API call in draft_parser_from_sample()."
    )
