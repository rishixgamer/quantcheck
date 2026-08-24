"""Public-only release evidence, verified with the private tree absent.

The scenario every test here builds is the one that actually ships: a copy of
the public tree, with `private/` physically not present, loaded and rendered
from scratch. If any of this needed private truth, the release package would be
unusable to anyone but its author.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import quantcheck as q
from tests.benchmark_support import FIXED_RUNTIME

V01_RELEASE_ROOT = Path(__file__).resolve().parents[1] / "evidence/v0_1_release"
V01_ARCHIVE_URL = (
    "https://github.com/rishixgamer/quantcheck/releases/download/"
    "v0.1.0/quantcheck-v0.1.0-public-evidence.tar.gz"
)
V01_ARCHIVE_SHA256 = "da778f05f4f27d1fa314046ddbd8f4616b0460d13b7c06374060d639410f2fcf"


@pytest.fixture(scope="module")
def executed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One real benchmark tree, produced offline through the ordinary runner."""
    root = tmp_path_factory.mktemp("evidence")
    q.run_benchmark(
        q.smoke_benchmark_config(),
        output_root=root,
        runtime=FIXED_RUNTIME,
    )
    return root


@pytest.fixture
def public_only(executed: Path, tmp_path: Path) -> Path:
    destination = tmp_path / "public_only"
    q.build_public_only_copy(source_root=executed, destination=destination)
    return destination


# --------------------------------------------------------------------------
# Building the public-only copy
# --------------------------------------------------------------------------


def test_the_copy_contains_no_private_tree(public_only: Path) -> None:
    assert not (public_only / "private").exists()
    assert list(public_only.iterdir()) == [public_only / "public"]


