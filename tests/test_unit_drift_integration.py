"""Complete trust-bounded Unit Drift vertical slice."""

from __future__ import annotations

import inspect
from decimal import Decimal

import quantcheck as q
from tests.unit_drift_support import reviewed_unit_drift_case


def test_controlled_case_completes_the_full_pipeline() -> None:
    case = reviewed_unit_drift_case()
    assert len(case.clean.records) == 5
    assert case.manifest.eligible_record_count == 5
    assert case.manifest.target_count == 1
    assert len(case.audit_report.findings) == 1
    assert case.score.metrics.true_positive_faults == 1
    assert case.score.metrics.false_positive_findings == 0
    assert case.score.metrics.false_negative_faults == 0
    assert case.impact.clean.aggregate_value == Decimal("600")
    assert case.impact.changed
    assert case.impact.exact_restoration


def test_detector_receives_only_sanitized_snapshot_and_public_config() -> None:
    case = reviewed_unit_drift_case()
    assert isinstance(case.audit_input, q.AuditInputSnapshot)
    assert not isinstance(case.audit_input, q.DatasetSnapshot)
    assert tuple(inspect.signature(q.detect_unit_drift).parameters) == (
        "audit_input",
        "config",
    )


def test_scoring_requires_a_finalized_report_and_manifest_but_runs_no_detector() -> None:
    parameters = inspect.signature(q.score_unit_drift).parameters
    assert tuple(parameters) == ("audit_report", "manifest")
    assert "audit_input" not in parameters
    assert "detector" not in parameters


def test_public_artifacts_exclude_all_private_manifest_truth() -> None:
    case = reviewed_unit_drift_case()
    public_bytes = q.canonical_json_bytes(
        {"audit_input": case.audit_input, "audit_report": case.audit_report}
    )
    for private_key in (
        b"original_record",
        b"mutation",
        b"selection_digest",
        b"target_rank",
        b"eligible_record_ids",
        b"clean_snapshot_hash",
        b"corrupted_snapshot_hash",
        b"seed",
    ):
        assert private_key not in public_bytes
