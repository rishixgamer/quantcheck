"""The strict public reader: positive, negative, and adversarial cases.

The reader is a trust boundary, so most of these tests are attacks. Each one
asserts that a hostile or broken tree is *refused*, not normalized into
something that looks fine.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import quantcheck as q
from quantcheck.public_artifact_reader import (
    PublicArtifactError,
    read_public_benchmark,
    resolve_public_path,
    validate_public_relative_path,
)
from tests.benchmark_support import (
    FIXED_RUNTIME,
    lookahead_profile,
    private_root,
    public_root,
    single_profile_config,
)
from tests.presentation_helpers import (
    build_failed_benchmark,
    build_incomplete_benchmark,
    build_smoke_benchmark,
    copy_public_only,
    rebuild_derived_public_artifacts,
)


@pytest.fixture(scope="module")
def smoke_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("reader-smoke")
    build_smoke_benchmark(root)
    return root


# --------------------------------------------------------------------------
# Positive paths
# --------------------------------------------------------------------------


def test_a_valid_smoke_tree_reads_completely(smoke_root: Path) -> None:
    artifacts = read_public_benchmark(smoke_root)
    assert len(artifacts.cases) == artifacts.matrix.case_count == q.SMOKE_CASE_COUNT
    assert all(case.terminal_status == "succeeded" for case in artifacts.cases)
    assert artifacts.config.benchmark_id == artifacts.aggregate.benchmark_id
    assert artifacts.runtime is not None


def test_the_public_directory_itself_is_also_a_valid_root(smoke_root: Path) -> None:
    from_output_root = read_public_benchmark(smoke_root)
    from_public_tree = read_public_benchmark(public_root(smoke_root))
    assert from_public_tree.aggregate == from_output_root.aggregate


def test_a_public_only_copy_reads_identically(smoke_root: Path, tmp_path: Path) -> None:
    """The whole point of the boundary: deleting private truth changes nothing."""
    destination = copy_public_only(smoke_root, tmp_path / "public-only")
    assert not (destination / q.PRIVATE_ROOT_NAME).exists()
    assert (
        read_public_benchmark(destination).aggregate == read_public_benchmark(smoke_root).aggregate
    )


def test_reading_never_touches_the_private_tree(smoke_root: Path, tmp_path: Path) -> None:
    """Physically remove the private tree from a copy and read it anyway."""
    copied = tmp_path / "no-private"
    copy_public_only(smoke_root, copied)
    artifacts = read_public_benchmark(copied)
    assert artifacts.matrix.case_count == q.SMOKE_CASE_COUNT
    assert not list(copied.rglob("manifest.json"))


def test_clean_controls_are_read_and_kept_visible(smoke_root: Path) -> None:
    controls = [
        case
        for case in read_public_benchmark(smoke_root).cases
        if case.case.case_kind == "clean_control"
    ]
    assert len(controls) == 4
    assert all(control.score is not None for control in controls)
    assert all(control.score.score_report is None for control in controls)  # type: ignore[union-attr]


def test_a_failed_case_is_read_as_failed_with_only_a_redacted_failure(
    tmp_path: Path,
) -> None:
    build_failed_benchmark(tmp_path)
    artifacts = read_public_benchmark(tmp_path)
    failed = [case for case in artifacts.cases if case.terminal_status == "failed"]
    assert len(failed) == 1
    failure = failed[0].failure
    assert failure is not None
    assert failure.category == "no_eligible_targets"
    assert failed[0].score is None


def test_an_incomplete_case_is_read_as_incomplete_not_successful(tmp_path: Path) -> None:
    case_id = build_incomplete_benchmark(tmp_path)
    artifacts = read_public_benchmark(tmp_path)
    by_id = {case.case.benchmark_case_id: case for case in artifacts.cases}
    assert by_id[case_id].terminal_status == "incomplete"
    assert by_id[case_id].score is None
    assert sum(1 for case in artifacts.cases if case.terminal_status == "succeeded") == 1


# --------------------------------------------------------------------------
# Path security
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unsafe",
    [
        "/etc/passwd",
        "/private/cases/x.json",
        "C:\\Windows\\system32\\config",
        "C:/Windows/system32",
        "\\\\server\\share\\file.json",
        "..",
        "../secret.json",
        "cases/../../private/manifest.json",
        "cases/./status.json",
        "private/manifest.json",
        "public/../private/manifest.json",
        "cases/private/manifest.json",
        "~/secrets.json",
        ".hidden.json",
        "",
        "a//b.json",
    ],
)
def test_unsafe_relative_paths_are_rejected(unsafe: str) -> None:
    with pytest.raises(PublicArtifactError):
        validate_public_relative_path(unsafe)


@pytest.mark.parametrize("value", [None, 3, b"cases/x.json", Path("cases/x.json")])
def test_a_non_string_path_is_rejected(value: object) -> None:
    with pytest.raises(PublicArtifactError):
        validate_public_relative_path(value)


def test_a_safe_path_resolves_below_the_public_root(smoke_root: Path) -> None:
    resolved = resolve_public_path(public_root(smoke_root), "case_matrix.json")
    assert resolved.is_file()
    assert resolved.is_relative_to(public_root(smoke_root).resolve())


def test_a_symlink_inside_the_public_root_pointing_outside_is_rejected(
    smoke_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"{}")
    link = public_root(smoke_root) / "escape.json"
    link.symlink_to(outside)
    try:
        with pytest.raises(PublicArtifactError):
            resolve_public_path(public_root(smoke_root), "escape.json")
    finally:
        link.unlink()


def test_a_symlink_into_the_private_tree_is_rejected(smoke_root: Path) -> None:
    link = public_root(smoke_root) / "leak.json"
    link.symlink_to(private_root(smoke_root))
    try:
        with pytest.raises(PublicArtifactError):
            resolve_public_path(public_root(smoke_root), "leak.json")
    finally:
        link.unlink()


def test_a_directory_symlink_cannot_smuggle_a_child_path_out(
    smoke_root: Path, tmp_path: Path
) -> None:
    """A safe-looking *relative* path through a symlinked directory still escapes."""
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "status.json").write_bytes(b"{}")
    link = public_root(smoke_root) / "linked"
    link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(PublicArtifactError):
            resolve_public_path(public_root(smoke_root), "linked/status.json")
    finally:
        link.unlink()


def test_resolution_requires_the_public_root_to_exist(tmp_path: Path) -> None:
    with pytest.raises(PublicArtifactError):
        resolve_public_path(tmp_path / "absent", "case_matrix.json")


# --------------------------------------------------------------------------
# Tree-level integrity
# --------------------------------------------------------------------------


def _corrupt(root: Path, relative: str, payload: bytes) -> None:
    (public_root(root) / relative).write_bytes(payload)


@pytest.fixture()
def tamperable(tmp_path: Path) -> Path:
    """A small single-profile tree each adversarial test may damage freely."""
    root = tmp_path / "tamperable"
    q.run_benchmark(
        single_profile_config(lookahead_profile(), name="tamperable"),
        output_root=root,
        runtime=FIXED_RUNTIME,
    )
    return root


def test_no_public_tree_at_all_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PublicArtifactError, match="no public benchmark tree"):
        read_public_benchmark(tmp_path)


def test_an_unexpected_root_without_a_matrix_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "unrelated.json").write_bytes(b"{}")
    with pytest.raises(PublicArtifactError, match="no public benchmark tree"):
        read_public_benchmark(tmp_path)


def test_malformed_json_is_rejected(tamperable: Path) -> None:
    _corrupt(tamperable, "benchmark_config.json", b"{not json at all")
    with pytest.raises(PublicArtifactError, match="not canonical JSON"):
        read_public_benchmark(tamperable)


def test_schema_invalid_json_is_rejected(tamperable: Path) -> None:
    _corrupt(tamperable, "benchmark_config.json", b'{"benchmark_id":"nope"}')
    with pytest.raises(PublicArtifactError, match="does not validate"):
        read_public_benchmark(tamperable)


def test_a_missing_root_artifact_is_rejected(tamperable: Path) -> None:
    (public_root(tamperable) / "aggregate_report.json").unlink()
    with pytest.raises(PublicArtifactError, match="absent"):
        read_public_benchmark(tamperable)


def test_a_missing_index_is_rejected(tamperable: Path) -> None:
    (public_root(tamperable) / "index.json").unlink()
    with pytest.raises(PublicArtifactError, match="absent"):
        read_public_benchmark(tamperable)


def test_a_bad_content_hash_in_the_index_is_rejected(tamperable: Path) -> None:
    """Edit an indexed artifact's bytes without updating the index."""
    matrix = public_root(tamperable) / "case_matrix.json"
    matrix.write_bytes(matrix.read_bytes() + b" ")
    with pytest.raises(PublicArtifactError, match="content hash"):
        read_public_benchmark(tamperable)


