"""Four-family dispatch, all-detector execution, and manifest isolation."""

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest

import quantcheck as q
from tests.benchmark_support import (
    REVIEWED_HISTORICAL_HORIZON,
    case_of,
    duplicate_profile,
    lookahead_profile,
    revision_overwrite_profile,
    single_profile_config,
    unit_drift_profile,
)

_PROFILE_BUILDERS: dict[str, Callable[..., q.BenchmarkProfile]] = {
    "lookahead_timestamp": lookahead_profile,
    "unit_drift": unit_drift_profile,
    "duplicate_observation": duplicate_profile,
    "revision_overwrite": revision_overwrite_profile,
}

_PRIMARY_DETECTOR = {
    "lookahead_timestamp": (q.LOOKAHEAD_DETECTOR_ID, q.LOOKAHEAD_DETECTOR_VERSION),
    "unit_drift": (q.UNIT_DRIFT_DETECTOR_ID, q.UNIT_DRIFT_DETECTOR_VERSION),
    "duplicate_observation": (q.DUPLICATE_DETECTOR_ID, q.DUPLICATE_DETECTOR_VERSION),
    "revision_overwrite": (q.REVISION_OVERWRITE_DETECTOR_ID, q.REVISION_OVERWRITE_DETECTOR_VERSION),
}


def _fault_case(profile_name: str) -> q.BenchmarkCaseConfig:
    config = single_profile_config(_PROFILE_BUILDERS[profile_name]())
    return case_of(config, profile_name)


def _control_case(profile_name: str) -> q.BenchmarkCaseConfig:
    builder = _PROFILE_BUILDERS[profile_name]
    severity = "low" if profile_name == "revision_overwrite" else "medium"
    config = single_profile_config(
        builder(control=q.BenchmarkCleanControl(severity=severity, seed=0))
    )
    return case_of(config, profile_name, kind="clean_control")


@pytest.mark.parametrize("profile_name", sorted(_PROFILE_BUILDERS))
def test_every_completed_fault_family_dispatches_successfully(profile_name: str) -> None:
    artifacts = q.dispatch_benchmark_case(_fault_case(profile_name))
    assert artifacts.corrupted_snapshot is not None
    assert artifacts.manifest is not None
    assert artifacts.repaired_snapshot is not None
    assert artifacts.research_impact is not None
    assert artifacts.score.score_report is not None
    assert artifacts.score.metrics.injected_faults >= 1


@pytest.mark.parametrize("profile_name", sorted(_PROFILE_BUILDERS))
def test_every_case_runs_all_four_detectors_on_one_sanitized_input(profile_name: str) -> None:
    case = _fault_case(profile_name)
    artifacts = q.dispatch_benchmark_case(case)
    combined = q.run_all_detectors(artifacts.audit_input, case.detector_configs)
    detectors = case.detector_configs
    expected = (
        q.detect_lookahead(artifacts.audit_input).findings
        + q.detect_unit_drift(artifacts.audit_input, detectors.unit_drift_detector).findings
        + q.detect_duplicate_observations(artifacts.audit_input).findings
        + q.detect_revision_overwrite(
            artifacts.audit_input, detectors.revision_overwrite_detector
        ).findings
    )
    assert sorted(combined, key=lambda f: f.finding_id) == sorted(
        expected, key=lambda f: f.finding_id
    )
    assert artifacts.audit_report.findings == tuple(
        sorted(expected, key=lambda finding: finding.finding_id)
    )


@pytest.mark.parametrize("profile_name", sorted(_PROFILE_BUILDERS))
def test_the_combined_report_carries_its_primary_family_identity(profile_name: str) -> None:
    artifacts = q.dispatch_benchmark_case(_fault_case(profile_name))
    detector_id, detector_version = _PRIMARY_DETECTOR[profile_name]
    assert artifacts.audit_report.detector_id == detector_id
    assert artifacts.audit_report.detector_version == detector_version
    assert artifacts.audit_report.audit_input_id == artifacts.audit_input.audit_input_id


