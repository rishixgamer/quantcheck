"""Exact Revision Overwrite matching, near misses, and metric conventions."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.revision_overwrite_support import (
    focused_snapshot,
    rebuild_revision_finding,
    rebuild_revision_report,
    reviewed_revision_overwrite_case,
    revision_record,
)


def _rebuild_evidence(
    evidence: q.RevisionOverwriteEvidence,
    **updates: object,
) -> q.RevisionOverwriteEvidence:
    fields = {name: getattr(evidence, name) for name in q.RevisionOverwriteEvidence.model_fields}
    fields.update(updates)
    return q.RevisionOverwriteEvidence.model_validate(fields)


def test_reviewed_finding_is_one_exact_match() -> None:
    case = reviewed_revision_overwrite_case()
    metrics = case.score.metrics
    assert metrics.injected_faults == 1
    assert metrics.findings == 1
    assert metrics.true_positive_faults == 1
    assert metrics.false_positive_findings == 0
    assert metrics.false_negative_faults == 0
    assert metrics.eligible_clean_denominator == 1
    assert metrics.precision == metrics.recall == case.score.f1 == Decimal(1)
    assert metrics.false_positive_rate == 0
    assert len(case.score.matches) == 1
    assert q.revision_overwrite_score_report_identity_matches(case.score)


@pytest.mark.parametrize(
    "updates",
    [
        {"detector_id": "other.detector"},
        {"detector_version": "other/v1"},
        {"fault_type": "lookahead_timestamp"},
        {"fault_subtype": "period_end_substitution"},
        {"rule_id": "temporal.other"},
        {"severity": "medium"},
        {"confidence": "suspicious"},
    ],
)
def test_wrong_class_rule_detector_severity_or_confidence_is_false_positive(
    updates: dict[str, object],
) -> None:
    case = reviewed_revision_overwrite_case()
    wrong = rebuild_revision_finding(case.audit_report.findings[0], **updates)
    score = q.score_revision_overwrite(
        rebuild_revision_report(case.audit_report, (wrong,)), case.manifest
    )
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.false_negative_faults == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("record_id", "rec_ffffffffffffffff"),
        ("observed_value", Decimal("999")),
        ("accession_number", "WRONG-ACCESSION"),
        ("source_locator", "wrong-source-row"),
        ("public_provenance_hash", "f" * 64),
    ],
)
def test_wrong_record_revision_source_or_provenance_evidence_is_false_positive(
    field: str,
    value: object,
) -> None:
    case = reviewed_revision_overwrite_case()
    finding = case.audit_report.findings[0]
    assert isinstance(finding.evidence, q.RevisionOverwriteEvidence)
    evidence = _rebuild_evidence(finding.evidence, **{field: value})
    updates: dict[str, object] = {"evidence": evidence}
    if field == "record_id":
        updates["affected_record_ids"] = (value,)
    wrong = rebuild_revision_finding(finding, **updates)
    score = q.score_revision_overwrite(
        rebuild_revision_report(case.audit_report, (wrong,)), case.manifest
    )
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_positive_findings == 1


def test_wrong_filing_date_evidence_is_false_positive() -> None:
    case = reviewed_revision_overwrite_case()
    finding = case.audit_report.findings[0]
    assert isinstance(finding.evidence, q.RevisionOverwriteEvidence)
    wrong_evidence = _rebuild_evidence(
        finding.evidence,
        filed_on=finding.evidence.filed_on + timedelta(days=1),
    )
    wrong = rebuild_revision_finding(finding, evidence=wrong_evidence)
    score = q.score_revision_overwrite(
        rebuild_revision_report(case.audit_report, (wrong,)), case.manifest
    )
    assert score.metrics.true_positive_faults == 0


def test_incomplete_evidence_is_rejected_by_the_contract() -> None:
    case = reviewed_revision_overwrite_case()
    finding = case.audit_report.findings[0]
    assert isinstance(finding.evidence, q.RevisionOverwriteEvidence)
    fields = {
        name: getattr(finding.evidence, name)
        for name in q.RevisionOverwriteEvidence.model_fields
        if name != "accession_number"
    }
    with pytest.raises(ValidationError):
        q.RevisionOverwriteEvidence.model_validate(fields)


def test_additional_affected_record_is_not_an_exact_match() -> None:
    case = reviewed_revision_overwrite_case()
    finding = case.audit_report.findings[0]
    fields = {name: getattr(finding, name) for name in q.Finding.model_fields}
    fields["affected_record_ids"] = (*finding.affected_record_ids, "rec_aaaaaaaaaaaaaaaa")
    body = {name: value for name, value in fields.items() if name != "finding_id"}
    fields["finding_id"] = q.revision_overwrite_finding_id(finding_body=body)
    forged = q.Finding.model_construct(**fields)
    report_body: dict[str, object] = {
        "detector_id": case.audit_report.detector_id,
        "detector_version": case.audit_report.detector_version,
        "audit_input_id": case.audit_report.audit_input_id,
        "dataset_name": case.audit_report.dataset_name,
        "as_of_date": case.audit_report.as_of_date,
        "findings": (forged,),
    }
    # Deliberately bypass the public-model validator so scoring is tested
    # against a finalized but malformed external report. The scorer must not
    # turn an extra affected record into an exact primary match.
    forged_report = q.AuditReport.model_construct(
        audit_report_id=q.revision_overwrite_audit_report_id(report_body=report_body),
        detector_id=case.audit_report.detector_id,
        detector_version=case.audit_report.detector_version,
        audit_input_id=case.audit_report.audit_input_id,
        dataset_name=case.audit_report.dataset_name,
        as_of_date=case.audit_report.as_of_date,
        findings=(forged,),
    )
    score = q.score_revision_overwrite(forged_report, case.manifest)
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_positive_findings == 1


def test_duplicate_finding_never_increases_recall() -> None:
    case = reviewed_revision_overwrite_case()
    finding = case.audit_report.findings[0]
    report = rebuild_revision_report(case.audit_report, (finding, finding))
    score = q.score_revision_overwrite(report, case.manifest)
    assert score.metrics.true_positive_faults == 1
    assert score.metrics.findings == 2
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.recall == 1
    assert score.duplicate_finding_ids == (finding.finding_id,)


def test_empty_findings_are_an_explicit_miss_with_null_precision_and_f1() -> None:
    case = reviewed_revision_overwrite_case()
    report = rebuild_revision_report(case.audit_report, ())
    score = q.score_revision_overwrite(report, case.manifest)
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_negative_faults == 1
    assert score.metrics.precision is None
    assert score.metrics.recall == 0
    assert score.f1 is None


def test_no_fault_no_finding_and_zero_denominator_null_conventions() -> None:
    case = reviewed_revision_overwrite_case()
    clean_report = q.detect_revision_overwrite(
        q.sanitize_for_audit(case.clean), q.RevisionOverwriteDetectorConfig()
    )
    body: dict[str, object] = {
        name: getattr(case.manifest, name)
        for name in q.RevisionOverwriteManifest.model_fields
        if name != "manifest_id"
    }
    body.update(
        {
            "eligible_units": (),
            "eligible_unit_count": 0,
            "target_count": 0,
            "entries": (),
        }
    )
    empty_manifest = q.RevisionOverwriteManifest.model_validate(
        {
            "manifest_id": q.revision_overwrite_manifest_id(manifest_body=body),
            **body,
        }
    )
    score = q.score_revision_overwrite(clean_report, empty_manifest)
    assert score.metrics.injected_faults == 0
    assert score.metrics.findings == 0
    assert score.metrics.precision is None
    assert score.metrics.recall is None
    assert score.metrics.false_positive_rate is None
    assert score.f1 is None


def test_report_from_another_detector_is_rejected_before_scoring() -> None:
    case = reviewed_revision_overwrite_case()
    lookahead_report = q.detect_lookahead(case.audit_input)
    with pytest.raises(q.RevisionOverwriteScoringError):
        q.score_revision_overwrite(lookahead_report, case.manifest)


def test_valid_lookahead_cross_signal_is_not_a_revision_overwrite_true_positive() -> None:
    historical = revision_record(
        "CROSS-SCORE#r1",
        value="100",
        filed_on=date(2024, 3, 31),
        period_end=date(2024, 3, 31),
        accession_number="CROSS-SCORE-1",
    )
    later = revision_record(
        "CROSS-SCORE#r2",
        value="125",
        filed_on=date(2024, 6, 1),
        period_end=date(2024, 3, 31),
        accession_number="CROSS-SCORE-2",
    )
    clean = focused_snapshot((historical, later))
    corrupted, manifest = q.inject_revision_overwrite(
        clean,
        (historical, later),
        q.RevisionOverwriteInjectionConfig(severity="high", seed=0),
    )
    audit_input = q.sanitize_for_audit(corrupted)
    revision_report = q.detect_revision_overwrite(audit_input, q.RevisionOverwriteDetectorConfig())
    lookahead_report = q.detect_lookahead(audit_input)
    assert len(revision_report.findings) == len(lookahead_report.findings) == 1

    score = q.score_revision_overwrite(
        rebuild_revision_report(revision_report, lookahead_report.findings),
        manifest,
    )
    assert score.metrics.true_positive_faults == 0
    assert score.metrics.false_positive_findings == 1
    assert score.metrics.false_negative_faults == 1


def test_false_positive_rate_uses_full_eligible_history_unit_denominator() -> None:
    case = reviewed_revision_overwrite_case()
    finding = case.audit_report.findings[0]
    assert isinstance(finding.evidence, q.RevisionOverwriteEvidence)
    wrong_evidence = _rebuild_evidence(finding.evidence, accession_number="WRONG-ACCESSION")
    wrong = rebuild_revision_finding(finding, evidence=wrong_evidence)
    score = q.score_revision_overwrite(
        rebuild_revision_report(case.audit_report, (finding, wrong)), case.manifest
    )
    assert score.metrics.eligible_clean_denominator == case.manifest.eligible_unit_count == 1
    assert score.metrics.false_positive_rate == 1
