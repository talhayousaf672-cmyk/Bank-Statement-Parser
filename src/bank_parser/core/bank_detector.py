"""Header-based bank identity detection shared by app adapters and parsers."""

from __future__ import annotations

import re


def detect_bank_id_from_header(normalized_text: str) -> str | None:
    header_text = _statement_header_text(normalized_text).lower()
    strong_bank_markers = (
        ("bank_of_america", ("bank of america",)),
        ("wells_fargo", ("wells fargo",)),
        ("chase_bank", ("chase bank", "jpmorgan chase", "jp morgan chase")),
        ("bank_alfalah", ("bank alfalah",)),
        ("allied_bank", ("allied bank", "allied bank limited")),
        ("meezan_bank", ("meezan bank", "meezan bank limited")),
        ("mcb_bank", ("mcb bank", "mcb bank limited", "muslim commercial bank")),
        ("ubl", ("united bank limited",)),
        ("hbl", ("habib bank limited",)),
    )
    for detected_bank_id, markers in strong_bank_markers:
        if any(_has_bank_marker(header_text, marker) for marker in markers):
            return detected_bank_id

    acronym_bank_markers = (
        ("ubl", ("ubl",)),
        ("hbl", ("hbl",)),
    )
    for detected_bank_id, markers in acronym_bank_markers:
        if any(_has_bank_marker(header_text, marker) for marker in markers):
            return detected_bank_id
    return None


def _statement_header_text(normalized_text: str) -> str:
    header_text = normalized_text[:2500]
    table_header_match = re.search(
        r"(?im)^\s*(txn\s+date|date)\s*\|",
        header_text,
    )
    if table_header_match:
        header_text = header_text[:table_header_match.start()]
    return header_text


def _has_bank_marker(text: str, marker: str) -> bool:
    words = marker.split()
    if len(words) == 1:
        return re.search(rf"\b{re.escape(marker)}\b", text) is not None
    return marker in text
