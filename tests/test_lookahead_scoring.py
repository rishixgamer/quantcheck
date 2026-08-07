"""Exact Look-Ahead matching, duplicate/ambiguity handling, and metrics."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, localcontext

import pytest

import quantcheck as q
from tests.lookahead_support import (
    rebuild_audit_report,
    rebuild_finding,
    reviewed_lookahead_case,
)


def _rebuild_manifest(
    manifest: q.FaultManifest,
    **updates: object,
) -> q.FaultManifest:
    body = {
        name: getattr(manifest, name)
        for name in q.FaultManifest.model_fields
        if name != "manifest_id"
    }
    body.update(updates)
    return q.FaultManifest.model_validate(
        {
            "manifest_id": q.fault_manifest_id(manifest_body=body),
            **body,
        }
    )


def test_exact_match_scores_one_for_precision_recall_f1() -> None:
    score = reviewed_lookahead_case().score
    assert score.metrics.injected_faults == 1
    assert score.metrics.findings == 1
    assert score.metrics.true_positive_faults == 1
    assert score.metrics.true_positive_findings == 1
    assert score.metrics.false_negative_faults == 0
    assert score.metrics.false_positive_findings == 0
    assert score.metrics.eligible_clean_denominator == 12
    assert score.metrics.precision == Decimal(1)
    assert score.metrics.recall == Decimal(1)
    assert score.f1 == Decimal(1)
    assert score.metrics.false_positive_rate == Decimal(0)
    assert q.score_report_identity_matches(score)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("fault_type", "unit_drift"),
        ("fault_subtype", "other_subtype"),
        ("rule_id", "temporal.other_rule"),
    ],
)
def test_wrong_class_subtype_or_rule_is_false_positive_and_fault_is_missed(
    field: str, replacement: str
) -> None:
    case = reviewed_lookahead_case()
    wrong = rebuild_finding(case.audit_report.findings[0], **{field: replacement})
    score = q.score_lookahead(rebuild_audit_report(case.audit_report, (wrong,)), case.manifest)
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.false_negative_faults == 1
    assert score.unmatched_finding_ids == (wrong.finding_id,)


def test_wrong_record_id_is_a_near_match_not_a_true_positive() -> None:
    case = reviewed_lookahead_case()
    finding = case.audit_report.findings[0]
    wrong_id = "rec_ffffffffffffffff"
    evidence = finding.evidence.model_copy(update={"record_id": wrong_id})
    wrong = rebuild_finding(
        finding,
        affected_record_ids=(wrong_id,),
        evidence=evidence,
    )
    score = q.score_lookahead(rebuild_audit_report(case.audit_report, (wrong,)), case.manifest)
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_positive_findings == 1


def test_incorrect_but_internally_valid_public_evidence_does_not_match() -> None:
    case = reviewed_lookahead_case()
    finding = case.audit_report.findings[0]
    assert isinstance(finding.evidence, q.LookAheadEvidence)
    evidence = q.LookAheadEvidence(
        record_id=finding.evidence.record_id,
        period_end=finding.evidence.period_end,
        available_on=finding.evidence.available_on,
        filed_on=finding.evidence.filed_on + timedelta(days=1),
        audit_as_of_date=finding.evidence.audit_as_of_date,
        leaked_days=finding.evidence.leaked_days + 1,
        source_name=finding.evidence.source_name,
        source_locator=finding.evidence.source_locator,
    )
    wrong = rebuild_finding(finding, evidence=evidence)
    score = q.score_lookahead(rebuild_audit_report(case.audit_report, (wrong,)), case.manifest)
    assert score.metrics.true_positive_findings == 0
    assert score.unmatched_finding_ids == (wrong.finding_id,)


def test_no_findings_produces_a_miss_and_documented_nulls() -> None:
    case = reviewed_lookahead_case()
    score = q.score_lookahead(rebuild_audit_report(case.audit_report, ()), case.manifest)
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_negative_faults == 1
    assert score.metrics.precision is None
    assert score.metrics.recall == Decimal(0)
    assert score.f1 is None
    assert score.missed_fault_ids == (case.manifest.entries[0].fault_id,)


def test_duplicate_finding_is_one_match_plus_one_false_positive() -> None:
    case = reviewed_lookahead_case()
    finding = case.audit_report.findings[0]
    report = rebuild_audit_report(case.audit_report, (finding, finding))
    score = q.score_lookahead(report, case.manifest)
    assert score.metrics.true_positive_faults == 1
    assert score.metrics.true_positive_findings == 1
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.recall == Decimal(1)
    assert score.metrics.precision == Decimal("0.5")
    assert score.duplicate_finding_ids == (finding.finding_id,)


def test_distinct_findings_competing_for_one_fault_are_ambiguous() -> None:
    case = reviewed_lookahead_case()
    original = case.audit_report.findings[0]
    competing = rebuild_finding(original, explanation=original.explanation + " Confirmed.")
    report = rebuild_audit_report(case.audit_report, (original, competing))
    score = q.score_lookahead(report, case.manifest)
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_negative_faults == 1
    assert score.metrics.false_positive_findings == 2
    assert score.ambiguous_fault_ids == (case.manifest.entries[0].fault_id,)
    assert score.ambiguous_finding_ids == tuple(sorted((original.finding_id, competing.finding_id)))


def test_no_fault_no_finding_case_uses_null_precision_recall_f1_and_fpr() -> None:
    case = reviewed_lookahead_case()
    no_fault_manifest = _rebuild_manifest(
        case.manifest,
        eligible_record_ids=(),
        eligible_record_count=0,
        target_count=0,
        entries=(),
    )
    empty_report = rebuild_audit_report(case.audit_report, ())
    score = q.score_lookahead(empty_report, no_fault_manifest)
    assert score.metrics.injected_faults == 0
    assert score.metrics.findings == 0
    assert score.metrics.precision is None
    assert score.metrics.recall is None
    assert score.f1 is None
    assert score.metrics.false_positive_rate is None


def test_zero_clean_denominator_makes_false_positive_rate_null() -> None:
    case = reviewed_lookahead_case()
    entry = case.manifest.entries[0]
    one_of_one = _rebuild_manifest(
        case.manifest,
        eligible_record_ids=(entry.original_record.record_id,),
        eligible_record_count=1,
        target_count=1,
        entries=(entry,),
    )
    score = q.score_lookahead(case.audit_report, one_of_one)
    assert score.metrics.eligible_clean_denominator == 0
    assert score.metrics.false_positive_rate is None


def test_exact_repeating_decimal_metrics_are_not_binary_float() -> None:
    case = reviewed_lookahead_case()
    finding = case.audit_report.findings[0]
    wrong = rebuild_finding(finding, fault_type="not_lookahead")
    report = rebuild_audit_report(case.audit_report, (finding, wrong, wrong))
    score = q.score_lookahead(report, case.manifest)
    with localcontext() as context:
        context.prec = 50
        expected_precision = Decimal(1) / Decimal(3)
        expected_f1 = (Decimal(2) * expected_precision) / (expected_precision + Decimal(1))
    assert score.metrics.precision == expected_precision
    assert score.metrics.recall == Decimal(1)
    assert score.f1 == expected_f1
    assert isinstance(score.metrics.precision, Decimal)


def test_forged_report_identity_is_rejected_before_scoring() -> None:
    case = reviewed_lookahead_case()
    forged = case.audit_report.model_copy(update={"audit_report_id": "arep_0000000000000000"})
    with pytest.raises(q.LookAheadScoringError, match="identity"):
        q.score_lookahead(forged, case.manifest)
