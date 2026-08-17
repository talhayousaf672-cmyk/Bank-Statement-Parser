"""Chase Bank statement parser override.

Layout Assumptions:
- Input language: English
- Statement contains metadata header with Account Number and Statement Period.
- Transactions appear after 'TRANSACTION DETAIL' header.
- Dates are formatted as MM/DD/YYYY and normalized to YYYY-MM-DD.
- Amount column is signed (+ for credits, - for debits).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import datetime
import re

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
_CURRENCY_RE = re.compile(r"Currency:\s*([A-Z]{3})", re.IGNORECASE)
_PERIOD_RE = re.compile(r"Statement Period:\s*(.+)", re.IGNORECASE)
_CHASE_DATE_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


class ChaseBankParser(BaseBankParser):
    bank_id = "chase_bank"
    language = Language.SPANISH

    def parse(self, normalized_text: str) -> ParseResult:
        lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]

        # Metadata extraction
        account_number = self._extract_regex(_ACCOUNT_RE, normalized_text)
        currency = self._extract_regex(_CURRENCY_RE, normalized_text) or "USD"
        statement_period = self._extract_regex(_PERIOD_RE, normalized_text)

        metadata = StatementMetadata(
            bank_id=self.bank_id,
            language=self.language,
            account_number=account_number,
            currency=currency,
            statement_period=statement_period,
        )

        transactions: list[Transaction] = []
        in_detail_section = False
        row_number = 0

        for line in lines:
            if "TRANSACTION DETAIL" in line:
                in_detail_section = True
                continue
            if not in_detail_section:
                continue

            if "Posting Date" in line or "Description" in line:
                continue

            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4:
                    row_number += 1
                    tx = self._parse_chase_row(parts, currency, row_number)
                    if tx:
                        transactions.append(tx)

        return ParseResult(
            metadata=metadata,
            transactions=transactions,
            review_flags=[],
        )

    def _extract_regex(self, pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text)
        return match.group(1).strip() if match else None

    def _parse_chase_row(
        self, parts: list[str], currency: str, row_number: int
    ) -> Transaction | None:
        raw_date, desc, amount_str, balance_str = parts[:4]
        flags: list[ReviewFlag] = []

        # Convert MM/DD/YYYY -> YYYY-MM-DD
        date_iso = None
        match = _CHASE_DATE_RE.match(raw_date)
        if match:
            mm, dd, yyyy = match.groups()
            date_iso = f"{yyyy}-{mm}-{dd}"
        else:
            flags.append(
                ReviewFlag(
                    code="unclear_date",
                    message=f"Date '{raw_date}' could not be parsed as MM/DD/YYYY.",
                    severity=ReviewSeverity.WARNING,
                    row_number=row_number,
                )
            )

        amount_val = self._parse_decimal(amount_str)
        balance_val = self._parse_decimal(balance_str)

        if amount_val is None:
            debit, credit, amount = None, None, Decimal("0.00")
            flags.append(
                ReviewFlag(
                    code="unclear_amount",
                    message=f"Amount '{amount_str}' is unclear.",
                    severity=ReviewSeverity.WARNING,
                    row_number=row_number,
                )
            )
        else:
            amount = amount_val
            if amount_val < 0:
                debit = abs(amount_val)
                credit = None
            else:
                debit = None
                credit = amount_val

        if balance_val is None:
            flags.append(
                ReviewFlag(
                    code="missing_balance",
                    message="Transaction balance is missing.",
                    severity=ReviewSeverity.WARNING,
                    row_number=row_number,
                )
            )

        return Transaction(
            transaction_date=date_iso,
            value_date=None,
            description=desc,
            reference=None,
            debit=debit,
            credit=credit,
            amount=amount,
            balance=balance_val,
            currency=currency,
            confidence=1.0 if not flags else 0.8,
            review_flags=flags,
        )

    def _parse_decimal(self, val_str: str) -> Decimal | None:
        cleaned = val_str.replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
