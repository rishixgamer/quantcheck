"""Structured failures, failure isolation, and safe resume semantics."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import quantcheck as q
from tests.benchmark_support import (
    FIXED_RUNTIME,
    duplicate_profile,
    lookahead_profile,
    private_root,
    public_bytes,
    public_root,
    single_profile_config,
)


def _ineligible_unit_drift_profile() -> q.BenchmarkUnitDriftProfile:
    """A Unit Drift profile whose horizon leaves no comparable series at all.

    Only the first observation of the benchmark series is visible, so the
    frozen three-observation comparability prerequisite cannot be met. This is
    a real eligibility failure, not a simulated one.
    """
    return q.BenchmarkUnitDriftProfile(
        fixture=q.BenchmarkFixtureConfig(
            fixture_id=q.UNIT_DRIFT_SERIES_FIXTURE_ID,
            dataset_name="benchmark-unit-drift-series",
            as_of_date=date(2024, 2, 1),
        ),
        severities=("medium",),
        seeds=(0,),
        research=q.BenchmarkUnitDriftResearch(research_as_of_date=date(2024, 2, 1)),
    )


def _mixed_config() -> q.BenchmarkConfig:
    return q.build_benchmark_config(
        benchmark_name="mixed",
        profiles=(
            _ineligible_unit_drift_profile(),
            lookahead_profile(),
            duplicate_profile(),
        ),
    )


def test_one_failed_case_does_not_stop_the_others(tmp_path: Path) -> None:
    result = q.run_benchmark(_mixed_config(), output_root=tmp_path, runtime=FIXED_RUNTIME)
    by_profile = {status.fault_profile: status for status in result.statuses}
    assert by_profile["unit_drift"].status == "failed"
    assert by_profile["lookahead_timestamp"].status == "succeeded"
    assert by_profile["duplicate_observation"].status == "succeeded"


def test_a_failed_case_stays_visible_in_the_matrix_and_the_totals(tmp_path: Path) -> None:
    result = q.run_benchmark(_mixed_config(), output_root=tmp_path, runtime=FIXED_RUNTIME)
    assert result.matrix.case_count == 3
    overall = result.aggregate.overall
    assert overall.configured_case_count == 3
    assert overall.failed_case_count == 1
    assert overall.successful_case_count == 2
    assert overall.incomplete_case_count == 0


def test_a_failed_case_is_excluded_from_pooled_detection_metrics(tmp_path: Path) -> None:
    result = q.run_benchmark(_mixed_config(), output_root=tmp_path, runtime=FIXED_RUNTIME)
    unit_drift = next(
        group for group in result.aggregate.by_fault_profile if group.key == "unit_drift"
    )
    assert unit_drift.configured_case_count == 1
    assert unit_drift.failed_case_count == 1
    assert unit_drift.injected_faults == 0
    assert unit_drift.findings == 0
    assert unit_drift.eligible_clean_denominator == 0
    assert unit_drift.recall is None
    assert unit_drift.false_positive_rate is None


def test_the_public_failure_is_categorized_and_redacted(tmp_path: Path) -> None:
    result = q.run_benchmark(_mixed_config(), output_root=tmp_path, runtime=FIXED_RUNTIME)
    failure = next(s for s in result.statuses if s.status == "failed").failure
    assert failure is not None
    assert failure.stage == "injection"
    assert failure.category == "no_eligible_targets"
    assert failure.error_code == "no_eligible_targets"
    assert failure.message == q.redacted_failure_message("no_eligible_targets")
    assert "Traceback" not in failure.message
    assert str(tmp_path) not in failure.message


def test_private_diagnostics_keep_the_developer_detail_out_of_public_bytes(
    tmp_path: Path,
) -> None:
    result = q.run_benchmark(_mixed_config(), output_root=tmp_path, runtime=FIXED_RUNTIME)
    failed = next(s for s in result.statuses if s.status == "failed")
    diagnostics_path = (
        private_root(tmp_path) / "cases" / failed.benchmark_case_id / "diagnostics.json"
    )
    diagnostics = q.BenchmarkPrivateDiagnostics.model_validate(
        q.parse_canonical_json(diagnostics_path.read_bytes())
    )
    assert diagnostics.exception_class == "NoEligibleUnitDriftTargetsError"
    assert diagnostics.exception_message
    assert "\n" not in diagnostics.exception_message
    payload = public_bytes(tmp_path)
    assert diagnostics.exception_message.encode() not in payload
    assert diagnostics.exception_class.encode() not in payload


def test_a_failed_case_persists_no_public_case_artifacts(tmp_path: Path) -> None:
    result = q.run_benchmark(_mixed_config(), output_root=tmp_path, runtime=FIXED_RUNTIME)
    failed = next(s for s in result.statuses if s.status == "failed")
    directory = public_root(tmp_path) / "cases" / failed.benchmark_case_id
    assert {path.name for path in directory.iterdir()} == {"status.json"}
    assert failed.artifacts == ()


def test_a_rerun_retries_the_failed_case_while_reusing_the_successful_ones(
    tmp_path: Path,
) -> None:
    """The retry policy is per case: failure is reattempted, success is reused."""
    config = _mixed_config()
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    failed_id = next(s.benchmark_case_id for s in first.statuses if s.status == "failed")
    succeeded_ids = {s.benchmark_case_id for s in first.statuses if s.status == "succeeded"}

    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    assert set(second.reused_case_ids) == succeeded_ids
    assert failed_id not in second.reused_case_ids
    assert failed_id not in second.dispatched_case_ids  # it failed again
    assert next(s for s in second.statuses if s.benchmark_case_id == failed_id).status == "failed"


def test_one_output_root_holds_exactly_one_logical_benchmark(tmp_path: Path) -> None:
    """A second, different benchmark cannot quietly take over an existing root."""
    q.run_benchmark(
        single_profile_config(lookahead_profile(), name="first"),
        output_root=tmp_path,
        runtime=FIXED_RUNTIME,
    )
    with pytest.raises(q.ArtifactIntegrityError, match="different content"):
        q.run_benchmark(
            single_profile_config(duplicate_profile(), name="second"),
            output_root=tmp_path,
            runtime=FIXED_RUNTIME,
        )


def test_rerunning_a_failed_case_reattempts_rather_than_reusing_it(tmp_path: Path) -> None:
    config = single_profile_config(_ineligible_unit_drift_profile(), name="reattempt")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    assert first.statuses[0].status == "failed"
    assert second.statuses[0].status == "failed"
    assert second.reused_case_ids == ()


def test_a_valid_prior_success_is_reused_without_redispatching(tmp_path: Path) -> None:
    config = single_profile_config(lookahead_profile(), name="reuse")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    before = {
        path: path.read_bytes()
        for path in sorted(public_root(tmp_path).rglob("*.json"))
        if path.name not in {"runtime_metadata.json", "index.json", "aggregate_report.json"}
    }
    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    assert first.dispatched_case_ids and second.dispatched_case_ids == ()
    assert set(second.reused_case_ids) == set(first.dispatched_case_ids)
    after = {path: path.read_bytes() for path in before}
    assert after == before


def test_an_incomplete_case_without_a_status_is_completed_on_the_next_run(
    tmp_path: Path,
) -> None:
    config = single_profile_config(lookahead_profile(), name="partial")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    case_id = first.statuses[0].benchmark_case_id
    status_path = public_root(tmp_path) / "cases" / case_id / "status.json"
    status_bytes = status_path.read_bytes()
    status_path.unlink()

    # Without a terminal status the case counts as incomplete, not successful.
    interim = q.aggregate_from_public_root(tmp_path)
    assert interim.overall.incomplete_case_count == 1

    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    assert second.dispatched_case_ids == (case_id,)
    assert second.statuses[0].status == "succeeded"
    assert status_path.read_bytes() == status_bytes


def test_a_successful_status_whose_artifact_is_missing_becomes_an_integrity_failure(
    tmp_path: Path,
) -> None:
    config = single_profile_config(lookahead_profile(), name="corrupt-missing")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    case_id = first.statuses[0].benchmark_case_id
    (public_root(tmp_path) / "cases" / case_id / "score.json").unlink()

    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    status = second.statuses[0]
    assert status.status == "failed"
    assert status.failure is not None
    assert status.failure.category == "integrity"
    assert status.failure.error_code == "prior_success_invalid"
    assert second.dispatched_case_ids == ()
    # The conflicting successful status is left exactly as it was found.
    stored = q.BenchmarkCaseStatus.model_validate(
        q.parse_canonical_json(
            (public_root(tmp_path) / "cases" / case_id / "status.json").read_bytes()
        )
    )
    assert stored.status == "succeeded"
    # Aggregation independently refuses to count it as a success.
    assert second.aggregate.overall.successful_case_count == 0
    assert second.aggregate.overall.incomplete_case_count == 1


def test_a_successful_status_whose_artifact_was_edited_becomes_an_integrity_failure(
    tmp_path: Path,
) -> None:
    config = single_profile_config(lookahead_profile(), name="corrupt-edited")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    case_id = first.statuses[0].benchmark_case_id
    tampered = public_root(tmp_path) / "cases" / case_id / "audit_report.json"
    tampered.write_bytes(b'{"audit_report_id":"arep_0000000000000000"}')

    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    assert second.statuses[0].status == "failed"
    assert second.statuses[0].failure is not None
    assert second.statuses[0].failure.error_code == "prior_success_invalid"
    assert tampered.read_bytes() == b'{"audit_report_id":"arep_0000000000000000"}'
    assert second.aggregate.overall.incomplete_case_count == 1


def test_conflicting_immutable_case_bytes_are_rejected_during_a_rerun(
    tmp_path: Path,
) -> None:
    """A partial rerun that would rewrite evidence differently fails loudly."""
    config = single_profile_config(lookahead_profile(), name="conflict")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    case_id = first.statuses[0].benchmark_case_id
    case_directory = public_root(tmp_path) / "cases" / case_id
    (case_directory / "status.json").unlink()
    conflicting = b'{"benchmark_case_id":"' + case_id.encode() + b'","changed":false}'
    (case_directory / "research_summary.json").write_bytes(conflicting)

    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    status = second.statuses[0]
    assert status.status == "failed"
    assert status.failure is not None
    assert status.failure.stage == "persistence"
    assert status.failure.error_code == "artifact_conflict"
    assert (case_directory / "research_summary.json").read_bytes() == conflicting


def test_resume_can_be_disabled_without_destroying_prior_evidence(tmp_path: Path) -> None:
    config = single_profile_config(lookahead_profile(), name="no-resume")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME, resume=False)
    assert second.dispatched_case_ids == first.dispatched_case_ids
    assert second.statuses[0].status == "succeeded"
    assert q.canonical_json_bytes(first.aggregate) == q.canonical_json_bytes(second.aggregate)


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (q.NoEligibleUnitDriftTargetsError("x"), ("injection", "no_eligible_targets")),
        (q.NoEligibleLookAheadTargetsError("x"), ("injection", "no_eligible_targets")),
        (q.NoEligibleDuplicateTargetsError("x"), ("injection", "no_eligible_targets")),
        (q.NoEligibleRevisionOverwriteTargetsError("x"), ("injection", "no_eligible_targets")),
        (q.LookAheadScoringError("x"), ("scoring", "integrity")),
        (q.DuplicateReplayError("x"), ("repair", "integrity")),
        (q.UnitDriftResearchError("x"), ("research", "integrity")),
        (q.RevisionOverwriteDetectionError("x"), ("detection", "integrity")),
        (q.CanonicalizationError("x"), ("serialization", "integrity")),
        (q.ArtifactIntegrityError("x"), ("persistence", "integrity")),
        (q.ArtifactPersistenceError("x"), ("persistence", "persistence")),
        (q.UnknownBenchmarkFixtureError("x"), ("fixture_load", "configuration")),
        (q.BenchmarkConfigurationError("x"), ("expansion", "configuration")),
        (q.BenchmarkDispatchError("x"), ("dispatch", "configuration")),
        (RuntimeError("x"), ("dispatch", "internal")),
    ],
)
def test_every_recognized_failure_maps_to_a_stable_stage_and_category(
    exception: BaseException,
    expected: tuple[str, str],
) -> None:
    stage, category, code = q.classify_case_exception(exception)
    assert (stage, category) == expected
    assert code and code == code.strip() and " " not in code


def test_an_unrecognized_failure_is_recorded_rather_than_swallowed() -> None:
    stage, category, code = q.classify_case_exception(ZeroDivisionError("boom"))
    assert (stage, category, code) == ("dispatch", "internal", "unexpected_internal_error")
    assert q.redacted_failure_message("internal")


def test_resume_validates_private_evidence_not_only_public_artifacts(
    tmp_path: Path,
) -> None:
    """A prior success whose hidden truth was altered is an integrity failure."""
    config = single_profile_config(lookahead_profile(), name="private-tamper")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    case_id = first.statuses[0].benchmark_case_id
    manifest_path = private_root(tmp_path) / "cases" / case_id / "manifest.json"
    original = manifest_path.read_bytes()
    manifest_path.write_bytes(b'{"manifest_id":"man_0000000000000000"}')

    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    status = second.statuses[0]
    assert status.status == "failed"
    assert status.failure is not None
    assert status.failure.error_code == "prior_success_invalid"
    assert second.dispatched_case_ids == ()
    # The tampered private artifact is reported, never silently rewritten.
    assert manifest_path.read_bytes() != original


def test_resume_rejects_a_success_whose_private_evidence_is_missing(
    tmp_path: Path,
) -> None:
    config = single_profile_config(lookahead_profile(), name="private-missing")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    case_id = first.statuses[0].benchmark_case_id
    (private_root(tmp_path) / "cases" / case_id / "repaired_snapshot.json").unlink()

    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    assert second.statuses[0].status == "failed"
    assert second.statuses[0].failure is not None
    assert second.statuses[0].failure.error_code == "prior_success_invalid"


def test_resume_rejects_a_success_whose_private_index_is_absent(tmp_path: Path) -> None:
    config = single_profile_config(lookahead_profile(), name="no-private-index")
    first = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    case_id = first.statuses[0].benchmark_case_id
    (private_root(tmp_path) / "cases" / case_id / "private_index.json").unlink()

    second = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    assert second.statuses[0].status == "failed"
    assert second.statuses[0].failure is not None
    assert second.statuses[0].failure.error_code == "prior_success_invalid"


def test_a_stale_failure_diagnostic_does_not_taint_a_later_success(
    tmp_path: Path,
) -> None:
    """Private forensics from an earlier attempt are kept, not mistaken for state."""
    config = single_profile_config(lookahead_profile(), name="stale-diagnostics")
    matrix = q.expand_benchmark_cases(config)
    case_id = matrix.cases[0].benchmark_case_id
    diagnostics = private_root(tmp_path) / "cases" / case_id / "diagnostics.json"
    diagnostics.parent.mkdir(parents=True)
    diagnostics.write_bytes(
        q.canonical_json_bytes(
            q.BenchmarkPrivateDiagnostics(
                benchmark_case_id=case_id,
                stage="injection",
                category="no_eligible_targets",
                error_code="no_eligible_targets",
                exception_class="NoEligibleLookAheadTargetsError",
                exception_message="from an earlier attempt",
            )
        )
    )
    result = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    assert result.statuses[0].status == "succeeded"
    assert diagnostics.is_file()
    assert b"from an earlier attempt" not in public_bytes(tmp_path)
