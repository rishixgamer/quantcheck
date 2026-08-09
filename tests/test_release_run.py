"""The release-only execution path.

The property under test is ordering: **nothing dispatches a final case until a
valid frozen candidate has been verified against the current repository.** A
release run that started work and then discovered drift would already have
produced held-out evidence under an unknown configuration.

These tests use a small stand-in matrix where possible; the full 124-case
release run is executed once, for real, outside the test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import quantcheck as q
from tests.benchmark_support import FIXED_RUNTIME
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


@pytest.fixture(autouse=True)
def _gate_is_closed() -> None:
    assert_gate_closed()


# --------------------------------------------------------------------------
# The configuration
# --------------------------------------------------------------------------


def test_the_release_configuration_expands_to_the_frozen_matrix() -> None:
    config = q.build_authorized_release_config(release_candidate_id="c")
    assert_gate_closed()
    with q.reserved_final_seeds(release_candidate_id="c", seeds=q.RELEASE_SEEDS):
        matrix = q.expand_benchmark_cases(config)
    assert matrix.case_count == 124
    faults = [case for case in matrix.cases if case.case_kind == "fault"]
    controls = [case for case in matrix.cases if case.case_kind == "clean_control"]
    assert len(faults) == 120
    assert len(controls) == 4
    assert {case.fault_profile for case in controls} == set(q.BENCHMARK_FAULT_PROFILES)
    assert {case.seed for case in faults} == set(q.RELEASE_SEEDS)
    assert {case.severity for case in faults} == {"low", "medium", "high"}
    assert {case.seed_class for case in matrix.cases} == {"final"}


def test_the_release_configuration_is_order_independent() -> None:
    first = q.build_authorized_release_config(release_candidate_id="a")
    second = q.build_authorized_release_config(release_candidate_id="b")
    assert first.benchmark_id == second.benchmark_id
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)


def test_the_rehearsal_shares_the_release_matrix_shape() -> None:
    """The rehearsal must exercise the release shape, not an approximation."""
    rehearsal = q.rehearsal_benchmark_config((0, 1))
    release = q.build_authorized_release_config(release_candidate_id="c")
    for left, right in zip(rehearsal.profiles, release.profiles, strict=True):
        assert left.fault_profile == right.fault_profile
        assert left.fixture == right.fixture
        assert left.severities == right.severities
        assert left.research == right.research
        assert left.max_targets == right.max_targets
        assert left.clean_control is not None
        assert right.clean_control is not None
        assert left.clean_control.severity == right.clean_control.severity
    assert rehearsal.detector_configs == release.detector_configs


def test_the_rehearsal_configuration_uses_no_reserved_seed() -> None:
    rehearsal = q.rehearsal_benchmark_config((0, 100))
    for profile in rehearsal.profiles:
        assert not set(profile.seeds) & set(q.RESERVED_FINAL_SEEDS)


def test_an_empty_rehearsal_seed_set_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one ordinary seed"):
        q.rehearsal_benchmark_config(())


# --------------------------------------------------------------------------
# The run refuses to start without a valid candidate
# --------------------------------------------------------------------------


def test_a_missing_freeze_record_refuses_the_run(tmp_path: Path) -> None:
    with pytest.raises(q.ReleaseFreezeError, match="no release freeze record"):
        q.run_release_benchmark(
            repo_root=REPO_ROOT,
            freeze_record_path=tmp_path / "absent.json",
            output_root=tmp_path / "out",
            runtime=FIXED_RUNTIME,
        )
    assert not (tmp_path / "out").exists()


def test_a_missing_repository_root_refuses_the_run(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    path = written_freeze(tmp_path, record)
    with pytest.raises(q.ReleaseRunError, match="repository root"):
        q.run_release_benchmark(
            repo_root=tmp_path / "absent",
            freeze_record_path=path,
            output_root=tmp_path / "out",
            runtime=FIXED_RUNTIME,
        )
    assert not (tmp_path / "out").exists()


def test_a_drifted_frozen_input_refuses_the_run_before_any_case_dispatches(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    """The whole point of the freeze: drift stops the run, not one case in."""
    scratch = repo_copy(tmp_path / "repo")
    target = scratch / "src/quantcheck/duplicate_contract.py"
    target.write_text(target.read_text() + "\n# drift\n")
    path = written_freeze(tmp_path, record)
    output = tmp_path / "out"

    with pytest.raises(q.ReleaseRunError, match="no longer verifies"):
        q.run_release_benchmark(
            repo_root=scratch,
            freeze_record_path=path,
            output_root=output,
            runtime=FIXED_RUNTIME,
        )
    # No benchmark tree at all: not an empty one, not a partial one.
    assert not output.exists()
    assert_gate_closed()


def test_a_tampered_freeze_record_refuses_the_run(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    tampered = record.model_copy(update={"benchmark_id": "bench_" + "0" * 16})
    path = tmp_path / q.RELEASE_FREEZE_RECORD_NAME
    path.write_bytes(q.canonical_json_bytes(tampered))
    output = tmp_path / "out"
    with pytest.raises(q.ReleaseRunError, match="no longer verifies"):
        q.run_release_benchmark(
            repo_root=REPO_ROOT,
            freeze_record_path=path,
            output_root=output,
            runtime=FIXED_RUNTIME,
        )
    assert not output.exists()


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("final_seeds", tuple(range(1000, 1009)), "reserved final seed partition"),
        ("final_seeds", (0, 1, 2, 3, 4, 5, 6, 7, 8, 9), "reserved final seed partition"),
        ("total_case_count", 132, "case total"),
        ("fault_case_count", 96, "fault case count"),
        ("control_case_count", 12, "control case count"),
    ],
)
def test_a_record_disagreeing_with_the_release_contract_refuses_the_run(
    tmp_path: Path,
    record: q.ReleaseFreezeRecord,
    field: str,
    value: object,
    reason: str,
) -> None:
    """A malformed release request does no final-seed work at all.

    Each of these is checked before the authorization opens, so the run stops
    while the gate is still closed.
    """
    altered = record.model_copy(update={field: value})
    path = tmp_path / q.RELEASE_FREEZE_RECORD_NAME
    path.write_bytes(q.canonical_json_bytes(altered))
    output = tmp_path / "out"
    with pytest.raises(q.ReleaseRunError, match=reason):
        q.run_release_benchmark(
            repo_root=REPO_ROOT,
            freeze_record_path=path,
            output_root=output,
            runtime=FIXED_RUNTIME,
        )
    assert not output.exists()
    assert_gate_closed()


def test_the_gate_is_closed_again_after_a_refused_run(
    tmp_path: Path, record: q.ReleaseFreezeRecord
) -> None:
    scratch = repo_copy(tmp_path / "repo")
    (scratch / "uv.lock").write_text((scratch / "uv.lock").read_text() + "\n")
    path = written_freeze(tmp_path, record)
    with pytest.raises(q.ReleaseRunError):
        q.run_release_benchmark(
            repo_root=scratch,
            freeze_record_path=path,
            output_root=tmp_path / "out",
            runtime=FIXED_RUNTIME,
        )
    assert_gate_closed()


# --------------------------------------------------------------------------
# The run does not change scientific behaviour
# --------------------------------------------------------------------------


def test_the_release_path_adds_no_parameter_that_changes_science() -> None:
    import inspect

    parameters = set(inspect.signature(q.run_release_benchmark).parameters)
    assert parameters == {
        "repo_root",
        "freeze_record_path",
        "output_root",
        "runtime",
        "resume",
    }


def test_the_release_path_has_no_force_overwrite_option() -> None:
    import inspect

    for function in (q.run_release_benchmark, q.build_authorized_release_freeze):
        assert "force" not in inspect.signature(function).parameters


def test_the_release_configuration_uses_the_reviewed_offline_fixtures() -> None:
    """No live SEC execution is introduced to make the release look realistic."""
    config = q.build_authorized_release_config(release_candidate_id="c")
    fixtures = {profile.fixture.fixture_id for profile in config.profiles}
    assert fixtures == {
        "quantcheck/reviewed-fixture/v1",
        "quantcheck/benchmark-unit-drift-series/v1",
    }
