"""Exact one-to-one scoring for finalized Unit Drift findings."""

from __future__ import annotations

from decimal import Decimal, localcontext

from quantcheck.hashing import unit_drift_score_report_id
from quantcheck.schemas import (
    AuditReport,
    DetectionMetrics,
    ExactFindingMatch,
    Finding,
    ScoreReport,
    UnitDriftEvidence,
    UnitDriftManifest,
    UnitDriftManifestEntry,
)
from quantcheck.unit_drift_contract import (
    UNIT_DRIFT_DETECTOR_ID,
    UNIT_DRIFT_DETECTOR_VERSION,
    UNIT_DRIFT_RULE_ID,
    UNIT_DRIFT_SCORING_SPEC_VERSION,
    unit_drift_finding_severity,
)
from quantcheck.unit_drift_detection import (
    unit_drift_audit_report_identity_matches,
    unit_drift_finding_identity_matches,
)
from quantcheck.unit_drift_manifest import validate_unit_drift_manifest
from quantcheck.unit_drift_math import decimal_divide

__all__ = [
    "UnitDriftScoringError",
    "score_unit_drift",
    "unit_drift_score_report_identity_matches",
]


class UnitDriftScoringError(ValueError):
    """Raised when report/manifest identities or case relationships disagree."""


def _exact_match(
    finding: Finding,
    entry: UnitDriftManifestEntry,
    report: AuditReport,
    manifest: UnitDriftManifest,
) -> bool:
    if not isinstance(finding.evidence, UnitDriftEvidence):
        return False
    evidence = finding.evidence
    corrupted = entry.corrupted_record
    original = entry.original_record
    reciprocal = decimal_divide(Decimal(1), entry.mutation.scale_factor)
    expected_confidence = "strong" if evidence.usable_neighbor_count == 2 else "suspicious"
    return (
        unit_drift_finding_identity_matches(finding)
        and finding.detector_id == UNIT_DRIFT_DETECTOR_ID
        and finding.detector_version == UNIT_DRIFT_DETECTOR_VERSION
        and finding.fault_type == entry.fault_type
        and finding.fault_subtype == entry.fault_subtype
        and finding.rule_id == UNIT_DRIFT_RULE_ID
        and finding.affected_record_ids == (corrupted.record_id,)
        and finding.severity == unit_drift_finding_severity(entry.mutation.scale_factor)
        and finding.confidence == expected_confidence
        and evidence.record_id == corrupted.record_id
        and evidence.comparable_series_key == entry.comparable_series_key
        and evidence.period_start == corrupted.period_start
        and evidence.period_end == corrupted.period_end
        and evidence.available_on == corrupted.available_on
        and evidence.audit_as_of_date == report.as_of_date == manifest.snapshot_as_of_date
        and evidence.observed_value == corrupted.value
        and evidence.candidate_scale_factor == entry.mutation.scale_factor
        and evidence.candidate_correction_factor in (entry.mutation.scale_factor, reciprocal)
        and evidence.corrected_value == original.value
        and evidence.source_name == corrupted.source.source_name
        and evidence.source_locator == corrupted.source.source_locator
    )


def _ratio(numerator: int, denominator: int) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return Decimal(numerator) / Decimal(denominator)


def _f1(precision: Decimal | None, recall: Decimal | None) -> Decimal | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return Decimal(0)
    with localcontext() as context:
        context.prec = 50
        return (Decimal(2) * precision * recall) / (precision + recall)


def unit_drift_score_report_identity_matches(report: ScoreReport) -> bool:
    """Report whether a Unit Drift score ID covers every other field."""
    body = {
        name: getattr(report, name)
        for name in ScoreReport.model_fields
        if name != "score_report_id"
    }
    return report.score_report_id == unit_drift_score_report_id(score_body=body)


