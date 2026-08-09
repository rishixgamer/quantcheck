"""Public-only release evidence: build it, verify it, and prove it leaks nothing.

Public/private separation is release-blocking, so this module does three
things and nothing else:

* :func:`build_public_only_copy` produces a copy of a benchmark output tree
  that contains the public tree and *no private tree at all* — not an empty
  one, not a filtered one, absent — so every later check runs with the private
  truth physically unavailable rather than merely unread.
* :func:`verify_public_evidence` loads that copy through the existing strict
  reader, rebuilds the aggregate from it, builds the shared presentation model,
  renders the deterministic HTML, and reports the identities it observed.
* :func:`scan_for_leaks` scans serialized bytes for private field names, local
  filesystem paths, and secret-shaped strings.

It executes no injection, detection, scoring, replay, or private research
logic; its whole ``quantcheck`` import closure is the presentation layer's.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from quantcheck.benchmark_aggregate import aggregate_from_public_root
from quantcheck.benchmark_contract import PRIVATE_ROOT_NAME, PUBLIC_ROOT_NAME
from quantcheck.hashing import canonical_sha256, sha256_hex_of_bytes
from quantcheck.html_summary import render_html_summary
from quantcheck.presentation import BenchmarkPresentation, build_presentation
from quantcheck.public_artifact_reader import read_public_benchmark
from quantcheck.serialization import canonical_json_bytes

__all__ = [
    "LOCAL_PATH_MARKERS",
    "PRIVATE_ONLY_ARTIFACT_KEYS",
    "SECRET_MARKERS",
    "PublicEvidenceReport",
    "ReleaseEvidenceError",
    "build_public_only_copy",
    "scan_for_leaks",
    "verify_public_evidence",
]


class ReleaseEvidenceError(RuntimeError):
    """Raised when public-only release evidence cannot be trusted."""


#: JSON object keys that exist only in private truth. Matched as exact object
#: keys, never as substrings, so a legitimately public detector-derived field
#: such as ``candidate_scale_factor`` is not confused with the manifest's
#: private ``scale_factor``.
PRIVATE_ONLY_ARTIFACT_KEYS: frozenset[str] = frozenset(
    {
        # Manifest and injector truth.
        "original_record",
        "original_value",
        "corrupted_value",
        "original_date",
        "corrupted_date",
        "original_filed_on",
        "corrupted_filed_on",
        "original_accession_number",
        "corrupted_accession_number",
        "original_source_row_key",
        "corrupted_source_row_key",
        "retained_available_on",
        "mutation",
        "selection_digest",
        "target_rank",
        "target_count",
        "eligible_record_ids",
        "eligible_record_count",
        "eligible_units",
        "eligible_unit_count",
        "eligibility_unit_id",
        "clean_snapshot_id",
        "clean_snapshot_hash",
        "corrupted_snapshot_id",
        "corrupted_snapshot_hash",
        "historical_record_id",
        "later_record_id",
        "historical_revision_id",
        "later_revision_id",
        "lineage_id",
        "minimum_relative_revision_size",
        "target_fraction",
        "scale_factor",
        # Source-record fields the audit boundary strips.
        "entity_name",
        "source_row_key",
        # Value-bearing research truth.
        "availability_count",
        "available_record_ids",
        "aggregate_value",
        "included_record_ids",
        "duplicate_record_ids",
        "duplicate_group_count",
        "total_record_count",
        "corruption_delta",
        "signed_change",
        "absolute_change",
        "relative_change",
        "total_count_delta",
        "duplicate_group_count_delta",
        "maximum_absolute_growth_change",
        "changed_entity_ids",
        "rankings",
        "top_entity_ids",
        # Private failure diagnostics.
        "exception_class",
        "exception_message",
    }
)

#: Substrings that would mean a local filesystem path reached public bytes.
LOCAL_PATH_MARKERS: tuple[str, ...] = (
    "/Users/",
    "/home/",
    "/root/",
    "/var/folders/",
    "/private/tmp",
    "/private/var",
    "/tmp/",
    "\\Users\\",
    "C:\\",
    "file://",
)

#: Substrings that would mean a credential or secret reached public bytes.
SECRET_MARKERS: tuple[str, ...] = (
    "BEGIN RSA PRIVATE KEY",
    "BEGIN PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "aws_secret_access_key",
    "AKIA",
    "Authorization: Bearer",
    "api_key=",
    "apikey=",
    "password=",
    "client_secret",
)

#: The private tree's own directory name, checked so a "public-only" copy that
#: still contains it is refused rather than quietly passed.
_PRIVATE_DIRECTORY = PRIVATE_ROOT_NAME

_TRACEBACK = re.compile(r"Traceback \(most recent call last\)")


@dataclass(frozen=True, slots=True)
class PublicEvidenceReport:
    """What one public-only verification observed. Carries no local path."""

    benchmark_id: str
    aggregate_report_id: str
    configured_case_count: int
    public_file_count: int
    private_file_count: int
    presentation_sha256: str
    html_sha256: str
    aggregate_matches_saved: bool


def _json_keys(document: object) -> set[str]:
    """Collect every JSON object key appearing anywhere in a parsed document."""
    if isinstance(document, dict):
        keys = set(document)
        for value in document.values():
            keys |= _json_keys(value)
        return keys
    if isinstance(document, list):
        nested: set[str] = set()
        for item in document:
            nested |= _json_keys(item)
        return nested
    return set()


def scan_for_leaks(*, json_files: list[Path], texts: list[str]) -> list[str]:
    """Return every leak found in saved JSON and rendered text, or an empty list.

    JSON is scanned structurally (exact object keys) and textually (paths and
    secrets); rendered text such as HTML or dashboard output is scanned
    textually only, because it has no key structure to inspect.
    """
    leaks: list[str] = []
    for path in json_files:
        raw = path.read_text(encoding="utf-8")
        for key in sorted(_json_keys(json.loads(raw)) & PRIVATE_ONLY_ARTIFACT_KEYS):
            leaks.append(f"private key {key!r} in {path.name}")
        texts.append(raw)
    for text in texts:
        for marker in LOCAL_PATH_MARKERS:
            if marker in text:
                leaks.append(f"local path marker {marker!r}")
        for marker in SECRET_MARKERS:
            if marker in text:
                leaks.append(f"secret marker {marker!r}")
        if _TRACEBACK.search(text):
            leaks.append("python traceback")
    return sorted(set(leaks))


def build_public_only_copy(*, source_root: Path, destination: Path) -> int:
    """Copy only the public tree, leaving no private tree in the destination.

    Symlinks are refused rather than followed or copied: a public evidence
    package that contains a link is a package whose contents depend on where
    it is unpacked.
    """
    source_public = Path(source_root) / PUBLIC_ROOT_NAME
    if not source_public.is_dir():
        raise ReleaseEvidenceError("the source benchmark tree has no public directory")
    if destination.exists():
        raise ReleaseEvidenceError("the public-only destination already exists")

    copied = 0
    for path in sorted(source_public.rglob("*")):
        if path.is_symlink():
            raise ReleaseEvidenceError(f"refusing to copy a symlink: {path.name}")
        relative = path.relative_to(source_public)
        target = destination / PUBLIC_ROOT_NAME / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied += 1

    leftover = destination / _PRIVATE_DIRECTORY
    if leftover.exists():  # pragma: no cover - nothing above can create it
        raise ReleaseEvidenceError("a private tree exists in the public-only copy")
    return copied


def verify_public_evidence(
    *,
    public_only_root: Path,
    html_destination: Path,
) -> PublicEvidenceReport:
    """Load, rebuild, present, and render a public-only tree, then scan it.

    Raises:
        ReleaseEvidenceError: when a private tree is present, when the rebuilt
            aggregate disagrees with the saved one, or when any leak is found.
    """
    root = Path(public_only_root)
    private_tree = root / _PRIVATE_DIRECTORY
    if private_tree.exists():
        raise ReleaseEvidenceError(
            "public-only verification requires the private tree to be physically absent"
        )
    # Counted rather than assumed zero: a manifest anywhere under the copy —
    # not only under a directory literally named ``private`` — is a leak.
    private_file_count = len([path for path in root.rglob("manifest.json") if path.is_file()])
    if private_file_count:
        raise ReleaseEvidenceError("the public-only copy contains a manifest")

    artifacts = read_public_benchmark(root)
    rebuilt = aggregate_from_public_root(root)
    aggregate_matches = canonical_json_bytes(rebuilt) == canonical_json_bytes(artifacts.aggregate)
    if not aggregate_matches:
        raise ReleaseEvidenceError(
            "the aggregate rebuilt from public artifacts differs from the saved aggregate"
        )

    presentation: BenchmarkPresentation = build_presentation(artifacts)
    html = render_html_summary(presentation)
    html_bytes = html.encode("utf-8")
    html_destination.parent.mkdir(parents=True, exist_ok=True)
    if html_destination.exists() and html_destination.read_bytes() != html_bytes:
        raise ReleaseEvidenceError("a different HTML summary already exists at that destination")
    html_destination.write_bytes(html_bytes)

    json_files = sorted((root / PUBLIC_ROOT_NAME).rglob("*.json"))
    leaks = scan_for_leaks(
        json_files=list(json_files),
        texts=[html, canonical_json_bytes(presentation).decode("utf-8")],
    )
    if leaks:
        raise ReleaseEvidenceError(f"public release evidence leaked: {leaks}")

    return PublicEvidenceReport(
        benchmark_id=artifacts.config.benchmark_id,
        aggregate_report_id=artifacts.aggregate.aggregate_report_id,
        configured_case_count=artifacts.aggregate.overall.configured_case_count,
        public_file_count=len(
            [path for path in (root / PUBLIC_ROOT_NAME).rglob("*") if path.is_file()]
        ),
        private_file_count=private_file_count,
        presentation_sha256=canonical_sha256(presentation),
        html_sha256=sha256_hex_of_bytes(html_bytes),
        aggregate_matches_saved=aggregate_matches,
    )