def test_no_detector_accepts_a_manifest_or_a_clean_snapshot_parameter() -> None:
    for detector in (
        q.detect_lookahead,
        q.detect_unit_drift,
        q.detect_duplicate_observations,
        q.detect_revision_overwrite,
    ):
        parameters = set(inspect.signature(detector).parameters)
        assert not parameters & {"manifest", "clean", "clean_snapshot", "seed", "severity"}


def test_the_all_detector_helper_exposes_no_manifest_channel() -> None:
    parameters = tuple(inspect.signature(q.run_all_detectors).parameters)
    assert parameters == ("audit_input", "detector_configs")
    assert "manifest" not in parameters
    assert "case" not in parameters


@pytest.mark.parametrize("profile_name", sorted(_PROFILE_BUILDERS))
def test_the_detector_input_is_the_sanitized_type_not_the_private_snapshot(
    profile_name: str,
) -> None:
    artifacts = q.dispatch_benchmark_case(_fault_case(profile_name))
    assert isinstance(artifacts.audit_input, q.AuditInputSnapshot)
    assert not isinstance(artifacts.audit_input, q.DatasetSnapshot)
    assert artifacts.corrupted_snapshot is not None
    sanitized_fields = set(q.AuditInputRecord.model_fields)
    private_fields = set(q.FinancialFact.model_fields)
    assert "entity_name" in private_fields - sanitized_fields
    assert "source" in private_fields - sanitized_fields


@pytest.mark.parametrize("profile_name", sorted(_PROFILE_BUILDERS))
def test_the_benchmark_score_is_the_untouched_family_score(profile_name: str) -> None:
    artifacts = q.dispatch_benchmark_case(_fault_case(profile_name))
    report = artifacts.score.score_report
    assert report is not None
    assert artifacts.score.metrics == report.metrics
    assert artifacts.score.f1 == report.f1
    assert report.audit_report_id == artifacts.audit_report.audit_report_id


def test_the_family_scorer_semantics_are_unchanged_by_the_benchmark_wrapper() -> None:
    """Re-scoring the benchmark's own report with the family scorer agrees exactly."""
    case = _fault_case("lookahead_timestamp")
    artifacts = q.dispatch_benchmark_case(case)
    assert artifacts.manifest is not None
    assert isinstance(artifacts.manifest, q.FaultManifest)
    direct = q.score_lookahead(artifacts.audit_report, artifacts.manifest)
    assert q.canonical_json_bytes(direct) == q.canonical_json_bytes(artifacts.score.score_report)


def test_cross_detector_findings_are_preserved_not_suppressed() -> None:
    """A Revision Overwrite case also trips the Duplicate contract; both survive."""
    artifacts = q.dispatch_benchmark_case(_fault_case("revision_overwrite"))
    fault_types = {finding.fault_type for finding in artifacts.audit_report.findings}
    assert "revision_overwrite" in fault_types
    assert len(fault_types) > 1, "expected a legitimate secondary detector finding"
    report = artifacts.score.score_report
    assert report is not None
    # The secondary finding is a false positive for the primary class, and it is
    # counted as one rather than removed to flatter the precision.
    assert report.metrics.false_positive_findings >= 1
    assert report.metrics.true_positive_findings == report.metrics.true_positive_faults


def test_a_wrong_class_finding_never_becomes_a_true_positive() -> None:
    artifacts = q.dispatch_benchmark_case(_fault_case("revision_overwrite"))
    report = artifacts.score.score_report
    assert report is not None
    matched = {match.finding_id for match in report.matches}
    by_id = {finding.finding_id: finding for finding in artifacts.audit_report.findings}
    assert all(by_id[finding_id].fault_type == "revision_overwrite" for finding_id in matched)