def score_unit_drift(
    audit_report: AuditReport,
    manifest: UnitDriftManifest,
) -> ScoreReport:
    """Score exact findings after audit finalization, preserving all failures."""
    if not unit_drift_audit_report_identity_matches(audit_report):
        raise UnitDriftScoringError("audit report identity does not match its content")
    validate_unit_drift_manifest(manifest)
    if (
        audit_report.detector_id != UNIT_DRIFT_DETECTOR_ID
        or audit_report.detector_version != UNIT_DRIFT_DETECTOR_VERSION
    ):
        raise UnitDriftScoringError("audit report was not finalized by the Unit Drift detector")
    if (
        audit_report.dataset_name != manifest.dataset_name
        or audit_report.as_of_date != manifest.snapshot_as_of_date
    ):
        raise UnitDriftScoringError("audit report and manifest describe different cases")

    candidates_by_finding: dict[int, list[int]] = {}
    for finding_index, finding in enumerate(audit_report.findings):
        candidates_by_finding[finding_index] = [
            entry_index
            for entry_index, entry in enumerate(manifest.entries)
            if _exact_match(finding, entry, audit_report, manifest)
        ]

    ambiguous_finding_indexes = {
        index for index, candidates in candidates_by_finding.items() if len(candidates) > 1
    }
    ambiguous_entry_indexes = {
        entry_index
        for index in ambiguous_finding_indexes
        for entry_index in candidates_by_finding[index]
    }
    matches: list[ExactFindingMatch] = []
    matched_finding_indexes: set[int] = set()
    matched_entry_indexes: set[int] = set()
    duplicate_finding_indexes: set[int] = set()

    for entry_index, entry in enumerate(manifest.entries):
        if entry_index in ambiguous_entry_indexes:
            continue
        candidates = [
            finding_index
            for finding_index, entry_indexes in candidates_by_finding.items()
            if entry_index in entry_indexes and finding_index not in ambiguous_finding_indexes
        ]
        if not candidates:
            continue
        ordered = sorted(
            candidates,
            key=lambda index: (audit_report.findings[index].finding_id, index),
        )
        first_finding = audit_report.findings[ordered[0]]
        if any(audit_report.findings[index] != first_finding for index in ordered[1:]):
            ambiguous_finding_indexes.update(ordered)
            ambiguous_entry_indexes.add(entry_index)
            continue
        accepted_index = ordered[0]
        matched_finding_indexes.add(accepted_index)
        matched_entry_indexes.add(entry_index)
        duplicate_finding_indexes.update(ordered[1:])
        matches.append(
            ExactFindingMatch(
                fault_id=entry.fault_id,
                finding_id=audit_report.findings[accepted_index].finding_id,
            )
        )

    false_positive_indexes = set(range(len(audit_report.findings))) - matched_finding_indexes
    unmatched_finding_indexes = (
        false_positive_indexes - duplicate_finding_indexes - ambiguous_finding_indexes
    )
    missed_entry_indexes = set(range(len(manifest.entries))) - matched_entry_indexes

    true_positive_count = len(matches)
    finding_count = len(audit_report.findings)
    fault_count = len(manifest.entries)
    false_positive_count = finding_count - true_positive_count
    false_negative_count = fault_count - true_positive_count
    eligible_clean_denominator = manifest.eligible_record_count
    precision = _ratio(true_positive_count, finding_count) if finding_count else None
    recall = _ratio(true_positive_count, fault_count) if fault_count else None
    false_positive_rate = (
        _ratio(false_positive_count, eligible_clean_denominator)
        if eligible_clean_denominator
        else None
    )
    metrics = DetectionMetrics(
        injected_faults=fault_count,
        findings=finding_count,
        true_positive_faults=true_positive_count,
        false_negative_faults=false_negative_count,
        true_positive_findings=true_positive_count,
        false_positive_findings=false_positive_count,
        eligible_clean_denominator=eligible_clean_denominator,
        precision=precision,
        recall=recall,
        false_positive_rate=false_positive_rate,
    )
    score_body: dict[str, object] = {
        "scoring_spec_version": UNIT_DRIFT_SCORING_SPEC_VERSION,
        "audit_report_id": audit_report.audit_report_id,
        "manifest_id": manifest.manifest_id,
        "metrics": metrics,
        "f1": _f1(precision, recall),
        "matches": tuple(matches),
        "unmatched_finding_ids": tuple(
            sorted({audit_report.findings[index].finding_id for index in unmatched_finding_indexes})
        ),
        "duplicate_finding_ids": tuple(
            sorted({audit_report.findings[index].finding_id for index in duplicate_finding_indexes})
        ),
        "ambiguous_finding_ids": tuple(
            sorted({audit_report.findings[index].finding_id for index in ambiguous_finding_indexes})
        ),
        "missed_fault_ids": tuple(
            sorted(manifest.entries[index].fault_id for index in missed_entry_indexes)
        ),
        "ambiguous_fault_ids": tuple(
            sorted(manifest.entries[index].fault_id for index in ambiguous_entry_indexes)
        ),
    }
    return ScoreReport.model_validate(
        {
            "score_report_id": unit_drift_score_report_id(score_body=score_body),
            **score_body,
        }
    )
