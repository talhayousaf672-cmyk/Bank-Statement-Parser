"""PySide6 Desktop App — local bank statement parser with SQLite review queue."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QColor, QFont
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QStatusBar,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    _PYSIDE6_AVAILABLE = True
except ImportError:
    _PYSIDE6_AVAILABLE = False

from bank_parser.core.models import Language, ParseResult
from bank_parser.core.pdf_extractor import PdfExtractionError, extract_text_blocks
from bank_parser.core.text_normalizer import normalize_text
from bank_parser.export.excel_writer import write_excel
from bank_parser.parsers import register_builtin_parsers
from bank_parser.validation.reconciliation import validate_parse_result
from bank_parser.validation.review_queue import build_review_queue
from bank_parser.validation.sqlite_review_store import SQLiteReviewQueueStore
from bank_parser.validation.summary import ValidationSummary, summarize_validation

_REGISTRY = register_builtin_parsers()
_DB_PATH = Path.home() / ".bank-parser" / "reviews.db"

_LANGUAGE_LABELS = {
    "Arabic (ar)": Language.ARABIC,
    "Urdu (ur)": Language.URDU,
    "Russian (ru)": Language.RUSSIAN,
    "Spanish (es)": Language.SPANISH,
    "Hindi (hi)": Language.HINDI,
}


class ParseWorker(QThread if _PYSIDE6_AVAILABLE else object):
    """Background thread: extract → parse → validate."""
    finished = Signal(object, object)   # parse_result, summary
    error = Signal(str)

    def __init__(self, pdf_path: Path, bank_id: str, language: Language) -> None:
        super().__init__()
        self._pdf_path = pdf_path
        self._bank_id = bank_id
        self._language = language

    def run(self) -> None:
        try:
            blocks = extract_text_blocks(self._pdf_path)
        except PdfExtractionError as exc:
            self.error.emit(str(exc))
            return

        normalized = normalize_text("\n".join(b.text for b in blocks))
        try:
            parser = _REGISTRY.create(self._bank_id, self._language)
        except LookupError as exc:
            self.error.emit(str(exc))
            return

        result = parser.parse(normalized)
        result = validate_parse_result(result)
        summary = summarize_validation(result)
        self.finished.emit(result, summary)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bank Statement Parser")
        self.resize(900, 680)
        self._parse_result: ParseResult | None = None
        self._summary: ValidationSummary | None = None

        self._store = SQLiteReviewQueueStore(_DB_PATH)
        self._store.initialize()

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        root_layout.addWidget(self._build_input_group())
        root_layout.addWidget(self._build_summary_group())
        root_layout.addWidget(self._build_flags_group())
        root_layout.addWidget(self._build_export_group())

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready.")

    def _build_input_group(self) -> QGroupBox:
        group = QGroupBox("1 · Input")
        layout = QHBoxLayout(group)

        self._pdf_edit = QLineEdit()
        self._pdf_edit.setPlaceholderText("Select a bank statement PDF ...")
        self._pdf_edit.setReadOnly(True)

        browse_btn = QPushButton("Browse …")
        browse_btn.clicked.connect(self._on_browse)

        self._bank_combo = QComboBox()
        for bank_id, _ in _REGISTRY.list_parsers():
            if bank_id not in [self._bank_combo.itemText(i) for i in range(self._bank_combo.count())]:
                self._bank_combo.addItem(bank_id)

        self._lang_combo = QComboBox()
        for label in _LANGUAGE_LABELS:
            self._lang_combo.addItem(label)

        self._parse_btn = QPushButton("Parse & Validate")
        self._parse_btn.setEnabled(False)
        self._parse_btn.clicked.connect(self._on_parse)

        layout.addWidget(QLabel("PDF:"))
        layout.addWidget(self._pdf_edit, stretch=3)
        layout.addWidget(browse_btn)
        layout.addWidget(QLabel("Bank:"))
        layout.addWidget(self._bank_combo)
        layout.addWidget(QLabel("Output Language:"))
        layout.addWidget(self._lang_combo)
        layout.addWidget(self._parse_btn)
        return group

    def _build_summary_group(self) -> QGroupBox:
        group = QGroupBox("2 · Validation Summary")
        layout = QHBoxLayout(group)

        def _stat(label: str) -> tuple[QLabel, QLabel]:
            lbl = QLabel(label)
            val = QLabel("—")
            val.setFont(QFont("Monospace", 12, QFont.Weight.Bold))
            layout.addWidget(lbl)
            layout.addWidget(val)
            layout.addSpacing(16)
            return lbl, val

        _, self._lbl_total = _stat("Total Rows:")
        _, self._lbl_clean = _stat("Clean:")
        _, self._lbl_warn = _stat("Warning:")
        _, self._lbl_error = _stat("Error:")
        _, self._lbl_readiness = _stat("Export Readiness:")
        return group

    def _build_flags_group(self) -> QGroupBox:
        group = QGroupBox("3 · Review Flags")
        layout = QVBoxLayout(group)

        self._flags_table = QTableWidget(0, 5)
        self._flags_table.setHorizontalHeaderLabels(["Row", "Code", "Severity", "Message", "Status"])
        self._flags_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._flags_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._flags_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._flags_table.setAlternatingRowColors(True)

        layout.addWidget(self._flags_table)
        return group

    def _build_export_group(self) -> QGroupBox:
        group = QGroupBox("4 · Export")
        layout = QHBoxLayout(group)

        self._export_btn = QPushButton("Export to Excel …")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)

        layout.addStretch()
        layout.addWidget(self._export_btn)
        return group

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if path:
            self._pdf_edit.setText(path)
            self._parse_btn.setEnabled(True)

    def _on_parse(self) -> None:
        pdf_path = Path(self._pdf_edit.text())
        bank_id = self._bank_combo.currentText()
        language = _LANGUAGE_LABELS[self._lang_combo.currentText()]

        self._parse_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
        self.statusBar().showMessage("Parsing …")

        self._worker = ParseWorker(pdf_path, bank_id, language)
        self._worker.finished.connect(self._on_parse_done)
        self._worker.error.connect(self._on_parse_error)
        self._worker.start()

    def _on_parse_done(self, result: ParseResult, summary: ValidationSummary) -> None:
        self._parse_result = result
        self._summary = summary
        self._parse_btn.setEnabled(True)

        # Update summary labels
        self._lbl_total.setText(str(summary.total_rows))
        self._lbl_clean.setText(str(summary.clean_rows))
        self._lbl_warn.setText(str(summary.warning_rows))
        self._lbl_error.setText(str(summary.error_rows))
        self._lbl_readiness.setText(summary.export_readiness.value.upper())

        # Populate flags table
        items = build_review_queue(result, statement_id=result.metadata.bank_id)
        self._store.save_items(items)
        self._populate_flags_table(items)

        if summary.export_ready:
            self._export_btn.setEnabled(True)
            self.statusBar().showMessage(
                f"Ready. {summary.total_rows} transactions, {len(items)} flags."
            )
        else:
            self.statusBar().showMessage("Blocked: statement has validation errors.")

    def _on_parse_error(self, msg: str) -> None:
        self._parse_btn.setEnabled(True)
        QMessageBox.critical(self, "Parse Error", msg)
        self.statusBar().showMessage("Parse failed.")

    def _on_export(self) -> None:
        if self._parse_result is None:
            return

        lang = _LANGUAGE_LABELS[self._lang_combo.currentText()]
        path, _ = QFileDialog.getSaveFileName(self, "Save Excel File", "", "Excel Files (*.xlsx)")
        if not path:
            return

        try:
            write_excel(self._parse_result, path, language=lang)
            QMessageBox.information(self, "Export Complete", f"Saved to:\n{path}")
            self.statusBar().showMessage(f"Exported: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))

    def _populate_flags_table(self, items) -> None:
        self._flags_table.setRowCount(0)
        _severity_colors = {
            "error": QColor("#FFDCDC"),
            "warning": QColor("#FFF3CD"),
            "info": QColor("#D1ECF1"),
        }
        for item in items:
            row = self._flags_table.rowCount()
            self._flags_table.insertRow(row)
            cells = [
                str(item.row_number or "—"),
                item.flag.code,
                item.flag.severity.value,
                item.flag.message,
                item.status.value,
            ]
            for col, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                bg = _severity_colors.get(item.flag.severity.value, QColor("white"))
                cell.setBackground(bg)
                self._flags_table.setItem(row, col, cell)


def run_app() -> None:
    if not _PYSIDE6_AVAILABLE:
        raise RuntimeError(
            "PySide6 is not installed. Install the desktop extra: pip install 'bank-statement-parser[desktop]'"
        )
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
