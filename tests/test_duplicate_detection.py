"""Manifest-blind Duplicate detection, isolation, and hard negatives."""

from __future__ import annotations

import ast
import inspect
from datetime import date

import pytest

import quantcheck as q
from tests.duplicate_support import (
    duplicate_record,
    duplicate_snapshot,
    reviewed_duplicate_case,
)


def _detect(
    records: tuple[q.FinancialFact, ...], *, as_of_date: date = date(2024, 12, 31)
) -> q.AuditReport:
    snapshot = duplicate_snapshot(records, as_of_date=as_of_date)
    return q.detect_duplicate_observations(q.sanitize_for_audit(snapshot))


def test_focused_clean_control_with_distinct_records_emits_no_findings() -> None:
    records = tuple(duplicate_record(f"row-{i}", concept=f"Concept{i}") for i in range(5))
    assert _detect(records).findings == ()


def test_current_reviewed_fixture_emits_exactly_one_finding_for_its_natural_pair() -> None:
    """The Milestone 2 fixture's independent-occurrence pair (entity 3, Q1 Assets)
    is byte-identical in every AuditInputRecord-visible field. The exact-copy
    contract is narrow: injection eligibility and detector visibility are
    separate concerns (see docs/DECISIONS.md ADR-004), so the detector legitimately
    proves this natural group without any Duplicate fault having been injected.
    """
    reviewed = q.build_dataset_snapshot(
        q.generate_reviewed_fixture(),
        dataset_name="reviewed-clean-control",
        as_of_date=date(2024, 8, 31),
    )
    report = q.detect_duplicate_observations(q.sanitize_for_audit(reviewed))
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert isinstance(finding.evidence, q.DuplicateEvidence)
    assert finding.evidence.group_size == 2
    assert finding.affected_record_ids == (
        "rec_521e565b7cad2f3b",
        "rec_a3eb29080d7921dc",
    )


def test_exact_copy_groups_regardless_of_generated_record_id() -> None:
    a = duplicate_record("row-a")
    b = duplicate_record("row-b")
    report = _detect((a, b))
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.affected_record_ids == tuple(sorted((a.record_id, b.record_id)))
    assert finding.severity == "medium"
    assert finding.confidence == "proven_by_contract"


def test_form_label_and_non_semantic_fields_do_not_split_an_exact_group() -> None:
    a = duplicate_record("row-a", form="10-Q")
    b = duplicate_record("row-b", form="10-K")
    report = _detect((a, b))
    assert len(report.findings) == 1
    assert report.findings[0].evidence.group_size == 2  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "variant",
    [
        {"entity_id": "OTHER"},
        {"concept_namespace": "ifrs-full"},
        {"concept": "Assets"},
        {"value": "999"},
        {"unit": "EUR"},
        {"dimensions": (q.Dimension(axis="Segment", member="Cloud"),)},
        {"period_type": "duration", "period_start": date(2024, 1, 1)},
        {"period_end": date(2024, 6, 30)},
        {"filed_on": date(2024, 5, 1)},
        {"available_on": date(2024, 5, 1)},
        {"accession_number": "0000000009-24-000009"},
    ],
)
def test_any_fingerprint_field_difference_keeps_occurrences_independent(
    variant: dict[str, object],
) -> None:
    a = duplicate_record("row-a")
    b = duplicate_record("row-b", **variant)  # type: ignore[arg-type]
    assert _detect((a, b)).findings == ()


def test_same_value_in_a_different_period_is_not_a_duplicate() -> None:
    a = duplicate_record(
        "row-a",
        period_end=date(2024, 3, 31),
        filed_on=date(2024, 4, 15),
        available_on=date(2024, 4, 15),
    )
    b = duplicate_record(
        "row-b",
        period_end=date(2024, 6, 30),
        filed_on=date(2024, 8, 15),
        available_on=date(2024, 8, 15),
    )
    assert _detect((a, b)).findings == ()


def test_same_looking_values_from_independent_filings_are_not_duplicates() -> None:
    """Two facts that agree on entity/concept/value/period but come from
    genuinely different filings (different accession, filed_on, available_on)
    are legitimately independent occurrences, not an exact copy."""
    a = duplicate_record(
        "row-a",
        accession_number="0000000001-24-000001",
        filed_on=date(2024, 4, 15),
        available_on=date(2024, 4, 15),
    )
    b = duplicate_record(
        "row-b",
        accession_number="0000000001-24-000009",
        filed_on=date(2024, 5, 1),
        available_on=date(2024, 5, 1),
    )
    assert _detect((a, b)).findings == ()


