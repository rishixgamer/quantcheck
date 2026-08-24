#!/usr/bin/env python3
"""Reject repository-only material from built wheel and source distributions."""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path

FORBIDDEN_SDIST_PREFIXES = (
    "docs/",
    "evidence/",
    "gates/",
    "reference/",
    "prompts/",
    "scripts/",
    "dashboard/",
    "video/",
    ".github/",
    ".streamlit/",
    ".claude/",
    ".serena/",
    ".venv/",
    "dist/",
    ".mypy_cache/",
    ".ruff_cache/",
    ".pytest_cache/",
    ".hypothesis/",
)
FORBIDDEN_SDIST_FILES = {
    "AGENTS.md",
    "IMPLEMENT.md",
    "PROJECT_SCOPE.md",
    "MVP_ACCEPTANCE_CRITERIA.md",
    "START_HERE.txt",
    "RECOVERY_SEQUENCE.md",
}


def _members(path: Path) -> tuple[str, ...]:
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as archive:
            return tuple(archive.namelist())
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, mode="r:gz") as archive:
            return tuple(member.name for member in archive.getmembers())
    raise ValueError(f"unsupported distribution type: {path.name}")


def _wheel_failures(names: tuple[str, ...]) -> list[str]:
    failures: list[str] = []
    for name in names:
        if name.startswith("quantcheck/"):
            continue
        if name.startswith("quantcheck-") and ".dist-info/" in name:
            continue
        failures.append(name)
    return failures


def _sdist_failures(names: tuple[str, ...]) -> list[str]:
    if not names:
        return ["(empty archive)"]
    root = names[0].split("/", 1)[0]
    failures: list[str] = []
    for name in names:
        relative = name.removeprefix(f"{root}/")
        if relative in FORBIDDEN_SDIST_FILES or any(
            relative.startswith(prefix) for prefix in FORBIDDEN_SDIST_PREFIXES
        ):
            failures.append(name)
    return failures


def check_distribution_directory(directory: Path) -> list[str]:
    wheels = sorted(directory.glob("*.whl"))
    sdists = sorted(directory.glob("*.tar.gz"))
    failures: list[str] = []
    if len(wheels) != 1:
        failures.append(f"expected exactly one wheel, found {len(wheels)}")
    if len(sdists) != 1:
        failures.append(f"expected exactly one sdist, found {len(sdists)}")
    if len(wheels) == 1:
        failures.extend(
            f"{wheels[0].name}: forbidden member {name}"
            for name in _wheel_failures(_members(wheels[0]))
        )
    if len(sdists) == 1:
        failures.extend(
            f"{sdists[0].name}: forbidden member {name}"
            for name in _sdist_failures(_members(sdists[0]))
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    directory = args.directory
    if not directory.is_dir():
        print(f"DISTRIBUTIONS_FAILED: directory does not exist: {directory}", file=sys.stderr)
        return 1
    try:
        failures = check_distribution_directory(directory)
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        print(f"DISTRIBUTIONS_FAILED: {error}", file=sys.stderr)
        return 1
    if failures:
        print("\n".join(failures), file=sys.stderr)
        print(f"DISTRIBUTIONS_FAILED ({len(failures)} issue(s))", file=sys.stderr)
        return 1
    print("DISTRIBUTIONS_CLEAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
