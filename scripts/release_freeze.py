"""Freeze the QuantCheck 0.1 release candidate, or verify an existing freeze.

This is a repository development tool, deliberately outside the wheel and the
sdist (the same rule as the fixture generators). It is not a CLI command: the
contracted CLI surface stays at exactly six root commands with no held-out or
release flag anywhere.

    uv run python scripts/release_freeze.py --write
    uv run python scripts/release_freeze.py --check
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from quantcheck.release_contract import RELEASE_FREEZE_RECORD_NAME
from quantcheck.release_freeze import (
    ReleaseFreezeError,
    read_release_freeze_record,
    release_freeze_record_hash,
    write_release_freeze_record,
)
from quantcheck.release_run import (
    build_authorized_release_freeze,
    verify_authorized_release_freeze,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _package_metadata() -> tuple[str, str]:
    """Read the version and Python requirement straight from pyproject."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    return str(project["version"]), str(project["requires-python"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="create the freeze record")
    group.add_argument("--check", action="store_true", help="verify the saved freeze record")
    args = parser.parse_args(argv)

    destination = REPO_ROOT / RELEASE_FREEZE_RECORD_NAME
    version, python_requirement = _package_metadata()

    try:
        if args.write:
            record = build_authorized_release_freeze(
                repo_root=REPO_ROOT,
                package_version=version,
                python_requirement=python_requirement,
            )
            write_release_freeze_record(record, destination=destination)
        else:
            record = read_release_freeze_record(destination)
            verify_authorized_release_freeze(record, repo_root=REPO_ROOT)
    except ReleaseFreezeError as exc:
        print(f"release freeze failed: {exc}", file=sys.stderr)
        return 1

    print(f"release_candidate_id      {record.release_candidate_id}")
    print(f"package_version          {record.package_version}")
    print(f"benchmark_id             {record.benchmark_id}")
    print(f"release_config_sha256    {record.release_config_sha256}")
    print(f"case_matrix_sha256       {record.case_matrix_sha256}")
    print(f"expanded_case_count      {record.expanded_case_count}")
    print(f"frozen_file_count        {len(record.frozen_files)}")
    print(f"freeze_record_sha256     {release_freeze_record_hash(record)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
