"""Interactive PySide6 desktop window for bulk parsing, HITL review, and export."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont
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
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bank_parser.core.models import (
    Language,
    ParseResult,
    ReviewFlag,
    ReviewSeverity,
    StatementMetadata,
    Transaction,
)
from bank_parser.desktop.workers import (
    BatchParseWorker,
    EnrichWorker,
    ParseWorker,
    list_bank_ids,
    parse_pdf_statement,
)
from bank_parser.export.csv_writer import write_bulk_csv, write_csv
from bank_parser.export.excel_writer import write_excel
from bank_parser.validation.reconciliation import validate_parse_result
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


class StatementEntry:
    """Represents a single statement in the batch queue."""

    def __init__(self, pdf_path: Path) -> None:
        self.pdf_path = pdf_path
        self.parse_result: ParseResult | None = None
        self.summary: ValidationSummary | None = None
        self.review_items: list[ReviewQueueItem] = []
        self.status: str = "Queued"
        self.error_message: str = ""


class MainWindow(QMainWindow):
    """Main desktop application window with batch parsing and HITL editing."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bank Statement Parser — Bulk & HITL Studio")
        self.resize(1200, 800)

        self._statements: dict[str, StatementEntry] = {}
        self._active_path: Path | None = None
        self._is_updating_table = False

        self._batch_worker: BatchParseWorker | None = None
        self._enrich_worker: EnrichWorker | None = None

        self._build_ui()
        self._apply_style()
        self._update_ui_state()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        # Header bar
        header_row = QHBoxLayout()
        title = QLabel("Bank Statement Parser Studio")
        title.setObjectName("title")
        header_row.addWidget(title)
        header_row.addStretch()

        header_row.addWidget(QLabel("Output Language:"))
        self._language_select = QComboBox()
        for label, language in _LANGUAGE_LABELS.items():
            self._language_select.addItem(label, language)
        header_row.addWidget(self._language_select)

        header_row.addWidget(QLabel("Default Bank:"))
        self._bank_select = QComboBox()
        for bank_id in self._ordered_bank_ids():
            self._bank_select.addItem(_BANK_LABELS.get(bank_id, bank_id), bank_id)
        header_row.addWidget(self._bank_select)

        main_layout.addLayout(header_row)

        # Splitter: Left Sidebar (Queue) | Right Workspace (HITL Editor)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar_widget = self._build_sidebar()
        editor_widget = self._build_editor()

        splitter.addWidget(sidebar_widget)
        splitter.addWidget(editor_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter, stretch=1)
        main_layout.addLayout(self._build_action_row())

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("card")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        lbl = QLabel("Statements Queue")
        lbl.setObjectName("sectionLabel")
        layout.addWidget(lbl)

        # Button row: Add PDFs, Clear
        btn_row = QHBoxLayout()
        self._add_files_btn = QPushButton("➕ Add PDF(s)")
        self._add_files_btn.clicked.connect(self._choose_pdfs)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear_queue)
        btn_row.addWidget(self._add_files_btn)
        btn_row.addWidget(self._clear_btn)
        layout.addLayout(btn_row)

        # List Widget
        self._queue_list = QListWidget()
        self._queue_list.currentItemChanged.connect(self._on_statement_selected)
        layout.addWidget(self._queue_list, stretch=1)

        # Parse buttons
        self._parse_all_btn = QPushButton("⚡ Parse All Statements")
        self._parse_all_btn.setObjectName("primaryBtn")
        self._parse_all_btn.clicked.connect(self._parse_all)
        layout.addWidget(self._parse_all_btn)

        self._parse_selected_btn = QPushButton("Parse Selected Only")
        self._parse_selected_btn.clicked.connect(self._parse_active)
        layout.addWidget(self._parse_selected_btn)

        return panel

    def _build_editor(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(self._build_metadata_card())
        layout.addWidget(self._build_review_card())

        # Table & Table tools header
        table_header_row = QHBoxLayout()
        tbl_lbl = QLabel("Transactions (Double-click any cell to edit)")
        tbl_lbl.setObjectName("sectionLabel")
        table_header_row.addWidget(tbl_lbl)
        table_header_row.addStretch()

        self._add_row_btn = QPushButton("➕ Add Row")
        self._add_row_btn.clicked.connect(self._add_transaction_row)
        self._del_row_btn = QPushButton("🗑️ Delete Selected Row")
        self._del_row_btn.clicked.connect(self._delete_transaction_row)
        self._recalc_btn = QPushButton("🔄 Re-Validate")
        self._recalc_btn.clicked.connect(self._revalidate_active)

        table_header_row.addWidget(self._add_row_btn)
        table_header_row.addWidget(self._del_row_btn)
        table_header_row.addWidget(self._recalc_btn)
        layout.addLayout(table_header_row)

        layout.addWidget(self._build_transaction_table(), stretch=1)
        layout.addWidget(self._build_flags_table())

        return panel

    def _build_metadata_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setColumnStretch(6, 1)

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

        self._status_badge = QLabel("No Statement Loaded")
        self._status_badge.setObjectName("statusBadge")
        grid.addWidget(self._status_badge, 0, 4, 2, 2)

        # Metadata fields (Editable)
        grid.addWidget(QLabel("Bank ID:"), 2, 0)
        self._meta_bank = QLineEdit("-")
        self._meta_bank.editingFinished.connect(self._on_metadata_edited)
        grid.addWidget(self._meta_bank, 2, 1)

        grid.addWidget(QLabel("Account Holder:"), 2, 2)
        self._meta_holder = QLineEdit("-")
        self._meta_holder.editingFinished.connect(self._on_metadata_edited)
        grid.addWidget(self._meta_holder, 2, 3)

        grid.addWidget(QLabel("Account No:"), 2, 4)
        self._meta_account = QLineEdit("-")
        self._meta_account.editingFinished.connect(self._on_metadata_edited)
        grid.addWidget(self._meta_account, 2, 5)

        grid.addWidget(QLabel("Currency:"), 3, 0)
        self._meta_currency = QLineEdit("-")
        self._meta_currency.editingFinished.connect(self._on_metadata_edited)
        grid.addWidget(self._meta_currency, 3, 1)

        grid.addWidget(QLabel("Period Start:"), 3, 2)
        self._meta_start = QLineEdit("-")
        self._meta_start.editingFinished.connect(self._on_metadata_edited)
        grid.addWidget(self._meta_start, 3, 3)

        grid.addWidget(QLabel("Period End:"), 3, 4)
        self._meta_end = QLineEdit("-")
        self._meta_end.editingFinished.connect(self._on_metadata_edited)
        grid.addWidget(self._meta_end, 3, 5)

        return card

    def _build_review_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)

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
        self._tx_table = QTableWidget(0, 8)
        self._tx_table.setHorizontalHeaderLabels(
            ["#", "Date", "Value Date", "Description", "Reference", "Debit", "Credit", "Balance"]
        )
        self._tx_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        # Enable inline cell editing
        self._tx_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self._tx_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tx_table.setAlternatingRowColors(True)
        self._tx_table.itemChanged.connect(self._on_cell_edited)
        return self._tx_table

    def _build_flags_table(self) -> QTableWidget:
        self._flags_table = QTableWidget(0, 5)
        self._flags_table.setHorizontalHeaderLabels(["Row", "Severity", "Issue", "Message", "Action"])
        self._flags_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._flags_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._flags_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._flags_table.setAlternatingRowColors(True)
        self._flags_table.hide()
        return self._flags_table

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()

        self._message = QLabel("Ready. Load PDF statements to begin.")
        self._message.setObjectName("message")

        self._export_single_btn = QPushButton("Export Active (Excel)")
        self._export_single_btn.clicked.connect(lambda: self._export_statement("excel"))

        self._export_single_csv_btn = QPushButton("Export Active (CSV)")
        self._export_single_csv_btn.clicked.connect(lambda: self._export_statement("csv"))

        self._bulk_export_btn = QPushButton("📦 Bulk Export All (Excel)")
        self._bulk_export_btn.clicked.connect(lambda: self._bulk_export("excel"))

        self._bulk_export_csv_btn = QPushButton("📦 Bulk Export All (CSV)")
        self._bulk_export_csv_btn.clicked.connect(lambda: self._bulk_export("csv"))

        self._enrich_btn = QPushButton("✨ AI Description Enrichment")
        self._enrich_btn.clicked.connect(self._enrich_active)

        row.addWidget(self._message)
        row.addStretch()
        row.addWidget(self._export_single_csv_btn)
        row.addWidget(self._export_single_btn)
        row.addWidget(self._bulk_export_csv_btn)
        row.addWidget(self._bulk_export_btn)
        row.addWidget(self._enrich_btn)
        return row

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QLabel#title { font-size: 18px; font-weight: 600; color: #111111; }
            QLabel#sectionLabel { font-size: 12px; font-weight: 600; text-transform: uppercase; color: #444444; }
            QLabel#number { font-size: 20px; font-weight: 600; font-family: Consolas, monospace; color: #111111; }
            QLabel#reviewTitle { font-weight: 600; color: #111111; }
            QLabel#message { color: #555555; }
            QLabel#statusBadge { border: 1px solid #166534; color: #166534; padding: 6px 12px; background: #ffffff; font-weight: 500; }
            QFrame#card { border: 1px solid #e0e0e0; background: #ffffff; border-radius: 4px; }
            QTableWidget { background: #ffffff; color: #111111; alternate-background-color: #fafafa; gridline-color: #ebebeb; }
            QHeaderView::section { background: #f0f0f0; color: #111111; padding: 6px; border: 1px solid #e0e0e0; font-weight: 600; }
            QPushButton#primaryBtn { background: #1f3864; color: #ffffff; font-weight: 600; padding: 6px 12px; }
            QListWidget { background: #ffffff; border: 1px solid #e0e0e0; }
            QListWidget::item:selected { background: #e8f0fe; color: #1f3864; font-weight: 600; }
            """
        )

    # -----------------------------------------------------------------------
    # Queue and Multi-File Handling
    # -----------------------------------------------------------------------

    def _choose_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select PDF Statements", "", "PDF Files (*.pdf)")
        if not paths:
            return

        for p_str in paths:
            p = Path(p_str)
            if p.name not in self._statements:
                entry = StatementEntry(p)
                self._statements[p.name] = entry

                item = QListWidgetItem(f"📄 {p.name}\n   Status: Queued")
                item.setData(Qt.ItemDataRole.UserRole, p.name)
                self._queue_list.addItem(item)

        if not self._active_path and self._statements:
            first_key = next(iter(self._statements))
            self._queue_list.setCurrentRow(0)

        self._message.setText(f"Added {len(paths)} statement(s) to queue.")
        self._update_ui_state()

    def _clear_queue(self) -> None:
        self._statements.clear()
        self._queue_list.clear()
        self._active_path = None
        self._reset_active_editor()
        self._update_ui_state()
        self._message.setText("Queue cleared.")

    def _on_statement_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if not current:
            return
        filename = str(current.data(Qt.ItemDataRole.UserRole))
        entry = self._statements.get(filename)
        if not entry:
            return

        self._active_path = entry.pdf_path
        if entry.parse_result and entry.summary:
            self._render_active_statement(entry.parse_result, entry.summary)
        else:
            self._reset_active_editor(entry.pdf_path.name)

        self._update_ui_state()

    def _update_queue_item_label(self, filename: str) -> None:
        entry = self._statements.get(filename)
        if not entry:
            return

        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == filename:
                if entry.parse_result:
                    bank_name = _BANK_LABELS.get(entry.parse_result.metadata.bank_id, entry.parse_result.metadata.bank_id)
                    tx_count = len(entry.parse_result.transactions)
                    status_str = entry.summary.export_readiness.value if entry.summary else "parsed"
                    item.setText(f"📄 {filename}\n   {bank_name} | {tx_count} txs | {status_str}")
                elif entry.error_message:
                    item.setText(f"📄 {filename}\n   ❌ Error: {entry.error_message[:20]}")
                else:
                    item.setText(f"📄 {filename}\n   Status: {entry.status}")
                break

    # -----------------------------------------------------------------------
    # Parsing Pipeline
    # -----------------------------------------------------------------------

    def _parse_all(self) -> None:
        if not self._statements:
            QMessageBox.information(self, "No PDFs", "Please add one or more PDF statements first.")
            return

        paths_to_parse = [e.pdf_path for e in self._statements.values()]
        self._parse_all_btn.setEnabled(False)
        self._parse_selected_btn.setEnabled(False)
        self._message.setText("Parsing batch of statements...")

        self._batch_worker = BatchParseWorker(paths_to_parse, self._selected_bank_id())
        self._batch_worker.file_started.connect(self._on_batch_file_started)
        self._batch_worker.file_finished.connect(self._on_batch_file_finished)
        self._batch_worker.file_error.connect(self._on_batch_file_error)
        self._batch_worker.all_finished.connect(self._on_batch_all_finished)
        self._batch_worker.start()

    def _parse_active(self) -> None:
        if not self._active_path:
            return

        entry = self._statements.get(self._active_path.name)
        if not entry:
            return

        self._message.setText(f"Parsing {self._active_path.name}...")
        self._parse_selected_btn.setEnabled(False)

        worker = ParseWorker(self._active_path, self._selected_bank_id())
        worker.finished.connect(lambda res, sumry: self._on_single_parse_done(entry, res, sumry))
        worker.error.connect(lambda err: self._on_single_parse_error(entry, err))
        worker.start()

    def _on_batch_file_started(self, path: Path, current: int, total: int) -> None:
        self._message.setText(f"Parsing ({current}/{total}): {path.name}...")

    def _on_batch_file_finished(self, path: Path, result: ParseResult, summary: ValidationSummary) -> None:
        entry = self._statements.get(path.name)
        if entry:
            entry.parse_result = result
            entry.summary = summary
            entry.status = "Parsed"
            entry.review_items = build_review_queue(result, statement_id=result.metadata.bank_id)
            self._update_queue_item_label(path.name)

            if self._active_path == path:
                self._render_active_statement(result, summary)

    def _on_batch_file_error(self, path: Path, error_msg: str) -> None:
        entry = self._statements.get(path.name)
        if entry:
            entry.error_message = error_msg
            entry.status = "Error"
            self._update_queue_item_label(path.name)

    def _on_batch_all_finished(self, _results: dict) -> None:
        self._parse_all_btn.setEnabled(True)
        self._parse_selected_btn.setEnabled(True)
        self._update_ui_state()
        self._message.setText("Batch parsing complete. Ready for review and editing.")

    def _on_single_parse_done(self, entry: StatementEntry, result: ParseResult, summary: ValidationSummary) -> None:
        entry.parse_result = result
        entry.summary = summary
        entry.status = "Parsed"
        entry.review_items = build_review_queue(result, statement_id=result.metadata.bank_id)
        self._update_queue_item_label(entry.pdf_path.name)

        if self._active_path == entry.pdf_path:
            self._render_active_statement(result, summary)

        self._parse_selected_btn.setEnabled(True)
        self._update_ui_state()
        self._message.setText(f"Parsed {entry.pdf_path.name} ({summary.total_rows} transactions).")

    def _on_single_parse_error(self, entry: StatementEntry, error_msg: str) -> None:
        entry.error_message = error_msg
        entry.status = "Error"
        self._update_queue_item_label(entry.pdf_path.name)
        self._parse_selected_btn.setEnabled(True)
        self._message.setText(f"Error parsing {entry.pdf_path.name}.")
        QMessageBox.critical(self, "Parse Error", error_msg)

    # -----------------------------------------------------------------------
    # Rendering & HITL Interactive Editing
    # -----------------------------------------------------------------------

    def _render_active_statement(self, result: ParseResult, summary: ValidationSummary) -> None:
        self._is_updating_table = True
        meta = result.metadata

        # Update metadata card
        self._meta_bank.setText(meta.bank_id or "")
        self._meta_holder.setText(meta.account_holder or "")
        self._meta_account.setText(meta.account_number or "")
        self._meta_currency.setText(meta.currency or "")
        self._meta_start.setText(str(meta.statement_period_start) if meta.statement_period_start else "")
        self._meta_end.setText(str(meta.statement_period_end) if meta.statement_period_end else "")

        # Summary numbers
        self._total_label.setText(str(summary.total_rows))
        self._clean_label.setText(str(summary.clean_rows))
        self._warning_label.setText(str(summary.warning_rows))
        self._error_label.setText(str(summary.error_rows))

        status_text = summary.export_readiness.value.replace("_", " ").title()
        self._status_badge.setText(status_text)

        if summary.export_ready:
            self._status_badge.setStyleSheet("border: 1px solid #166534; color: #166534; padding: 6px 12px; background: #f0fdf4;")
        else:
            self._status_badge.setStyleSheet("border: 1px solid #b91c1c; color: #b91c1c; padding: 6px 12px; background: #fef2f2;")

        # Populate transaction table
        self._tx_table.setRowCount(len(result.transactions))
        for row_idx, tx in enumerate(result.transactions):
            # Row index (non-editable)
            item_idx = QTableWidgetItem(str(row_idx + 1))
            item_idx.setFlags(item_idx.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._tx_table.setItem(row_idx, 0, item_idx)

            # Date
            self._tx_table.setItem(row_idx, 1, QTableWidgetItem(str(tx.transaction_date) if tx.transaction_date else ""))

            # Value Date
            self._tx_table.setItem(row_idx, 2, QTableWidgetItem(str(tx.value_date) if tx.value_date else ""))

            # Description
            self._tx_table.setItem(row_idx, 3, QTableWidgetItem(tx.description or ""))

            # Reference
            self._tx_table.setItem(row_idx, 4, QTableWidgetItem(tx.reference or ""))

            # Debit
            self._tx_table.setItem(row_idx, 5, QTableWidgetItem(f"{float(tx.debit):.2f}" if tx.debit is not None else ""))

            # Credit
            self._tx_table.setItem(row_idx, 6, QTableWidgetItem(f"{float(tx.credit):.2f}" if tx.credit is not None else ""))

            # Balance
            self._tx_table.setItem(row_idx, 7, QTableWidgetItem(f"{float(tx.balance):.2f}" if tx.balance is not None else ""))

            # Flag highlight
            if tx.review_flags:
                has_error = any(f.severity == ReviewSeverity.ERROR for f in tx.review_flags)
                bg_color = QColor(254, 242, 242) if has_error else QColor(254, 252, 232)
                for col in range(8):
                    cell = self._tx_table.item(row_idx, col)
                    if cell:
                        cell.setBackground(bg_color)

        self._is_updating_table = False
        self._render_review_flags(result)

    def _render_review_flags(self, result: ParseResult) -> None:
        flags = []
        for idx, tx in enumerate(result.transactions, start=1):
            for f in tx.review_flags:
                flags.append((idx, f))

        self._flags_table.setRowCount(len(flags))
        for row, (line_no, flag) in enumerate(flags):
            self._flags_table.setItem(row, 0, QTableWidgetItem(str(flag.row_number or line_no)))
            self._flags_table.setItem(row, 1, QTableWidgetItem(flag.severity.value))
            self._flags_table.setItem(row, 2, QTableWidgetItem(flag.code))
            self._flags_table.setItem(row, 3, QTableWidgetItem(flag.message))

            dismiss_btn = QPushButton("Resolve")
            dismiss_btn.clicked.connect(lambda _, r=row, f_code=flag.code, l_no=line_no: self._dismiss_flag(l_no, f_code))
            self._flags_table.setCellWidget(row, 4, dismiss_btn)

        error_count = sum(1 for _, f in flags if f.severity == ReviewSeverity.ERROR)
        warning_count = sum(1 for _, f in flags if f.severity == ReviewSeverity.WARNING)

        self._review_counts.setText(f"{error_count} errors, {warning_count} warnings")
        if flags:
            self._review_title.setText(f"Review: {len(flags)} items require attention")
            self._toggle_flags_btn.setEnabled(True)
        else:
            self._review_title.setText("Review: All flags resolved (100% Clean)")
            self._toggle_flags_btn.setEnabled(False)
            self._flags_table.hide()

    def _on_cell_edited(self, item: QTableWidgetItem) -> None:
        if self._is_updating_table or not self._active_path:
            return

        entry = self._statements.get(self._active_path.name)
        if not entry or not entry.parse_result:
            return

        row = item.row()
        col = item.column()
        val = item.text().strip()

        if row >= len(entry.parse_result.transactions):
            return

        tx = entry.parse_result.transactions[row]

        # Column mappings: 1:Date, 2:ValueDate, 3:Description, 4:Reference, 5:Debit, 6:Credit, 7:Balance
        if col == 1:
            tx.transaction_date = _parse_date_str(val)
        elif col == 2:
            tx.value_date = _parse_date_str(val)
        elif col == 3:
            tx.description = val
        elif col == 4:
            tx.reference = val or None
        elif col == 5:
            d = _parse_decimal_str(val)
            tx.debit = d
            tx.amount = (tx.credit or Decimal("0.00")) - (d or Decimal("0.00"))
        elif col == 6:
            c = _parse_decimal_str(val)
            tx.credit = c
            tx.amount = (c or Decimal("0.00")) - (tx.debit or Decimal("0.00"))
        elif col == 7:
            tx.balance = _parse_decimal_str(val)

        # Clear existing flags on manual user edit and re-run reconciliation
        tx.review_flags = []
        self._revalidate_active()

    def _on_metadata_edited(self) -> None:
        if not self._active_path:
            return
        entry = self._statements.get(self._active_path.name)
        if not entry or not entry.parse_result:
            return

        meta = entry.parse_result.metadata
        meta.bank_id = self._meta_bank.text().strip() or meta.bank_id
        meta.account_holder = self._meta_holder.text().strip() or None
        meta.account_number = self._meta_account.text().strip() or None
        meta.currency = self._meta_currency.text().strip() or None
        meta.statement_period_start = _parse_date_str(self._meta_start.text())
        meta.statement_period_end = _parse_date_str(self._meta_end.text())

        self._revalidate_active()

    def _add_transaction_row(self) -> None:
        if not self._active_path:
            return
        entry = self._statements.get(self._active_path.name)
        if not entry or not entry.parse_result:
            return

        new_tx = Transaction(
            transaction_date=date.today(),
            description="New Transaction",
            amount=Decimal("0.00"),
            currency=entry.parse_result.metadata.currency or "PKR",
            confidence=1.0,
        )
        entry.parse_result.transactions.append(new_tx)
        self._revalidate_active()

    def _delete_transaction_row(self) -> None:
        if not self._active_path:
            return
        entry = self._statements.get(self._active_path.name)
        if not entry or not entry.parse_result:
            return

        selected_rows = sorted({idx.row() for idx in self._tx_table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            QMessageBox.information(self, "No Row Selected", "Please click a row in the table to delete.")
            return

        for r in selected_rows:
            if 0 <= r < len(entry.parse_result.transactions):
                entry.parse_result.transactions.pop(r)

        self._revalidate_active()

    def _dismiss_flag(self, line_no: int, code: str) -> None:
        if not self._active_path:
            return
        entry = self._statements.get(self._active_path.name)
        if not entry or not entry.parse_result:
            return

        tx_idx = line_no - 1
        if 0 <= tx_idx < len(entry.parse_result.transactions):
            tx = entry.parse_result.transactions[tx_idx]
            tx.review_flags = [f for f in tx.review_flags if f.code != code]

        self._revalidate_active()

    def _revalidate_active(self) -> None:
        if not self._active_path:
            return
        entry = self._statements.get(self._active_path.name)
        if not entry or not entry.parse_result:
            return

        entry.parse_result = validate_parse_result(entry.parse_result)
        entry.summary = summarize_validation(entry.parse_result)
        self._render_active_statement(entry.parse_result, entry.summary)
        self._update_queue_item_label(self._active_path.name)
        self._update_ui_state()

    def _reset_active_editor(self, filename: str = "") -> None:
        self._is_updating_table = True
        self._tx_table.setRowCount(0)
        self._flags_table.setRowCount(0)
        self._flags_table.hide()
        self._total_label.setText("0")
        self._clean_label.setText("0")
        self._warning_label.setText("0")
        self._error_label.setText("0")
        self._status_badge.setText("Ready to Parse" if filename else "No Statement Loaded")
        self._meta_bank.setText("-")
        self._meta_holder.setText("-")
        self._meta_account.setText("-")
        self._meta_currency.setText("-")
        self._meta_start.setText("-")
        self._meta_end.setText("-")
        self._review_title.setText("Review: no flags")
        self._review_counts.setText("0 errors, 0 warnings")
        self._is_updating_table = False

    def _toggle_flags(self) -> None:
        if self._flags_table.isVisible():
            self._flags_table.hide()
            self._toggle_flags_btn.setText("Show all review flags")
        else:
            self._flags_table.show()
            self._toggle_flags_btn.setText("Hide review flags")

    def _enrich_active(self) -> None:
        if not self._active_path:
            return
        entry = self._statements.get(self._active_path.name)
        if not entry or not entry.parse_result:
            return

        self._enrich_btn.setEnabled(False)
        self._message.setText("Enriching descriptions with AI...")

        self._enrich_worker = EnrichWorker(entry.parse_result, self._selected_language())
        self._enrich_worker.finished.connect(lambda res: self._on_enrich_done(entry, res))
        self._enrich_worker.error.connect(self._on_enrich_error)
        self._enrich_worker.start()

    def _on_enrich_done(self, entry: StatementEntry, result: ParseResult) -> None:
        entry.parse_result = result
        self._revalidate_active()
        self._enrich_btn.setEnabled(True)
        self._message.setText("AI Enrichment completed.")

    def _on_enrich_error(self, message: str) -> None:
        self._enrich_btn.setEnabled(True)
        self._message.setText("AI enrichment unavailable.")
        QMessageBox.warning(self, "AI Enrichment", message)

    # -----------------------------------------------------------------------
    # Export Actions (Single & Bulk)
    # -----------------------------------------------------------------------

    def _export_statement(self, fmt: str = "excel") -> None:
        if not self._active_path:
            return
        entry = self._statements.get(self._active_path.name)
        if not entry or not entry.parse_result:
            return

        default_name = f"{entry.parse_result.metadata.bank_id or 'statement'}_{self._active_path.stem}.{ 'xlsx' if fmt == 'excel' else 'csv' }"
        save_path = Path.home() / "Downloads" / default_name

        filter_str = "Excel Files (*.xlsx)" if fmt == "excel" else "CSV Files (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, f"Save {fmt.title()} File", str(save_path), filter_str)
        if not path:
            return

        output_path = Path(path)
        try:
            if fmt == "excel":
                write_excel(entry.parse_result, output_path, language=self._selected_language())
            else:
                write_csv(entry.parse_result, output_path, language=self._selected_language())
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
            return

        self._message.setText(f"Exported: {output_path.name}")
        QMessageBox.information(self, "Export Complete", f"Successfully exported to:\n{output_path}")

    def _bulk_export(self, fmt: str = "excel") -> None:
        parsed_entries = [e for e in self._statements.values() if e.parse_result]
        if not parsed_entries:
            QMessageBox.warning(self, "No Parsed Statements", "None of the loaded statements have been parsed yet.")
            return

        default_name = f"bulk_bank_statements.{ 'xlsx' if fmt == 'excel' else 'csv' }"
        save_path = Path.home() / "Downloads" / default_name

        filter_str = "Excel Files (*.xlsx)" if fmt == "excel" else "CSV Files (*.csv)"
        path, _ = QFileDialog.getSaveFileName(self, f"Save Consolidated {fmt.title()}", str(save_path), filter_str)
        if not path:
            return

        output_path = Path(path)
        try:
            if fmt == "csv":
                write_bulk_csv(
                    [e.parse_result for e in parsed_entries],
                    output_path,
                    language=self._selected_language(),
                )
            else:
                # Consolidated Excel with all statements
                from openpyxl import Workbook
                wb = Workbook()
                wb.remove(wb.active)  # remove default sheet
                from bank_parser.export.excel_writer import _write_review_flags_sheet, _write_statement_sheet
                from bank_parser.export.header_map import HEADER_MAP, HEADER_MAP_EN

                lang = self._selected_language()
                headers = HEADER_MAP.get(lang, HEADER_MAP_EN)

                for idx, entry in enumerate(parsed_entries, start=1):
                    ws = wb.create_sheet(title=f"Statement {idx} ({entry.parse_result.metadata.bank_id[:10]})")
                    _write_statement_sheet(wb, entry.parse_result, headers, lang)

                wb.save(output_path)

        except Exception as exc:
            QMessageBox.critical(self, "Bulk Export Error", str(exc))
            return

        self._message.setText(f"Bulk export complete: {output_path.name}")
        QMessageBox.information(
            self,
            "Bulk Export Complete",
            f"Successfully exported {len(parsed_entries)} statements to:\n{output_path}",
        )

    # -----------------------------------------------------------------------
    # Helper utilities
    # -----------------------------------------------------------------------

    def _update_ui_state(self) -> None:
        has_statements = bool(self._statements)
        has_active = bool(self._active_path and self._statements.get(self._active_path.name, None))
        active_entry = self._statements.get(self._active_path.name) if self._active_path else None
        active_is_parsed = bool(active_entry and active_entry.parse_result)

        self._clear_btn.setEnabled(has_statements)
        self._parse_all_btn.setEnabled(has_statements)
        self._parse_selected_btn.setEnabled(has_active)

        self._add_row_btn.setEnabled(active_is_parsed)
        self._del_row_btn.setEnabled(active_is_parsed)
        self._recalc_btn.setEnabled(active_is_parsed)

        self._export_single_btn.setEnabled(active_is_parsed)
        self._export_single_csv_btn.setEnabled(active_is_parsed)
        self._enrich_btn.setEnabled(active_is_parsed)

        parsed_count = sum(1 for e in self._statements.values() if e.parse_result)
        self._bulk_export_btn.setEnabled(parsed_count > 0)
        self._bulk_export_csv_btn.setEnabled(parsed_count > 0)

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
        return Language.ENGLISH


def _parse_date_str(val: str) -> date | None:
    val = val.strip()
    if not val or val == "-":
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    return None


def _parse_decimal_str(val: str) -> Decimal | None:
    val = val.replace(",", "").strip()
    if not val or val == "-":
        return None
    try:
        return Decimal(val)
    except InvalidOperation:
        return None
