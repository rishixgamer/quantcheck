"""The sanitize_for_audit trust boundary."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.fixtures import generate_reviewed_fixture
from quantcheck.hashing import audit_input_snapshot_identity_matches, source_record_id
from quantcheck.point_in_time import build_dataset_snapshot
from quantcheck.schemas import (
    AuditInputRecord,
    DatasetSnapshot,
    Dimension,
    FinancialFact,
    SourceReference,
)
from quantcheck.serialization import canonical_json_bytes

_FIXTURE = generate_reviewed_fixture()

#: Field/text markers that must never appear in sanitized audit-input bytes.
_PROHIBITED_MARKERS = (
    b"source_row_key",
    b"entity_name",
    b"#r1",
    b"#r2",
    b"#r3",
    b"seed",
    b"fixture_name",
    b"spec_version",
)


def _snapshot(as_of_date: date = date(2025, 1, 1)) -> DatasetSnapshot:
    return build_dataset_snapshot(_FIXTURE, dataset_name="reviewed", as_of_date=as_of_date)


def test_sanitize_returns_only_audit_input_records() -> None:
    audit_input = sanitize_for_audit(_snapshot())
    assert all(isinstance(record, AuditInputRecord) for record in audit_input.records)


def test_sanitize_preserves_every_record_by_id() -> None:
    snapshot = _snapshot()
    audit_input = sanitize_for_audit(snapshot)
    assert {r.record_id for r in audit_input.records} == {r.record_id for r in snapshot.records}


def test_sanitize_preserves_the_historical_cutoff() -> None:
    snapshot = _snapshot(date(2024, 5, 1))
    audit_input = sanitize_for_audit(snapshot)
    assert audit_input.as_of_date == snapshot.as_of_date == date(2024, 5, 1)
    assert audit_input.dataset_name == snapshot.dataset_name


def test_sanitize_preserves_public_financial_fields() -> None:
    snapshot = _snapshot()
    by_id = {r.record_id: r for r in snapshot.records}
    audit_input = sanitize_for_audit(snapshot)
    for audit_record in audit_input.records:
        source_record = by_id[audit_record.record_id]
        assert audit_record.entity_id == source_record.entity_id
        assert audit_record.concept == source_record.concept
        assert audit_record.value == source_record.value
        assert audit_record.unit == source_record.unit
        assert audit_record.period_end == source_record.period_end
        assert audit_record.filed_on == source_record.filed_on
        assert audit_record.available_on == source_record.available_on
        assert audit_record.source_name == source_record.source.source_name
        assert audit_record.source_locator == source_record.source.source_locator


def test_audit_input_identity_verifies() -> None:
    audit_input = sanitize_for_audit(_snapshot())
    assert audit_input_snapshot_identity_matches(audit_input)


def test_sanitize_does_not_mutate_the_source_snapshot() -> None:
    snapshot = _snapshot()
    before = canonical_json_bytes(snapshot)
    sanitize_for_audit(snapshot)
    assert canonical_json_bytes(snapshot) == before


def test_sanitized_records_are_canonically_ordered_regardless_of_snapshot_order() -> None:
    snapshot = _snapshot()
    audit_input = sanitize_for_audit(snapshot)
    ids = [r.record_id for r in audit_input.records]
    assert ids == sorted(ids)


def test_record_order_reversal_does_not_change_canonical_output() -> None:
    snapshot = _snapshot()
    reversed_snapshot = DatasetSnapshot(
        snapshot_id=snapshot.snapshot_id,
        dataset_name=snapshot.dataset_name,
        as_of_date=snapshot.as_of_date,
        records=tuple(reversed(snapshot.records)),
    )
    assert canonical_json_bytes(sanitize_for_audit(snapshot)) == canonical_json_bytes(
        sanitize_for_audit(reversed_snapshot)
    )


def test_round_trip_parsing_reproduces_the_same_logical_artifact() -> None:
    from quantcheck.serialization import parse_canonical_json

    audit_input = sanitize_for_audit(_snapshot())
    parsed = parse_canonical_json(canonical_json_bytes(audit_input))
    assert isinstance(parsed, dict)
    restored = type(audit_input).model_validate(parsed)
    assert restored == audit_input


def test_canonical_bytes_contain_no_prohibited_private_field_names() -> None:
    audit_input = sanitize_for_audit(_snapshot())
    raw = canonical_json_bytes(audit_input)
    for marker in _PROHIBITED_MARKERS:
        assert marker not in raw, marker


def test_canonical_bytes_contain_no_entity_name_even_when_source_has_one() -> None:
    fact = FinancialFact(
        record_id=source_record_id(source_name="t", source_locator="t", source_row_key="only-row"),
        entity_id="CIK1231231234",
        entity_name="A Name That Must Not Cross The Boundary",
        concept_namespace="us-gaap",
        concept="Revenues",
        value=Decimal("1"),
        unit="USD",
        period_type="duration",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        filed_on=date(2024, 4, 1),
        available_on=date(2024, 4, 1),
        source=SourceReference(source_name="t", source_locator="t", source_row_key="only-row"),
    )
    snapshot = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 12, 31))
    audit_input = sanitize_for_audit(snapshot)
    raw = canonical_json_bytes(audit_input)
    assert b"A Name That Must Not Cross The Boundary" not in raw
    assert b"only-row" not in raw


def test_declared_revision_lineage_marker_does_not_cross_the_boundary() -> None:
    fact = FinancialFact(
        record_id=source_record_id(source_name="t", source_locator="t", source_row_key="LIN#r1"),
        entity_id="CIK1231231234",
        concept_namespace="us-gaap",
        concept="Revenues",
        value=Decimal("1"),
        unit="USD",
        period_type="duration",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        filed_on=date(2024, 4, 1),
        available_on=date(2024, 4, 1),
        source=SourceReference(source_name="t", source_locator="t", source_row_key="LIN#r1"),
    )
    snapshot = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 12, 31))
    audit_input = sanitize_for_audit(snapshot)
    raw = canonical_json_bytes(audit_input)
    assert b"LIN#r1" not in raw
    assert b"LIN" not in raw


def test_dimensions_are_preserved_through_the_boundary() -> None:
    fact = FinancialFact(
        record_id=source_record_id(source_name="t", source_locator="t", source_row_key="dim-row"),
        entity_id="CIK1231231234",
        concept_namespace="us-gaap",
        concept="Revenues",
        value=Decimal("1"),
        unit="USD",
        dimensions=(Dimension(axis="Segment", member="Total"),),
        period_type="duration",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        filed_on=date(2024, 4, 1),
        available_on=date(2024, 4, 1),
        source=SourceReference(source_name="t", source_locator="t", source_row_key="dim-row"),
    )
    snapshot = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 12, 31))
    audit_input = sanitize_for_audit(snapshot)
    assert audit_input.records[0].dimensions == (Dimension(axis="Segment", member="Total"),)


def test_empty_snapshot_sanitizes_to_an_empty_audit_input() -> None:
    empty_snapshot = build_dataset_snapshot([], dataset_name="d", as_of_date=date(2024, 1, 1))
    audit_input = sanitize_for_audit(empty_snapshot)
    assert audit_input.records == ()
    assert audit_input_snapshot_identity_matches(audit_input)


def test_sanitizing_is_deterministic_across_repeated_calls() -> None:
    snapshot = _snapshot()
    first = canonical_json_bytes(sanitize_for_audit(snapshot))
    second = canonical_json_bytes(sanitize_for_audit(snapshot))
    assert first == second
