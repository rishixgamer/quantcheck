"""Exact Duplicate matching, duplicate/ambiguity handling, and metrics."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.duplicate_support import (
    ReviewedDuplicateCase,
    rebuild_duplicate_finding,
    rebuild_duplicate_report,
    reviewed_duplicate_case,
)


def _rebuild_manifest(manifest: q.DuplicateManifest, **updates: object) -> q.DuplicateManifest:
    body = {
        name: getattr(manifest, name)
        for name in q.DuplicateManifest.model_fields
        if name != "manifest_id"
    }
    body.update(updates)
    return q.DuplicateManifest.model_validate(
        {
            "manifest_id": q.duplicate_manifest_id(manifest_body=body),
            **body,
        }
    )


def _exact_findings(case: ReviewedDuplicateCase) -> tuple[q.Finding, ...]:
    entry_groups = {
        tuple(sorted((entry.original_record.record_id, entry.created_record.record_id)))
        for entry in case.manifest.entries
    }
    return tuple(
        finding
        for finding in case.audit_report.findings
        if finding.affected_record_ids in entry_groups
    )


def test_exact_match_scores_every_injected_fault_and_uses_eligible_denominator() -> None:
    case = reviewed_duplicate_case()
    assert case.manifest.target_count == 4
    score = case.score
    assert score.metrics.injected_faults == 4
    assert score.metrics.true_positive_faults == 4
    assert score.metrics.false_negative_faults == 0
    assert score.metrics.true_positive_findings == 4
    assert score.metrics.eligible_clean_denominator == case.manifest.eligible_record_count
    assert score.metrics.recall == Decimal(1)
    assert score.metrics.precision == Decimal(4) / Decimal(5)
    assert score.f1 is not None


def test_natural_unrelated_group_is_an_unmatched_false_positive_not_a_miss() -> None:
    case = reviewed_duplicate_case()
    exact = _exact_findings(case)
    assert len(exact) == 4
    unrelated = [f for f in case.audit_report.findings if f not in exact]
    assert len(unrelated) == 1
    score = case.score
    assert score.metrics.false_positive_findings == 1
    assert unrelated[0].finding_id in score.unmatched_finding_ids
    assert score.metrics.false_negative_faults == 0


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("fault_type", "unit_drift"),
        ("fault_subtype", "fuzzy_copy"),
        ("rule_id", "occurrence.other_rule"),
    ],
)
def test_wrong_class_subtype_or_rule_is_unmatched_and_fault_is_missed(
    field: str, replacement: str
) -> None:
    case = reviewed_duplicate_case()
    target = _exact_findings(case)[0]
    wrong = rebuild_duplicate_finding(target, **{field: replacement})
    report = rebuild_duplicate_report(
        case.audit_report,
        tuple(f for f in case.audit_report.findings if f != target) + (wrong,),
    )
    score = q.score_duplicate_observations(report, case.manifest)
    assert score.metrics.true_positive_faults == 3
    assert score.metrics.false_negative_faults == 1
    assert wrong.finding_id in score.unmatched_finding_ids


def test_wrong_group_membership_is_a_near_match_not_true_positive() -> None:
    case = reviewed_duplicate_case()
    target = _exact_findings(case)[0]
    evidence = target.evidence
    assert isinstance(evidence, q.DuplicateEvidence)
    wrong_ids = tuple(sorted(("rec_ffffffffffffffff", "rec_eeeeeeeeeeeeeeee")))
    wrong_evidence = evidence.model_copy(update={"record_ids": wrong_ids})
    wrong = rebuild_duplicate_finding(
        target, affected_record_ids=wrong_ids, evidence=wrong_evidence
    )
    report = rebuild_duplicate_report(
        case.audit_report,
        tuple(f for f in case.audit_report.findings if f != target) + (wrong,),
    )
    score = q.score_duplicate_observations(report, case.manifest)
    assert score.metrics.true_positive_faults == 3
    assert wrong.finding_id in score.unmatched_finding_ids


def test_wrong_fingerprint_hash_is_a_near_match() -> None:
    case = reviewed_duplicate_case()
    target = _exact_findings(case)[0]
    evidence = target.evidence
    assert isinstance(evidence, q.DuplicateEvidence)
    wrong_evidence = evidence.model_copy(update={"fingerprint_hash": "0" * 64})
    wrong = rebuild_duplicate_finding(target, evidence=wrong_evidence)
    report = rebuild_duplicate_report(
        case.audit_report,
        tuple(f for f in case.audit_report.findings if f != target) + (wrong,),
    )
    score = q.score_duplicate_observations(report, case.manifest)
    assert score.metrics.true_positive_faults == 3
    assert wrong.finding_id in score.unmatched_finding_ids


def test_wrong_confidence_or_severity_is_a_near_match() -> None:
    case = reviewed_duplicate_case()
    target = _exact_findings(case)[0]
    wrong = rebuild_duplicate_finding(target, confidence="suspicious")
    report = rebuild_duplicate_report(
        case.audit_report,
        tuple(f for f in case.audit_report.findings if f != target) + (wrong,),
    )
    score = q.score_duplicate_observations(report, case.manifest)
    assert score.metrics.true_positive_faults == 3


def test_missing_required_public_evidence_is_rejected_by_schema() -> None:
    case = reviewed_duplicate_case()
    evidence = _exact_findings(case)[0].evidence
    assert isinstance(evidence, q.DuplicateEvidence)
    payload = evidence.model_dump()
    del payload["fingerprint_hash"]
    with pytest.raises(ValidationError):
        q.DuplicateEvidence.model_validate(payload)


def test_no_findings_produces_all_misses_and_documented_nulls() -> None:
    case = reviewed_duplicate_case()
    score = q.score_duplicate_observations(
        rebuild_duplicate_report(case.audit_report, ()), case.manifest
    )
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_negative_faults == case.manifest.target_count
    assert score.metrics.precision is None
    assert score.metrics.recall == Decimal(0)
    assert score.f1 is None
    assert set(score.missed_fault_ids) == {entry.fault_id for entry in case.manifest.entries}


def test_duplicate_finding_adds_false_positive_but_cannot_inflate_recall() -> None:
    case = reviewed_duplicate_case()
    target = _exact_findings(case)[0]
    others = tuple(f for f in case.audit_report.findings if f != target)
    report = rebuild_duplicate_report(case.audit_report, others + (target, target))
    score = q.score_duplicate_observations(report, case.manifest)
    assert score.metrics.true_positive_faults == 4
    assert score.metrics.true_positive_findings == 4
    assert score.metrics.recall == Decimal(1)
    assert target.finding_id in score.duplicate_finding_ids


def test_distinct_findings_competing_for_one_fault_are_ambiguous() -> None:
    case = reviewed_duplicate_case()
    target = _exact_findings(case)[0]
    competing = rebuild_duplicate_finding(target, explanation=target.explanation + " Confirmed.")
    others = tuple(f for f in case.audit_report.findings if f != target)
    report = rebuild_duplicate_report(case.audit_report, others + (target, competing))
    score = q.score_duplicate_observations(report, case.manifest)
    assert score.metrics.true_positive_faults == 3
    entry = next(
        e
        for e in case.manifest.entries
        if tuple(sorted((e.original_record.record_id, e.created_record.record_id)))
        == target.affected_record_ids
    )
    assert entry.fault_id in score.ambiguous_fault_ids
    assert set(score.ambiguous_finding_ids) == {target.finding_id, competing.finding_id}


def test_no_fault_no_finding_uses_all_documented_nulls() -> None:
    case = reviewed_duplicate_case()
    empty_manifest = _rebuild_manifest(
        case.manifest, eligible_record_ids=(), eligible_record_count=0, target_count=0, entries=()
    )
    score = q.score_duplicate_observations(
        rebuild_duplicate_report(case.audit_report, ()), empty_manifest
    )
    assert score.metrics.injected_faults == 0
    assert score.metrics.findings == 0
    assert score.metrics.precision is None
    assert score.metrics.recall is None
    assert score.metrics.false_positive_rate is None
    assert score.f1 is None


def test_zero_clean_denominator_makes_false_positive_rate_null() -> None:
    case = reviewed_duplicate_case()
    empty_manifest = _rebuild_manifest(
        case.manifest, eligible_record_ids=(), eligible_record_count=0, target_count=0, entries=()
    )
    wrong = rebuild_duplicate_finding(
        _exact_findings(case)[0], fault_type="not_duplicate_observation"
    )
    score = q.score_duplicate_observations(
        rebuild_duplicate_report(case.audit_report, (wrong,)), empty_manifest
    )
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.false_positive_rate is None


def test_forged_report_identity_is_rejected_before_scoring() -> None:
    case = reviewed_duplicate_case()
    forged = case.audit_report.model_copy(update={"audit_report_id": "arep_0000000000000000"})
    with pytest.raises(q.DuplicateScoringError, match="identity"):
        q.score_duplicate_observations(forged, case.manifest)