def test_a_missing_indexed_artifact_is_rejected(tamperable: Path) -> None:
    index = q.BenchmarkPublicIndex.model_validate(
        q.parse_canonical_json((public_root(tamperable) / "index.json").read_bytes())
    )
    status_entry = next(entry for entry in index.entries if entry.kind == "status")
    (public_root(tamperable) / status_entry.relative_path).unlink()
    with pytest.raises(PublicArtifactError, match="absent"):
        read_public_benchmark(tamperable)


def _rewrite_index(root: Path, entries: tuple[q.BenchmarkArtifactReference, ...]) -> None:
    index = q.BenchmarkPublicIndex.model_validate(
        q.parse_canonical_json((public_root(root) / "index.json").read_bytes())
    )
    q.AtomicArtifactStore(public_root(root)).write_run_artifact(
        "index.json",
        q.BenchmarkPublicIndex(
            benchmark_id=index.benchmark_id,
            spec_version=index.spec_version,
            entries=entries,
        ),
    )


def test_an_unknown_artifact_role_in_the_index_is_rejected(tamperable: Path) -> None:
    index = q.BenchmarkPublicIndex.model_validate(
        q.parse_canonical_json((public_root(tamperable) / "index.json").read_bytes())
    )
    kept = tuple(entry for entry in index.entries if entry.kind != "aggregate_report")
    forged = q.BenchmarkArtifactReference(
        kind="private_manifest",
        relative_path="aggregate_report.json",
        content_hash=q.sha256_hex_of_bytes(
            (public_root(tamperable) / "aggregate_report.json").read_bytes()
        ),
    )
    _rewrite_index(tamperable, (*kept, forged))
    with pytest.raises(PublicArtifactError, match="unknown public artifact role"):
        read_public_benchmark(tamperable)


