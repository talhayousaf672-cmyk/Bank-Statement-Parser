"""Minimal CLI entry point."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse a bank statement PDF into Excel.")
    parser.add_argument("input_pdf", help="Path to the bank statement PDF.")
    parser.add_argument("--bank-id", required=True, help="Bank identifier registered in the parser factory.")
    parser.add_argument("--language", required=True, help="Statement language code.")
    parser.add_argument("--output", required=True, help="Output XLSX path.")
    return parser


def main() -> int:
    parser = build_parser()
    parser.parse_args()
    print("CLI skeleton ready. Parsing pipeline is not implemented yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
