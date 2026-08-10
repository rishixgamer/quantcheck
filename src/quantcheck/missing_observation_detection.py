"""Manifest-blind detection of explicitly contextualized missing observations."""

from __future__ import annotations

from quantcheck.hashing import audit_input_snapshot_identity_matches, canonical_sha256
from quantcheck.missing_observation_contract import (
    MISSING_OBSERVATION_DETECTOR_ID,
    MISSING_OBSERVATION_DETECTOR_VERSION,
    MissingObservationAuditReportV1,
    MissingObservationDetectorConfigV1,
    detector_config_identity_matches,
    missing_audit_report_id,
)
from quantcheck.missing_observation_expectations import (
    build_missing_finding,
    matching_audit_records,
)
from quantcheck.schemas import AuditInputSnapshot

__all__ = ["MissingObservationDetectionError", "detect_missing_observations"]


class MissingObservationDetectionError(ValueError):
    """Raised when public detector input or expectation identity is invalid."""


def detect_missing_observations(
    audit_input: AuditInputSnapshot,
    config: MissingObservationDetectorConfigV1,
) -> MissingObservationAuditReportV1:
    """Find absences only where an explicit expectation is due.

    A quarter, entity, concept, or source that is not represented in ``config``
    is outside the detector's authority and never becomes a finding merely
    because adjacent records suggest a cadence.
    """
    if not isinstance(config, MissingObservationDetectorConfigV1):
        raise MissingObservationDetectionError(
            "config must be a strict MissingObservationDetectorConfigV1"
        )
    if not detector_config_identity_matches(config):
        raise MissingObservationDetectionError("detector config identity is invalid")
    if not audit_input_snapshot_identity_matches(audit_input):
        raise MissingObservationDetectionError("audit input identity does not match its content")

    evaluated = tuple(
        expectation
        for expectation in config.expectations
        if expectation.expected_by <= audit_input.as_of_date
    )
    not_evaluated = tuple(
        expectation
        for expectation in config.expectations
        if expectation.expected_by > audit_input.as_of_date
    )
    findings = tuple(
        sorted(
            (
                build_missing_finding(audit_input, expectation)
                for expectation in evaluated
                if not matching_audit_records(audit_input, expectation)
            ),
            key=lambda finding: finding.finding_id,
        )
    )
    body: dict[str, object] = {
        "detector_id": MISSING_OBSERVATION_DETECTOR_ID,
        "detector_version": MISSING_OBSERVATION_DETECTOR_VERSION,
        "audit_input_id": audit_input.audit_input_id,
        "dataset_name": audit_input.dataset_name,
        "as_of_date": audit_input.as_of_date,
        "detector_config_id": config.detector_config_id,
        "detector_config_hash": canonical_sha256(config),
        "evaluated_expectation_ids": tuple(
            expectation.expected_observation_id for expectation in evaluated
        ),
        "not_evaluated_expectation_ids": tuple(
            expectation.expected_observation_id for expectation in not_evaluated
        ),
        "findings": findings,
    }
    return MissingObservationAuditReportV1.model_validate(
        {"audit_report_id": missing_audit_report_id(body=body), **body}
    )
