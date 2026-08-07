"""Exact one-to-one Duplicate finding/manifest scoring.

This module consumes an already finalized immutable :class:`AuditReport` and
the private manifest. It never invokes detection and cannot affect findings.
"""

from __future__ import annotations

from decimal import Decimal, localcontext

from quantcheck.duplicate_contract import (
    DUPLICATE_DETECTOR_ID,
    DUPLICATE_DETECTOR_VERSION,
    DUPLICATE_FINDING_SEVERITY,
    DUPLICATE_RULE_ID,
    DUPLICATE_SCORING_SPEC_VERSION,
)
from quantcheck.duplicate_detection import (
    duplicate_audit_report_identity_matches,
    duplicate_finding_identity_matches,
)
from quantcheck.duplicate_manifest import validate_duplicate_manifest
from quantcheck.hashing import duplicate_score_report_id
from quantcheck.schemas import (
    AuditReport,
    DetectionMetrics,
    DuplicateEvidence,
    DuplicateManifest,
    DuplicateManifestEntry,
    ExactFindingMatch,
    Finding,
    ScoreReport,
)

__all__ = [
    "DuplicateScoringError",
    "duplicate_score_report_identity_matches",
    "score_duplicate_observations",
]


class DuplicateScoringError(ValueError):
    """Raised when report/manifest identities or case relationships disagree."""


def _exact_match(
    finding: Finding,
    entry: DuplicateManifestEntry,
    report: AuditReport,
    manifest: DuplicateManifest,
) -> bool:
    if not isinstance(finding.evidence, DuplicateEvidence):
        return False
    evidence = finding.evidence
    original = entry.original_record
    created = entry.created_record
    expected_group = tuple(sorted((original.record_id, created.record_id)))
    return (
        duplicate_finding_identity_matches(finding)
        and finding.detector_id == DUPLICATE_DETECTOR_ID
        and finding.detector_version == DUPLICATE_DETECTOR_VERSION
        and finding.fault_type == entry.fault_type
        and finding.fault_subtype == entry.fault_subtype
        and finding.rule_id == DUPLICATE_RULE_ID
        and finding.affected_record_ids == expected_group
        and finding.severity == DUPLICATE_FINDING_SEVERITY
        and finding.confidence == "proven_by_contract"
        and evidence.record_ids == expected_group
        and evidence.fingerprint_hash == entry.fingerprint_hash
        and evidence.group_size == 2
        and evidence.entity_id == original.entity_id
        and evidence.concept_namespace == original.concept_namespace
        and evidence.concept == original.concept
        and evidence.value == original.value
        and evidence.unit == original.unit
        and evidence.dimensions == original.dimensions
        and evidence.period_type == original.period_type
        and evidence.period_start == original.period_start
        and evidence.period_end == original.period_end
        and evidence.filed_on == original.filed_on
        and evidence.available_on == original.available_on
        and evidence.accession_number == original.accession_number
        and evidence.audit_as_of_date == report.as_of_date == manifest.snapshot_as_of_date
        and evidence.source_name == original.source.source_name
        and evidence.source_locator == original.source.source_locator
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


def duplicate_score_report_identity_matches(report: ScoreReport) -> bool:
    """Report whether a Duplicate score ID covers every other field."""
    body = {
        name: getattr(report, name)
        for name in ScoreReport.model_fields
        if name != "score_report_id"
    }
    return report.score_report_id == duplicate_score_report_id(score_body=body)


def score_duplicate_observations(
    audit_report: AuditReport,
    manifest: DuplicateManifest,
) -> ScoreReport:
    """Score exact findings after audit finalization, preserving all failures."""
    if not duplicate_audit_report_identity_matches(audit_report):
        raise DuplicateScoringError("audit report identity does not match its content")
    validate_duplicate_manifest(manifest)
    if (
        audit_report.detector_id != DUPLICATE_DETECTOR_ID
        or audit_report.detector_version != DUPLICATE_DETECTOR_VERSION
    ):
        raise DuplicateScoringError("audit report was not finalized by the Duplicate detector")
    if (
        audit_report.dataset_name != manifest.dataset_name
        or audit_report.as_of_date != manifest.snapshot_as_of_date
    ):
        raise DuplicateScoringError("audit report and manifest describe different cases")

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
        "scoring_spec_version": DUPLICATE_SCORING_SPEC_VERSION,
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
            "score_report_id": duplicate_score_report_id(score_body=score_body),
            **score_body,
        }
    )
