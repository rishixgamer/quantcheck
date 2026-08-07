"""Manifest-blind detection of later provenance in an earlier state."""

from __future__ import annotations

from quantcheck.hashing import (
    audit_input_snapshot_identity_matches,
    revision_overwrite_audit_report_id,
    revision_overwrite_finding_id,
)
from quantcheck.revision_overwrite_contract import (
    REVISION_OVERWRITE_DETECTOR_ID,
    REVISION_OVERWRITE_DETECTOR_VERSION,
    REVISION_OVERWRITE_FAULT_SUBTYPE,
    REVISION_OVERWRITE_FAULT_TYPE,
    REVISION_OVERWRITE_FINDING_SEVERITY,
    REVISION_OVERWRITE_RULE_ID,
)
from quantcheck.revision_overwrite_series import (
    economic_fact_key,
    public_revision_provenance_hash,
)
from quantcheck.schemas import (
    AuditInputRecord,
    AuditInputSnapshot,
    AuditReport,
    Finding,
    RevisionOverwriteDetectorConfig,
    RevisionOverwriteEvidence,
)

__all__ = [
    "RevisionOverwriteDetectionError",
    "detect_revision_overwrite",
    "revision_overwrite_audit_report_identity_matches",
    "revision_overwrite_finding_identity_matches",
]


class RevisionOverwriteDetectionError(ValueError):
    """Raised when sanitized input/configuration fails its public contract."""


def _finding_from_record(
    record: AuditInputRecord,
    audit_input: AuditInputSnapshot,
) -> Finding:
    assert record.accession_number is not None
    evidence = RevisionOverwriteEvidence(
        record_id=record.record_id,
        economic_fact_key=economic_fact_key(record),
        observed_value=record.value,
        available_on=record.available_on,
        filed_on=record.filed_on,
        audit_as_of_date=audit_input.as_of_date,
        accession_number=record.accession_number,
        form=record.form,
        source_name=record.source_name,
        source_locator=record.source_locator,
        public_provenance_hash=public_revision_provenance_hash(record),
    )
    explanation = (
        f"Record {record.record_id} carries filing provenance dated "
        f"{record.filed_on.isoformat()} in a historical state as of "
        f"{audit_input.as_of_date.isoformat()}, while claiming availability "
        f"{record.available_on.isoformat()}; this satisfies {REVISION_OVERWRITE_RULE_ID}."
    )
    body: dict[str, object] = {
        "detector_id": REVISION_OVERWRITE_DETECTOR_ID,
        "detector_version": REVISION_OVERWRITE_DETECTOR_VERSION,
        "fault_type": REVISION_OVERWRITE_FAULT_TYPE,
        "fault_subtype": REVISION_OVERWRITE_FAULT_SUBTYPE,
        "rule_id": REVISION_OVERWRITE_RULE_ID,
        "affected_record_ids": (record.record_id,),
        "severity": REVISION_OVERWRITE_FINDING_SEVERITY,
        "confidence": "proven_by_contract",
        "evidence": evidence,
        "explanation": explanation,
    }
    return Finding.model_validate(
        {
            "finding_id": revision_overwrite_finding_id(finding_body=body),
            **body,
        }
    )


def revision_overwrite_finding_identity_matches(finding: Finding) -> bool:
    if not isinstance(finding.evidence, RevisionOverwriteEvidence):
        return False
    body = {name: getattr(finding, name) for name in Finding.model_fields if name != "finding_id"}
    return finding.finding_id == revision_overwrite_finding_id(finding_body=body)


def revision_overwrite_audit_report_identity_matches(report: AuditReport) -> bool:
    body = {
        name: getattr(report, name)
        for name in AuditReport.model_fields
        if name != "audit_report_id"
    }
    return report.audit_report_id == revision_overwrite_audit_report_id(report_body=body)


def detect_revision_overwrite(
    audit_input: AuditInputSnapshot,
    config: RevisionOverwriteDetectorConfig,
) -> AuditReport:
    """Detect only the public temporal contradiction in sanitized records."""
    if not isinstance(config, RevisionOverwriteDetectorConfig):
        raise RevisionOverwriteDetectionError(
            "config must be a strict RevisionOverwriteDetectorConfig"
        )
    if not audit_input_snapshot_identity_matches(audit_input):
        raise RevisionOverwriteDetectionError("audit input identity does not match its content")
    findings = tuple(
        sorted(
            (
                _finding_from_record(record, audit_input)
                for record in audit_input.records
                if record.accession_number is not None
                and record.available_on <= audit_input.as_of_date < record.filed_on
                and record.available_on < record.filed_on
            ),
            key=lambda finding: finding.finding_id,
        )
    )
    body: dict[str, object] = {
        "detector_id": REVISION_OVERWRITE_DETECTOR_ID,
        "detector_version": REVISION_OVERWRITE_DETECTOR_VERSION,
        "audit_input_id": audit_input.audit_input_id,
        "dataset_name": audit_input.dataset_name,
        "as_of_date": audit_input.as_of_date,
        "findings": findings,
    }
    return AuditReport.model_validate(
        {
            "audit_report_id": revision_overwrite_audit_report_id(report_body=body),
            **body,
        }
    )
