"""Manifest-blind local-series detection for Unit Drift."""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from quantcheck.hashing import (
    audit_input_snapshot_identity_matches,
    unit_drift_audit_report_id,
    unit_drift_finding_id,
)
from quantcheck.schemas import (
    AuditInputRecord,
    AuditInputSnapshot,
    AuditReport,
    Finding,
    UnitDriftDetectorConfig,
    UnitDriftEvidence,
    UnitDriftNeighborEvidence,
)
from quantcheck.unit_drift_contract import (
    UNIT_DRIFT_DETECTOR_ID,
    UNIT_DRIFT_DETECTOR_VERSION,
    UNIT_DRIFT_FAULT_SUBTYPE,
    UNIT_DRIFT_FAULT_TYPE,
    UNIT_DRIFT_RULE_ID,
    unit_drift_finding_severity,
)
from quantcheck.unit_drift_math import decimal_divide, symmetric_absolute_ratio
from quantcheck.unit_drift_series import ComparableObservation, build_comparable_observations

__all__ = [
    "UnitDriftDetectionError",
    "detect_unit_drift",
    "unit_drift_audit_report_identity_matches",
    "unit_drift_finding_identity_matches",
]


class UnitDriftDetectionError(ValueError):
    """Raised when sanitized detector input fails its content identity check."""


class _CorrectionCandidate(NamedTuple):
    scale_factor: Decimal
    operation: str
    correction_factor: Decimal
    corrected_value: Decimal
    after_ratios: tuple[Decimal, ...]


def _candidate_correction(
    observation: ComparableObservation[AuditInputRecord],
    config: UnitDriftDetectorConfig,
) -> tuple[_CorrectionCandidate, tuple[Decimal, ...]] | None:
    record = observation.record
    before_ratios = tuple(
        symmetric_absolute_ratio(record.value, neighbor.value)
        for _position, neighbor in observation.neighbors
    )
    if any(ratio < config.ratio_threshold for ratio in before_ratios):
        return None

    candidates: list[_CorrectionCandidate] = []
    for factor in config.supported_scale_factors:
        for operation in ("divide", "multiply"):
            correction_factor = (
                decimal_divide(Decimal(1), factor) if operation == "divide" else factor
            )
            corrected = record.value * correction_factor
            after_ratios = tuple(
                symmetric_absolute_ratio(corrected, neighbor.value)
                for _position, neighbor in observation.neighbors
            )
            if all(ratio < config.ratio_threshold for ratio in after_ratios):
                candidates.append(
                    _CorrectionCandidate(
                        scale_factor=factor,
                        operation=operation,
                        correction_factor=correction_factor,
                        corrected_value=corrected,
                        after_ratios=after_ratios,
                    )
                )
    if not candidates:
        return None
    operation_order = {"divide": 0, "multiply": 1}
    selected = min(
        candidates,
        key=lambda candidate: (
            max(candidate.after_ratios),
            sum(candidate.after_ratios, Decimal(0)),
            candidate.scale_factor,
            operation_order[candidate.operation],
        ),
    )
    return selected, before_ratios


