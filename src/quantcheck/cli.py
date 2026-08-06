"""Bootstrap-stage command-line entry point for QuantCheck.

This is a minimal, dependency-free placeholder that only supports
``--help`` and ``--version``. It carries no financial behavior and is
expected to be replaced by the contracted CLI surface in a later
milestone (see IMPLEMENT.md).
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from quantcheck import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantcheck",
        description=(
            "QuantCheck: deterministic point-in-time financial data "
            "reliability auditing framework (bootstrap placeholder)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"quantcheck {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
