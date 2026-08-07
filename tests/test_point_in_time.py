"""Point-in-time availability and canonical snapshot construction."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from quantcheck.fixtures import generate_reviewed_fixture
from quantcheck.hashing import (
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
    source_record_id,
)
from quantcheck.point_in_time import build_dataset_snapshot
from quantcheck.schemas import FinancialFact, SourceReference

_FIXTURE = generate_reviewed_fixture()


def _fact(row_key: str, *, available_on: date, filed_on: date | None = None) -> FinancialFact:
    source = SourceReference(source_name="t", source_locator="t", source_row_key=row_key)
    return FinancialFact(
        record_id=source_record_id(source_name="t", source_locator="t", source_row_key=row_key),
        entity_id="CIK9999999999",
        concept_namespace="us-gaap",
        concept="Revenues",
        value=Decimal("100"),
        unit="USD",
        period_type="duration",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        filed_on=filed_on or available_on,
        available_on=available_on,
        source=source,
    )


# --- Availability boundary --------------------------------------------------


def test_available_before_as_of_date_is_included() -> None:
    fact = _fact("a", available_on=date(2024, 4, 1))
    snapshot = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 4, 30))
    assert fact.record_id in [record.record_id for record in snapshot.records]


def test_available_exactly_on_as_of_date_is_included() -> None:
    fact = _fact("a", available_on=date(2024, 4, 30))
    snapshot = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 4, 30))
    assert fact.record_id in [record.record_id for record in snapshot.records]


def test_available_after_as_of_date_is_excluded() -> None:
    fact = _fact("a", available_on=date(2024, 5, 1))
    snapshot = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 4, 30))
    assert snapshot.records == ()


def test_empty_eligible_selection_is_an_empty_snapshot() -> None:
    fact = _fact("a", available_on=date(2099, 1, 1))
    snapshot = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 1, 1))
    assert snapshot.records == ()
    assert dataset_snapshot_identity_matches(snapshot)


def test_no_input_records_is_an_empty_snapshot() -> None:
    snapshot = build_dataset_snapshot([], dataset_name="d", as_of_date=date(2024, 1, 1))
    assert snapshot.records == ()
    assert snapshot.snapshot_id == dataset_snapshot_id(
        dataset_name="d", as_of_date=date(2024, 1, 1), records=[]
    )


def test_quarter_end_boundary_is_not_confused_with_filing_day_cutoff() -> None:
    # period_end is the last day of Q1; filed/available happen well afterward.
    # Only available_on controls eligibility, never period_end or filed_on alone.
    fact = _fact("a", available_on=date(2024, 5, 2), filed_on=date(2024, 5, 2))
    assert fact.period_end == date(2024, 3, 31)

    before = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 3, 31))
    assert before.records == ()

    on_filing_day = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 5, 2))
    assert len(on_filing_day.records) == 1


def test_filed_on_alone_never_controls_eligibility() -> None:
    """A record filed early but not yet available must stay excluded."""
    fact = _fact("a", filed_on=date(2024, 1, 1), available_on=date(2024, 12, 31))
    snapshot = build_dataset_snapshot([fact], dataset_name="d", as_of_date=date(2024, 6, 1))
    assert snapshot.records == ()


# --- Canonical snapshot construction ----------------------------------------


_LATE_AS_OF = date(2025, 1, 1)


def test_snapshot_id_and_content_hash_verify() -> None:
    snapshot = build_dataset_snapshot(_FIXTURE, dataset_name="reviewed", as_of_date=_LATE_AS_OF)
    assert dataset_snapshot_identity_matches(snapshot)


def test_records_are_sorted_deterministically_by_record_id() -> None:
    snapshot = build_dataset_snapshot(_FIXTURE, dataset_name="reviewed", as_of_date=_LATE_AS_OF)
    ids = [record.record_id for record in snapshot.records]
    assert ids == sorted(ids)


def test_repeated_builds_produce_identical_canonical_bytes() -> None:
    from quantcheck.serialization import canonical_json_bytes

    first = build_dataset_snapshot(_FIXTURE, dataset_name="reviewed", as_of_date=_LATE_AS_OF)
    second = build_dataset_snapshot(_FIXTURE, dataset_name="reviewed", as_of_date=_LATE_AS_OF)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_input_sequence_is_not_mutated() -> None:
    records = list(_FIXTURE)
    original_ids = [record.record_id for record in records]
    build_dataset_snapshot(records, dataset_name="reviewed", as_of_date=date(2024, 5, 1))
    assert [record.record_id for record in records] == original_ids


def test_input_list_object_identity_is_untouched() -> None:
    records = list(_FIXTURE)
    snapshot_a = build_dataset_snapshot(records, dataset_name="d", as_of_date=date(2024, 5, 1))
    records.reverse()
    snapshot_b = build_dataset_snapshot(records, dataset_name="d", as_of_date=date(2024, 5, 1))
    assert snapshot_a.snapshot_id == snapshot_b.snapshot_id


_MID_AS_OF = date(2024, 6, 1)


def test_reordering_input_records_does_not_change_snapshot_id() -> None:
    forward = build_dataset_snapshot(_FIXTURE, dataset_name="reviewed", as_of_date=_MID_AS_OF)
    reversed_input = list(reversed(_FIXTURE))
    backward = build_dataset_snapshot(
        reversed_input, dataset_name="reviewed", as_of_date=_MID_AS_OF
    )
    assert forward.snapshot_id == backward.snapshot_id
    assert [r.record_id for r in forward.records] == [r.record_id for r in backward.records]


@pytest.mark.parametrize("dataset_name", ["reviewed", "another-dataset"])
def test_dataset_name_is_part_of_snapshot_identity(dataset_name: str) -> None:
    snapshot = build_dataset_snapshot(_FIXTURE, dataset_name=dataset_name, as_of_date=_MID_AS_OF)
    assert snapshot.snapshot_id == dataset_snapshot_id(
        dataset_name=dataset_name, as_of_date=_MID_AS_OF, records=list(snapshot.records)
    )
