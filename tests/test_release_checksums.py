"""The release integrity manifest.

A checksum manifest is only useful if it fails when it should. These tests
cover the three failure modes that matter: a covered file changed, a covered
file vanished, and the manifest lists something outside its own coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import quantcheck as q
from tests.release_support import historical_v01_checksums_match_tag, repo_copy


@pytest.fixture
def scratch(tmp_path: Path) -> Path:
    """A repository copy holding every covered file and a fresh manifest."""
    root = repo_copy(tmp_path / "repo")
    for relative in q.CHECKSUM_COVERED_FILES:
        target = root / relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"placeholder for {relative}\n")
    (root / q.CHECKSUMS_FILE_NAME).write_text(q.render_checksums_document(repo_root=root))
    return root


def test_the_manifest_covers_the_frozen_source_and_the_release_documents() -> None:
    covered = set(q.CHECKSUM_COVERED_FILES)
    assert set(q.FROZEN_SOURCE_FILES) <= covered
    assert q.RELEASE_FREEZE_RECORD_NAME in covered
    assert "README.md" in covered
    assert "CHANGELOG.md" in covered
    assert "LICENSE" in covered


def test_the_covered_list_is_sorted_and_deduplicated() -> None:
    assert list(q.CHECKSUM_COVERED_FILES) == sorted(set(q.CHECKSUM_COVERED_FILES))


def test_a_freshly_written_manifest_verifies(scratch: Path) -> None:
    assert q.verify_checksums_document(repo_root=scratch) == ()


def test_a_changed_file_is_reported(scratch: Path) -> None:
    target = scratch / "src/quantcheck/schemas.py"
    target.write_text(target.read_text() + "\n# changed\n")
    mismatches = q.verify_checksums_document(repo_root=scratch)
    assert [m.path for m in mismatches] == ["src/quantcheck/schemas.py"]
    assert mismatches[0].reason == "content hash differs"


def test_a_missing_file_is_reported(scratch: Path) -> None:
    (scratch / "src/quantcheck/hashing.py").unlink()
    mismatches = q.verify_checksums_document(repo_root=scratch)
    assert [m.path for m in mismatches] == ["src/quantcheck/hashing.py"]
    assert mismatches[0].reason == "covered file is missing"


def test_every_mismatch_is_reported_not_only_the_first(scratch: Path) -> None:
    for relative in ("src/quantcheck/schemas.py", "src/quantcheck/hashing.py", "README.md"):
        target = scratch / relative
        target.write_text(target.read_text() + "\n")
    assert len(q.verify_checksums_document(repo_root=scratch)) == 3


def test_an_uncovered_entry_in_the_manifest_is_reported(scratch: Path) -> None:
    document = scratch / q.CHECKSUMS_FILE_NAME
    document.write_text(document.read_text().replace("```\n", f"```\n{'0' * 64}  extra.txt\n", 1))
    mismatches = q.verify_checksums_document(repo_root=scratch)
    assert any(m.path == "extra.txt" for m in mismatches)


def test_a_missing_manifest_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(q.ReleaseChecksumError, match="does not exist"):
        q.verify_checksums_document(repo_root=tmp_path)


def test_rendering_refuses_when_a_covered_file_is_absent(tmp_path: Path) -> None:
    with pytest.raises(q.ReleaseChecksumError, match="missing"):
        q.render_checksums_document(repo_root=tmp_path)


def test_the_manifest_round_trips_through_its_own_parser(scratch: Path) -> None:
    document = q.render_checksums_document(repo_root=scratch)
    entries = q.parse_checksums_document(document)
    assert [entry.path for entry in entries] == list(q.CHECKSUM_COVERED_FILES)
    for entry in entries:
        assert len(entry.sha256) == 64


def test_a_duplicate_entry_is_rejected() -> None:
    digest = "0" * 64
    with pytest.raises(q.ReleaseChecksumError, match="duplicate"):
        q.parse_checksums_document(f"```\n{digest}  a.txt\n{digest}  a.txt\n```\n")


def test_a_manifest_with_no_digest_lines_is_rejected() -> None:
    with pytest.raises(q.ReleaseChecksumError, match="no digest lines"):
        q.parse_checksums_document("# heading\n\nprose only\n")


def test_the_manifest_records_no_generated_benchmark_artifact() -> None:
    """Committed release surface only: artifacts are reproduced, not committed."""
    for relative in q.CHECKSUM_COVERED_FILES:
        assert "public/" not in relative
        assert "private/" not in relative
        assert not relative.endswith("aggregate_report.json")


def test_the_historical_manifest_matches_the_immutable_v01_tag() -> None:
    """The old manifest authenticates its tag, not the additive v0.2 worktree."""
    assert historical_v01_checksums_match_tag() == ()
