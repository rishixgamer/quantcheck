"""Build and verify the public-only QuantCheck release evidence package.

A repository development tool, outside the wheel, sdist, and CLI.

    uv run python scripts/verify_release_evidence.py \\
        --source release_evidence/final \\
        --public-only release_evidence/public_only \\
        --html release_evidence/public_only/summary.html

The public-only copy contains the public tree and no private tree at all. Every
check below runs against that copy with the private truth physically absent.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from quantcheck.release_evidence import (
    ReleaseEvidenceError,
    build_public_only_copy,
    verify_public_evidence,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="the benchmark output root")
    parser.add_argument(
        "--public-only", required=True, type=Path, help="destination for the public-only copy"
    )
    parser.add_argument("--html", required=True, type=Path, help="HTML summary destination")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="remove an existing public-only destination before copying",
    )
    args = parser.parse_args(argv)

    try:
        if args.replace and args.public_only.exists():
            shutil.rmtree(args.public_only)
        copied = build_public_only_copy(source_root=args.source, destination=args.public_only)
        report = verify_public_evidence(
            public_only_root=args.public_only,
            html_destination=args.html,
        )
    except ReleaseEvidenceError as exc:
        print(f"release evidence verification failed: {exc}", file=sys.stderr)
        return 1

    print(f"copied_public_files      {copied}")
    print(f"benchmark_id             {report.benchmark_id}")
    print(f"aggregate_report_id      {report.aggregate_report_id}")
    print(f"configured_case_count    {report.configured_case_count}")
    print(f"public_file_count        {report.public_file_count}")
    print(f"private_file_count       {report.private_file_count}")
    print(f"aggregate_matches_saved  {report.aggregate_matches_saved}")
    print(f"presentation_sha256      {report.presentation_sha256}")
    print(f"html_sha256              {report.html_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
