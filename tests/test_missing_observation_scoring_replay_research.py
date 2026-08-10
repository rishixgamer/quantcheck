"""Exact scoring, private replay, and controlled research impact."""

from __future__ import annotations

import pytest

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.hashing import dataset_snapshot_id
from quantcheck.missing_observation_contract import (
    MissingObservationAuditReportV1,
    MissingObservationFindingV1,
    MissingObservationManifestV1,
    MissingObservationResearchImpactV1,
    MissingObservationScoreReportV1,
    missing_audit_report_id,
)
from quantcheck.missing_observation_detection import detect_missing_observations
from quantcheck.missing_observation_expectations import build_missing_finding
from quantcheck.missing_observation_fixture import (
    MissingObservationEvaluationCase,
    build_missing_observation_evaluation_case,
)
from quantcheck.missing_observation_injection import inject_missing_observations
from quantcheck.missing_observation_manifest import (
    MissingObservationManifestError,
    validate_missing_observation_manifest,
)
from quantcheck.missing_observation_replay import (
    MissingObservationReplayError,
    manifest_assisted_exact_missing_observation_replay,
)
from quantcheck.missing_observation_research import compare_missing_observation_research
from quantcheck.missing_observation_scoring import (
    missing_score_report_identity_matches,
    score_missing_observations,
)
from quantcheck.schemas import DatasetSnapshot
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json


def _case_artifacts() -> tuple[
    MissingObservationEvaluationCase,
    DatasetSnapshot,
    MissingObservationManifestV1,
    MissingObservationAuditReportV1,
]:
    case = build_missing_observation_evaluation_case("development", "random_missingness")
    corrupted, manifest = inject_missing_observations(
        case.clean_snapshot, case.detector_config, case.injection_config
    )
    report = detect_missing_observations(sanitize_for_audit(corrupted), case.detector_config)
    return case, corrupted, manifest, report


def _report_with_findings(
    report: MissingObservationAuditReportV1,
    findings: tuple[MissingObservationFindingV1, ...],
) -> MissingObservationAuditReportV1:
    body = {
        name: getattr(report, name)
        for name in MissingObservationAuditReportV1.model_fields
        if name not in {"audit_report_id", "findings"}
    }
    body["findings"] = tuple(sorted(findings, key=lambda finding: finding.finding_id))
    return MissingObservationAuditReportV1.model_validate(
        {"audit_report_id": missing_audit_report_id(body=body), **body}
    )


def test_exact_one_to_one_score_and_identity() -> None:
    _case, _corrupted, manifest, report = _case_artifacts()
    score = score_missing_observations(report, manifest)
    assert score.metrics.injected_faults == manifest.target_count
    assert score.metrics.true_positive_faults == manifest.target_count
    assert score.metrics.false_positive_findings == 0
    assert score.metrics.false_negative_faults == 0
    assert score.metrics.precision == 1
    assert score.metrics.recall == 1
    assert score.f1 == 1
    assert missing_score_report_identity_matches(score)


def test_missing_finding_is_an_exact_false_negative() -> None:
    _case, _corrupted, manifest, report = _case_artifacts()
    shortened = _report_with_findings(report, report.findings[:-1])
    score = score_missing_observations(shortened, manifest)
    assert score.metrics.true_positive_faults == manifest.target_count - 1
    assert score.metrics.false_negative_faults == 1
    assert len(score.missed_fault_ids) == 1


def test_duplicate_finding_does_not_inflate_recall() -> None:
    _case, _corrupted, manifest, report = _case_artifacts()
    duplicated = _report_with_findings(report, report.findings + (report.findings[0],))
    score = score_missing_observations(duplicated, manifest)
    assert score.metrics.true_positive_faults == manifest.target_count
    assert score.metrics.true_positive_findings == manifest.target_count
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.recall == 1
    assert score.duplicate_finding_ids == (report.findings[0].finding_id,)


