import pytest

from bank_parser.core.text_normalizer import normalize_text


def test_normalize_text_applies_nfkc_for_english_parser_input() -> None:
    text = "ＡＣＣＯＵＮＴ　ＳＴＡＴＥＭＥＮＴ"

    assert normalize_text(text) == "ACCOUNT STATEMENT"


def test_normalize_text_collapses_repeated_spacing_and_blank_lines() -> None:
    text = "Date\t\tDescription      Debit\r\n\r\n2026-01-02   ATM   Withdrawal"

    assert normalize_text(text) == "Date Description Debit\n2026-01-02 ATM Withdrawal"


def test_normalize_text_preserves_amounts_dates_and_description_words() -> None:
    text = "2026-01-02    POS Purchase - Grocery Store    1,234.56    (100.00)"

    assert normalize_text(text) == "2026-01-02 POS Purchase - Grocery Store 1,234.56 (100.00)"


def test_normalize_text_keeps_output_language_separate_from_parser_input_language() -> None:
    with pytest.raises(ValueError, match="Unsupported parser input language"):
        normalize_text("Statement", source_language="fr")


def test_normalize_text_defers_future_multilingual_source_languages_to_basic_cleanup() -> None:
    assert normalize_text("Statement   Total", source_language="ur") == "Statement Total"
