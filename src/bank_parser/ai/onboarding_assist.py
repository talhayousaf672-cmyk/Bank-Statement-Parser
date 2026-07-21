"""AI-assisted bank parser onboarding using Groq/Llama-70B.

Given a sample of normalized statement text, Llama drafts a Python parser skeleton
following the project's BaseBankParser contract.

The output is ALWAYS a string (Python source code).
It is NEVER auto-saved or auto-registered — a human MUST review it first.
"""

from __future__ import annotations

from bank_parser.ai.groq_client import DEFAULT_MODEL, get_groq_client

_PROMPT_TEMPLATE = """\
You are a Python expert helping onboard a new bank's statement parser.

The project uses this base class (already imported in scope):

```python
class BaseBankParser(ABC):
    bank_id: str        # e.g. "mcb_bank"  — snake_case, unique
    language: Language  # e.g. Language.SPANISH (output language for Excel headers)

    def parse(self, normalized_text: str) -> ParseResult:
        ...
```

Available imports you can use:
```python
from decimal import Decimal, InvalidOperation
from datetime import date
import re
from bank_parser.core.models import (
    Language, ParseResult, ReviewFlag, ReviewSeverity,
    StatementMetadata, Transaction,
)
from bank_parser.core.parser import BaseBankParser
```

ParseResult fields:
- metadata: StatementMetadata(bank_id, language, account_number, account_holder,
    currency, statement_period_start: date, statement_period_end: date)
- transactions: list[Transaction](transaction_date, value_date, description,
    reference, debit, credit, amount, balance, currency, confidence, review_flags)
- review_flags: list[ReviewFlag]

Rules you MUST follow:
1. Only parse English-input text. Language field controls output Excel headers.
2. Use Decimal (NEVER float) for all monetary values.
3. Debit rows: amount is NEGATIVE; credit rows: amount is POSITIVE.
4. Emit ReviewFlag for unclear/missing fields. Never silently skip a row.
5. Do NOT attempt balance reconciliation (that's a separate validation layer).
6. Class name must be {class_name}Parser, file name {bank_id}.py.
7. Skip header rows and opening/closing balance rows.
8. Include a docstring listing layout assumptions.

Sample statement text (already normalized — single spaces, no page numbers):
---
{sample_text}
---

Bank ID to assign: {bank_id}

Write a complete, working Python parser implementation. Return ONLY the Python code.
No explanations, no markdown fences.
"""


class OnboardingUnavailableError(RuntimeError):
    """Raised when no GROQ_API_KEY is configured."""


def draft_parser_from_sample(
    sample_text: str,
    bank_id: str,
    api_key: str | None = None,
) -> str:
    """Ask Llama-70B to draft a parser skeleton for a new bank.

    Args:
        sample_text: Normalized statement text (already through normalize_text()).
        bank_id: Snake_case bank identifier, e.g. "js_bank".
        api_key: Groq API key. Falls back to GROQ_API_KEY env var.

    Returns:
        Python source code as a string.

    Important:
        DO NOT auto-save or auto-register the output.
        Always review and test before adding to parsers/__init__.py.
    """
    try:
        client = get_groq_client(api_key)
    except ValueError as exc:
        raise OnboardingUnavailableError(str(exc)) from exc

    class_name = "".join(word.capitalize() for word in bank_id.split("_"))
    prompt = _PROMPT_TEMPLATE.format(
        sample_text=sample_text[:3000],
        bank_id=bank_id,
        class_name=class_name,
    )

    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000,
        temperature=0.1,
    )

    code = response.choices[0].message.content.strip()

    # Strip markdown fences if Llama wrapped the code
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return code.strip()
