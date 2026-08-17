"""Accuracy report — runs QA harness against all fixture pairs and prints results."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Allow running as: python scripts/run_accuracy_report.py
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from bank_parser.parsers import register_builtin_parsers
from bank_parser.validation.qa_harness import compare_parse_results
from bank_parser.core.models import ParseResult

FIXTURE_BASE = Path("tests/fixtures/parsers")

_BANK_PARSER_MAP = {
    "chase_bank": "chase_bank",
    "generic_english": "generic_english",
    "hbl": "hbl",
    "ubl": "ubl",
    "meezan_bank": "meezan_bank",
    "wells_fargo": "wells_fargo",
    "bank_of_america": "bank_of_america",
}


def run_accuracy_report() -> int:
    registry = register_builtin_parsers()

    total = 0
    passed = 0
    failed_banks: list[str] = []

    print("=" * 70)
    print("BANK STATEMENT PARSER — ACCURACY REPORT")
    print("=" * 70)

    for bank_id in sorted(FIXTURE_BASE.iterdir(), key=lambda p: p.name):
        if not bank_id.is_dir():
            continue
        for lang_dir in sorted(bank_id.iterdir()):
            if not lang_dir.is_dir():
                continue
            statement_file = lang_dir / "statement_text.txt"
            expected_file = lang_dir / "expected_parse.json"
            if not statement_file.exists() or not expected_file.exists():
                continue

            fixture_key = f"{bank_id.name}/{lang_dir.name}"
            total += 1

            # Find parser — try with language-specific or Spanish fallback
            parser = None
            for key_id, _ in registry.list_parsers():
                if key_id == bank_id.name:
                    from bank_parser.core.models import Language
                    try:
                        parser = registry.create(bank_id.name, Language.SPANISH)
                    except LookupError:
                        pass
                    break

            if parser is None:
                print(f"  [SKIP ] {fixture_key:40} — no parser registered")
                continue

            try:
                text = statement_file.read_text(encoding="utf-8")
                actual = parser.parse(text)
                expected_data = json.loads(expected_file.read_text(encoding="utf-8"))
                expected = ParseResult.model_validate(expected_data)

                report = compare_parse_results(expected, actual)
                if report.passed:
                    passed += 1
                    print(f"  [PASS ] {fixture_key:40} {len(actual.transactions)} txns | accuracy={report.accuracy:.0%}")
                else:
                    failed_banks.append(fixture_key)
                    print(f"  [FAIL ] {fixture_key:40} {len(report.mismatches)} mismatch(es) | accuracy={report.accuracy:.0%}:")
                    for m in report.mismatches[:3]:
                        print(f"           └─ row={m.row_number} field={m.field_name}: expected={m.expected!r} got={m.actual!r}")
            except Exception as exc:
                failed_banks.append(fixture_key)
                print(f"  [ERROR] {fixture_key:40} {exc}")

    print("=" * 70)
    print(f"Result: {passed}/{total} fixtures passing")
    if failed_banks:
        print(f"Failed: {', '.join(failed_banks)}")
    print("=" * 70)
    return 0 if not failed_banks else 1


if __name__ == "__main__":
    raise SystemExit(run_accuracy_report())
