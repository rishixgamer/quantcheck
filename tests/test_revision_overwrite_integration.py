"""Complete trust-bounded Revision Overwrite vertical slice."""

from __future__ import annotations

import inspect

import quantcheck as q
from tests.revision_overwrite_support import reviewed_revision_overwrite_case


def test_reviewed_case_completes_the_full_frozen_vintage_pipeline() -> None:
    case = reviewed_revision_overwrite_case()
    assert len(case.source_records) == 26
    assert len(case.clean.records) == len(case.corrupted.records) == 13
    assert case.manifest.eligible_unit_count == 1
    assert case.manifest.target_count == 1
    assert len(case.audit_report.findings) == 1
    assert case.score.metrics.true_positive_faults == 1
    assert case.score.metrics.false_positive_findings == 0
    assert case.score.metrics.false_negative_faults == 0
    assert case.research_impact.changed
    assert case.research_impact.exact_restoration


def test_reviewed_case_rebuilt_artifact_ids_are_frozen() -> None:
    """These values freeze this rebuild only; they are not historical IDs."""
    case = reviewed_revision_overwrite_case()
    assert case.clean.snapshot_id == "snap_9ccebecfbab28347"
    assert case.corrupted.snapshot_id == "snap_558bb8cd38d16f45"
    assert case.manifest.manifest_id == "man_7a0431e79f46f9f8"
    assert case.manifest.entries[0].fault_id == "fault_2b66b6f371c24e07"
    assert case.manifest.entries[0].corrupted_record.record_id == "rec_c54d8f84b558cf7b"
    assert case.audit_input.audit_input_id == "audit_2e9f7fa542fca759"
    assert case.audit_report.audit_report_id == "arep_f2a9f4e8fdf453e4"
    assert case.audit_report.findings[0].finding_id == "find_d6371e871f8e9e26"
    assert case.score.score_report_id == "score_2f1ffc11323a1e9b"
    assert case.research_impact.impact_id == "impact_0c79963fac7b9114"


def test_clean_control_and_corrupted_case_use_the_same_detector() -> None:
    case = reviewed_revision_overwrite_case()
    clean_report = q.detect_revision_overwrite(
        q.sanitize_for_audit(case.clean), q.RevisionOverwriteDetectorConfig()
    )
    corrupted_report = q.detect_revision_overwrite(
        case.audit_input, q.RevisionOverwriteDetectorConfig()
    )
    assert clean_report.findings == ()
    assert corrupted_report == case.audit_report


def test_detector_receives_sanitized_input_not_private_snapshot_or_manifest() -> None:
    case = reviewed_revision_overwrite_case()
    assert isinstance(case.audit_input, q.AuditInputSnapshot)
    assert not isinstance(case.audit_input, q.DatasetSnapshot)
    assert tuple(inspect.signature(q.detect_revision_overwrite).parameters) == (
        "audit_input",
        "config",
    )


def test_scoring_requires_an_existing_report_and_private_manifest_only() -> None:
    parameters = inspect.signature(q.score_revision_overwrite).parameters
    assert tuple(parameters) == ("audit_report", "manifest")
    assert "audit_input" not in parameters
    assert "detector" not in parameters


def test_public_audit_artifacts_exclude_private_revision_answer_key_truth() -> None:
    case = reviewed_revision_overwrite_case()
    public_bytes = q.canonical_json_bytes(
        {"audit_input": case.audit_input, "audit_report": case.audit_report}
    )
    private_only_keys = (
        b"historical_record",
        b"later_record",
        b"mutation",
        b"selection_digest",
        b"target_rank",
        b"eligible_units",
        b"historical_revision_id",
        b"later_revision_id",
        b"source_row_key",
        b"clean_snapshot_hash",
        b"corrupted_snapshot_hash",
        b"seed",
    )
    assert all(key not in public_bytes for key in private_only_keys)


def test_replay_then_redetect_reproduces_the_clean_control() -> None:
    case = reviewed_revision_overwrite_case()
    repaired_report = q.detect_revision_overwrite(
        q.sanitize_for_audit(case.repaired), q.RevisionOverwriteDetectorConfig()
    )
    clean_report = q.detect_revision_overwrite(
        q.sanitize_for_audit(case.clean), q.RevisionOverwriteDetectorConfig()
    )
    assert repaired_report.findings == clean_report.findings == ()