def test_repository_does_not_track_private_evidence_paths() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--", "evidence/**/private/**"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""


def test_repository_does_not_track_incomplete_release_evidence_tree() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--", "release_evidence/**"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""


def test_tracked_markdown_does_not_publish_personal_worktree_metadata() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--", "*.md"],
        check=True,
        capture_output=True,
        text=True,
    )
    for relative_path in result.stdout.splitlines():
        text = Path(relative_path).read_text()
        assert "/Users/" not in text, relative_path
        assert ".claude-flow" not in text, relative_path


def test_curated_v01_summaries_bind_to_release_freeze_without_index() -> None:
    """The compact checked-in set is canonical, not a partial fake evidence tree."""
    freeze = json.loads((V01_RELEASE_ROOT.parents[1] / "release_freeze.json").read_text())
    aggregate = json.loads((V01_RELEASE_ROOT / "aggregate_report.json").read_text())
    config = json.loads((V01_RELEASE_ROOT / "benchmark_config.json").read_text())
    case_matrix = json.loads((V01_RELEASE_ROOT / "case_matrix.json").read_text())
    runtime = json.loads((V01_RELEASE_ROOT / "runtime_metadata.json").read_text())

    assert {path.name for path in V01_RELEASE_ROOT.glob("*.json")} == {
        "aggregate_report.json",
        "benchmark_config.json",
        "case_matrix.json",
        "runtime_metadata.json",
    }
    assert aggregate["aggregate_report_id"] == "agg_571aae0b7c60a4a5"
    assert aggregate["benchmark_id"] == freeze["benchmark_id"]
    assert config["benchmark_id"] == freeze["benchmark_id"]
    assert case_matrix["benchmark_id"] == freeze["benchmark_id"]
    assert runtime["benchmark_id"] == freeze["benchmark_id"]
    config_hash = hashlib.sha256(
        (V01_RELEASE_ROOT / "benchmark_config.json").read_bytes()
    ).hexdigest()
    assert config_hash == freeze["release_config_sha256"]
    assert (
        hashlib.sha256((V01_RELEASE_ROOT / "case_matrix.json").read_bytes()).hexdigest()
        == (freeze["case_matrix_sha256"])
    )

    readme = (V01_RELEASE_ROOT / "README.md").read_text()
    assert V01_ARCHIVE_URL in readme
    assert V01_ARCHIVE_SHA256 in readme
    for path in V01_RELEASE_ROOT.glob("*.json"):
        text = path.read_text()
        assert "/Users/" not in text
        assert "/home/" not in text
        assert "private/" not in text


def test_the_copy_contains_no_manifest_anywhere(public_only: Path) -> None:
    assert list(public_only.rglob("manifest.json")) == []
    assert list(public_only.rglob("clean_snapshot.json")) == []
    assert list(public_only.rglob("corrupted_snapshot.json")) == []
    assert list(public_only.rglob("research_impact.json")) == []


def test_copying_over_an_existing_destination_is_refused(executed: Path, tmp_path: Path) -> None:
    destination = tmp_path / "public_only"
    q.build_public_only_copy(source_root=executed, destination=destination)
    with pytest.raises(q.ReleaseEvidenceError, match="already exists"):
        q.build_public_only_copy(source_root=executed, destination=destination)


def test_a_source_without_a_public_tree_is_refused(tmp_path: Path) -> None:
    with pytest.raises(q.ReleaseEvidenceError, match="no public directory"):
        q.build_public_only_copy(source_root=tmp_path, destination=tmp_path / "out")


def test_a_symlink_in_the_public_tree_is_refused(executed: Path, tmp_path: Path) -> None:
    """A package containing a link has contents that depend on where it lands."""
    staged = tmp_path / "staged"
    q.build_public_only_copy(source_root=executed, destination=staged)
    link = staged / "public" / "escape.json"
    link.symlink_to(executed / "private")
    with pytest.raises(q.ReleaseEvidenceError, match="symlink"):
        q.build_public_only_copy(source_root=staged, destination=tmp_path / "out")


# --------------------------------------------------------------------------
# Verifying the public-only copy
# --------------------------------------------------------------------------


def test_the_public_only_copy_loads_rebuilds_and_renders(public_only: Path, tmp_path: Path) -> None:
    report = q.verify_public_evidence(
        public_only_root=public_only,
        html_destination=tmp_path / "summary.html",
    )
    assert report.aggregate_matches_saved
    assert report.private_file_count == 0
    assert report.public_file_count > 0
    assert report.configured_case_count == q.SMOKE_CASE_COUNT
    assert len(report.html_sha256) == 64
    assert (tmp_path / "summary.html").is_file()


def test_the_rendered_html_is_byte_identical_across_destinations(
    public_only: Path, tmp_path: Path
) -> None:
    first = q.verify_public_evidence(
        public_only_root=public_only, html_destination=tmp_path / "a" / "summary.html"
    )
    second = q.verify_public_evidence(
        public_only_root=public_only, html_destination=tmp_path / "b" / "summary.html"
    )
    assert first.html_sha256 == second.html_sha256
    assert first.presentation_sha256 == second.presentation_sha256
    assert (tmp_path / "a" / "summary.html").read_bytes() == (
        tmp_path / "b" / "summary.html"
    ).read_bytes()


def test_rendering_over_conflicting_html_bytes_is_refused(
    public_only: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "summary.html"
    destination.write_text("<html>different</html>")
    with pytest.raises(q.ReleaseEvidenceError, match="already exists"):
        q.verify_public_evidence(public_only_root=public_only, html_destination=destination)


def test_verification_refuses_a_copy_that_still_has_a_private_tree(
    executed: Path, tmp_path: Path
) -> None:
    with pytest.raises(q.ReleaseEvidenceError, match="physically absent"):
        q.verify_public_evidence(
            public_only_root=executed,
            html_destination=tmp_path / "summary.html",
        )


def test_verification_refuses_a_copy_containing_a_manifest(
    public_only: Path, tmp_path: Path
) -> None:
    """A manifest anywhere is a leak, not only one under ``private/``."""
    smuggled = public_only / "public" / "manifest.json"
    smuggled.write_text("{}")
    with pytest.raises(q.ReleaseEvidenceError, match="contains a manifest"):
        q.verify_public_evidence(
            public_only_root=public_only,
            html_destination=tmp_path / "summary.html",
        )


def test_a_tampered_aggregate_is_caught_by_the_rebuild(public_only: Path, tmp_path: Path) -> None:
    aggregate = public_only / "public" / "aggregate_report.json"
    document = json.loads(aggregate.read_text())
    document["overall"]["findings"] = document["overall"]["findings"] + 1
    aggregate.write_text(json.dumps(document))
    with pytest.raises(Exception):  # noqa: B017 - reader or rebuild, both acceptable
        q.verify_public_evidence(
            public_only_root=public_only,
            html_destination=tmp_path / "summary.html",
        )


# --------------------------------------------------------------------------
# Leak scanning
# --------------------------------------------------------------------------


def test_the_scanner_finds_a_private_object_key(tmp_path: Path) -> None:
    """The scan must not pass vacuously; prove it detects a real leak."""
    leaky = tmp_path / "leak.json"
    leaky.write_text(json.dumps({"case": {"mutation": {"original_value": "1"}}}))
    leaks = q.scan_for_leaks(json_files=[leaky], texts=[])
    assert any("mutation" in leak for leak in leaks)
    assert any("original_value" in leak for leak in leaks)


@pytest.mark.parametrize(
    "text",
    [
        "/Users/someone/quantcheck",
        "/home/runner/work",
        "/var/folders/xy/T/tmpabc",
        "C:\\Users\\someone",
        "file:///etc/passwd",
    ],
)
def test_the_scanner_finds_a_local_path(text: str) -> None:
    assert q.scan_for_leaks(json_files=[], texts=[text])


@pytest.mark.parametrize(
    "text",
    [
        "-----BEGIN PRIVATE KEY-----",
        "aws_secret_access_key=abc",
        "Authorization: Bearer abc",
        "client_secret",
    ],
)
def test_the_scanner_finds_a_secret(text: str) -> None:
    assert q.scan_for_leaks(json_files=[], texts=[text])


def test_the_scanner_finds_a_traceback() -> None:
    leaks = q.scan_for_leaks(
        json_files=[],
        texts=["Traceback (most recent call last):\n  File ..."],
    )
    assert "python traceback" in leaks


def test_the_scanner_passes_on_clean_text() -> None:
    assert q.scan_for_leaks(json_files=[], texts=["precision 0.5", "cases/bcase_abc"]) == []


def test_a_public_derived_field_is_not_mistaken_for_private_truth(tmp_path: Path) -> None:
    """``candidate_scale_factor`` is detector output, not the manifest's value."""
    document = tmp_path / "finding.json"
    document.write_text(json.dumps({"evidence": {"candidate_scale_factor": "1000"}}))
    assert q.scan_for_leaks(json_files=[document], texts=[]) == []


def test_the_release_privacy_key_set_covers_the_benchmark_privacy_scan() -> None:
    """One privacy contract, two consumers: the release list must not be smaller."""
    from tests.test_benchmark_artifacts import _PRIVATE_ONLY_KEYS

    missing = sorted(_PRIVATE_ONLY_KEYS - q.PRIVATE_ONLY_ARTIFACT_KEYS)
    assert missing == [], missing


# --------------------------------------------------------------------------
# The evidence module runs no scientific logic
# --------------------------------------------------------------------------


def test_the_evidence_module_imports_no_scientific_module() -> None:
    import ast

    source = Path(q.__file__).resolve().parent / "release_evidence.py"
    imported = set()
    for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = ("injection", "detection", "scoring", "manifest", "replay", "research", "dispatch")
    for module in imported:
        assert not module.endswith(forbidden), module
