"""Bank of America statement parser.

Layout Assumptions:
- Input language: English
- US bank — space-aligned tabular layout
- Columns: Date (MM/DD), Description, Amount (+/-), Balance
- Dates formatted as MM/DD (year inferred from statement period)
- Opening/closing balance rows skipped
- Currency: USD
"""

from __future__ import annotations

import re
from datetime import date
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

_ACCOUNT_RE = re.compile(r"Account Number:\s*([\w\-]+)", re.IGNORECASE)
_HOLDER_RE = re.compile(r"Account Holder:\s*(.+)", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"Currency:\s*([A-Z]{3})", re.IGNORECASE)
_PERIOD_RE = re.compile(
    r"Statement Period:\s*(\d{2}/\d{2}/\d{4})\s+through\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
# BofA short date: MM/DD or MM/DD/YYYY
_TX_RE = re.compile(
    r"^(\d{2}/\d{2}(?:/\d{4})?)\s+(.+?)\s{2,}([+-]?[\d,]+\.\d{2})\s+([\d,]+\.\d{2})$"
)

_SKIP_WORDS = {"beginning balance", "ending balance"}


def _parse_mdy(raw: str, year: int) -> date | None:
    raw = raw.strip()
    try:
        parts = raw.split("/")
        if len(parts) == 2:
            m, d = parts
            return date(year, int(m), int(d))
        elif len(parts) == 3:
            m, d, y = parts
            return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None


def _parse_decimal(val: str | None) -> Decimal | None:
    if not val:
        return None
    cleaned = val.replace(",", "").replace("+", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


class BankOfAmericaParser(BaseBankParser):
    bank_id = "bank_of_america"
    language = Language.SPANISH

    def parse(self, normalized_text: str) -> ParseResult:
        account_number = self._regex(normalized_text, _ACCOUNT_RE)
        account_holder = self._regex(normalized_text, _HOLDER_RE)
        currency = self._regex(normalized_text, _CURRENCY_RE) or "USD"

        period_start = period_end = None
        pm = _PERIOD_RE.search(normalized_text)
        if pm:
            period_start = self._parse_full_date(pm.group(1))
            period_end = self._parse_full_date(pm.group(2))

        year = period_start.year if period_start else date.today().year

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
            m = _TX_RE.match(line)
            if not m:
                continue
            raw_date, description, amount_str, balance_str = (
                m.group(1), m.group(2).strip(), m.group(3), m.group(4)
            )
            if description.lower() in _SKIP_WORDS:
                continue
            tx_date = _parse_mdy(raw_date, year)
            if tx_date is None:
                continue

            row_number += 1
            transactions.append(
                self._build_tx(description, tx_date, amount_str, balance_str, currency, row_number)
            )

        return ParseResult(metadata=metadata, transactions=transactions, review_flags=[])

    def _build_tx(
        self,
        description: str,
        tx_date: date,
        amount_str: str,
        balance_str: str,
        currency: str,
        row_number: int,
    ) -> Transaction:
        flags: list[ReviewFlag] = []
        signed_amount = _parse_decimal(amount_str)
        balance = _parse_decimal(balance_str)

        if signed_amount is None:
            flags.append(ReviewFlag(
                code="unclear_amount",
                message=f"Amount '{amount_str}' could not be parsed.",
                severity=ReviewSeverity.WARNING,
                row_number=row_number,
            ))
            amount = Decimal("0.00")
            debit = credit = None
        else:
            amount = signed_amount
            if signed_amount < 0 or amount_str.strip().startswith("-"):
                debit = abs(signed_amount)
                credit = None
            else:
                debit = None
                credit = signed_amount

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

    def _parse_full_date(self, raw: str) -> date | None:
        try:
            m, d, y = raw.strip().split("/")
            return date(int(y), int(m), int(d))
        except (ValueError, AttributeError):
            return None
