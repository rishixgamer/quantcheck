"""Exact Unit Drift matching, duplicate/ambiguity handling, and metrics."""

from __future__ import annotations

from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.unit_drift_support import (
    rebuild_unit_drift_finding,
    rebuild_unit_drift_report,
    reviewed_unit_drift_case,
)


def _rebuild_manifest(
    manifest: q.UnitDriftManifest,
    **updates: object,
) -> q.UnitDriftManifest:
    body = {
        name: getattr(manifest, name)
        for name in q.UnitDriftManifest.model_fields
        if name != "manifest_id"
    }
    body.update(updates)
    return q.UnitDriftManifest.model_validate(
        {
            "manifest_id": q.unit_drift_manifest_id(manifest_body=body),
            **body,
        }
    )


def _symmetric_ratio(left: Decimal, right: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return max(abs(left) / abs(right), abs(right) / abs(left))


def test_exact_match_scores_one_and_uses_clean_comparability_denominator() -> None:
    score = reviewed_unit_drift_case().score
    assert score.metrics.injected_faults == 1
    assert score.metrics.findings == 1
    assert score.metrics.true_positive_faults == 1
    assert score.metrics.false_negative_faults == 0
    assert score.metrics.true_positive_findings == 1
    assert score.metrics.false_positive_findings == 0
    assert score.metrics.eligible_clean_denominator == 5
    assert score.metrics.precision == Decimal(1)
    assert score.metrics.recall == Decimal(1)
    assert score.metrics.false_positive_rate == Decimal(0)
    assert score.f1 == Decimal(1)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("fault_type", "lookahead_timestamp"),
        ("fault_subtype", "unit_label_only"),
        ("rule_id", "value.other_rule"),
    ],
)
def test_wrong_class_subtype_or_rule_is_unmatched_and_fault_is_missed(
    field: str,
    replacement: str,
) -> None:
    case = reviewed_unit_drift_case()
    wrong = rebuild_unit_drift_finding(case.audit_report.findings[0], **{field: replacement})
    score = q.score_unit_drift(
        rebuild_unit_drift_report(case.audit_report, (wrong,)),
        case.manifest,
    )
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.false_negative_faults == 1
    assert score.unmatched_finding_ids == (wrong.finding_id,)


def test_wrong_record_id_is_a_near_match_not_true_positive() -> None:
    case = reviewed_unit_drift_case()
    finding = case.audit_report.findings[0]
    evidence = finding.evidence
    assert isinstance(evidence, q.UnitDriftEvidence)
    wrong_id = "rec_ffffffffffffffff"
    wrong_evidence = evidence.model_copy(update={"record_id": wrong_id})
    wrong = rebuild_unit_drift_finding(
        finding,
        affected_record_ids=(wrong_id,),
        evidence=wrong_evidence,
    )
    score = q.score_unit_drift(
        rebuild_unit_drift_report(case.audit_report, (wrong,)), case.manifest
    )
    assert score.metrics.true_positive_faults == 0
    assert score.unmatched_finding_ids == (wrong.finding_id,)


def test_wrong_but_internally_valid_candidate_factor_does_not_match() -> None:
    case = reviewed_unit_drift_case()
    finding = case.audit_report.findings[0]
    evidence = finding.evidence
    assert isinstance(evidence, q.UnitDriftEvidence)
    corrected = evidence.observed_value / Decimal("100")
    neighbors = tuple(
        neighbor.model_copy(update={"after_ratio": _symmetric_ratio(corrected, neighbor.value)})
        for neighbor in evidence.neighbors
    )
    wrong_evidence = q.UnitDriftEvidence(
        **{
            **evidence.model_dump(),
            "candidate_scale_factor": Decimal("100"),
            "candidate_correction_factor": Decimal("0.01"),
            "corrected_value": corrected,
            "neighbors": neighbors,
        }
    )
    wrong = rebuild_unit_drift_finding(
        finding,
        severity="low",
        evidence=wrong_evidence,
    )
    score = q.score_unit_drift(
        rebuild_unit_drift_report(case.audit_report, (wrong,)), case.manifest
    )
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_positive_findings == 1


