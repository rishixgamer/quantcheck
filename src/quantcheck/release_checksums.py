"""The repository's release integrity manifest (``CHECKSUMS.md``).

No `CHECKSUMS.md` survived the source loss and no current contract defined its
format, so this is the smallest deterministic one that does the job: a
Markdown document whose body is a fenced block of ``<sha256>  <path>`` lines,
sorted by path, over an explicit file list. Both the generator and the
verifier read that block, so the file is human-readable and machine-checkable
without a second representation.

Scope is deliberate: the manifest covers the *committed release surface* — the
frozen source and lock state, the release freeze record, and the release
documentation whose numbers must match the saved evidence. It does not cover
generated benchmark artifacts, which are reproduced rather than committed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.release_contract import FROZEN_SOURCE_FILES, RELEASE_FREEZE_RECORD_NAME

__all__ = [
    "CHECKSUMS_FILE_NAME",
    "CHECKSUM_COVERED_FILES",
    "ChecksumEntry",
    "ChecksumMismatch",
    "ReleaseChecksumError",
    "parse_checksums_document",
    "render_checksums_document",
    "verify_checksums_document",
]

CHECKSUMS_FILE_NAME = "CHECKSUMS.md"

#: Release documentation whose content is part of the release claim.
_RELEASE_DOCUMENTS: tuple[str, ...] = (
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "docs/ARTIFACTS_AND_PRIVACY.md",
    "docs/CLI_CONTRACT.md",
    "docs/DASHBOARD_AND_HTML.md",
    "docs/DECISIONS.md",
    "docs/FINAL_BENCHMARK_RESULTS.md",
    "docs/LIMITATIONS.md",
    "docs/METHODOLOGY.md",
    "docs/RELEASE_CHECKLIST.md",
    "docs/RELEASE_NOTES_0.1.0.md",
    "docs/REPRODUCIBILITY.md",
    "docs/SERIALIZATION_AND_HASHING.md",
    "docs/THREAT_MODEL.md",
    "docs/faults/DUPLICATE_OBSERVATIONS.md",
    "docs/faults/LOOK_AHEAD.md",
    "docs/faults/REVISION_OVERWRITE.md",
    "docs/faults/UNIT_DRIFT.md",
)

#: Every file the checksum manifest covers, sorted and deduplicated.
CHECKSUM_COVERED_FILES: tuple[str, ...] = tuple(
    sorted({*FROZEN_SOURCE_FILES, *_RELEASE_DOCUMENTS, RELEASE_FREEZE_RECORD_NAME})
)

_LINE = re.compile(r"^(?P<sha256>[0-9a-f]{64})  (?P<path>\S.*)$")
_FENCE = "```"


class ReleaseChecksumError(RuntimeError):
    """Raised when the checksum manifest cannot be produced or parsed."""


@dataclass(frozen=True, slots=True)
class ChecksumEntry:
    """One covered file and its recorded digest."""

    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ChecksumMismatch:
    """One disagreement between the manifest and the working tree."""

    path: str
    recorded: str | None
    actual: str | None

    @property
    def reason(self) -> str:
        if self.actual is None:
            return "covered file is missing"
        if self.recorded is None:
            return "file is not recorded in the manifest"
        return "content hash differs"


def _digest(repo_root: Path, relative: str) -> str | None:
    path = repo_root / relative
    if not path.is_file():
        return None
    return sha256_hex_of_bytes(path.read_bytes())


def render_checksums_document(*, repo_root: Path) -> str:
    """Render the checksum manifest for the current working tree.

    A covered file that does not exist is an error rather than a silently
    skipped line: a manifest that quietly shrinks proves nothing.
    """
    lines: list[str] = []
    for relative in CHECKSUM_COVERED_FILES:
        digest = _digest(repo_root, relative)
        if digest is None:
            raise ReleaseChecksumError(f"checksum-covered file is missing: {relative}")
        lines.append(f"{digest}  {relative}")
    body = "\n".join(lines)
    return (
        "# QuantCheck release checksums\n"
        "\n"
        "SHA-256 of every committed file in the QuantCheck 0.1 release surface: the frozen\n"
        "source and lock state, the release freeze record, and the release documentation.\n"
        "Generated benchmark artifacts are deliberately absent — they are reproduced from\n"
        "the frozen configuration rather than committed.\n"
        "\n"
        "Regenerate and verify with:\n"
        "\n"
        f"{_FENCE}bash\n"
        "uv run python scripts/release_checksums.py --check\n"
        "uv run python scripts/release_checksums.py --write\n"
        f"{_FENCE}\n"
        "\n"
        f"{_FENCE}\n"
        f"{body}\n"
        f"{_FENCE}\n"
    )


def parse_checksums_document(text: str) -> tuple[ChecksumEntry, ...]:
    """Parse the digest lines out of a checksum manifest."""
    entries: list[ChecksumEntry] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        match = _LINE.match(raw.strip())
        if match is None:
            continue
        path = match.group("path")
        if path in seen:
            raise ReleaseChecksumError(f"duplicate checksum entry: {path}")
        seen.add(path)
        entries.append(ChecksumEntry(path=path, sha256=match.group("sha256")))
    if not entries:
        raise ReleaseChecksumError("the checksum manifest contains no digest lines")
    return tuple(entries)


def verify_checksums_document(*, repo_root: Path) -> tuple[ChecksumMismatch, ...]:
    """Compare a saved manifest against the working tree.

    Returns every mismatch rather than the first, so one run reports the whole
    picture. An empty result means the manifest is current.
    """
    document = repo_root / CHECKSUMS_FILE_NAME
    if not document.is_file():
        raise ReleaseChecksumError(f"{CHECKSUMS_FILE_NAME} does not exist")
    recorded = {
        entry.path: entry.sha256 for entry in parse_checksums_document(document.read_text())
    }

    mismatches: list[ChecksumMismatch] = []
    for relative in CHECKSUM_COVERED_FILES:
        actual = _digest(repo_root, relative)
        expected = recorded.get(relative)
        if expected is None or actual is None or expected != actual:
            mismatches.append(ChecksumMismatch(path=relative, recorded=expected, actual=actual))
    for path in sorted(set(recorded) - set(CHECKSUM_COVERED_FILES)):
        mismatches.append(ChecksumMismatch(path=path, recorded=recorded[path], actual=None))
    return tuple(mismatches)
