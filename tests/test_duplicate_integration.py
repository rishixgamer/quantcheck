"""One complete reviewed Duplicate Observations vertical slice over the checked-in fixture."""

from __future__ import annotations

import inspect

import quantcheck as q
from tests.duplicate_support import reviewed_duplicate_case


def test_reviewed_case_completes_the_full_trust_bounded_pipeline() -> None:
    case = reviewed_duplicate_case()
    assert len(case.clean.records) == 23
    assert case.manifest.eligible_record_count == 21
    assert case.manifest.target_count == 4
    assert len(case.audit_report.findings) == 5
    assert case.score.metrics.true_positive_faults == 4
    assert case.score.metrics.false_negative_faults == 0
    assert case.score.metrics.false_positive_findings == 1
    assert case.record_count_impact.changed
    assert case.record_count_impact.exact_restoration


def test_reviewed_case_rebuilt_artifact_ids_are_frozen() -> None:
    """These values freeze this rebuild only; they are not historical IDs."""
    case = reviewed_duplicate_case()
    assert case.clean.snapshot_id == "snap_f61ce32ea30f8432"
    assert case.corrupted.snapshot_id == "snap_1ce1415f3fe029cf"
    assert case.manifest.manifest_id == "man_9bcade00876bf919"
    assert case.manifest.entries[0].fault_id == "fault_1060b0016101c508"
    assert case.manifest.entries[0].created_record.record_id == "rec_4b48250fd3675159"
    assert case.audit_report.audit_report_id == "arep_3a83b9b91e37e28f"
    assert case.score.score_report_id == "score_0f8d9a664bd1e73c"
    assert case.record_count_impact.impact_id == "impact_d45a2505e5f6048a"


def test_clean_control_finds_only_the_natural_group_the_corrupted_case_finds_more() -> None:
    case = reviewed_duplicate_case()
    clean_report = q.detect_duplicate_observations(q.sanitize_for_audit(case.clean))
    corrupted_report = q.detect_duplicate_observations(case.audit_input)
    assert len(clean_report.findings) == 1
    assert corrupted_report == case.audit_report
    assert len(corrupted_report.findings) == len(clean_report.findings) + case.manifest.target_count


def test_detector_receives_the_sanitized_type_not_the_private_snapshot_or_manifest() -> None:
    case = reviewed_duplicate_case()
    assert isinstance(case.audit_input, q.AuditInputSnapshot)
    assert not isinstance(case.audit_input, q.DatasetSnapshot)
    assert "manifest" not in inspect.signature(q.detect_duplicate_observations).parameters
    assert "clean" not in inspect.signature(q.detect_duplicate_observations).parameters


def test_scoring_requires_existing_report_and_manifest_but_never_an_audit_input() -> None:
    parameters = inspect.signature(q.score_duplicate_observations).parameters
    assert tuple(parameters) == ("audit_report", "manifest")
    assert "audit_input" not in parameters
    assert "detector" not in parameters


def test_manifest_private_truth_is_absent_from_public_audit_artifacts() -> None:
    case = reviewed_duplicate_case()
    public_bytes = q.canonical_json_bytes(
        {"audit_input": case.audit_input, "audit_report": case.audit_report}
    )
    private_only_keys = (
        b"original_record",
        b"mutation",
        b"selection_digest",
        b"target_rank",
        b"eligible_record_ids",
        b"clean_snapshot_hash",
        b"corrupted_snapshot_hash",
        b"copy_ordinal",
    )
    assert all(key not in public_bytes for key in private_only_keys)


def test_replay_then_redetect_reproduces_the_clean_only_natural_finding() -> None:
    case = reviewed_duplicate_case()
    repaired_audit_input = q.sanitize_for_audit(case.repaired)
    repaired_report = q.detect_duplicate_observations(repaired_audit_input)
    clean_report = q.detect_duplicate_observations(q.sanitize_for_audit(case.clean))
    assert repaired_report.findings == clean_report.findings
