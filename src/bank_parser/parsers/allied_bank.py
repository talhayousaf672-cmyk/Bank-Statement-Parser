"""Allied Bank Limited (ABL) statement parser.

Layout Assumptions:
- Input language: English
- Pakistani bank — pipe-delimited tabular layout
- Columns: Value Date | Transaction Date | Description | Reference | Debit | Credit | Balance
- Dates formatted as DD-MM-YYYY
- Currency: PKR
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from bank_parser.core.models import (
    Language, ParseResult, ReviewFlag, ReviewSeverity, StatementMetadata, Transaction,
)
from bank_parser.core.parser import BaseBankParser

_ACCOUNT_RE = re.compile(r"Account (?:No|Number)[.:\s]+([A-Z0-9\-]+)", re.IGNORECASE)
_HOLDER_RE = re.compile(r"(?:Account Title|Account Holder)[:\s]+(.+)", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"Currency[:\s]+([A-Z]{3})", re.IGNORECASE)
_PERIOD_RE = re.compile(
    r"(?:From|Period)[:\s]+(\d{2}-\d{2}-\d{4})\s+(?:To|Through)[:\s]+(\d{2}-\d{2}-\d{4})",
    re.IGNORECASE,
)
_SKIP_DESC = {"opening balance", "closing balance", "b/f"}


def _parse_dmy_dash(raw: str) -> date | None:
    try:
        d, m, y = raw.strip().split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None


def _parse_decimal(val: str) -> Decimal | None:
    cleaned = val.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


class AlliedBankParser(BaseBankParser):
    bank_id = "allied_bank"
    language = Language.SPANISH

    def parse(self, normalized_text: str) -> ParseResult:
        account_number = self._regex(normalized_text, _ACCOUNT_RE)
        account_holder = self._regex(normalized_text, _HOLDER_RE)
        currency = self._regex(normalized_text, _CURRENCY_RE) or "PKR"

        period_start = period_end = None
        pm = _PERIOD_RE.search(normalized_text)
        if pm:
            period_start = _parse_dmy_dash(pm.group(1))
            period_end = _parse_dmy_dash(pm.group(2))

        metadata = StatementMetadata(
            bank_id=self.bank_id, language=self.language,
            account_number=account_number, account_holder=account_holder,
            currency=currency, statement_period_start=period_start, statement_period_end=period_end,
        )

        transactions: list[Transaction] = []
        row_number = 0
        for line in normalized_text.splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 7:
                continue
            if parts[0].upper() in ("VALUE DATE", "DATE", ""):
                continue
            value_date = _parse_dmy_dash(parts[0])
            tx_date = _parse_dmy_dash(parts[1]) or value_date
            if tx_date is None:
                continue
            description = parts[2] if len(parts) > 2 else ""
            if description.lower() in _SKIP_DESC:
                continue
            row_number += 1

            flags: list[ReviewFlag] = []
            reference = parts[3] if len(parts) > 3 else None
            debit = _parse_decimal(parts[4] if len(parts) > 4 else "")
            credit = _parse_decimal(parts[5] if len(parts) > 5 else "")
            balance = _parse_decimal(parts[6] if len(parts) > 6 else "")

            if debit is not None:
                amount = -debit
            elif credit is not None:
                amount = credit
            else:
                amount = Decimal("0.00")
                flags.append(ReviewFlag(code="unclear_amount", message="No amount found.",
                                        severity=ReviewSeverity.WARNING, row_number=row_number))

            transactions.append(Transaction(
                transaction_date=tx_date, value_date=value_date, description=description,
                reference=reference or None, debit=debit, credit=credit,
                amount=amount, balance=balance, currency=currency,
                confidence=1.0 if not flags else 0.8, review_flags=flags,
            ))

        return ParseResult(metadata=metadata, transactions=transactions, review_flags=[])

    def _regex(self, text: str, pattern: re.Pattern) -> str | None:
        m = pattern.search(text)
        return m.group(1).strip() if m else None
