"""Shared public expectation matching for Missing Observations.

This module contains no injector or manifest knowledge.  The injector uses it
only to precompute the exact public evidence that an independent detector is
expected to reproduce after rows are removed.
"""

from __future__ import annotations

from collections.abc import Sequence

from quantcheck.missing_observation_contract import (
    CONTEXT_TO_RULE_ID,
    CONTEXT_TO_SEVERITY,
    CONTEXT_TO_SUBTYPE,
    MISSING_OBSERVATION_DETECTOR_ID,
    MISSING_OBSERVATION_DETECTOR_VERSION,
    MISSING_OBSERVATION_FAULT_TYPE,
    ExpectedObservationV1,
    MissingObservationEvidenceV1,
    MissingObservationFindingV1,
    MissingObservationSeriesKeyV1,
    missing_finding_id,
)
from quantcheck.schemas import AuditInputRecord, AuditInputSnapshot

__all__ = [
    "audit_record_matches_expectation",
    "build_missing_evidence",
    "build_missing_finding",
    "matching_audit_records",
]


def _series_matches(record: AuditInputRecord, series: MissingObservationSeriesKeyV1) -> bool:
    return (
        record.entity_id == series.entity_id
        and record.concept_namespace == series.concept_namespace
        and record.concept == series.concept
        and record.unit == series.unit
        and record.dimensions == series.dimensions
        and record.period_type == series.period_type
        and record.source_name == series.source_name
        and record.source_locator == series.source_locator
    )


def audit_record_matches_expectation(
    record: AuditInputRecord, expectation: ExpectedObservationV1
) -> bool:
    """Match one visible record to one exact expected economic/source cell."""
    return (
        _series_matches(record, expectation.series)
        and record.period_start == expectation.period_start
        and record.period_end == expectation.period_end
    )


def matching_audit_records(
    audit_input: AuditInputSnapshot, expectation: ExpectedObservationV1
) -> tuple[AuditInputRecord, ...]:
    return tuple(
        record
        for record in audit_input.records
        if audit_record_matches_expectation(record, expectation)
    )


def _supporting_record_ids(
    records: Sequence[AuditInputRecord], expectation: ExpectedObservationV1
) -> tuple[str, ...]:
    same_series = sorted(
        (
            record
            for record in records
            if _series_matches(record, expectation.series)
            and record.period_end != expectation.period_end
        ),
        key=lambda record: (record.period_end, record.record_id),
    )
    previous = [record for record in same_series if record.period_end < expectation.period_end]
    following = [record for record in same_series if record.period_end > expectation.period_end]
    supporting = []
    if previous:
        supporting.append(previous[-1].record_id)
    if following:
        supporting.append(following[0].record_id)
    return tuple(sorted(supporting))


def build_missing_evidence(
    audit_input: AuditInputSnapshot, expectation: ExpectedObservationV1
) -> MissingObservationEvidenceV1:
    """Build public absence evidence for one due expectation.

    The caller must already have established that no exact matching record is
    present.  A future expectation is refused rather than treated as absent.
    """
    if expectation.expected_by > audit_input.as_of_date:
        raise ValueError("an expectation cannot be evaluated before expected_by")
    if matching_audit_records(audit_input, expectation):
        raise ValueError("an observed expectation cannot produce missing evidence")
    return MissingObservationEvidenceV1(
        expected_observation_id=expectation.expected_observation_id,
        context=expectation.context,
        series=expectation.series,
        period_start=expectation.period_start,
        period_end=expectation.period_end,
        expected_by=expectation.expected_by,
        evidence_reference=expectation.evidence_reference,
        audit_as_of_date=audit_input.as_of_date,
        observed_matching_record_count=0,
        supporting_record_ids=_supporting_record_ids(audit_input.records, expectation),
    )


def build_missing_finding(
    audit_input: AuditInputSnapshot, expectation: ExpectedObservationV1
) -> MissingObservationFindingV1:
    evidence = build_missing_evidence(audit_input, expectation)
    body: dict[str, object] = {
        "detector_id": MISSING_OBSERVATION_DETECTOR_ID,
        "detector_version": MISSING_OBSERVATION_DETECTOR_VERSION,
        "fault_type": MISSING_OBSERVATION_FAULT_TYPE,
        "fault_subtype": CONTEXT_TO_SUBTYPE[expectation.context],
        "rule_id": CONTEXT_TO_RULE_ID[expectation.context],
        "expected_observation_id": expectation.expected_observation_id,
        "affected_record_ids": evidence.supporting_record_ids,
        "severity": CONTEXT_TO_SEVERITY[expectation.context],
        "confidence": "proven_by_explicit_expectation",
        "evidence": evidence,
        "explanation": (
            f"Expected observation {expectation.expected_observation_id} was due by "
            f"{expectation.expected_by.isoformat()} under {expectation.evidence_reference} "
            f"but no exact matching record is present as of "
            f"{audit_input.as_of_date.isoformat()}."
        ),
    }
    return MissingObservationFindingV1.model_validate(
        {"finding_id": missing_finding_id(body=body), **body}
    )