def test_duplicate_identical_findings_do_not_inflate_recall() -> None:
    artifacts = q.dispatch_benchmark_case(_fault_case("duplicate_observation"))
    report = artifacts.score.score_report
    assert report is not None
    assert report.metrics.true_positive_faults <= report.metrics.injected_faults
    assert report.metrics.true_positive_faults == report.metrics.true_positive_findings


@pytest.mark.parametrize("profile_name", sorted(_PROFILE_BUILDERS))
def test_clean_controls_run_every_detector_and_keep_every_finding(profile_name: str) -> None:
    case = _control_case(profile_name)
    artifacts = q.dispatch_benchmark_case(case)
    assert artifacts.corrupted_snapshot is None
    assert artifacts.manifest is None
    assert artifacts.research_summary is None
    assert artifacts.score.score_report is None
    assert artifacts.score.metrics.injected_faults == 0
    assert artifacts.score.metrics.recall is None
    assert artifacts.score.f1 is None
    findings = len(artifacts.audit_report.findings)
    assert artifacts.score.metrics.findings == findings
    assert artifacts.score.metrics.false_positive_findings == findings
    assert artifacts.score.metrics.true_positive_findings == 0


@pytest.mark.parametrize("profile_name", sorted(_PROFILE_BUILDERS))
def test_a_controls_denominator_is_its_fault_siblings_eligible_population(
    profile_name: str,
) -> None:
    """Control and fault denominators come from the same frozen eligibility rule."""
    builder = _PROFILE_BUILDERS[profile_name]
    severity = "low" if profile_name == "revision_overwrite" else "medium"
    config = single_profile_config(
        builder(control=q.BenchmarkCleanControl(severity=severity, seed=0))
    )
    fault = q.dispatch_benchmark_case(case_of(config, profile_name))
    control = q.dispatch_benchmark_case(case_of(config, profile_name, kind="clean_control"))
    fault_denominator = fault.score.metrics.eligible_clean_denominator
    control_denominator = control.score.metrics.eligible_clean_denominator
    assert control_denominator >= fault_denominator
    injected = fault.score.metrics.injected_faults
    assert control_denominator - fault_denominator in (0, injected)


def test_the_research_adapter_exposes_only_safe_public_facts() -> None:
    artifacts = q.dispatch_benchmark_case(_fault_case("lookahead_timestamp"))
    summary = artifacts.research_summary
    assert summary is not None
    assert set(q.BenchmarkResearchSummary.model_fields) == {
        "benchmark_case_id",
        "method",
        "changed",
        "exact_restoration",
    }
    impact = artifacts.research_impact
    assert isinstance(impact, q.ResearchImpact)
    assert summary.changed == impact.changed
    assert summary.exact_restoration == impact.exact_restoration


@pytest.mark.parametrize(
    ("profile_name", "method"),
    [
        ("lookahead_timestamp", "availability_count_v0_1"),
        ("unit_drift", "aggregate_value_v0_1"),
        ("duplicate_observation", "record_count_v0_1"),
        ("revision_overwrite", "growth_ranking_v0_1"),
    ],
)
def test_each_family_keeps_its_own_research_method(profile_name: str, method: str) -> None:
    artifacts = q.dispatch_benchmark_case(_fault_case(profile_name))
    assert artifacts.research_summary is not None
    assert artifacts.research_summary.method == method


def test_dispatch_rejects_an_unsupported_fault_profile() -> None:
    """A fault family outside the closed v0.1 set is refused, never improvised."""
    audit_input = q.sanitize_for_audit(
        q.build_dataset_snapshot(
            q.generate_reviewed_fixture(),
            dataset_name="reviewed",
            as_of_date=REVIEWED_HISTORICAL_HORIZON,
        )
    )
    with pytest.raises(q.BenchmarkDispatchError, match="unsupported fault profile"):
        q.combined_audit_report(audit_input, (), fault_profile="entity_swap")
