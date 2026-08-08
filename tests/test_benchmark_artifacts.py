"""Public/private artifact separation, atomic persistence, and privacy scans."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.benchmark_support import (
    FIXED_RUNTIME,
    duplicate_profile,
    lookahead_profile,
    private_root,
    public_bytes,
    public_root,
    revision_overwrite_profile,
    single_profile_config,
    unit_drift_profile,
)


@pytest.fixture(scope="module")
def full_config() -> q.BenchmarkConfig:
    return q.build_benchmark_config(
        benchmark_name="artifacts",
        profiles=(
            lookahead_profile(control=q.BenchmarkCleanControl(severity="medium", seed=0)),
            unit_drift_profile(control=q.BenchmarkCleanControl(severity="medium", seed=0)),
            duplicate_profile(control=q.BenchmarkCleanControl(severity="medium", seed=0)),
            revision_overwrite_profile(control=q.BenchmarkCleanControl(severity="low", seed=0)),
        ),
    )


@pytest.fixture(scope="module")
def executed(
    full_config: q.BenchmarkConfig, tmp_path_factory: pytest.TempPathFactory
) -> tuple[q.BenchmarkRunResult, Path]:
    root = tmp_path_factory.mktemp("benchmark-artifacts")
    result = q.run_benchmark(full_config, output_root=root, runtime=FIXED_RUNTIME)
    return result, root


def test_every_case_succeeds_and_persists_its_public_artifacts(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, root = executed
    assert all(status.status == "succeeded" for status in result.statuses)
    for status in result.statuses:
        directory = public_root(root) / "cases" / status.benchmark_case_id
        expected = {
            "case_config.json",
            "audit_input.json",
            "audit_report.json",
            "score.json",
            "status.json",
        }
        if status.case_kind == "fault":
            expected.add("research_summary.json")
        assert {path.name for path in directory.iterdir()} == expected


def test_private_truth_is_stored_only_under_the_private_tree(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, root = executed
    for status in result.statuses:
        private_case = private_root(root) / "cases" / status.benchmark_case_id
        if status.case_kind == "fault":
            names = {path.name for path in private_case.iterdir()}
            assert names == {
                "clean_snapshot.json",
                "corrupted_snapshot.json",
                "manifest.json",
                "repaired_snapshot.json",
                "research_impact.json",
                "private_index.json",
            }
        else:
            # A control injects nothing, so it has no manifest, corrupted or
            # repaired snapshot, or research impact — but its clean snapshot is
            # still private truth: it carries entity names and source row keys
            # that ``sanitize_for_audit`` deliberately strips.
            assert {path.name for path in private_case.iterdir()} == {
                "clean_snapshot.json",
                "private_index.json",
            }


def test_no_public_file_lives_inside_the_private_tree(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    _, root = executed
    public_paths = {
        path.relative_to(public_root(root)) for path in public_root(root).rglob("*.json")
    }
    assert public_paths
    assert not any("private" in path.parts for path in public_paths)


def test_public_index_paths_are_relative_and_stay_inside_the_public_tree(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    _, root = executed
    index = q.BenchmarkPublicIndex.model_validate(
        q.parse_canonical_json((public_root(root) / "index.json").read_bytes())
    )
    assert index.entries
    for entry in index.entries:
        assert not entry.relative_path.startswith("/")
        assert ".." not in entry.relative_path
        assert "\\" not in entry.relative_path
        assert "private" not in entry.relative_path.split("/")
        assert (public_root(root) / entry.relative_path).is_file()


def test_public_index_content_hashes_match_the_stored_bytes(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    _, root = executed
    index = q.BenchmarkPublicIndex.model_validate(
        q.parse_canonical_json((public_root(root) / "index.json").read_bytes())
    )
    for entry in index.entries:
        payload = (public_root(root) / entry.relative_path).read_bytes()
        assert q.sha256_hex_of_bytes(payload) == entry.content_hash


@pytest.mark.parametrize(
    "path",
    [
        "private/cases/x/manifest.json",
        "../private/manifest.json",
        "/absolute/manifest.json",
        "cases/../../private/manifest.json",
        "~/manifest.json",
        "..",
        ".",
    ],
)
def test_a_public_reference_cannot_express_a_private_or_escaping_path(path: str) -> None:
    with pytest.raises(ValidationError):
        q.BenchmarkArtifactReference(
            kind="manifest",
            relative_path=path,
            content_hash="0" * 64,
        )


#: Field names that exist only in private truth. These are matched as exact
#: JSON object keys rather than as substrings, so a legitimately public field
#: like ``candidate_scale_factor`` — which a detector derives from the
#: sanitized input it was given — is not mistaken for the manifest's private
#: ``scale_factor``.
_PRIVATE_ONLY_KEYS = frozenset(
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


def test_public_serialized_bytes_contain_no_manifest_or_hidden_truth(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    """Scan what was written to disk, not Python attributes: bytes are what leak."""
    _, root = executed
    keys: set[str] = set()
    files = sorted(public_root(root).rglob("*.json"))
    assert files
    for path in files:
        keys |= _json_keys(json.loads(path.read_text()))
    leaked = sorted(keys & _PRIVATE_ONLY_KEYS)
    assert leaked == [], leaked


def test_the_private_tree_really_does_hold_the_hidden_truth(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    """The privacy scan above would also pass if nothing had been recorded."""
    _, root = executed
    keys: set[str] = set()
    for path in sorted(private_root(root).rglob("*.json")):
        keys |= _json_keys(json.loads(path.read_text()))
    for expected in ("mutation", "original_value", "selection_digest", "entity_name"):
        assert expected in keys, expected


def test_public_bytes_contain_no_local_temp_or_home_paths(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    _, root = executed
    payload = public_bytes(root)
    for fragment in (
        str(root).encode(),
        b"/Users/",
        b"/home/",
        b"/var/folders/",
        b"/private/tmp",
        b"/tmp/",
        b"C:\\\\",
    ):
        assert fragment not in payload, fragment


def test_public_bytes_carry_no_private_diagnostic_or_secret_material(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    _, root = executed
    payload = public_bytes(root)
    for fragment in (
        b"Traceback",
        b"exception_message",
        b"exception_class",
        b"password",
        b"secret",
        b"token",
        b"api_key",
        b"Authorization",
    ):
        assert fragment not in payload, fragment


def test_the_sanitized_audit_input_leaks_no_seed_severity_or_target(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    """Orchestration adds nothing a detector could read as an answer key."""
    result, root = executed
    for status in result.statuses:
        path = public_root(root) / "cases" / status.benchmark_case_id / "audit_input.json"
        document = json.loads(path.read_text())
        assert set(document) == {"as_of_date", "audit_input_id", "dataset_name", "records"}
        for record in document["records"]:
            assert set(record).isdisjoint(
                {
                    "seed",
                    "severity",
                    "injected",
                    "is_target",
                    "target_rank",
                    "fault_id",
                    "manifest_id",
                    "benchmark_case_id",
                    "case_kind",
                    "entity_name",
                    "source_row_key",
                }
            )


def test_the_audit_input_on_disk_is_exactly_the_sanitized_projection(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, root = executed
    for status in result.statuses:
        if status.case_kind != "fault":
            continue
        stored_input = (
            public_root(root) / "cases" / status.benchmark_case_id / "audit_input.json"
        ).read_bytes()
        corrupted = q.DatasetSnapshot.model_validate(
            q.parse_canonical_json(
                (
                    private_root(root)
                    / "cases"
                    / status.benchmark_case_id
                    / "corrupted_snapshot.json"
                ).read_bytes()
            )
        )
        assert stored_input == q.canonical_json_bytes(q.sanitize_for_audit(corrupted))


def test_identical_immutable_bytes_are_reused_without_rewriting(tmp_path: Path) -> None:
    store = q.AtomicArtifactStore(tmp_path)
    artifact = q.BenchmarkResearchSummary(
        benchmark_case_id="bcase_0123456789abcdef",
        method="record_count_v0_1",
        changed=True,
        exact_restoration=True,
    )
    first = store.write_immutable("case/summary.json", artifact)
    written_at = (tmp_path / "case" / "summary.json").stat().st_mtime_ns
    second = store.write_immutable("case/summary.json", artifact)
    assert first == second
    assert (tmp_path / "case" / "summary.json").stat().st_mtime_ns == written_at


def test_conflicting_immutable_bytes_are_rejected_not_overwritten(tmp_path: Path) -> None:
    store = q.AtomicArtifactStore(tmp_path)
    original = q.BenchmarkResearchSummary(
        benchmark_case_id="bcase_0123456789abcdef",
        method="record_count_v0_1",
        changed=True,
        exact_restoration=True,
    )
    conflicting = q.BenchmarkResearchSummary(
        benchmark_case_id="bcase_0123456789abcdef",
        method="record_count_v0_1",
        changed=False,
        exact_restoration=True,
    )
    payload = store.write_immutable("case/summary.json", original)
    with pytest.raises(q.ArtifactIntegrityError, match="different content"):
        store.write_immutable("case/summary.json", conflicting)
    assert (tmp_path / "case" / "summary.json").read_bytes() == payload


def test_the_store_offers_no_force_overwrite_option() -> None:
    import inspect

    parameters = set(inspect.signature(q.AtomicArtifactStore.write_immutable).parameters)
    assert not parameters & {"force", "overwrite", "replace", "allow_conflict"}


def test_a_store_path_cannot_escape_its_root(tmp_path: Path) -> None:
    store = q.AtomicArtifactStore(tmp_path / "public")
    (tmp_path / "public").mkdir()
    with pytest.raises(q.ArtifactIntegrityError, match="escapes the store root"):
        store.path_for("../private/manifest.json")


def test_atomic_writes_leave_no_temporary_files_behind(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    _, root = executed
    leftovers = [path.name for path in root.rglob("*") if path.name.endswith(".tmp")]
    assert leftovers == []


def test_success_status_is_written_after_every_required_artifact(tmp_path: Path) -> None:
    """The status file is the newest file in a successful case directory."""
    config = single_profile_config(lookahead_profile())
    q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    case_directory = next((tmp_path / "public" / "cases").iterdir())
    status_path = case_directory / "status.json"
    others = [path for path in case_directory.iterdir() if path != status_path]
    assert others
    assert all(status_path.stat().st_mtime_ns >= path.stat().st_mtime_ns for path in others)


def test_a_case_directory_without_a_status_is_not_treated_as_successful(
    tmp_path: Path,
) -> None:
    config = single_profile_config(lookahead_profile())
    result = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    case_id = result.statuses[0].benchmark_case_id
    (tmp_path / "public" / "cases" / case_id / "status.json").unlink()
    rebuilt = q.aggregate_from_public_root(tmp_path)
    assert rebuilt.overall.successful_case_count == 0
    assert rebuilt.overall.incomplete_case_count == 1
    assert rebuilt.overall.configured_case_count == 1