def _finding_from_observation(
    observation: ComparableObservation[AuditInputRecord],
    audit_input: AuditInputSnapshot,
    config: UnitDriftDetectorConfig,
) -> Finding | None:
    correction_result = _candidate_correction(observation, config)
    if correction_result is None:
        return None
    candidate, before_ratios = correction_result
    record = observation.record
    neighbors = tuple(
        UnitDriftNeighborEvidence(
            position=position,  # type: ignore[arg-type]
            record_id=neighbor.record_id,
            period_start=neighbor.period_start,
            period_end=neighbor.period_end,
            value=neighbor.value,
            before_ratio=before_ratio,
            after_ratio=after_ratio,
        )
        for (position, neighbor), before_ratio, after_ratio in zip(
            observation.neighbors,
            before_ratios,
            candidate.after_ratios,
            strict=True,
        )
    )
    evidence = UnitDriftEvidence(
        record_id=record.record_id,
        comparable_series_key=observation.key,
        period_start=record.period_start,
        period_end=record.period_end,
        available_on=record.available_on,
        audit_as_of_date=audit_input.as_of_date,
        observed_value=record.value,
        candidate_scale_factor=candidate.scale_factor,
        correction_operation=candidate.operation,  # type: ignore[arg-type]
        candidate_correction_factor=candidate.correction_factor,
        corrected_value=candidate.corrected_value,
        ratio_threshold=config.ratio_threshold,
        neighbors=neighbors,
        usable_neighbor_count=len(neighbors),
        source_name=record.source_name,
        source_locator=record.source_locator,
    )
    confidence = "strong" if len(neighbors) == 2 else "suspicious"
    explanation = (
        f"Record {record.record_id} has a local scale discontinuity resolved by "
        f"{candidate.operation} with approved factor {candidate.scale_factor}; "
        f"{len(neighbors)} usable neighbor(s) satisfy {UNIT_DRIFT_RULE_ID}."
    )
    finding_body: dict[str, object] = {
        "detector_id": UNIT_DRIFT_DETECTOR_ID,
        "detector_version": UNIT_DRIFT_DETECTOR_VERSION,
        "fault_type": UNIT_DRIFT_FAULT_TYPE,
        "fault_subtype": UNIT_DRIFT_FAULT_SUBTYPE,
        "rule_id": UNIT_DRIFT_RULE_ID,
        "affected_record_ids": (record.record_id,),
        "severity": unit_drift_finding_severity(candidate.scale_factor),
        "confidence": confidence,
        "evidence": evidence,
        "explanation": explanation,
    }
    return Finding.model_validate(
        {
            "finding_id": unit_drift_finding_id(finding_body=finding_body),
            **finding_body,
        }
    )


def unit_drift_finding_identity_matches(finding: Finding) -> bool:
    """Report whether a Unit Drift finding ID covers all other fields."""
    if not isinstance(finding.evidence, UnitDriftEvidence):
        return False
    body = {name: getattr(finding, name) for name in Finding.model_fields if name != "finding_id"}
    return finding.finding_id == unit_drift_finding_id(finding_body=body)


def unit_drift_audit_report_identity_matches(report: AuditReport) -> bool:
    """Report whether a Unit Drift audit report ID covers all other fields."""
    body = {
        name: getattr(report, name)
        for name in AuditReport.model_fields
        if name != "audit_report_id"
    }
    return report.audit_report_id == unit_drift_audit_report_id(report_body=body)


def detect_unit_drift(
    audit_input: AuditInputSnapshot,
    config: UnitDriftDetectorConfig,
) -> AuditReport:
    """Detect approved scale corrections using sanitized data only."""
    if not audit_input_snapshot_identity_matches(audit_input):
        raise UnitDriftDetectionError("audit input identity does not match its content")
    observations = build_comparable_observations(
        audit_input.records,
        as_of_date=audit_input.as_of_date,
    )
    findings = tuple(
        sorted(
            (
                finding
                for record_id in sorted(observations)
                if (
                    finding := _finding_from_observation(
                        observations[record_id], audit_input, config
                    )
                )
                is not None
            ),
            key=lambda finding: finding.finding_id,
        )
    )
    report_body: dict[str, object] = {
        "detector_id": UNIT_DRIFT_DETECTOR_ID,
        "detector_version": UNIT_DRIFT_DETECTOR_VERSION,
        "audit_input_id": audit_input.audit_input_id,
        "dataset_name": audit_input.dataset_name,
        "as_of_date": audit_input.as_of_date,
        "findings": findings,
    }
    return AuditReport.model_validate(
        {
            "audit_report_id": unit_drift_audit_report_id(report_body=report_body),
            **report_body,
        }
    )
