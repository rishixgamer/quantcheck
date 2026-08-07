"""Manifest-blind exact-fingerprint-group detection for Duplicate Observations.

The only scientific input accepted here is :class:`AuditInputSnapshot`. This
module deliberately has no import of injection, replay, or scoring code, and
no free detector configuration: exact fingerprint matching has no parameters
to tune. The detector proves that a set of sanitized occurrences satisfies
the exact duplicate contract; it does not, and cannot, prove which member of
a group is the injected copy.
"""

from __future__ import annotations

from quantcheck.duplicate_contract import (
    DUPLICATE_DETECTOR_ID,
    DUPLICATE_DETECTOR_VERSION,
    DUPLICATE_FAULT_SUBTYPE,
    DUPLICATE_FAULT_TYPE,
    DUPLICATE_FINDING_SEVERITY,
    DUPLICATE_RULE_ID,
)
from quantcheck.duplicate_fingerprint import DuplicateGroup, build_duplicate_groups
from quantcheck.hashing import (
    audit_input_snapshot_identity_matches,
    duplicate_audit_report_id,
    duplicate_finding_id,
)
from quantcheck.schemas import (
    AuditInputRecord,
    AuditInputSnapshot,
    AuditReport,
    DuplicateEvidence,
    Finding,
)

__all__ = [
    "DuplicateDetectionError",
    "detect_duplicate_observations",
    "duplicate_audit_report_identity_matches",
    "duplicate_finding_identity_matches",
]


class DuplicateDetectionError(ValueError):
    """Raised when a sanitized audit input fails its content identity check."""


def _finding_from_group(
    group: DuplicateGroup[AuditInputRecord],
    audit_input: AuditInputSnapshot,
) -> Finding:
    record_ids = tuple(record.record_id for record in group.records)
    representative = group.records[0]
    evidence_body: dict[str, object] = {
        "record_ids": record_ids,
        "fingerprint_hash": group.fingerprint_hash,
        "group_size": len(record_ids),
        "entity_id": representative.entity_id,
        "concept_namespace": representative.concept_namespace,
        "concept": representative.concept,
        "value": representative.value,
        "unit": representative.unit,
        "dimensions": representative.dimensions,
        "period_type": representative.period_type,
        "period_start": representative.period_start,
        "period_end": representative.period_end,
        "filed_on": representative.filed_on,
        "available_on": representative.available_on,
        "accession_number": representative.accession_number,
        "audit_as_of_date": audit_input.as_of_date,
        "source_name": representative.source_name,
        "source_locator": representative.source_locator,
    }
    evidence = DuplicateEvidence.model_validate(evidence_body)
    explanation = (
        f"Records {', '.join(record_ids)} share an exact duplicate fingerprint "
        f"({len(record_ids)} occurrences) under {DUPLICATE_RULE_ID}."
    )
    finding_body: dict[str, object] = {
        "detector_id": DUPLICATE_DETECTOR_ID,
        "detector_version": DUPLICATE_DETECTOR_VERSION,
        "fault_type": DUPLICATE_FAULT_TYPE,
        "fault_subtype": DUPLICATE_FAULT_SUBTYPE,
        "rule_id": DUPLICATE_RULE_ID,
        "affected_record_ids": record_ids,
        "severity": DUPLICATE_FINDING_SEVERITY,
        "confidence": "proven_by_contract",
        "evidence": evidence,
        "explanation": explanation,
    }
    return Finding.model_validate(
        {
            "finding_id": duplicate_finding_id(finding_body=finding_body),
            **finding_body,
        }
    )


def duplicate_finding_identity_matches(finding: Finding) -> bool:
    """Report whether a Duplicate finding ID covers all other fields."""
    if not isinstance(finding.evidence, DuplicateEvidence):
        return False
    body = {name: getattr(finding, name) for name in Finding.model_fields if name != "finding_id"}
    return finding.finding_id == duplicate_finding_id(finding_body=body)


def duplicate_audit_report_identity_matches(report: AuditReport) -> bool:
    """Report whether a Duplicate audit report ID covers all other fields."""
    body = {
        name: getattr(report, name)
        for name in AuditReport.model_fields
        if name != "audit_report_id"
    }
    return report.audit_report_id == duplicate_audit_report_id(report_body=body)


def detect_duplicate_observations(audit_input: AuditInputSnapshot) -> AuditReport:
    """Detect exact public duplicate-fingerprint groups in sanitized data only."""
    if not audit_input_snapshot_identity_matches(audit_input):
        raise DuplicateDetectionError("audit input identity does not match its content")

    groups = build_duplicate_groups(audit_input.records, as_of_date=audit_input.as_of_date)
    findings = tuple(
        sorted(
            (
                _finding_from_group(group, audit_input)
                for group in groups.values()
                if len(group.records) >= 2
            ),
            key=lambda finding: finding.finding_id,
        )
    )
    report_body: dict[str, object] = {
        "detector_id": DUPLICATE_DETECTOR_ID,
        "detector_version": DUPLICATE_DETECTOR_VERSION,
        "audit_input_id": audit_input.audit_input_id,
        "dataset_name": audit_input.dataset_name,
        "as_of_date": audit_input.as_of_date,
        "findings": findings,
    }
    return AuditReport.model_validate(
        {
            "audit_report_id": duplicate_audit_report_id(report_body=report_body),
            **report_body,
        }
    )