def test_a_root_role_pointing_at_the_wrong_path_is_rejected(tamperable: Path) -> None:
    index = q.BenchmarkPublicIndex.model_validate(
        q.parse_canonical_json((public_root(tamperable) / "index.json").read_bytes())
    )
    kept = tuple(
        entry
        for entry in index.entries
        if entry.kind not in {"aggregate_report", "runtime_metadata"}
    )
    forged = q.BenchmarkArtifactReference(
        kind="aggregate_report",
        relative_path="runtime_metadata.json",
        content_hash=q.sha256_hex_of_bytes(
            (public_root(tamperable) / "runtime_metadata.json").read_bytes()
        ),
    )
    _rewrite_index(tamperable, (*kept, forged))
    with pytest.raises(PublicArtifactError, match="not the expected path"):
        read_public_benchmark(tamperable)


def test_a_cross_case_index_reference_is_rejected(tamperable: Path) -> None:
    """A case artifact indexed under a *different* case's directory."""
    index = q.BenchmarkPublicIndex.model_validate(
        q.parse_canonical_json((public_root(tamperable) / "index.json").read_bytes())
    )
    score = next(entry for entry in index.entries if entry.kind == "score")
    other_case = "bcase_" + "0" * 16
    forged = q.BenchmarkArtifactReference(
        kind="score",
        relative_path=f"cases/{other_case}/score.json",
        content_hash=score.content_hash,
    )
    kept = tuple(entry for entry in index.entries if entry.kind != "score")
    _rewrite_index(tamperable, (*kept, forged))
    with pytest.raises(PublicArtifactError, match="absent|not the expected path"):
        read_public_benchmark(tamperable)


def test_an_index_naming_a_different_benchmark_is_rejected(tamperable: Path) -> None:
    index = q.BenchmarkPublicIndex.model_validate(
        q.parse_canonical_json((public_root(tamperable) / "index.json").read_bytes())
    )
    q.AtomicArtifactStore(public_root(tamperable)).write_run_artifact(
        "index.json",
        q.BenchmarkPublicIndex(
            benchmark_id="bench_" + "1" * 16,
            spec_version=index.spec_version,
            entries=index.entries,
        ),
    )
    with pytest.raises(PublicArtifactError, match="benchmark identity"):
        read_public_benchmark(tamperable)


def test_a_status_naming_a_different_case_is_rejected(tamperable: Path) -> None:
    public = public_root(tamperable)
    status_path = next(public.rglob("status.json"))
    status = q.BenchmarkCaseStatus.model_validate(q.parse_canonical_json(status_path.read_bytes()))
    forged = status.model_copy(update={"benchmark_case_id": "bcase_" + "2" * 16})
    status_path.write_bytes(q.canonical_json_bytes(forged))
    rebuild_derived_public_artifacts(tamperable)
    with pytest.raises(PublicArtifactError, match="different case"):
        read_public_benchmark(tamperable)


def test_a_stale_aggregate_that_contradicts_the_statuses_is_rejected(
    tmp_path: Path,
) -> None:
    """Remove a status without re-aggregating: the two views now disagree."""
    root = tmp_path / "stale"
    build_smoke_benchmark(root)
    status_path = next(iter(sorted(public_root(root).rglob("status.json"))))
    status_path.unlink()
    # The index still references the removed status, so that is caught first;
    # rebuild only the index to isolate the aggregate/status contradiction.
    index = q.BenchmarkPublicIndex.model_validate(
        q.parse_canonical_json((public_root(root) / "index.json").read_bytes())
    )
    kept = tuple(
        entry for entry in index.entries if (public_root(root) / entry.relative_path).is_file()
    )
    _rewrite_index(root, kept)
    with pytest.raises(PublicArtifactError, match="does not describe the saved case statuses"):
        read_public_benchmark(root)


def test_an_unindexed_extra_artifact_is_ignored_rather_than_read(tamperable: Path) -> None:
    """A file nobody indexed is not evidence, and is never picked up."""
    (public_root(tamperable) / "cases" / "stray.json").write_bytes(b'{"x":1}')
    artifacts = read_public_benchmark(tamperable)
    assert len(artifacts.cases) == artifacts.matrix.case_count


def test_reading_is_unaffected_by_a_hostile_working_directory(
    smoke_root: Path, tmp_path: Path
) -> None:
    """Relative-path handling must not depend on the process's cwd."""
    previous = Path.cwd()
    os.chdir(tmp_path)
    try:
        assert read_public_benchmark(smoke_root).matrix.case_count == q.SMOKE_CASE_COUNT
    finally:
        os.chdir(previous)
