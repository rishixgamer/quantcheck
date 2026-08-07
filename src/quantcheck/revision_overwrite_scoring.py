"""Exact one-to-one scoring for finalized Revision Overwrite findings."""

from __future__ import annotations

from decimal import Decimal, localcontext

from quantcheck.hashing import revision_overwrite_score_report_id
from quantcheck.revision_overwrite_contract import (
    REVISION_OVERWRITE_DETECTOR_ID,
    REVISION_OVERWRITE_DETECTOR_VERSION,
    REVISION_OVERWRITE_FINDING_SEVERITY,
    REVISION_OVERWRITE_RULE_ID,
    REVISION_OVERWRITE_SCORING_SPEC_VERSION,
)
from quantcheck.revision_overwrite_detection import (
    revision_overwrite_audit_report_identity_matches,
    revision_overwrite_finding_identity_matches,
)
from quantcheck.revision_overwrite_manifest import validate_revision_overwrite_manifest
from quantcheck.revision_overwrite_series import (
    economic_fact_key,
    public_revision_provenance_hash,
)
from quantcheck.schemas import (
    AuditReport,
    DetectionMetrics,
    ExactFindingMatch,
    Finding,
    RevisionHistoryUnit,
    RevisionOverwriteEvidence,
    RevisionOverwriteManifest,
    RevisionOverwriteManifestEntry,
    ScoreReport,
)

__all__ = [
    "RevisionOverwriteScoringError",
    "revision_overwrite_score_report_identity_matches",
    "score_revision_overwrite",
]


class RevisionOverwriteScoringError(ValueError):
    """Raised when report/manifest identities or case relationships disagree."""


def _exact_match(
    finding: Finding,
    entry: RevisionOverwriteManifestEntry,
    unit: RevisionHistoryUnit,
    report: AuditReport,
    manifest: RevisionOverwriteManifest,
) -> bool:
    if not isinstance(finding.evidence, RevisionOverwriteEvidence):
        return False
    evidence = finding.evidence
    corrupted = entry.corrupted_record
    later = unit.later_record
    return (
        revision_overwrite_finding_identity_matches(finding)
        and finding.detector_id == REVISION_OVERWRITE_DETECTOR_ID
        and finding.detector_version == REVISION_OVERWRITE_DETECTOR_VERSION
        and finding.fault_type == entry.fault_type
        and finding.fault_subtype == entry.fault_subtype
        and finding.rule_id == REVISION_OVERWRITE_RULE_ID
        and finding.affected_record_ids == (corrupted.record_id,)
        and finding.severity == REVISION_OVERWRITE_FINDING_SEVERITY
        and finding.confidence == "proven_by_contract"
        and evidence.record_id == corrupted.record_id
        and evidence.economic_fact_key == economic_fact_key(corrupted)
        and evidence.observed_value == corrupted.value == later.value
        and evidence.available_on == corrupted.available_on == unit.historical_record.available_on
        and evidence.filed_on == corrupted.filed_on == later.filed_on
        and evidence.audit_as_of_date == report.as_of_date == manifest.snapshot_as_of_date
        and evidence.accession_number == corrupted.accession_number == later.accession_number
        and evidence.form == corrupted.form == later.form
        and evidence.source_name == corrupted.source.source_name == later.source.source_name
        and evidence.source_locator
        == corrupted.source.source_locator
        == later.source.source_locator
        and evidence.public_provenance_hash == public_revision_provenance_hash(corrupted)
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


def revision_overwrite_score_report_identity_matches(report: ScoreReport) -> bool:
    body = {
        name: getattr(report, name)
        for name in ScoreReport.model_fields
        if name != "score_report_id"
    }
    return report.score_report_id == revision_overwrite_score_report_id(score_body=body)


def score_revision_overwrite(
    audit_report: AuditReport,
    manifest: RevisionOverwriteManifest,
) -> ScoreReport:
    """Score exact primary Revision Overwrite findings after audit finalization."""
    if not revision_overwrite_audit_report_identity_matches(audit_report):
        raise RevisionOverwriteScoringError("audit report identity does not match its content")
    validate_revision_overwrite_manifest(manifest)
    if (
        audit_report.detector_id != REVISION_OVERWRITE_DETECTOR_ID
        or audit_report.detector_version != REVISION_OVERWRITE_DETECTOR_VERSION
    ):
        raise RevisionOverwriteScoringError(
            "audit report was not finalized by the Revision Overwrite detector"
        )
    if (
        audit_report.dataset_name != manifest.dataset_name
        or audit_report.as_of_date != manifest.snapshot_as_of_date
    ):
        raise RevisionOverwriteScoringError("audit report and manifest describe different cases")

    units_by_id = {unit.eligibility_unit_id: unit for unit in manifest.eligible_units}
    candidates_by_finding: dict[int, list[int]] = {}
    for finding_index, finding in enumerate(audit_report.findings):
        candidates_by_finding[finding_index] = [
            entry_index
            for entry_index, entry in enumerate(manifest.entries)
            if _exact_match(
                finding,
                entry,
                units_by_id[entry.eligibility_unit_id],
                audit_report,
                manifest,
            )
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
    denominator = manifest.eligible_unit_count
    precision = _ratio(true_positive_count, finding_count) if finding_count else None
    recall = _ratio(true_positive_count, fault_count) if fault_count else None
    false_positive_rate = _ratio(false_positive_count, denominator) if denominator else None
    metrics = DetectionMetrics(
        injected_faults=fault_count,
        findings=finding_count,
        true_positive_faults=true_positive_count,
        false_negative_faults=false_negative_count,
        true_positive_findings=true_positive_count,
        false_positive_findings=false_positive_count,
        eligible_clean_denominator=denominator,
        precision=precision,
        recall=recall,
        false_positive_rate=false_positive_rate,
    )
    body: dict[str, object] = {
        "scoring_spec_version": REVISION_OVERWRITE_SCORING_SPEC_VERSION,
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
            "score_report_id": revision_overwrite_score_report_id(score_body=body),
            **body,
        }
    )