def test_wrong_confidence_or_public_source_evidence_is_a_near_match() -> None:
    case = reviewed_unit_drift_case()
    finding = case.audit_report.findings[0]
    wrong_confidence = rebuild_unit_drift_finding(finding, confidence="suspicious")
    score = q.score_unit_drift(
        rebuild_unit_drift_report(case.audit_report, (wrong_confidence,)),
        case.manifest,
    )
    assert score.metrics.true_positive_findings == 0

    evidence = finding.evidence
    assert isinstance(evidence, q.UnitDriftEvidence)
    wrong_evidence = evidence.model_copy(update={"source_locator": "other-source"})
    wrong_source = rebuild_unit_drift_finding(finding, evidence=wrong_evidence)
    score = q.score_unit_drift(
        rebuild_unit_drift_report(case.audit_report, (wrong_source,)), case.manifest
    )
    assert score.metrics.true_positive_findings == 0


def test_missing_required_public_evidence_is_rejected_by_schema() -> None:
    evidence = reviewed_unit_drift_case().audit_report.findings[0].evidence
    assert isinstance(evidence, q.UnitDriftEvidence)
    payload = evidence.model_dump()
    del payload["candidate_scale_factor"]
    with pytest.raises(ValidationError):
        q.UnitDriftEvidence.model_validate(payload)


def test_no_findings_produces_one_miss_and_documented_nulls() -> None:
    case = reviewed_unit_drift_case()
    score = q.score_unit_drift(rebuild_unit_drift_report(case.audit_report, ()), case.manifest)
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_negative_faults == 1
    assert score.metrics.precision is None
    assert score.metrics.recall == Decimal(0)
    assert score.f1 is None
    assert score.missed_fault_ids == (case.manifest.entries[0].fault_id,)


def test_duplicate_finding_adds_false_positive_but_cannot_inflate_recall() -> None:
    case = reviewed_unit_drift_case()
    finding = case.audit_report.findings[0]
    score = q.score_unit_drift(
        rebuild_unit_drift_report(case.audit_report, (finding, finding)),
        case.manifest,
    )
    assert score.metrics.true_positive_faults == 1
    assert score.metrics.true_positive_findings == 1
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.recall == Decimal(1)
    assert score.metrics.precision == Decimal("0.5")
    assert score.duplicate_finding_ids == (finding.finding_id,)


def test_distinct_findings_competing_for_one_fault_are_ambiguous() -> None:
    case = reviewed_unit_drift_case()
    original = case.audit_report.findings[0]
    competing = rebuild_unit_drift_finding(
        original, explanation=original.explanation + " Confirmed."
    )
    score = q.score_unit_drift(
        rebuild_unit_drift_report(case.audit_report, (original, competing)),
        case.manifest,
    )
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_positive_findings == 2
    assert score.ambiguous_fault_ids == (case.manifest.entries[0].fault_id,)
    assert score.ambiguous_finding_ids == tuple(sorted((original.finding_id, competing.finding_id)))


def test_no_fault_no_finding_uses_all_documented_nulls() -> None:
    case = reviewed_unit_drift_case()
    empty_manifest = _rebuild_manifest(
        case.manifest,
        eligible_record_ids=(),
        eligible_record_count=0,
        target_count=0,
        entries=(),
    )
    score = q.score_unit_drift(rebuild_unit_drift_report(case.audit_report, ()), empty_manifest)
    assert score.metrics.injected_faults == 0
    assert score.metrics.findings == 0
    assert score.metrics.precision is None
    assert score.metrics.recall is None
    assert score.metrics.false_positive_rate is None
    assert score.f1 is None


def test_zero_clean_denominator_makes_false_positive_rate_null() -> None:
    case = reviewed_unit_drift_case()
    empty_manifest = _rebuild_manifest(
        case.manifest,
        eligible_record_ids=(),
        eligible_record_count=0,
        target_count=0,
        entries=(),
    )
    wrong = rebuild_unit_drift_finding(case.audit_report.findings[0], fault_type="not_unit_drift")
    score = q.score_unit_drift(
        rebuild_unit_drift_report(case.audit_report, (wrong,)), empty_manifest
    )
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.false_positive_rate is None


def test_false_positive_rate_uses_all_clean_comparable_observations() -> None:
    case = reviewed_unit_drift_case()
    exact = case.audit_report.findings[0]
    wrong = rebuild_unit_drift_finding(exact, fault_type="wrong")
    score = q.score_unit_drift(
        rebuild_unit_drift_report(case.audit_report, (exact, wrong)), case.manifest
    )
    assert score.metrics.eligible_clean_denominator == 5
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.false_positive_rate == Decimal("0.2")


def test_forged_report_identity_is_rejected_before_scoring() -> None:
    case = reviewed_unit_drift_case()
    forged = case.audit_report.model_copy(update={"audit_report_id": "arep_0000000000000000"})
    with pytest.raises(q.UnitDriftScoringError, match="identity"):
        q.score_unit_drift(forged, case.manifest)
