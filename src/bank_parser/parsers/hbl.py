"""HBL (Habib Bank Limited) statement parser.

Layout Assumptions:
- Input language: English
- Pakistani bank — pipe-delimited tabular layout
- Columns: DATE | VALUE DATE | DESCRIPTION | REFERENCE | DEBIT | CREDIT | BALANCE
- Dates formatted as DD-Mon-YYYY (e.g. 01-Jan-2026)
- Header keywords: 'Account Number', 'Account Title', 'Currency', 'Statement Period'
- Currency: PKR
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

_ACCOUNT_RE = re.compile(r"(?:Account Number|IBAN)[:\s]+([A-Z0-9]+)", re.IGNORECASE)
_HOLDER_RE = re.compile(r"Account Title:\s*(.+)", re.IGNORECASE)
_CURRENCY_RE = re.compile(r"(?:Currency:\s*([A-Z]{3})|(PKR))", re.IGNORECASE)  # Fallback to PKR
_PERIOD_RE = re.compile(
    r"(?:Statement Period|Statement Duration)[:\s]+(\d{1,2}[/\-\s]+[A-Za-z0-9]+[/\-\s]+\d{4}).*?(?:To|till)\s+(\d{1,2}[/\-\s]+[A-Za-z0-9]+[/\-\s]+\d{4})",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"^(\d{1,2})[-/]([A-Za-z]{3}|\d{1,2})[-/](\d{4})$")

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_hbl_date(raw: str) -> date | None:
    m = _DATE_RE.match(raw.strip())
    if not m:
        return None
    day_str, mon_str, year_str = m.group(1), m.group(2).lower(), m.group(3)
    
    if mon_str.isdigit():
        month = int(mon_str)
    else:
        month = _MONTH_MAP.get(mon_str)
        
    if not month or not (1 <= month <= 12):
        return None
    try:
        return date(int(year_str), month, int(day_str))
    except ValueError:
        return None


def _parse_period_date(raw: str) -> date | None:
    # Matches both "01 Jan 2026" and "6/19/2020" (MM/DD/YYYY)
    raw = raw.strip().replace("-", "/").replace(" ", "/")
    parts = [p for p in raw.split("/") if p]
    if len(parts) != 3:
        return None
    
    # If first part is M or MM, and second is D or DD (American format in HBL duration)
    if parts[0].isdigit() and parts[1].isdigit():
        m, d, y = int(parts[0]), int(parts[1]), int(parts[2])
        if m > 12 >= d: # It's probably DD/MM/YYYY
            d, m = m, d
        try:
            return date(y, m, d)
        except ValueError:
            pass

    # Standard DD-Mon-YYYY
    day, mon_str, year = parts[0], parts[1].lower(), parts[2]
    month = _MONTH_MAP.get(mon_str)
    if not month:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _parse_decimal(val: str) -> Decimal | None:
    cleaned = val.replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


class HBLParser(BaseBankParser):
    bank_id = "hbl"
    language = Language.SPANISH

    def parse(self, normalized_text: str) -> ParseResult:
        account_number = self._regex(normalized_text, _ACCOUNT_RE)
        account_holder = self._regex(normalized_text, _HOLDER_RE)
        currency = self._regex(normalized_text, _CURRENCY_RE) or "PKR"

        period_start: date | None = None
        period_end: date | None = None
        period_m = _PERIOD_RE.search(normalized_text)
        if period_m:
            period_start = _parse_period_date(period_m.group(1))
            period_end = _parse_period_date(period_m.group(2))

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
            if len(parts) < 6:
                continue
            # Skip header row
            if parts[0].upper() in ("DATE", "TRANSACTION DATE", ""):
                continue
            # Must start with a parseable date
            tx_date = _parse_hbl_date(parts[0])
            if tx_date is None:
                continue
            row_number += 1
            transactions.append(self._build_tx(parts, tx_date, currency, row_number))

        return ParseResult(metadata=metadata, transactions=transactions, review_flags=[])

    def _build_tx(
        self, parts: list[str], tx_date: date, currency: str, row_number: int
    ) -> Transaction:
        flags: list[ReviewFlag] = []
        value_date = _parse_hbl_date(parts[1]) if len(parts) > 1 else None
        description = parts[2] if len(parts) > 2 else ""
        
        # In newer formats (6 columns), there is no explicit Reference column.
        if len(parts) == 6:
            reference = None
            debit_raw = parts[3]
            credit_raw = parts[4]
            balance_raw = parts[5]
        else:
            reference = parts[3] if len(parts) > 3 else None
            debit_raw = parts[4] if len(parts) > 4 else ""
            credit_raw = parts[5] if len(parts) > 5 else ""
            balance_raw = parts[6] if len(parts) > 6 else ""

        debit = _parse_decimal(debit_raw)
        credit = _parse_decimal(credit_raw)
        balance = _parse_decimal(balance_raw)

        if debit is not None:
            amount = -debit
        elif credit is not None:
            amount = credit
        else:
            amount = Decimal("0.00")
            flags.append(ReviewFlag(
                code="unclear_amount",
                message="Neither debit nor credit amount found.",
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
            value_date=value_date,
            description=description,
            reference=reference or None,
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
        if m:
            for g in m.groups():
                if g: return g.strip()
        return None
