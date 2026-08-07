"""Manifest-blind detection for period-end Look-Ahead violations.

The only scientific input accepted here is :class:`AuditInputSnapshot`.
This module deliberately has no import of injection, replay, or scoring code.
"""

from __future__ import annotations

from quantcheck.hashing import (
    audit_input_snapshot_identity_matches,
    lookahead_audit_report_id,
    lookahead_finding_id,
)
from quantcheck.lookahead_contract import (
    LOOKAHEAD_DETECTOR_ID,
    LOOKAHEAD_DETECTOR_VERSION,
    LOOKAHEAD_FAULT_SUBTYPE,
    LOOKAHEAD_FAULT_TYPE,
    LOOKAHEAD_RULE_ID,
    finding_severity,
)
from quantcheck.schemas import AuditInputRecord, AuditInputSnapshot, AuditReport, Finding

__all__ = [
    "LookAheadDetectionError",
    "audit_report_identity_matches",
    "detect_lookahead",
    "finding_identity_matches",
]


class LookAheadDetectionError(ValueError):
    """Raised when a sanitized audit input fails its content identity check."""


def _finding_body(record: AuditInputRecord, as_of_date: object) -> dict[str, object]:
    leaked_days = (record.filed_on - record.available_on).days
    evidence = {
        "record_id": record.record_id,
        "period_end": record.period_end,
        "available_on": record.available_on,
        "filed_on": record.filed_on,
        "audit_as_of_date": as_of_date,
        "leaked_days": leaked_days,
        "source_name": record.source_name,
        "source_locator": record.source_locator,
    }
    explanation = (
        f"Record {record.record_id} reports available_on {record.available_on.isoformat()} "
        f"at period end, before filed_on {record.filed_on.isoformat()}; this exposes "
        f"{leaked_days} days of information early under {LOOKAHEAD_RULE_ID}."
    )
    return {
        "detector_id": LOOKAHEAD_DETECTOR_ID,
        "detector_version": LOOKAHEAD_DETECTOR_VERSION,
        "fault_type": LOOKAHEAD_FAULT_TYPE,
        "fault_subtype": LOOKAHEAD_FAULT_SUBTYPE,
        "rule_id": LOOKAHEAD_RULE_ID,
        "affected_record_ids": (record.record_id,),
        "severity": finding_severity(leaked_days),
        "confidence": "proven_by_contract",
        "evidence": evidence,
        "explanation": explanation,
    }


def _finding_from_record(record: AuditInputRecord, audit_input: AuditInputSnapshot) -> Finding:
    body = _finding_body(record, audit_input.as_of_date)
    return Finding.model_validate(
        {
            "finding_id": lookahead_finding_id(finding_body=body),
            **body,
        }
    )


def finding_identity_matches(finding: Finding) -> bool:
    """Report whether a finding ID matches every other finding field."""
    body = {name: getattr(finding, name) for name in Finding.model_fields if name != "finding_id"}
    return finding.finding_id == lookahead_finding_id(finding_body=body)


def audit_report_identity_matches(report: AuditReport) -> bool:
    """Report whether a report ID matches every other report field."""
    body = {
        name: getattr(report, name)
        for name in AuditReport.model_fields
        if name != "audit_report_id"
    }
    return report.audit_report_id == lookahead_audit_report_id(report_body=body)


def detect_lookahead(audit_input: AuditInputSnapshot) -> AuditReport:
    """Detect exact public period-end substitutions in sanitized data only."""
    if not audit_input_snapshot_identity_matches(audit_input):
        raise LookAheadDetectionError("audit input identity does not match its content")

    findings = tuple(
        sorted(
            (
                _finding_from_record(record, audit_input)
                for record in audit_input.records
                if record.available_on == record.period_end
                and record.available_on < record.filed_on
                and record.available_on <= audit_input.as_of_date
            ),
            key=lambda finding: finding.finding_id,
        )
    )
    report_body: dict[str, object] = {
        "detector_id": LOOKAHEAD_DETECTOR_ID,
        "detector_version": LOOKAHEAD_DETECTOR_VERSION,
        "audit_input_id": audit_input.audit_input_id,
        "dataset_name": audit_input.dataset_name,
        "as_of_date": audit_input.as_of_date,
        "findings": findings,
    }
    return AuditReport.model_validate(
        {
            "audit_report_id": lookahead_audit_report_id(report_body=report_body),
            **report_body,
        }
    )
