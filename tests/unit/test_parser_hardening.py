import time
from pathlib import Path

from bank_parser.core.models import Language, ReviewSeverity
from bank_parser.core.text_normalizer import normalize_text
from bank_parser.parsers.generic_english import GenericEnglishBankParser

FIXTURES_DIR = Path(__file__).parents[1] / "fixtures" / "parsers" / "generic_english" / "ar"


def test_multiline_description_parsing() -> None:
    text = """
    Account Number: ACC100
    Currency: USD

    2026-01-05 | Primary Purchase Line | REF01 | 100.00 | | 900.00
    Continuation line 1 for description
    Continuation line 2 for description
    2026-01-06 | Next Transaction Line | REF02 | 50.00 | | 850.00
    """
    parser = GenericEnglishBankParser()
    result = parser.parse(text)

    assert len(result.transactions) == 2
    tx1 = result.transactions[0]
    assert tx1.description == "Primary Purchase Line Continuation line 1 for description Continuation line 2 for description"
    tx2 = result.transactions[1]
    assert tx2.description == "Next Transaction Line"


def test_page_break_and_repeated_header_removal() -> None:
    raw_pdf_text = """
    Account Number: ACC100
    Currency: USD

    Date | Description | Reference | Debit | Credit | Balance
    2026-01-05 | Item 1 | REF1 | 10.00 | | 990.00
    Page 1 of 3
    Date | Description | Reference | Debit | Credit | Balance
    2026-01-06 | Item 2 | REF2 | 20.00 | | 970.00
    Page 2 of 3
    """
    normalized = normalize_text(raw_pdf_text)
    assert "Page 1 of 3" not in normalized
    assert "Page 2 of 3" not in normalized

    parser = GenericEnglishBankParser()
    result = parser.parse(normalized)
    assert len(result.transactions) == 2


def test_large_statement_performance_smoke_test() -> None:
    lines = [
        "Account Number: ACC_LARGE",
        "Currency: USD",
        "Date | Description | Reference | Debit | Credit | Balance",
    ]
    for i in range(1, 501):
        lines.append(f"2026-01-01 | Bulk Transaction Row {i} | REF{i:04d} | 10.00 | | {10000.00 - i * 10:.2f}")

    large_text = "\n".join(lines)
    parser = GenericEnglishBankParser()

    start_time = time.perf_counter()
    result = parser.parse(large_text)
    duration = time.perf_counter() - start_time

    assert len(result.transactions) == 500
    assert duration < 0.500  # Must finish under 500 milliseconds


def test_unsupported_layout_failure_behavior() -> None:
    unrecognized_text = """
    Random text with no bank metadata or transaction tables.
    Lorem ipsum dolor sit amet, consectetur adipiscing elit.
    """
    parser = GenericEnglishBankParser()
    result = parser.parse(unrecognized_text)

    assert len(result.transactions) == 0
    assert any(flag.code == "unsupported_layout" and flag.severity == ReviewSeverity.ERROR for flag in result.review_flags)


def test_multilingual_fixture_coverage() -> None:
    text_path = FIXTURES_DIR / "statement_text.txt"
    text = text_path.read_text(encoding="utf-8")

    parser = GenericEnglishBankParser()
    result = parser.parse(text)

    assert result.metadata.account_number == "9988776655"
    assert result.metadata.currency == "AED"
    assert len(result.transactions) == 2
