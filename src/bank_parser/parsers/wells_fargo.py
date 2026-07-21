"""Wells Fargo statement parser.

Layout Assumptions:
- Input language: English
- US bank — pipe-delimited tabular layout
- Columns: Date | Description | Withdrawals | Deposits | Balance
- Dates formatted as MM/DD/YYYY
- Opening balance row present (skipped)
- Currency: USD
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from bank_parser.core.models import (
    Language,
    ParseResult,
    ReviewFlag,
    ReviewSeverity,
    StatementMetadata,
    Transaction,
)
from bank_parser.core.parser import BaseBankParser

_ACCOUNT_RE = re.compile(r"Account Number:\s*([\*\w]+)", re.IGNORECASE)
_HOLDER_RE = re.compile(r"Account Holder:\s*(.+)", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"Currency:\s*([A-Z]{3})", re.IGNORECASE)
_PERIOD_RE = re.compile(
    r"Statement Period:\s*(\w+ \d+,\s*\d{4})\s*-\s*(\w+ \d+,\s*\d{4})",
    re.IGNORECASE,
)

_SKIP_DESCRIPTIONS = {"beginning balance", "ending balance"}


def _parse_mdy(raw: str) -> date | None:
    raw = raw.strip()
    try:
        m, d, y = raw.split("/")
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


class WellsFargoParser(BaseBankParser):
    bank_id = "wells_fargo"
    language = Language.SPANISH

    def parse(self, normalized_text: str) -> ParseResult:
        account_number = self._regex(normalized_text, _ACCOUNT_RE)
        account_holder = self._regex(normalized_text, _HOLDER_RE)
        currency = self._regex(normalized_text, _CURRENCY_RE) or "USD"

        period_start = period_end = None
        pm = _PERIOD_RE.search(normalized_text)
        if pm:
            try:
                period_start = datetime.strptime(pm.group(1).strip(), "%B %d, %Y").date()
                period_end = datetime.strptime(pm.group(2).strip(), "%B %d, %Y").date()
            except ValueError:
                pass

        metadata = StatementMetadata(
            bank_id=self.bank_id,
            language=self.language,
            account_number=account_number,
            account_holder=account_holder,
            currency=currency,
            statement_period_start=period_start,
            statement_period_end=period_end,
        )

        transactions: list[Transaction] = []
        row_number = 0
        for line in normalized_text.splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 5:
                continue
            if parts[0].upper() in ("DATE", ""):
                continue
            tx_date = _parse_mdy(parts[0])
            if tx_date is None:
                continue
            description = parts[1] if len(parts) > 1 else ""
            if description.lower() in _SKIP_DESCRIPTIONS:
                continue
            row_number += 1
            transactions.append(self._build_tx(parts, tx_date, currency, row_number))

        return ParseResult(metadata=metadata, transactions=transactions, review_flags=[])

    def _build_tx(
        self, parts: list[str], tx_date: date, currency: str, row_number: int
    ) -> Transaction:
        flags: list[ReviewFlag] = []
        description = parts[1] if len(parts) > 1 else ""
        withdrawal_raw = parts[2] if len(parts) > 2 else ""
        deposit_raw = parts[3] if len(parts) > 3 else ""
        balance_raw = parts[4] if len(parts) > 4 else ""

        debit = _parse_decimal(withdrawal_raw)
        credit = _parse_decimal(deposit_raw)
        balance = _parse_decimal(balance_raw)

        if debit is not None:
            amount = -debit
        elif credit is not None:
            amount = credit
        else:
            amount = Decimal("0.00")
            flags.append(ReviewFlag(
                code="unclear_amount",
                message="Neither withdrawal nor deposit amount found.",
                severity=ReviewSeverity.WARNING,
                row_number=row_number,
            ))

        if balance is None:
            flags.append(ReviewFlag(
                code="missing_balance",
                message="Balance is missing.",
                severity=ReviewSeverity.WARNING,
                row_number=row_number,
            ))

        return Transaction(
            transaction_date=tx_date,
            value_date=None,
            description=description,
            reference=None,
            debit=debit,
            credit=credit,
            amount=amount,
            balance=balance,
            currency=currency,
            confidence=1.0 if not flags else 0.8,
            review_flags=flags,
        )

    def _regex(self, text: str, pattern: re.Pattern) -> str | None:
        m = pattern.search(text)
        return m.group(1).strip() if m else None