def test_unrelated_contextual_absence_is_a_false_positive() -> None:
    case, corrupted, manifest, report = _case_artifacts()
    selected_ids = {
        entry.expected_observation.expected_observation_id for entry in manifest.entries
    }
    unrelated = next(
        expectation
        for expectation in case.detector_config.expectations
        if expectation.expected_observation_id not in selected_ids
    )
    matching_record = next(
        record
        for record in corrupted.records
        if record.entity_id == unrelated.series.entity_id
        and record.concept == unrelated.series.concept
        and record.period_end == unrelated.period_end
    )
    temporary_records = tuple(
        record for record in corrupted.records if record.record_id != matching_record.record_id
    )
    temporary = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name=corrupted.dataset_name,
            as_of_date=corrupted.as_of_date,
            records=temporary_records,
        ),
        dataset_name=corrupted.dataset_name,
        as_of_date=corrupted.as_of_date,
        records=temporary_records,
    )
    extra = build_missing_finding(sanitize_for_audit(temporary), unrelated)
    expanded = _report_with_findings(report, report.findings + (extra,))
    score = score_missing_observations(expanded, manifest)
    assert score.metrics.true_positive_faults == manifest.target_count
    assert score.metrics.false_positive_findings == 1
    assert score.unmatched_finding_ids == (extra.finding_id,)


def test_private_replay_restores_exact_clean_bytes_and_is_idempotent() -> None:
    case, corrupted, manifest, _report = _case_artifacts()
    repaired = manifest_assisted_exact_missing_observation_replay(corrupted, manifest)
    assert canonical_json_bytes(repaired) == canonical_json_bytes(case.clean_snapshot)
    assert manifest_assisted_exact_missing_observation_replay(repaired, manifest) is repaired


def test_replay_refuses_a_different_valid_snapshot() -> None:
    _case, corrupted, manifest, _report = _case_artifacts()
    records = corrupted.records[:-1]
    tampered = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name=corrupted.dataset_name,
            as_of_date=corrupted.as_of_date,
            records=records,
        ),
        dataset_name=corrupted.dataset_name,
        as_of_date=corrupted.as_of_date,
        records=records,
    )
    with pytest.raises(MissingObservationReplayError, match="neither"):
        manifest_assisted_exact_missing_observation_replay(tampered, manifest)


def test_manifest_integrity_rejects_stale_identity() -> None:
    _case, _corrupted, manifest, _report = _case_artifacts()
    stale = manifest.model_copy(update={"manifest_id": "man_0000000000000000"})
    with pytest.raises(MissingObservationManifestError, match="identity"):
        validate_missing_observation_manifest(stale)


def test_controlled_cohort_mean_changes_and_exactly_restores() -> None:
    case, corrupted, manifest, _report = _case_artifacts()
    repaired = manifest_assisted_exact_missing_observation_replay(corrupted, manifest)
    impact = compare_missing_observation_research(
        case.clean_snapshot,
        corrupted,
        repaired,
        case.detector_config,
    )
    assert impact.changed is True
    assert impact.observed_count_delta == -manifest.target_count
    assert impact.aggregate_value_delta != 0
    assert impact.cohort_mean_delta != 0
    assert impact.exact_restoration is True


def test_score_and_research_artifacts_round_trip_canonically() -> None:
    case, corrupted, manifest, report = _case_artifacts()
    score = score_missing_observations(report, manifest)
    repaired = manifest_assisted_exact_missing_observation_replay(corrupted, manifest)
    impact = compare_missing_observation_research(
        case.clean_snapshot,
        corrupted,
        repaired,
        case.detector_config,
    )
    parsed_score = MissingObservationScoreReportV1.model_validate(
        parse_canonical_json(canonical_json_bytes(score))
    )
    parsed_impact = MissingObservationResearchImpactV1.model_validate(
        parse_canonical_json(canonical_json_bytes(impact))
    )
    assert parsed_score == score
    assert parsed_impact == impact
