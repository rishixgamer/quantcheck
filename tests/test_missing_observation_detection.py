"""Manifest-blind contextual detection and hard negatives."""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.hashing import dataset_snapshot_id
from quantcheck.missing_observation_contract import (
    CONTEXT_TO_RULE_ID,
    MissingObservationDetectorConfigV1,
    build_expected_observation,
    build_missing_observation_detector_config,
    missing_audit_report_identity_matches,
)
from quantcheck.missing_observation_detection import (
    MissingObservationDetectionError,
    detect_missing_observations,
)
from quantcheck.missing_observation_fixture import (
    EVALUATION_MECHANISMS,
    build_missing_observation_evaluation_case,
)
from quantcheck.missing_observation_injection import inject_missing_observations
from quantcheck.schemas import DatasetSnapshot
from quantcheck.serialization import canonical_json_bytes


@pytest.mark.parametrize("mechanism", EVALUATION_MECHANISMS)
def test_clean_control_has_no_findings_and_corruption_has_context_rule(
    mechanism: str,
) -> None:
    case = build_missing_observation_evaluation_case("development", mechanism)  # type: ignore[arg-type]
    clean_report = detect_missing_observations(
        sanitize_for_audit(case.clean_snapshot), case.detector_config
    )
    assert clean_report.findings == ()

    corrupted, manifest = inject_missing_observations(
        case.clean_snapshot, case.detector_config, case.injection_config
    )
    report = detect_missing_observations(sanitize_for_audit(corrupted), case.detector_config)
    expected_context = manifest.entries[0].expected_observation.context
    assert len(report.findings) == manifest.target_count
    assert {finding.rule_id for finding in report.findings} == {
        CONTEXT_TO_RULE_ID[expected_context]
    }
    assert missing_audit_report_identity_matches(report)


def test_absent_quarter_without_an_explicit_expectation_is_not_flagged() -> None:
    case = build_missing_observation_evaluation_case("development", "periodic_reporting_gap")
    removed_record = case.clean_snapshot.records[5]
    records = tuple(
        record
        for record in case.clean_snapshot.records
        if record.record_id != removed_record.record_id
    )
    snapshot = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name=case.clean_snapshot.dataset_name,
            as_of_date=case.clean_snapshot.as_of_date,
            records=records,
        ),
        dataset_name=case.clean_snapshot.dataset_name,
        as_of_date=case.clean_snapshot.as_of_date,
        records=records,
    )
    expectations = tuple(
        expectation
        for expectation in case.detector_config.expectations
        if not (
            expectation.series.entity_id == removed_record.entity_id
            and expectation.series.concept == removed_record.concept
            and expectation.period_end == removed_record.period_end
        )
    )
    config = build_missing_observation_detector_config(expectations)
    report = detect_missing_observations(sanitize_for_audit(snapshot), config)
    assert report.findings == ()


def test_future_expectation_is_explicitly_not_evaluated() -> None:
    case = build_missing_observation_evaluation_case("development", "random_missingness")
    base = case.detector_config.expectations[0]
    future = build_expected_observation(
        context=base.context,
        series=base.series,
        period_start=None,
        period_end=base.period_end,
        expected_by=date(2025, 1, 31),
        evidence_reference=base.evidence_reference,
    )
    config = build_missing_observation_detector_config((future,))
    records = tuple(
        record
        for record in case.clean_snapshot.records
        if record.record_id
        != next(
            record.record_id
            for record in case.clean_snapshot.records
            if record.entity_id == base.series.entity_id
            and record.concept == base.series.concept
            and record.period_end == base.period_end
        )
    )
    snapshot = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name=case.clean_snapshot.dataset_name,
            as_of_date=case.clean_snapshot.as_of_date,
            records=records,
        ),
        dataset_name=case.clean_snapshot.dataset_name,
        as_of_date=case.clean_snapshot.as_of_date,
        records=records,
    )
    report = detect_missing_observations(sanitize_for_audit(snapshot), config)
    assert report.findings == ()
    assert report.evaluated_expectation_ids == ()
    assert report.not_evaluated_expectation_ids == (future.expected_observation_id,)


def test_detector_boundary_has_no_manifest_or_injector_channel() -> None:
    signature = inspect.signature(detect_missing_observations)
    assert tuple(signature.parameters) == ("audit_input", "config")
    module = inspect.getmodule(detect_missing_observations)
    assert module is not None
    source = inspect.getsource(module)
    assert "missing_observation_injection" not in source
    assert "missing_observation_manifest" not in source
    assert "manifest" not in signature.parameters
    assert "clean_snapshot" not in signature.parameters
    assert "seed" not in signature.parameters


def test_sanitized_input_and_public_report_exclude_deleted_private_truth() -> None:
    case = build_missing_observation_evaluation_case("development", "entity_dependent_missingness")
    corrupted, manifest = inject_missing_observations(
        case.clean_snapshot, case.detector_config, case.injection_config
    )
    audit_input = sanitize_for_audit(corrupted)
    report = detect_missing_observations(audit_input, case.detector_config)
    public_bytes = canonical_json_bytes((audit_input, report))
    for entry in manifest.entries:
        assert entry.deleted_record.record_id.encode() not in public_bytes
        assert entry.deleted_record.source.source_row_key.encode() not in public_bytes
        assert (entry.deleted_record.entity_name or "").encode() not in public_bytes
    assert b"deleted_record" not in public_bytes
    assert b"selection_digest" not in public_bytes
    assert b"target_rank" not in public_bytes


def test_detector_refuses_config_with_stale_identity() -> None:
    case = build_missing_observation_evaluation_case("development", "random_missingness")
    stale = case.detector_config.model_copy(update={"detector_config_id": "mconf_0000000000000000"})
    assert isinstance(stale, MissingObservationDetectorConfigV1)
    with pytest.raises(MissingObservationDetectionError, match="identity"):
        detect_missing_observations(sanitize_for_audit(case.clean_snapshot), stale)
