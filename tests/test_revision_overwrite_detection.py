"""Manifest-blind detection, clean controls, hard negatives, and isolation."""

from __future__ import annotations

import ast
import inspect
from datetime import date

import quantcheck as q
import quantcheck.revision_overwrite_detection as detection_module
from tests.revision_overwrite_support import (
    focused_history,
    focused_snapshot,
    reviewed_revision_overwrite_case,
    revision_record,
)


def test_reviewed_corruption_emits_one_exact_public_finding() -> None:
    case = reviewed_revision_overwrite_case()
    assert len(case.audit_report.findings) == 1
    finding = case.audit_report.findings[0]
    entry = case.manifest.entries[0]
    assert finding.fault_type == "revision_overwrite"
    assert finding.fault_subtype == "later_vintage_in_earlier_state"
    assert finding.rule_id == "revision.later_vintage_in_earlier_state"
    assert finding.affected_record_ids == (entry.corrupted_record.record_id,)
    assert finding.severity == "high"
    assert finding.confidence == "proven_by_contract"
    assert isinstance(finding.evidence, q.RevisionOverwriteEvidence)
    assert q.revision_overwrite_finding_identity_matches(finding)
    assert q.revision_overwrite_audit_report_identity_matches(case.audit_report)


def test_reviewed_clean_control_including_zero_and_negative_values_has_no_findings() -> None:
    case = reviewed_revision_overwrite_case()
    report = q.detect_revision_overwrite(
        q.sanitize_for_audit(case.clean), q.RevisionOverwriteDetectorConfig()
    )
    assert report.findings == ()


def test_historical_revision_in_its_proper_state_is_clean() -> None:
    records = focused_history()
    clean = focused_snapshot(records)
    report = q.detect_revision_overwrite(
        q.sanitize_for_audit(clean), q.RevisionOverwriteDetectorConfig()
    )
    assert report.findings == ()


def test_legitimate_later_revision_in_its_proper_later_state_is_clean() -> None:
    records = focused_history()
    later_state = focused_snapshot(records, as_of_date=date(2024, 6, 2))
    assert later_state.records == (records[1],)
    report = q.detect_revision_overwrite(
        q.sanitize_for_audit(later_state), q.RevisionOverwriteDetectorConfig()
    )
    assert report.findings == ()


def test_amendment_metadata_without_temporal_contamination_is_clean() -> None:
    amended = revision_record(
        "AMENDMENT",
        value="125",
        filed_on=date(2024, 6, 1),
        form="10-Q/A",
        accession_number="AMENDED-ACC",
    )
    snapshot = focused_snapshot((amended,), as_of_date=date(2024, 6, 1))
    report = q.detect_revision_overwrite(
        q.sanitize_for_audit(snapshot), q.RevisionOverwriteDetectorConfig()
    )
    assert report.findings == ()


def test_temporal_contradiction_without_accession_is_not_source_supported() -> None:
    record = revision_record(
        "NO-ACCESSION",
        value="125",
        filed_on=date(2024, 6, 1),
        available_on=date(2024, 4, 15),
        accession_number="TEMP",
    ).model_copy(update={"accession_number": None})
    snapshot = q.DatasetSnapshot(
        snapshot_id=q.dataset_snapshot_id(
            dataset_name="no-accession",
            as_of_date=date(2024, 4, 30),
            records=(record,),
        ),
        dataset_name="no-accession",
        as_of_date=date(2024, 4, 30),
        records=(record,),
    )
    report = q.detect_revision_overwrite(
        q.sanitize_for_audit(snapshot), q.RevisionOverwriteDetectorConfig()
    )
    assert report.findings == ()


def test_future_record_correctly_excluded_by_point_in_time_selection_cannot_be_found() -> None:
    future = revision_record(
        "FUTURE",
        value="125",
        filed_on=date(2024, 6, 1),
    )
    snapshot = focused_snapshot((future,), as_of_date=date(2024, 4, 30))
    assert snapshot.records == ()
    report = q.detect_revision_overwrite(
        q.sanitize_for_audit(snapshot), q.RevisionOverwriteDetectorConfig()
    )
    assert report.findings == ()


def test_detector_receives_only_sanitized_input_and_empty_public_config() -> None:
    parameters = inspect.signature(q.detect_revision_overwrite).parameters
    assert tuple(parameters) == ("audit_input", "config")
    assert parameters["audit_input"].annotation in {
        "AuditInputSnapshot",
        q.AuditInputSnapshot,
    }
    assert "manifest" not in parameters
    assert "clean" not in parameters
    assert "seed" not in parameters


def test_detector_source_has_no_private_dependency_or_prohibited_field_access() -> None:
    source = inspect.getsource(detection_module)
    tree = ast.parse(source)
    imported_modules = {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    forbidden_fragments = (
        "injection",
        "manifest",
        "scoring",
        "replay",
        "revision_overwrite_research",
    )
    assert all(
        fragment not in module for module in imported_modules for fragment in forbidden_fragments
    )
    for private_name in (
        "original_record",
        "historical_record",
        "later_record",
        "source_row_key",
        "target_rank",
        "selection_digest",
        "seed",
    ):
        assert private_name not in source


def test_canonical_public_bytes_exclude_private_answer_key_fields_and_values() -> None:
    case = reviewed_revision_overwrite_case()
    public_bytes = q.canonical_json_bytes(
        {"audit_input": case.audit_input, "audit_report": case.audit_report}
    )
    for key in (
        b"historical_record",
        b"later_record",
        b"original_value",
        b"relative_revision_size",
        b"historical_revision_id",
        b"later_revision_id",
        b"source_row_key",
        b"selection_digest",
        b"target_rank",
        b"eligible_units",
        b"seed",
    ):
        assert key not in public_bytes
    unit = case.manifest.eligible_units[0]
    assert unit.historical_record.record_id.encode() not in public_bytes


def test_revision_and_lookahead_detectors_remain_independent_cross_signals() -> None:
    historical = revision_record(
        "CROSS#r1",
        value="100",
        filed_on=date(2024, 3, 31),
        period_end=date(2024, 3, 31),
        accession_number="CROSS-1",
    )
    later = revision_record(
        "CROSS#r2",
        value="125",
        filed_on=date(2024, 6, 1),
        period_end=date(2024, 3, 31),
        accession_number="CROSS-2",
    )
    records = (historical, later)
    clean = focused_snapshot(records)
    corrupted, _manifest = q.inject_revision_overwrite(
        clean,
        records,
        q.RevisionOverwriteInjectionConfig(severity="high", seed=0),
    )
    audit_input = q.sanitize_for_audit(corrupted)
    revision_report = q.detect_revision_overwrite(audit_input, q.RevisionOverwriteDetectorConfig())
    lookahead_report = q.detect_lookahead(audit_input)
    assert len(revision_report.findings) == 1
    assert len(lookahead_report.findings) == 1
    assert revision_report.findings[0].rule_id != lookahead_report.findings[0].rule_id
