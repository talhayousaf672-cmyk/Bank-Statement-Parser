"""Simple PySide6 desktop window for parsing and exporting statements."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bank_parser.core.models import Language, ParseResult
from bank_parser.desktop.workers import EnrichWorker, ParseWorker, list_bank_ids
from bank_parser.export.excel_writer import write_excel
from bank_parser.validation.review_queue import ReviewQueueItem, build_review_queue
from bank_parser.validation.summary import ValidationSummary, summarize_validation

_LANGUAGE_LABELS = {
    "English": Language.ENGLISH,
    "Arabic": Language.ARABIC,
    "Urdu": Language.URDU,
    "Russian": Language.RUSSIAN,
    "Spanish": Language.SPANISH,
    "Hindi": Language.HINDI,
}

_BANK_LABELS = {
    "generic_english": "Auto-Detect",
    "hbl": "HBL",
    "meezan_bank": "Meezan Bank",
    "ubl": "UBL",
    "mcb_bank": "MCB Bank",
    "allied_bank": "Allied Bank",
    "bank_alfalah": "Bank Alfalah",
    "chase_bank": "Chase Bank",
    "wells_fargo": "Wells Fargo",
    "bank_of_america": "Bank of America",
}

_BANK_ORDER = [
    "generic_english",
    "hbl",
    "meezan_bank",
    "ubl",
    "mcb_bank",
    "allied_bank",
    "bank_alfalah",
    "chase_bank",
    "wells_fargo",
    "bank_of_america",
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bank Statement Parser")
        self.resize(1050, 720)

        self._parse_result: ParseResult | None = None
        self._summary: ValidationSummary | None = None
        self._review_items: list[ReviewQueueItem] = []
        self._parse_worker: ParseWorker | None = None
        self._enrich_worker: EnrichWorker | None = None

        self._build_ui()
        self._apply_style()
        self._reset_result_state()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Bank Statement Parser")
        title.setObjectName("title")
        layout.addWidget(title)

        layout.addLayout(self._build_input_row())
        layout.addWidget(self._build_status_card())
        layout.addWidget(self._build_review_card())
        layout.addWidget(self._build_transaction_table(), stretch=1)
        layout.addWidget(self._build_flags_table())
        layout.addLayout(self._build_action_row())

    def _build_input_row(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)

        self._pdf_path = QLineEdit()
        self._pdf_path.setReadOnly(True)
        self._pdf_path.setPlaceholderText("Choose a PDF statement")

        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._choose_pdf)

        self._bank_select = QComboBox()
        for bank_id in self._ordered_bank_ids():
            self._bank_select.addItem(_BANK_LABELS.get(bank_id, bank_id), bank_id)

        self._language_select = QComboBox()
        for label, language in _LANGUAGE_LABELS.items():
            self._language_select.addItem(label, language)

        self._parse_btn = QPushButton("Parse Statement")
        self._parse_btn.clicked.connect(self._parse_pdf)

        grid.addWidget(QLabel("PDF"), 0, 0)
        grid.addWidget(self._pdf_path, 0, 1)
        grid.addWidget(browse_btn, 0, 2)
        grid.addWidget(QLabel("Bank"), 1, 0)
        grid.addWidget(self._bank_select, 1, 1)
        grid.addWidget(QLabel("Output Language"), 1, 2)
        grid.addWidget(self._language_select, 1, 3)
        grid.addWidget(self._parse_btn, 1, 4)
        return grid

    def _build_status_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setColumnStretch(5, 1)

        self._bank_label = QLabel("Bank: -")
        self._account_label = QLabel("Account: -")
        self._currency_label = QLabel("Currency: -")
        self._period_label = QLabel("Period: -")
        self._status_label = QLabel("Ready")
        self._status_label.setObjectName("statusBadge")

        self._total_label = QLabel("0")
        self._clean_label = QLabel("0")
        self._warning_label = QLabel("0")
        self._error_label = QLabel("0")

        for index, (caption, value) in enumerate(
            (
                ("Transactions", self._total_label),
                ("Clean", self._clean_label),
                ("Warnings", self._warning_label),
                ("Errors", self._error_label),
            )
        ):
            grid.addWidget(QLabel(caption), 0, index)
            value.setObjectName("number")
            grid.addWidget(value, 1, index)

        grid.addWidget(self._status_label, 0, 4, 2, 1)
        grid.addWidget(self._bank_label, 2, 0)
        grid.addWidget(self._account_label, 2, 1)
        grid.addWidget(self._currency_label, 2, 2)
        grid.addWidget(self._period_label, 2, 3, 1, 2)
        return card

    def _build_review_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)

        row = QHBoxLayout()
        self._review_title = QLabel("Review: no flags")
        self._review_title.setObjectName("reviewTitle")
        self._review_counts = QLabel("0 errors, 0 warnings")
        row.addWidget(self._review_title)
        row.addStretch()
        row.addWidget(self._review_counts)
        layout.addLayout(row)

        self._toggle_flags_btn = QPushButton("Show all review flags")
        self._toggle_flags_btn.clicked.connect(self._toggle_flags)
        layout.addWidget(self._toggle_flags_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        return card

    def _build_transaction_table(self) -> QTableWidget:
        self._tx_table = QTableWidget(0, 7)
        self._tx_table.setHorizontalHeaderLabels(
            ["#", "Date", "Description", "Reference", "Debit", "Credit", "Balance"]
        )
        self._tx_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tx_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tx_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tx_table.setAlternatingRowColors(True)
        return self._tx_table

    def _build_flags_table(self) -> QTableWidget:
        self._flags_table = QTableWidget(0, 4)
        self._flags_table.setHorizontalHeaderLabels(["Row", "Severity", "Issue", "Message"])
        self._flags_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._flags_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._flags_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._flags_table.setAlternatingRowColors(True)
        self._flags_table.hide()
        return self._flags_table

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self._message = QLabel("Ready.")
        self._message.setObjectName("message")
        self._export_btn = QPushButton("Export to Excel")
        self._export_btn.clicked.connect(self._export_excel)
        self._enrich_btn = QPushButton("Enrich with AI")
        self._enrich_btn.clicked.connect(self._enrich)

        row.addWidget(self._message)
        row.addStretch()
        row.addWidget(self._export_btn)
        row.addWidget(self._enrich_btn)
        return row

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QLabel#title { font-size: 18px; font-weight: 600; color: #111111; }
            QLabel#number { font-size: 20px; font-weight: 600; font-family: Consolas, monospace; color: #111111; }
            QLabel#reviewTitle { font-weight: 600; color: #111111; }
            QLabel#message { color: #666666; }
            QLabel#statusBadge { border: 1px solid #166534; color: #166534; padding: 8px 14px; background: #ffffff; }
            QFrame#card { border: 1px solid #e0e0e0; background: #ffffff; }
            QTableWidget { background: #ffffff; color: #111111; alternate-background-color: #f7f7f7; }
            QHeaderView::section { background: #f5f5f5; color: #111111; padding: 6px; }
            """
        )

    def _ordered_bank_ids(self) -> list[str]:
        available = set(list_bank_ids())
        ordered = [bank_id for bank_id in _BANK_ORDER if bank_id in available]
        ordered.extend(sorted(available.difference(ordered)))
        return ordered

    def _selected_bank_id(self) -> str:
        return str(self._bank_select.currentData())

    def _selected_language(self) -> Language:
        data = self._language_select.currentData()
        if isinstance(data, Language):
            return data
        if isinstance(data, str):
            try:
                return Language(data)
            except ValueError:
                return _LANGUAGE_LABELS.get(self._language_select.currentText(), Language.ENGLISH)
        return _LANGUAGE_LABELS.get(self._language_select.currentText(), Language.ENGLISH)

    def _reset_result_state(self) -> None:
        self._parse_result = None
        self._summary = None
        self._review_items = []
        self._parse_btn.setEnabled(bool(self._pdf_path.text()))
        self._export_btn.setEnabled(False)
        self._enrich_btn.setEnabled(False)
        self._toggle_flags_btn.setEnabled(False)
        self._tx_table.setRowCount(0)
        self._flags_table.setRowCount(0)
        self._flags_table.hide()
        self._total_label.setText("0")
        self._clean_label.setText("0")
        self._warning_label.setText("0")
        self._error_label.setText("0")
        self._status_label.setText("Ready")
        self._status_label.setStyleSheet(
            "border: 1px solid #166534; color: #166534; padding: 8px 14px;"
        )
        self._bank_label.setText("Bank: -")
        self._account_label.setText("Account: -")
        self._currency_label.setText("Currency: -")
        self._period_label.setText("Period: -")
        self._review_title.setText("Review: no flags")
        self._review_counts.setText("0 errors, 0 warnings")
        self._message.setText("Ready.")

    def _choose_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        self._pdf_path.setText(path)
        self._reset_result_state()
        self._parse_btn.setEnabled(True)

    def _parse_pdf(self) -> None:
        pdf_path = Path(self._pdf_path.text())
        if not pdf_path.exists():
            QMessageBox.warning(self, "Missing PDF", "Please choose a valid PDF first.")
            return

        self._parse_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
        self._enrich_btn.setEnabled(False)
        self._message.setText("Parsing statement...")

        self._parse_worker = ParseWorker(pdf_path, self._selected_bank_id())
        self._parse_worker.finished.connect(self._parse_done)
        self._parse_worker.error.connect(self._parse_error)
        self._parse_worker.start()

    def _parse_done(self, result: ParseResult, summary: ValidationSummary) -> None:
        self._parse_result = result
        self._summary = summary
        self._review_items = build_review_queue(result, statement_id=result.metadata.bank_id)

        self._render_summary(result, summary)
        self._render_review()
        self._render_transactions(result)
        self._render_flags()

        self._parse_btn.setEnabled(True)
        self._export_btn.setEnabled(True)
        self._enrich_btn.setEnabled(True)
        self._export_btn.setText("Export with Review Flags" if not summary.export_ready else "Export to Excel")
        self._message.setText(f"Parsed {summary.total_rows} transactions.")

    def _parse_error(self, message: str) -> None:
        self._parse_btn.setEnabled(True)
        self._message.setText("Parse failed.")
        QMessageBox.critical(self, "Parse Error", message)

    def _enrich(self) -> None:
        if self._parse_result is None:
            return

        self._enrich_btn.setEnabled(False)
        self._message.setText("Enriching descriptions...")
        self._enrich_worker = EnrichWorker(self._parse_result, self._selected_language())
        self._enrich_worker.finished.connect(self._enrich_done)
        self._enrich_worker.error.connect(self._enrich_error)
        self._enrich_worker.start()

    def _enrich_done(self, result: ParseResult) -> None:
        self._parse_result = result
        self._summary = summarize_validation(result)
        self._render_transactions(result)
        self._enrich_btn.setEnabled(True)
        self._message.setText("Descriptions enriched.")

    def _enrich_error(self, message: str) -> None:
        self._enrich_btn.setEnabled(True)
        self._message.setText("AI enrichment unavailable.")
        QMessageBox.warning(self, "AI Enrichment", message)

    def _export_excel(self) -> None:
        if self._parse_result is None:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Excel File",
            self._default_export_path(),
            "Excel Files (*.xlsx)",
        )
        if not path:
            return

        output_path = Path(path)
        if output_path.suffix.lower() != ".xlsx":
            output_path = output_path.with_suffix(".xlsx")

        try:
            write_excel(self._parse_result, output_path, language=self._selected_language())
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
            return

        self._message.setText(f"Exported: {output_path}")
        QMessageBox.information(self, "Export Complete", f"Saved to:\n{output_path}")

    def _default_export_path(self) -> str:
        if self._parse_result is None:
            return "statement.xlsx"

        meta = self._parse_result.metadata
        parts = [meta.bank_id or "statement"]
        if meta.statement_period_start:
            parts.append(str(meta.statement_period_start))
        if meta.statement_period_end:
            parts.append(str(meta.statement_period_end))
        if len(parts) == 1 and meta.account_number:
            parts.append(meta.account_number[-4:])
        filename = "_".join(_filename_part(part) for part in parts if part)
        return str(Path.home() / "Downloads" / f"{filename}.xlsx")

    def _toggle_flags(self) -> None:
        show = not self._flags_table.isVisible()
        self._flags_table.setVisible(show)
        self._toggle_flags_btn.setText(
            "Hide review flags" if show else f"Show all {len(self._review_items)} review flags"
        )

    def _render_summary(self, result: ParseResult, summary: ValidationSummary) -> None:
        self._total_label.setText(str(summary.total_rows))
        self._clean_label.setText(str(summary.clean_rows))
        self._warning_label.setText(str(summary.warning_rows))
        self._error_label.setText(str(summary.error_rows))

        if not summary.export_ready:
            text, color = "Needs review", "#b91c1c"
        elif summary.warning_rows or summary.statement_flag_count:
            text, color = "Ready with warnings", "#92400e"
        else:
            text, color = "Ready", "#166534"
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"border: 1px solid {color}; color: {color}; padding: 8px 14px;")

        meta = result.metadata
        self._bank_label.setText(f"Bank: {meta.bank_id.replace('_', ' ')}")
        self._account_label.setText(f"Account: {meta.account_number or '-'}")
        self._currency_label.setText(f"Currency: {meta.currency or '-'}")
        start = meta.statement_period_start
        end = meta.statement_period_end
        self._period_label.setText(f"Period: {start or '-'} / {end or '-'}")

    def _render_review(self) -> None:
        errors = [item for item in self._review_items if item.flag.severity.value == "error"]
        warnings = [item for item in self._review_items if item.flag.severity.value != "error"]

        self._review_counts.setText(f"{len(errors)} errors, {len(warnings)} warnings")
        self._toggle_flags_btn.setEnabled(bool(self._review_items))
        self._toggle_flags_btn.setText(f"Show all {len(self._review_items)} review flags")
        self._flags_table.hide()

        if not self._review_items:
            self._review_title.setText("Review: no flags")
            return

        if errors:
            self._review_title.setText("Review: needs attention")
        else:
            self._review_title.setText("Review: ready with warnings")

    def _render_transactions(self, result: ParseResult) -> None:
        self._tx_table.setRowCount(0)
        for index, tx in enumerate(result.transactions, start=1):
            self._tx_table.insertRow(index - 1)
            values = [
                str(index),
                str(tx.transaction_date) if tx.transaction_date else "-",
                tx.description,
                tx.reference or "",
                _money(tx.debit),
                _money(tx.credit),
                _money(tx.balance),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col in {0, 4, 5, 6}:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._tx_table.setItem(index - 1, col, cell)

    def _render_flags(self) -> None:
        self._flags_table.setRowCount(0)
        for row, item in enumerate(self._review_items):
            self._flags_table.insertRow(row)
            values = [
                str(item.row_number or "Statement"),
                item.flag.severity.value,
                item.flag.code.replace("_", " ").title(),
                item.flag.message,
            ]
            for col, value in enumerate(values):
                self._flags_table.setItem(row, col, QTableWidgetItem(value))


def _money(value) -> str:
    if value is None:
        return ""
    return f"{float(value):,.2f}"


def _filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    return cleaned.strip("._") or "statement"
