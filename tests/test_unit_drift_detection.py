"""Manifest-blind Unit Drift detection, isolation, and hard negatives."""

from __future__ import annotations

import ast
import inspect
from datetime import date, timedelta
from decimal import Decimal

import pytest

import quantcheck as q
from tests.unit_drift_support import (
    reviewed_unit_drift_case,
    unit_drift_records,
    unit_drift_snapshot,
)


def _detect_values(values: tuple[str, ...]) -> q.AuditReport:
    snapshot = unit_drift_snapshot(unit_drift_records(values=values))
    return q.detect_unit_drift(q.sanitize_for_audit(snapshot), q.UnitDriftDetectorConfig())


def test_current_reviewed_fixture_and_focused_clean_control_emit_no_findings() -> None:
    reviewed = q.build_dataset_snapshot(
        q.generate_reviewed_fixture(),
        dataset_name="reviewed-clean-control",
        as_of_date=date(2024, 8, 31),
    )
    assert (
        q.detect_unit_drift(q.sanitize_for_audit(reviewed), q.UnitDriftDetectorConfig()).findings
        == ()
    )
    assert _detect_values(("100", "110", "120", "130", "140")).findings == ()


def test_endpoint_positive_has_one_neighbor_and_suspicious_confidence() -> None:
    case = reviewed_unit_drift_case(seed=0)
    assert len(case.audit_report.findings) == 1
    finding = case.audit_report.findings[0]
    assert isinstance(finding.evidence, q.UnitDriftEvidence)
    assert finding.confidence == "suspicious"
    assert finding.evidence.usable_neighbor_count == 1
    assert finding.evidence.candidate_scale_factor == Decimal("1000")
    assert finding.evidence.candidate_correction_factor == Decimal("0.001")
    assert finding.evidence.corrected_value == case.manifest.entries[0].original_record.value


def test_interior_positive_has_two_neighbors_and_strong_confidence() -> None:
    case = reviewed_unit_drift_case(seed=6)
    assert len(case.audit_report.findings) == 1
    finding = case.audit_report.findings[0]
    assert isinstance(finding.evidence, q.UnitDriftEvidence)
    assert finding.confidence == "strong"
    assert finding.evidence.usable_neighbor_count == 2
    assert tuple(neighbor.position for neighbor in finding.evidence.neighbors) == (
        "previous",
        "next",
    )
    assert all(
        neighbor.before_ratio >= Decimal("50") and neighbor.after_ratio < Decimal("50")
        for neighbor in finding.evidence.neighbors
    )


def test_detector_can_represent_reciprocal_direction_for_too_small_value() -> None:
    report = _detect_values(("100", "110", "1", "120", "130"))
    assert len(report.findings) == 1
    evidence = report.findings[0].evidence
    assert isinstance(evidence, q.UnitDriftEvidence)
    assert evidence.correction_operation == "multiply"
    assert evidence.candidate_scale_factor == Decimal("100")
    assert evidence.candidate_correction_factor == Decimal("100")
    assert evidence.corrected_value == Decimal("100")


def test_exact_threshold_is_inclusive_before_and_strict_after_correction() -> None:
    at_threshold = _detect_values(("100", "100", "5000", "100", "100"))
    assert len(at_threshold.findings) == 1
    evidence = at_threshold.findings[0].evidence
    assert isinstance(evidence, q.UnitDriftEvidence)
    assert {neighbor.before_ratio for neighbor in evidence.neighbors} == {Decimal("50")}

    below_threshold = _detect_values(("100", "100", "4999", "100", "100"))
    assert below_threshold.findings == ()


def test_best_supported_correction_is_selected_deterministically() -> None:
    report = _detect_values(("100", "100", "100000", "100", "100"))
    assert len(report.findings) == 1
    evidence = report.findings[0].evidence
    assert isinstance(evidence, q.UnitDriftEvidence)
    assert evidence.candidate_scale_factor == Decimal("1000")
    assert evidence.corrected_value == Decimal("100")


def test_zero_loss_profit_and_sign_transitions_are_not_scale_findings() -> None:
    assert _detect_values(("100", "-100", "0", "100", "-100")).findings == ()


def test_naturally_large_but_below_threshold_changes_are_not_findings() -> None:
    assert _detect_values(("1", "10", "20", "30", "40")).findings == ()


def test_large_movement_no_supported_correction_resolves_is_not_a_finding() -> None:
    assert _detect_values(("1", "1", "100000000", "1", "1")).findings == ()


