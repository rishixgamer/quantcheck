"""Explicit revision-history ordering and selection.

These construct small synthetic (not fixture) revision histories so each
scenario — including deliberately ambiguous ones — is isolated and easy to
read. The checked-in reviewed fixture itself stays clean; see
``tests/test_fixtures.py`` for coverage of its two real revision histories.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from quantcheck.hashing import revision_id, source_record_id
from quantcheck.point_in_time import (
    AmbiguousRevisionHistoryError,
    RevisionLineage,
    build_dataset_snapshot,
    parse_declared_revision_lineage,
)
from quantcheck.schemas import Dimension, FinancialFact, SourceReference


def _fact(
    row_key: str,
    *,
    value: str,
    available_on: date,
    filed_on: date | None = None,
    concept: str = "Revenues",
    entity_id: str = "CIK1111111111",
    unit: str = "USD",
    dimensions: tuple[Dimension, ...] = (),
) -> FinancialFact:
    return FinancialFact(
        record_id=source_record_id(source_name="t", source_locator="t", source_row_key=row_key),
        entity_id=entity_id,
        concept_namespace="us-gaap",
        concept=concept,
        value=Decimal(value),
        unit=unit,
        dimensions=dimensions,
        period_type="duration",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        filed_on=filed_on or available_on,
        available_on=available_on,
        source=SourceReference(source_name="t", source_locator="t", source_row_key=row_key),
    )


# --- Marker parsing ----------------------------------------------------------


def test_row_key_without_marker_is_not_a_lineage() -> None:
    assert parse_declared_revision_lineage("plain-row-key") is None


def test_row_key_with_marker_parses_lineage_and_sequence() -> None:
    assert parse_declared_revision_lineage("AAPL-Q1-REV#r2") == RevisionLineage(
        lineage_id="AAPL-Q1-REV", sequence=2
    )


def test_marker_with_zero_or_leading_zero_sequence_is_not_recognized() -> None:
    assert parse_declared_revision_lineage("x#r0") is None
    assert parse_declared_revision_lineage("x#r01") is None


# --- Selection across cutoffs -------------------------------------------------


def test_early_cutoff_selects_the_earlier_known_revision() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1))
    r2 = _fact("X#r2", value="110", available_on=date(2024, 6, 1))
    snapshot = build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 5, 1))
    assert [record.record_id for record in snapshot.records] == [r1.record_id]


def test_later_cutoff_selects_the_later_visible_revision() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1))
    r2 = _fact("X#r2", value="110", available_on=date(2024, 6, 1))
    snapshot = build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 7, 1))
    assert [record.record_id for record in snapshot.records] == [r2.record_id]


def test_later_revision_never_contaminates_an_earlier_snapshot() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1))
    r2 = _fact("X#r2", value="999999", available_on=date(2024, 6, 1))
    snapshot = build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 5, 1))
    assert len(snapshot.records) == 1
    assert snapshot.records[0].value == Decimal("100")


def test_reversed_source_order_does_not_change_selection() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1))
    r2 = _fact("X#r2", value="110", available_on=date(2024, 6, 1))
    forward = build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 7, 1))
    backward = build_dataset_snapshot([r2, r1], dataset_name="d", as_of_date=date(2024, 7, 1))
    assert forward.snapshot_id == backward.snapshot_id
    assert [record.record_id for record in forward.records] == [
        record.record_id for record in backward.records
    ]


def test_equal_value_revisions_remain_separate_source_events() -> None:
    """Lineage says these are two revisions, even though the value never changed."""
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1))
    r2 = _fact("X#r2", value="100", available_on=date(2024, 6, 1))
    assert r1.record_id != r2.record_id

    early = build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 5, 1))
    late = build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 7, 1))
    assert [record.record_id for record in early.records] == [r1.record_id]
    assert [record.record_id for record in late.records] == [r2.record_id]


def test_revision_unavailable_at_cutoff_excludes_the_whole_lineage() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 6, 1))
    snapshot = build_dataset_snapshot([r1], dataset_name="d", as_of_date=date(2024, 1, 1))
    assert snapshot.records == ()


# --- Independent occurrences are not merged into a history --------------------


def test_independent_records_with_no_lineage_marker_are_all_preserved() -> None:
    a = _fact("A", value="50", available_on=date(2024, 4, 1))
    b = _fact("B", value="50", available_on=date(2024, 4, 1))
    snapshot = build_dataset_snapshot([a, b], dataset_name="d", as_of_date=date(2024, 5, 1))
    assert {record.record_id for record in snapshot.records} == {a.record_id, b.record_id}


def test_records_sharing_a_business_key_but_no_lineage_are_independent() -> None:
    """Same entity/concept/period/unit/value, but no declared lineage: not a revision pair."""
    a = _fact("dup-a", value="500000", available_on=date(2024, 4, 1))
    b = _fact("dup-b", value="500000", available_on=date(2024, 4, 1))
    snapshot = build_dataset_snapshot([a, b], dataset_name="d", as_of_date=date(2024, 12, 31))
    assert len(snapshot.records) == 2


def test_different_lineage_ids_are_independent_histories() -> None:
    a1 = _fact("A#r1", value="1", available_on=date(2024, 4, 1))
    b1 = _fact("B#r1", value="2", available_on=date(2024, 4, 1))
    snapshot = build_dataset_snapshot([a1, b1], dataset_name="d", as_of_date=date(2024, 5, 1))
    assert {record.record_id for record in snapshot.records} == {a1.record_id, b1.record_id}


# --- Rejected ambiguity --------------------------------------------------------


def test_duplicate_sequence_number_is_rejected() -> None:
    # Two source occurrences that both (incorrectly) declare lineage "X", sequence 1.
    r1a = _fact("X#r1", value="100", available_on=date(2024, 4, 1))
    r1b = _fact("X#r1", value="200", available_on=date(2024, 4, 2))
    with pytest.raises(AmbiguousRevisionHistoryError):
        build_dataset_snapshot([r1a, r1b], dataset_name="d", as_of_date=date(2024, 12, 31))


def test_mismatched_economic_identity_within_a_lineage_is_rejected() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1), concept="Revenues")
    r2 = _fact("X#r2", value="100", available_on=date(2024, 5, 1), concept="NetIncomeLoss")
    with pytest.raises(AmbiguousRevisionHistoryError):
        build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 12, 31))


def test_mismatched_unit_within_a_lineage_is_rejected() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1), unit="USD")
    r2 = _fact("X#r2", value="100", available_on=date(2024, 5, 1), unit="EUR")
    with pytest.raises(AmbiguousRevisionHistoryError):
        build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 12, 31))


def test_mismatched_dimensions_within_a_lineage_is_rejected() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1), dimensions=())
    r2 = _fact(
        "X#r2",
        value="100",
        available_on=date(2024, 5, 1),
        dimensions=(Dimension(axis="Segment", member="Total"),),
    )
    with pytest.raises(AmbiguousRevisionHistoryError):
        build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 12, 31))


def test_non_monotonic_availability_by_declared_sequence_is_rejected() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 6, 1))
    r2 = _fact("X#r2", value="110", available_on=date(2024, 4, 1))
    with pytest.raises(AmbiguousRevisionHistoryError):
        build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 12, 31))


def test_non_monotonic_filing_by_declared_sequence_is_rejected() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1), filed_on=date(2024, 6, 1))
    r2 = _fact("X#r2", value="110", available_on=date(2024, 5, 1), filed_on=date(2024, 4, 1))
    with pytest.raises(AmbiguousRevisionHistoryError):
        build_dataset_snapshot([r1, r2], dataset_name="d", as_of_date=date(2024, 12, 31))


def test_ambiguous_history_is_rejected_regardless_of_input_order() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 6, 1))
    r2 = _fact("X#r2", value="110", available_on=date(2024, 4, 1))
    with pytest.raises(AmbiguousRevisionHistoryError):
        build_dataset_snapshot([r2, r1], dataset_name="d", as_of_date=date(2024, 12, 31))


def test_single_member_lineage_is_not_ambiguous() -> None:
    r1 = _fact("X#r1", value="100", available_on=date(2024, 4, 1))
    snapshot = build_dataset_snapshot([r1], dataset_name="d", as_of_date=date(2024, 12, 31))
    assert [record.record_id for record in snapshot.records] == [r1.record_id]


# --- Dedicated revision identifiers -------------------------------------------


def test_revision_id_is_deterministic() -> None:
    first = revision_id(lineage_id="X", sequence=1)
    second = revision_id(lineage_id="X", sequence=1)
    assert first == second
    assert first.startswith("rev_")


def test_revision_id_distinguishes_sequence_and_lineage() -> None:
    a = revision_id(lineage_id="X", sequence=1)
    b = revision_id(lineage_id="X", sequence=2)
    c = revision_id(lineage_id="Y", sequence=1)
    assert len({a, b, c}) == 3


def test_revision_id_rejects_non_positive_sequence() -> None:
    from quantcheck.json_types import CanonicalizationError

    with pytest.raises(CanonicalizationError):
        revision_id(lineage_id="X", sequence=0)
    with pytest.raises(CanonicalizationError):
        revision_id(lineage_id="X", sequence=-1)