def test_legitimate_amendment_with_a_changed_value_is_not_a_duplicate() -> None:
    original = duplicate_record(
        "row-a",
        value="100",
        accession_number="0000000001-24-000001",
        filed_on=date(2024, 4, 15),
        available_on=date(2024, 4, 15),
    )
    amendment = duplicate_record(
        "row-b",
        value="105",
        form="10-Q/A",
        accession_number="0000000001-24-000002",
        filed_on=date(2024, 5, 20),
        available_on=date(2024, 5, 20),
    )
    assert _detect((original, amendment)).findings == ()


def test_group_of_three_reports_one_finding_with_full_group_size() -> None:
    records = tuple(duplicate_record(f"row-{i}") for i in range(3))
    report = _detect(records)
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.evidence.group_size == 3  # type: ignore[union-attr]
    assert finding.affected_record_ids == tuple(sorted(record.record_id for record in records))


def test_multiple_independent_groups_each_produce_one_finding() -> None:
    group_a = (
        duplicate_record("a-1", concept="Revenues"),
        duplicate_record("a-2", concept="Revenues"),
    )
    group_b = (duplicate_record("b-1", concept="Assets"), duplicate_record("b-2", concept="Assets"))
    report = _detect(group_a + group_b)
    assert len(report.findings) == 2


def test_only_end_of_day_visible_occurrences_participate() -> None:
    later = date(2024, 5, 2)
    a = duplicate_record("row-a", available_on=later, filed_on=later)
    b = duplicate_record("row-b", available_on=later, filed_on=later)
    assert _detect((a, b), as_of_date=date(2024, 5, 1)).findings == ()
    assert len(_detect((a, b), as_of_date=later).findings) == 1


def test_detector_input_and_source_are_manifest_isolated() -> None:
    parameters = inspect.signature(q.detect_duplicate_observations).parameters
    assert tuple(parameters) == ("audit_input",)
    module = inspect.getmodule(q.detect_duplicate_observations)
    assert module is not None
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        forbidden in module_name
        for module_name in imports
        for forbidden in ("injection", "manifest", "scoring", "replay")
    )
    assert "DuplicateManifest" not in source
    assert "FinancialFact" not in source
    assert "DatasetSnapshot" not in source
    assert "seed" not in parameters
    assert "severity" not in parameters
    assert "copy_ordinal" not in source


def test_sanitized_bytes_contain_no_private_truth_or_injection_configuration() -> None:
    case = reviewed_duplicate_case()
    data = q.canonical_json_bytes(case.audit_input)
    prohibited = (
        b"manifest",
        b"original_record",
        b"created_record",
        b"copy_ordinal",
        b"selection_digest",
        b"target_rank",
        b"eligible_record_ids",
        b"seed",
        b"severity",
        b"target_fraction",
        b"target_count",
        b"max_targets",
        b"fault_id",
        b"source_row_key",
    )
    assert all(marker not in data for marker in prohibited)


def test_finding_order_and_identity_are_deterministic() -> None:
    first = reviewed_duplicate_case(seed=7).audit_report
    second = reviewed_duplicate_case(seed=7).audit_report
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)
    assert tuple(finding.finding_id for finding in first.findings) == tuple(
        sorted(finding.finding_id for finding in first.findings)
    )
    assert all(q.duplicate_finding_identity_matches(finding) for finding in first.findings)


def test_detector_input_order_does_not_change_findings() -> None:
    case = reviewed_duplicate_case()
    reversed_audit_input = q.AuditInputSnapshot(
        audit_input_id=case.audit_input.audit_input_id,
        dataset_name=case.audit_input.dataset_name,
        as_of_date=case.audit_input.as_of_date,
        records=tuple(reversed(case.audit_input.records)),
    )
    report = q.detect_duplicate_observations(reversed_audit_input)
    assert q.canonical_json_bytes(report) == q.canonical_json_bytes(case.audit_report)


def test_forged_audit_input_identity_is_rejected() -> None:
    case = reviewed_duplicate_case()
    forged = case.audit_input.model_copy(update={"audit_input_id": "audit_0000000000000000"})
    with pytest.raises(q.DuplicateDetectionError, match="identity"):
        q.detect_duplicate_observations(forged)