@pytest.mark.parametrize(
    "variant",
    [
        {"entity_id": "OTHER"},
        {"concept_namespace": "ifrs-full"},
        {"concept": "Assets"},
        {"unit": "EUR"},
        {"dimensions": (q.Dimension(axis="Segment", member="Cloud"),)},
    ],
)
def test_same_values_in_unrelated_exact_groups_are_not_compared(
    variant: dict[str, object],
) -> None:
    base = unit_drift_records(values=("100", "100000"), source_key="base")
    unrelated = tuple(
        record.model_copy(update=variant)
        for record in unit_drift_records(values=("100", "100000"), source_key="other")
    )
    snapshot = unit_drift_snapshot(base + unrelated)
    report = q.detect_unit_drift(q.sanitize_for_audit(snapshot), q.UnitDriftDetectorConfig())
    assert report.findings == ()


def test_instant_and_duration_or_incompatible_duration_shapes_are_not_compared() -> None:
    instant = unit_drift_records(values=("100", "100000"), source_key="instant")
    duration_30 = unit_drift_records(
        values=("100", "100000"), period_type="duration", source_key="duration-30"
    )
    duration_30_first = duration_30[0]
    assert duration_30_first.period_start is not None
    duration_31 = duration_30_first.model_copy(
        update={
            "record_id": "rec_ffffffffffffffff",
            "period_start": duration_30_first.period_start - timedelta(days=1),
        }
    )
    snapshot = unit_drift_snapshot(instant + duration_30 + (duration_31,))
    report = q.detect_unit_drift(q.sanitize_for_audit(snapshot), q.UnitDriftDetectorConfig())
    assert report.findings == ()


def test_insufficient_history_and_no_nonzero_neighbor_are_not_findings() -> None:
    assert _detect_values(("100", "100000")).findings == ()
    assert _detect_values(("0", "100000", "0")).findings == ()


def test_amendment_metadata_without_scale_evidence_is_not_a_finding() -> None:
    records = list(unit_drift_records(values=("100", "105", "110", "115")))
    records[1] = records[1].model_copy(
        update={"form": "10-Q/A", "accession_number": "0000000001-24-999999"}
    )
    snapshot = unit_drift_snapshot(tuple(records))
    assert (
        q.detect_unit_drift(q.sanitize_for_audit(snapshot), q.UnitDriftDetectorConfig()).findings
        == ()
    )
    assert "source_status" not in q.AuditInputRecord.model_fields


def test_detector_input_and_source_are_manifest_isolated() -> None:
    parameters = inspect.signature(q.detect_unit_drift).parameters
    assert tuple(parameters) == ("audit_input", "config")
    module = inspect.getmodule(q.detect_unit_drift)
    assert module is not None
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        forbidden in module
        for module in imports
        for forbidden in ("injection", "manifest", "scoring", "replay")
    )
    assert "UnitDriftManifest" not in source
    assert "FinancialFact" not in source
    assert "DatasetSnapshot" not in source
    assert "seed" not in parameters
    assert "severity" not in parameters


def test_sanitized_bytes_contain_no_private_truth_or_injection_configuration() -> None:
    case = reviewed_unit_drift_case()
    data = q.canonical_json_bytes(case.audit_input)
    prohibited = (
        b"manifest",
        b"original_record",
        b"original_value",
        b"scale_factor",
        b"selection_digest",
        b"target_rank",
        b"eligible_record_ids",
        b"seed",
        b"severity",
        b"target_fraction",
        b"target_count",
        b"max_targets",
        b"fault_id",
    )
    assert all(marker not in data for marker in prohibited)
    assert b"mod_" not in data


def test_finding_order_and_identity_are_deterministic() -> None:
    first = reviewed_unit_drift_case(seed=6).audit_report
    second = reviewed_unit_drift_case(seed=6).audit_report
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)
    assert tuple(finding.finding_id for finding in first.findings) == tuple(
        sorted(finding.finding_id for finding in first.findings)
    )
    assert all(q.unit_drift_finding_identity_matches(finding) for finding in first.findings)


def test_forged_audit_input_identity_is_rejected() -> None:
    case = reviewed_unit_drift_case()
    forged = case.audit_input.model_copy(update={"audit_input_id": "audit_0000000000000000"})
    with pytest.raises(q.UnitDriftDetectionError, match="identity"):
        q.detect_unit_drift(forged, q.UnitDriftDetectorConfig())
