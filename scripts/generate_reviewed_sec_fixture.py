#!/usr/bin/env python3
"""Regenerate or verify the curated SEC Company Facts field-shape fixture."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quantcheck.sec_fixture import canonical_reviewed_sec_fixture_bytes

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "sec_companyfacts_curated.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the checked-in fixture without writing",
    )
    args = parser.parse_args(argv)
    regenerated = canonical_reviewed_sec_fixture_bytes()

    if args.check:
        if not FIXTURE_PATH.exists():
            print(f"missing checked-in fixture: {FIXTURE_PATH}", file=sys.stderr)
            return 1
        if FIXTURE_PATH.read_bytes() != regenerated:
            print(
                f"{FIXTURE_PATH} is out of date; rerun without --check to regenerate it",
                file=sys.stderr,
            )
            return 1
        print(f"{FIXTURE_PATH} matches regenerated curated bytes")
        return 0

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_bytes(regenerated)
    print(f"wrote {FIXTURE_PATH} ({len(regenerated)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
