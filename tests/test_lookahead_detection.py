"""Manifest-blind Look-Ahead detection and isolation evidence."""

from __future__ import annotations

import ast
import inspect
from datetime import date

import quantcheck as q
from quantcheck import lookahead_detection
from tests.lookahead_support import reviewed_lookahead_case
from tests.support import audit_input_record


def _audit_snapshot(*records: q.AuditInputRecord, as_of_date: date) -> q.AuditInputSnapshot:
    return q.AuditInputSnapshot(
        audit_input_id=q.audit_input_snapshot_id(
            dataset_name="focused", as_of_date=as_of_date, records=records
        ),
        dataset_name="focused",
        as_of_date=as_of_date,
        records=records,
    )


def test_clean_reviewed_control_emits_no_findings() -> None:
    case = reviewed_lookahead_case()
    report = q.detect_lookahead(q.sanitize_for_audit(case.clean))
    assert report.findings == ()
    assert q.audit_report_identity_matches(report)


def test_exact_positive_finding_contains_only_public_date_evidence() -> None:
    case = reviewed_lookahead_case()
    finding = case.audit_report.findings[0]
    entry = case.manifest.entries[0]
    assert isinstance(finding.evidence, q.LookAheadEvidence)
    assert finding.affected_record_ids == (entry.corrupted_record.record_id,)
    assert finding.rule_id == q.LOOKAHEAD_RULE_ID
    assert finding.evidence.available_on == entry.corrupted_record.period_end
    assert finding.evidence.filed_on == entry.corrupted_record.filed_on
    assert (
        finding.evidence.leaked_days
        == (entry.corrupted_record.filed_on - entry.corrupted_record.available_on).days
    )
    assert finding.confidence == "proven_by_contract"
    assert "days of information early" in finding.explanation


def test_same_day_available_and_filed_is_not_a_violation() -> None:
    record = audit_input_record(
        period_end=date(2024, 3, 31),
        filed_on=date(2024, 3, 31),
        available_on=date(2024, 3, 31),
    )
    assert q.detect_lookahead(_audit_snapshot(record, as_of_date=date(2024, 4, 1))).findings == ()


def test_available_before_filing_but_not_at_period_end_is_outside_narrow_subtype() -> None:
    record = audit_input_record(
        period_end=date(2024, 3, 31),
        available_on=date(2024, 4, 1),
        filed_on=date(2024, 4, 15),
    )
    assert q.detect_lookahead(_audit_snapshot(record, as_of_date=date(2024, 4, 30))).findings == ()


def test_record_not_visible_by_audit_date_is_not_flagged() -> None:
    record = audit_input_record(
        period_end=date(2024, 4, 15),
        available_on=date(2024, 4, 15),
        filed_on=date(2024, 4, 30),
    )
    assert q.detect_lookahead(_audit_snapshot(record, as_of_date=date(2024, 4, 14))).findings == ()


def test_public_leaked_day_severity_bands_are_exact() -> None:
    assert q.finding_severity(1) == "low"
    assert q.finding_severity(13) == "low"
    assert q.finding_severity(14) == "medium"
    assert q.finding_severity(29) == "medium"
    assert q.finding_severity(30) == "high"


def test_findings_are_canonically_sorted_and_order_independent() -> None:
    first = audit_input_record(
        record_id="rec_aaaaaaaaaaaaaaaa",
        available_on=date(2024, 3, 31),
        filed_on=date(2024, 4, 15),
    )
    second = audit_input_record(
        record_id="rec_bbbbbbbbbbbbbbbb",
        available_on=date(2024, 3, 31),
        filed_on=date(2024, 4, 20),
    )
    forward = q.detect_lookahead(_audit_snapshot(first, second, as_of_date=date(2024, 4, 30)))
    backward = q.detect_lookahead(_audit_snapshot(second, first, as_of_date=date(2024, 4, 30)))
    assert q.canonical_json_bytes(forward) == q.canonical_json_bytes(backward)
    assert [finding.finding_id for finding in forward.findings] == sorted(
        finding.finding_id for finding in forward.findings
    )


def test_serialized_audit_input_reload_produces_identical_report() -> None:
    case = reviewed_lookahead_case()
    parsed = q.parse_canonical_json(q.canonical_json_bytes(case.audit_input))
    reloaded = q.AuditInputSnapshot.model_validate(parsed)
    assert q.canonical_json_bytes(q.detect_lookahead(reloaded)) == q.canonical_json_bytes(
        case.audit_report
    )


def test_detector_signature_accepts_only_sanitized_audit_input() -> None:
    parameters = inspect.signature(q.detect_lookahead).parameters
    assert tuple(parameters) == ("audit_input",)
    assert parameters["audit_input"].annotation in {
        "AuditInputSnapshot",
        q.AuditInputSnapshot,
    }


def test_detector_module_has_no_injector_scoring_replay_or_manifest_dependency() -> None:
    source = inspect.getsource(lookahead_detection)
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any("injection" in module for module in imports)
    assert not any("scoring" in module for module in imports)
    assert not any("replay" in module for module in imports)
    assert not any("manifest" in module for module in imports)
    assert "FaultManifest" not in source
    assert "FinancialFact" not in source
    assert "DatasetSnapshot" not in source


def test_sanitized_bytes_contain_no_answer_key_roles_or_configuration() -> None:
    case = reviewed_lookahead_case()
    data = q.canonical_json_bytes(case.audit_input)
    prohibited = (
        b"manifest",
        b"original_record",
        b"true_available_on",
        b"selection_digest",
        b"target_rank",
        b"eligible_record_ids",
        b"seed",
        b"severity",
        b"target_fraction",
        b"target_count",
        b"max_targets",
        b"expected_finding_count",
        b"source_row_key",
        b"fault_id",
    )
    assert all(marker not in data for marker in prohibited)


def test_record_id_does_not_reveal_original_or_modified_role() -> None:
    case = reviewed_lookahead_case()
    data = q.canonical_json_bytes(case.audit_input)
    assert b"mod_" not in data
    assert case.manifest.entries[0].corrupted_record.record_id.encode() in data


def test_hard_negative_zero_and_negative_values_remain_clean() -> None:
    case = reviewed_lookahead_case()
    clean_audit = q.sanitize_for_audit(case.clean)
    hard_negative_ids = {record.record_id for record in clean_audit.records if record.value <= 0}
    assert hard_negative_ids
    report = q.detect_lookahead(clean_audit)
    assert not any(
        hard_negative_ids.intersection(finding.affected_record_ids) for finding in report.findings
    )


def test_forged_audit_input_identity_is_rejected() -> None:
    case = reviewed_lookahead_case()
    forged = case.audit_input.model_copy(update={"audit_input_id": "audit_0000000000000000"})
    try:
        q.detect_lookahead(forged)
    except q.LookAheadDetectionError as error:
        assert "identity" in str(error)
    else:
        raise AssertionError("forged audit identity was accepted")
