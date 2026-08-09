"""The release-candidate freeze record: content, identity, privacy, and drift.

A freeze record's job is to make "what was frozen" checkable rather than
asserted. These tests cover the three ways that can fail: the record could
omit something scientific, it could leak something private, or it could keep
verifying after the repository changed underneath it.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

import quantcheck as q
from tests.release_support import (
    REPO_ROOT,
    assert_gate_closed,
    freeze_record,
    repo_copy,
    written_freeze,
)


@pytest.fixture(scope="module")
def record() -> q.ReleaseFreezeRecord:
    return freeze_record()


# --------------------------------------------------------------------------
# The record covers the scientific configuration
# --------------------------------------------------------------------------


def test_the_record_freezes_the_release_matrix(record: q.ReleaseFreezeRecord) -> None:
    assert tuple(record.fault_profiles) == q.BENCHMARK_FAULT_PROFILES
    assert tuple(record.severities) == ("low", "medium", "high")
    assert tuple(record.final_seeds) == tuple(range(1000, 1010))
    assert record.clean_control_policy == "one_per_fault_profile"
    assert record.fault_case_count == 120
    assert record.control_case_count == 4
    assert record.total_case_count == 124
    assert record.expanded_case_count == 124


def test_the_record_freezes_all_four_fault_specifications(
    record: q.ReleaseFreezeRecord,
) -> None:
    profiles = {spec.fault_profile for spec in record.fault_specifications}
    assert profiles == set(q.BENCHMARK_FAULT_PROFILES)
    for spec in record.fault_specifications:
        assert spec.injector_spec_version
        assert spec.detector_id
        assert spec.detector_version
        assert spec.scoring_spec_version
        assert spec.matching_rule.startswith("exact_one_to_one")
        assert spec.false_positive_denominator_rule
        assert spec.replay_method == "private_manifest_assisted_exact_replay"


def test_the_record_freezes_every_severity_definition(record: q.ReleaseFreezeRecord) -> None:
    """Twelve cells: four families times three severities, each with numbers."""
    cells = {(p.fault_profile, p.severity) for p in record.severity_profiles}
    assert len(cells) == 12
    lookahead_high = next(
        p
        for p in record.severity_profiles
        if p.fault_profile == "lookahead_timestamp" and p.severity == "high"
    )
    assert lookahead_high.frozen_target_fraction == Decimal("0.10")
    assert lookahead_high.frozen_parameter_name == "minimum_lag_days"
    assert lookahead_high.frozen_parameter_value == Decimal("30")

    revision_medium = next(
        p
        for p in record.severity_profiles
        if p.fault_profile == "revision_overwrite" and p.severity == "medium"
    )
    assert revision_medium.frozen_parameter_name == "minimum_relative_revision_size"
    assert revision_medium.frozen_parameter_value == Decimal("0.05")


def test_the_record_freezes_the_detector_threshold_and_configuration(
    record: q.ReleaseFreezeRecord,
) -> None:
    assert record.unit_drift_ratio_threshold == Decimal("50")
    assert len(record.detector_configs_sha256) == 64


def test_the_record_freezes_both_reviewed_fixtures(record: q.ReleaseFreezeRecord) -> None:
    assert record.reviewed_fixture_id == q.REVIEWED_FIXTURE_ID
    assert record.reviewed_fixture_sha256 == q.sha256_hex_of_bytes(
        q.canonical_reviewed_fixture_bytes()
    )
    assert record.sec_reviewed_fixture_id
    assert len(record.sec_reviewed_fixture_sha256) == 64


def test_the_record_freezes_the_configuration_and_the_lockfile(
    record: q.ReleaseFreezeRecord,
) -> None:
    assert record.benchmark_id.startswith("bench_")
    assert len(record.release_config_sha256) == 64
    assert len(record.case_matrix_sha256) == 64
    lockfile = next(entry for entry in record.frozen_files if entry.path == "uv.lock")
    assert record.lockfile_sha256 == lockfile.sha256


def test_the_frozen_file_list_covers_every_scientific_module(
    record: q.ReleaseFreezeRecord,
) -> None:
    """Any module that can change a result must be frozen.

    The check is derived from the package tree rather than restated, so a new
    scientific module cannot be added without either freezing it or updating
    the deliberate exclusion list here.
    """
    frozen = {entry.path for entry in record.frozen_files}
    source = Path(q.__file__).resolve().parent
    #: Modules deliberately outside the frozen set, each because it cannot
    #: change a saved artifact's bytes or a scientific result.
    excluded = {"py.typed"}
    for module in sorted(source.glob("*.py")):
        relative = f"src/quantcheck/{module.name}"
        if module.name in excluded:
            continue
        assert relative in frozen, relative


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


def test_the_candidate_identity_is_a_stable_function_of_the_frozen_content(
    record: q.ReleaseFreezeRecord,
) -> None:
    again = freeze_record()
    assert again.release_candidate_id == record.release_candidate_id
    assert q.release_freeze_record_hash(again) == q.release_freeze_record_hash(record)


def test_a_different_package_version_produces_a_different_candidate(
    record: q.ReleaseFreezeRecord,
) -> None:
    other = freeze_record(package_version="0.1.1")
    assert other.release_candidate_id != record.release_candidate_id


def test_the_candidate_identity_uses_its_own_namespace(record: q.ReleaseFreezeRecord) -> None:
    assert record.release_candidate_id.startswith("relc_")
    assert record.release_candidate_id != record.benchmark_id


def test_a_freeze_may_only_cover_the_release_configuration() -> None:
    with pytest.raises(q.ReleaseFreezeError, match="release benchmark configuration"):
        q.build_release_freeze_record(
            repo_root=REPO_ROOT,
            package_version="0.1.0",
            python_requirement=">=3.12,<3.13",
            config=q.smoke_benchmark_config(),
        )


def test_building_a_freeze_leaves_the_gate_closed() -> None:
    freeze_record()
    assert_gate_closed()


def test_verifying_a_freeze_leaves_the_gate_closed(record: q.ReleaseFreezeRecord) -> None:
    q.verify_authorized_release_freeze(record, repo_root=REPO_ROOT)
    assert_gate_closed()


# --------------------------------------------------------------------------
# Privacy
# --------------------------------------------------------------------------


def test_the_freeze_record_contains_no_private_or_local_information(
    record: q.ReleaseFreezeRecord,
) -> None:
    text = q.canonical_json_bytes(record).decode("utf-8")
    leaks = q.scan_for_leaks(json_files=[], texts=[text])
    assert leaks == [], leaks


def test_the_freeze_record_contains_no_manifest_or_answer_key_field(
    record: q.ReleaseFreezeRecord,
) -> None:
    document = json.loads(q.canonical_json_bytes(record))

    def keys(node: object) -> set[str]:
        if isinstance(node, dict):
            found = set(node)
            for value in node.values():
                found |= keys(value)
            return found
        if isinstance(node, list):
            found = set()
            for item in node:
                found |= keys(item)
            return found
        return set()

    #: ``target_fraction`` is a private *manifest* field name. The freeze
    #: records the same public constant under ``frozen_target_fraction`` so
    #: the context-free privacy scan never has to be given an exemption.
    assert "target_fraction" not in keys(document)
    assert "frozen_target_fraction" in keys(document)
    assert "mutation" not in keys(document)
    assert "original_record" not in keys(document)
    assert "selection_digest" not in keys(document)
    assert "target_rank" not in keys(document)
    assert "eligible_record_ids" not in keys(document)


def test_every_frozen_path_is_repository_relative(record: q.ReleaseFreezeRecord) -> None:
    for entry in record.frozen_files:
        assert not entry.path.startswith("/")
        assert "\\" not in entry.path
        assert ".." not in entry.path
        assert "~" not in entry.path


# --------------------------------------------------------------------------
# Verification and drift
# --------------------------------------------------------------------------


def test_an_unmodified_repository_verifies(record: q.ReleaseFreezeRecord) -> None:
    q.verify_authorized_release_freeze(record, repo_root=REPO_ROOT)
    assert_gate_closed()


def test_a_drifted_frozen_source_file_invalidates_the_candidate(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    scratch = repo_copy(tmp_path / "repo")
    target = scratch / "src/quantcheck/unit_drift_contract.py"
    target.write_text(target.read_text() + "\n# drift\n")
    with pytest.raises(q.ReleaseFreezeError, match="drifted"):
        q.verify_authorized_release_freeze(record, repo_root=scratch)


def test_a_drifted_lockfile_invalidates_the_candidate(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    scratch = repo_copy(tmp_path / "repo")
    lockfile = scratch / "uv.lock"
    lockfile.write_text(lockfile.read_text() + "\n")
    with pytest.raises(q.ReleaseFreezeError, match="drifted"):
        q.verify_authorized_release_freeze(record, repo_root=scratch)


def test_a_drifted_reviewed_fixture_invalidates_the_candidate(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    scratch = repo_copy(tmp_path / "repo")
    fixture = scratch / "tests/fixtures/reviewed_financial_facts.json"
    fixture.write_text(fixture.read_text() + " ")
    with pytest.raises(q.ReleaseFreezeError, match="drifted"):
        q.verify_authorized_release_freeze(record, repo_root=scratch)


def test_a_missing_frozen_file_invalidates_the_candidate(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    scratch = repo_copy(tmp_path / "repo")
    (scratch / "src/quantcheck/lookahead_scoring.py").unlink()
    with pytest.raises(q.ReleaseFreezeError, match="missing"):
        q.verify_authorized_release_freeze(record, repo_root=scratch)


def test_a_tampered_candidate_identity_is_rejected(record: q.ReleaseFreezeRecord) -> None:
    tampered = record.model_copy(update={"package_version": "9.9.9"})
    with pytest.raises(q.ReleaseFreezeError, match="identity"):
        q.verify_authorized_release_freeze(tampered, repo_root=REPO_ROOT)


def test_a_record_for_a_different_configuration_is_rejected(
    record: q.ReleaseFreezeRecord,
) -> None:
    """The freeze must be checked against the configuration it froze."""
    with pytest.raises(q.ReleaseFreezeError, match="not the frozen one"):
        q.verify_release_freeze_record(
            record, repo_root=REPO_ROOT, config=q.smoke_benchmark_config()
        )


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------


def test_a_written_record_round_trips(tmp_path: Path, record: q.ReleaseFreezeRecord) -> None:
    path = written_freeze(tmp_path, record)
    assert q.read_release_freeze_record(path) == record


def test_rewriting_identical_bytes_is_a_safe_no_op(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    path = written_freeze(tmp_path, record)
    before = path.stat().st_mtime_ns
    q.write_release_freeze_record(record, destination=path)
    assert path.stat().st_mtime_ns == before


def test_writing_a_different_record_over_an_existing_one_is_refused(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    """A silently replaced candidate is exactly what must never happen."""
    path = written_freeze(tmp_path, record)
    other = freeze_record(package_version="0.1.1")
    with pytest.raises(q.ReleaseFreezeError, match="already exists"):
        q.write_release_freeze_record(other, destination=path)
    assert q.read_release_freeze_record(path) == record


def test_reading_a_missing_record_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(q.ReleaseFreezeError, match="no release freeze record"):
        q.read_release_freeze_record(tmp_path / "absent.json")


def test_reading_a_malformed_record_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / q.RELEASE_FREEZE_RECORD_NAME
    path.write_text('{"release_candidate_id": "relc_x"}')
    with pytest.raises(Exception):  # noqa: B017 - Pydantic validation, not a release error
        q.read_release_freeze_record(path)
