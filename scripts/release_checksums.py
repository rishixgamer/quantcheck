"""Write or verify ``CHECKSUMS.md``, the release integrity manifest.

A repository development tool, outside the wheel, sdist, and CLI.

    uv run python scripts/release_checksums.py --write
    uv run python scripts/release_checksums.py --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quantcheck.release_checksums import (
    CHECKSUM_COVERED_FILES,
    CHECKSUMS_FILE_NAME,
    ReleaseChecksumError,
    render_checksums_document,
    verify_checksums_document,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="regenerate the manifest")
    group.add_argument("--check", action="store_true", help="verify the saved manifest")
    args = parser.parse_args(argv)

    try:
        if args.write:
            document = render_checksums_document(repo_root=REPO_ROOT)
            (REPO_ROOT / CHECKSUMS_FILE_NAME).write_text(document, encoding="utf-8")
            print(f"wrote {CHECKSUMS_FILE_NAME} covering {len(CHECKSUM_COVERED_FILES)} files")
            return 0
        mismatches = verify_checksums_document(repo_root=REPO_ROOT)
    except ReleaseChecksumError as exc:
        print(f"checksum verification failed: {exc}", file=sys.stderr)
        return 1

    if mismatches:
        for mismatch in mismatches:
            print(f"{mismatch.path}: {mismatch.reason}", file=sys.stderr)
        print(f"{len(mismatches)} checksum mismatch(es)", file=sys.stderr)
        return 1
    print(f"{CHECKSUMS_FILE_NAME} is current: {len(CHECKSUM_COVERED_FILES)} files verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
