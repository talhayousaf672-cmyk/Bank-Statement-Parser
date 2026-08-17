"""Generic English statement parser implementation."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
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
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class GenericEnglishBankParser(BaseBankParser):
    bank_id = "generic_english"
    language = Language.SPANISH

    def parse(self, normalized_text: str) -> ParseResult:
        lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
        
        # 1. Parse Statement Metadata
        account_number = self._extract_regex(_ACCOUNT_RE, normalized_text)
        currency = self._extract_regex(_CURRENCY_RE, normalized_text)
        statement_period = self._extract_regex(_PERIOD_RE, normalized_text)

        metadata_flags: list[ReviewFlag] = []
        if not account_number:
            metadata_flags.append(
                ReviewFlag(
                    code="missing_required_field",
                    message="Statement account number could not be identified.",
                    severity=ReviewSeverity.WARNING,
                )
            )

        metadata = StatementMetadata(
            bank_id=self.bank_id,
            language=self.language,
            account_number=account_number,
            currency=currency,
            statement_period=statement_period,
        )

        # 2. Parse Transactions
        transactions: list[Transaction] = []
        row_number = 0

        for line in lines:
            if line.startswith("Bank Name:") or line.startswith("Account Number:") or line.startswith("Currency:") or line.startswith("Statement Period:"):
                continue
            if "Date" in line and "Description" in line:
                continue

            # Check for pipe-delimited line format
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 6:
                    row_number += 1
                    tx = self._parse_pipe_row(parts, currency, row_number)
                    if tx:
                        transactions.append(tx)
                    continue

            # Check for space/tab delimited row format
            # e.g., 2026-01-05 Opening Deposit REF1001 1000.00 1000.00
            tokens = line.split()
            if len(tokens) >= 4 and _DATE_RE.match(tokens[0]):
                row_number += 1
                tx = self._parse_space_row(tokens, line, currency, row_number)
                if tx:
                    transactions.append(tx)
                continue

            # Continuation line for multiline description
            if transactions and not line.startswith("Page"):
                last_tx = transactions[-1]
                updated_desc = f"{last_tx.description} {line}".strip()
                transactions[-1] = last_tx.model_copy(update={"description": updated_desc})

        if not transactions and not account_number and not currency:
            metadata_flags.append(
                ReviewFlag(
                    code="unsupported_layout",
                    message="Statement text layout was not recognized by the generic parser.",
                    severity=ReviewSeverity.ERROR,
                )
            )

        return ParseResult(
            metadata=metadata,
            transactions=transactions,
            review_flags=metadata_flags,
        )


    def _extract_regex(self, pattern: re.Pattern[str], text: str) -> str | None:
        match = pattern.search(text)
        return match.group(1).strip() if match else None

    def _parse_pipe_row(
        self, parts: list[str], currency: str | None, row_number: int
    ) -> Transaction | None:
        date_str, desc, ref, debit_str, credit_str, balance_str = parts[:6]
        flags: list[ReviewFlag] = []

        if not _DATE_RE.match(date_str):
            flags.append(
                ReviewFlag(
                    code="unclear_date",
                    message=f"Date '{date_str}' format is unclear.",
                    severity=ReviewSeverity.WARNING,
                    row_number=row_number,
                )
            )

        debit = self._parse_decimal(debit_str)
        credit = self._parse_decimal(credit_str)
        balance = self._parse_decimal(balance_str)

        if debit is None and credit is None:
            amount = Decimal("0.00")
            flags.append(
                ReviewFlag(
                    code="unclear_amount",
                    message="Neither debit nor credit amount could be parsed.",
                    severity=ReviewSeverity.WARNING,
                    row_number=row_number,
                )
            )
        elif debit is not None:
            amount = -debit
        else:
            amount = credit if credit is not None else Decimal("0.00")

        return Transaction(
            transaction_date=date_str if _DATE_RE.match(date_str) else None,
            value_date=None,
            description=desc,
            reference=ref if ref else None,
            debit=debit,
            credit=credit,
            amount=amount,
            balance=balance,
            currency=currency,
            confidence=1.0 if not flags else 0.8,
            review_flags=flags,
        )

    def _parse_space_row(
        self, tokens: list[str], raw_line: str, currency: str | None, row_number: int
    ) -> Transaction:
        date_str = tokens[0]
        flags: list[ReviewFlag] = []

        balance = self._parse_decimal(tokens[-1])
        amount_val = self._parse_decimal(tokens[-2])

        if amount_val is not None:
            debit = -amount_val if amount_val < 0 else None
            credit = amount_val if amount_val > 0 else None
            amount = amount_val
            desc = " ".join(tokens[1:-2])
        else:
            debit, credit, amount = None, None, Decimal("0.00")
            desc = " ".join(tokens[1:-1])
            flags.append(
                ReviewFlag(
                    code="unclear_amount",
                    message="Could not parse transaction amount.",
                    severity=ReviewSeverity.WARNING,
                    row_number=row_number,
                )
            )

        return Transaction(
            transaction_date=date_str,
            value_date=None,
            description=desc,
            reference=None,
            debit=debit,
            credit=credit,
            amount=amount,
            balance=balance,
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
