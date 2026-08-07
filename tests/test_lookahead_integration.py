"""One complete reviewed Look-Ahead vertical slice over the checked-in fixture."""

from __future__ import annotations

import inspect

import quantcheck as q
from tests.lookahead_support import reviewed_lookahead_case


def test_reviewed_case_completes_the_full_trust_bounded_pipeline() -> None:
    case = reviewed_lookahead_case()
    assert len(case.clean.records) == 13
    assert case.manifest.eligible_record_count == 13
    assert case.manifest.target_count == 1
    assert len(case.audit_report.findings) == 1
    assert case.score.metrics.true_positive_faults == 1
    assert case.score.metrics.false_positive_findings == 0
    assert case.score.metrics.false_negative_faults == 0
    assert case.impact.changed
    assert case.impact.exact_restoration


def test_reviewed_case_rebuilt_artifact_ids_are_frozen() -> None:
    """These values freeze this rebuild only; they are not historical IDs."""
    case = reviewed_lookahead_case()
    assert case.clean.snapshot_id == "snap_1ba1e74184f1123a"
    assert case.corrupted.snapshot_id == "snap_d290dc2684c09a62"
    assert case.manifest.manifest_id == "man_0b6bf9c4c5160852"
    assert case.manifest.entries[0].fault_id == "fault_6f59dbda440431ef"
    assert case.manifest.entries[0].corrupted_record.record_id == "rec_5d2412c678714ae6"
    assert case.audit_report.audit_report_id == "arep_d4838cacf3c5927e"
    assert case.audit_report.findings[0].finding_id == "find_5507c4daa814e7a7"
    assert case.score.score_report_id == "score_7fef38b1cc45f4a8"
    assert case.impact.impact_id == "impact_d7904bf5ebb2c586"


def test_clean_control_and_corrupted_case_use_the_same_detector() -> None:
    case = reviewed_lookahead_case()
    clean_report = q.detect_lookahead(q.sanitize_for_audit(case.clean))
    corrupted_report = q.detect_lookahead(case.audit_input)
    assert clean_report.findings == ()
    assert corrupted_report == case.audit_report


def test_detector_receives_the_sanitized_type_not_the_private_snapshot_or_manifest() -> None:
    case = reviewed_lookahead_case()
    assert isinstance(case.audit_input, q.AuditInputSnapshot)
    assert not isinstance(case.audit_input, q.DatasetSnapshot)
    assert "manifest" not in inspect.signature(q.detect_lookahead).parameters
    assert "clean" not in inspect.signature(q.detect_lookahead).parameters


def test_scoring_requires_existing_report_and_manifest_but_never_an_audit_input() -> None:
    parameters = inspect.signature(q.score_lookahead).parameters
    assert tuple(parameters) == ("audit_report", "manifest")
    assert "audit_input" not in parameters
    assert "detector" not in parameters


def test_manifest_private_truth_is_absent_from_public_audit_artifacts() -> None:
    case = reviewed_lookahead_case()
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
    )
    assert all(key not in public_bytes for key in private_only_keys)
