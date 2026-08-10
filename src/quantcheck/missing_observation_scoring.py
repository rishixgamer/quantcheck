"""Exact one-to-one scoring after Missing Observations audit finalization."""

from __future__ import annotations

from decimal import Decimal, localcontext

from quantcheck.missing_observation_contract import (
    MissingObservationAuditReportV1,
    MissingObservationExactMatchV1,
    MissingObservationFindingV1,
    MissingObservationManifestEntryV1,
    MissingObservationManifestV1,
    MissingObservationScoreReportV1,
    finding_identity_matches,
    missing_audit_report_identity_matches,
    missing_score_report_id,
)
from quantcheck.missing_observation_manifest import validate_missing_observation_manifest
from quantcheck.schemas import DetectionMetrics

__all__ = [
    "MissingObservationScoringError",
    "missing_score_report_identity_matches",
    "score_missing_observations",
]


class MissingObservationScoringError(ValueError):
    """Raised when report and private truth do not describe one finalized case."""


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
        return Decimal(2) * precision * recall / (precision + recall)


def _exact_match(
    finding: MissingObservationFindingV1,
    entry: MissingObservationManifestEntryV1,
) -> bool:
    expectation = entry.expected_observation
    return (
        finding_identity_matches(finding)
        and finding.expected_observation_id == expectation.expected_observation_id
        and finding.evidence == entry.expected_evidence
        and finding.affected_record_ids == entry.expected_evidence.supporting_record_ids
    )


def missing_score_report_identity_matches(report: MissingObservationScoreReportV1) -> bool:
    body = {
        name: getattr(report, name)
        for name in MissingObservationScoreReportV1.model_fields
        if name != "score_report_id"
    }
    return report.score_report_id == missing_score_report_id(body=body)


def score_missing_observations(
    audit_report: MissingObservationAuditReportV1,
    manifest: MissingObservationManifestV1,
) -> MissingObservationScoreReportV1:
    """Score exact contextual absences against private deleted-row truth."""
    if not missing_audit_report_identity_matches(audit_report):
        raise MissingObservationScoringError("audit report identity is invalid")
    validate_missing_observation_manifest(manifest)
    if (
        audit_report.dataset_name != manifest.dataset_name
        or audit_report.as_of_date != manifest.snapshot_as_of_date
        or audit_report.detector_config_id != manifest.detector_config.detector_config_id
        or audit_report.detector_config_hash != manifest.detector_config_hash
    ):
        raise MissingObservationScoringError("audit report and manifest describe different cases")

    entries_by_expectation = {
        entry.expected_observation.expected_observation_id: (index, entry)
        for index, entry in enumerate(manifest.entries)
    }
    candidates: dict[int, tuple[int, MissingObservationManifestEntryV1] | None] = {}
    for finding_index, finding in enumerate(audit_report.findings):
        candidate = entries_by_expectation.get(finding.expected_observation_id)
        if candidate is not None and _exact_match(finding, candidate[1]):
            candidates[finding_index] = candidate
        else:
            candidates[finding_index] = None

    matches: list[MissingObservationExactMatchV1] = []
    matched_findings: set[int] = set()
    matched_entries: set[int] = set()
    duplicate_findings: set[int] = set()
    for entry_index, entry in enumerate(manifest.entries):
        exact_findings = sorted(
            (
                finding_index
                for finding_index, candidate in candidates.items()
                if candidate is not None and candidate[0] == entry_index
            ),
            key=lambda index: (audit_report.findings[index].finding_id, index),
        )
        if not exact_findings:
            continue
        accepted = exact_findings[0]
        matched_findings.add(accepted)
        matched_entries.add(entry_index)
        duplicate_findings.update(exact_findings[1:])
        matches.append(
            MissingObservationExactMatchV1(
                fault_id=entry.fault_id,
                finding_id=audit_report.findings[accepted].finding_id,
            )
        )

    all_finding_indexes = set(range(len(audit_report.findings)))
    unmatched = all_finding_indexes - matched_findings - duplicate_findings
    missed = set(range(len(manifest.entries))) - matched_entries
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
        "scoring_spec_version": "quantcheck/missing-observation-scoring/v1",
        "audit_report_id": audit_report.audit_report_id,
        "manifest_id": manifest.manifest_id,
        "metrics": metrics,
        "f1": _f1(precision, recall),
        "matches": tuple(sorted(matches, key=lambda match: (match.fault_id, match.finding_id))),
        "unmatched_finding_ids": tuple(
            sorted({audit_report.findings[index].finding_id for index in unmatched})
        ),
        "duplicate_finding_ids": tuple(
            sorted({audit_report.findings[index].finding_id for index in duplicate_findings})
        ),
        "missed_fault_ids": tuple(sorted(manifest.entries[index].fault_id for index in missed)),
    }
    return MissingObservationScoreReportV1.model_validate(
        {"score_report_id": missing_score_report_id(body=body), **body}
    )
