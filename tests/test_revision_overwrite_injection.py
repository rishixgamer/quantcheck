"""Eligibility, selection, and exact Revision Overwrite injection."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

import quantcheck as q
from tests.revision_overwrite_support import (
    focused_history,
    focused_snapshot,
    reviewed_revision_overwrite_case,
    revision_record,
)


def test_reviewed_fixture_has_one_low_severity_explicit_unit() -> None:
    case = reviewed_revision_overwrite_case()
    assert case.manifest.eligible_unit_count == 1
    unit = case.manifest.eligible_units[0]
    assert unit.lineage_id == "E2-NI-Q1-2024"
    assert unit.historical_sequence == 1
    assert unit.later_sequence == 2
    assert unit.relative_revision_size == Decimal("0.02")


@pytest.mark.parametrize("severity", ["low", "medium", "high"])
def test_twenty_five_percent_revision_meets_every_threshold(
    severity: q.RevisionOverwriteSeverity,
) -> None:
    records = focused_history()
    clean = focused_snapshot(records)
    corrupted, manifest = q.inject_revision_overwrite(
        clean,
        records,
        q.RevisionOverwriteInjectionConfig(severity=severity, seed=1),
    )
    assert manifest.eligible_unit_count == 1
    assert manifest.target_count == 1
    assert corrupted != clean


def test_cutoff_includes_historical_boundary_and_excludes_later_boundary() -> None:
    records = focused_history(
        historical_filed_on=date(2024, 4, 30),
        later_filed_on=date(2024, 5, 1),
    )
    clean = focused_snapshot(records, as_of_date=date(2024, 4, 30))
    units = q.build_revision_history_units(
        records,
        clean_snapshot=clean,
        minimum_relative_revision_size=Decimal("0.20"),
    )
    assert len(units) == 1
    assert units[0].historical_record.available_on == clean.as_of_date


def test_injection_changes_only_identity_and_later_vintage_fields() -> None:
    records = focused_history()
    clean = focused_snapshot(records)
    corrupted, manifest = q.inject_revision_overwrite(
        clean,
        records,
        q.RevisionOverwriteInjectionConfig(severity="high", seed=1),
    )
    unit = manifest.eligible_units[0]
    entry = manifest.entries[0]
    historical = unit.historical_record
    later = unit.later_record
    changed = {
        name
        for name in q.FinancialFact.model_fields
        if getattr(historical, name) != getattr(entry.corrupted_record, name)
    }
    assert changed == {
        "record_id",
        "value",
        "filed_on",
        "form",
        "accession_number",
        "source",
    }
    assert entry.corrupted_record.available_on == historical.available_on
    assert entry.corrupted_record.value == later.value
    assert entry.corrupted_record.source == later.source
    assert entry.corrupted_record in corrupted.records


def test_unrelated_records_are_byte_identical_and_later_source_is_preserved() -> None:
    pair = focused_history()
    unrelated = revision_record(
        "UNRELATED",
        value="77",
        filed_on=date(2024, 4, 10),
        concept="Assets",
        period_type="instant",
        period_start=None,
    )
    records = (*pair, unrelated)
    clean = focused_snapshot(records)
    source_before = q.canonical_json_bytes(records)
    corrupted, manifest = q.inject_revision_overwrite(
        clean,
        records,
        q.RevisionOverwriteInjectionConfig(severity="high", seed=1),
    )
    assert unrelated in clean.records and unrelated in corrupted.records
    assert q.canonical_json_bytes(records) == source_before
    assert pair[1] in records
    assert manifest.eligible_units[0].later_record == pair[1]


@pytest.mark.parametrize(
    ("historical_value", "later_value"),
    [("0", "10"), ("100", "100"), ("100", "100.5")],
)
def test_zero_same_value_and_below_threshold_pairs_are_ineligible(
    historical_value: str,
    later_value: str,
) -> None:
    records = focused_history(
        historical_value=historical_value,
        later_value=later_value,
    )
    clean = focused_snapshot(records)
    with pytest.raises(q.NoEligibleRevisionOverwriteTargetsError):
        q.inject_revision_overwrite(
            clean,
            records,
            q.RevisionOverwriteInjectionConfig(severity="low", seed=0),
        )


def test_no_later_revision_is_ineligible() -> None:
    historical = focused_history()[0]
    clean = focused_snapshot((historical,))
    with pytest.raises(q.NoEligibleRevisionOverwriteTargetsError):
        q.inject_revision_overwrite(
            clean,
            (historical,),
            q.RevisionOverwriteInjectionConfig(severity="low", seed=0),
        )


def test_later_revision_already_available_uses_the_later_clean_state_not_overwrite() -> None:
    records = focused_history()
    clean = focused_snapshot(records, as_of_date=date(2024, 6, 1))
    assert clean.records == (records[1],)
    with pytest.raises(q.NoEligibleRevisionOverwriteTargetsError):
        q.inject_revision_overwrite(
            clean,
            records,
            q.RevisionOverwriteInjectionConfig(severity="low", seed=0),
        )


def test_independent_similar_occurrences_never_form_a_revision_history() -> None:
    records = (
        revision_record("A", value="100", filed_on=date(2024, 4, 15)),
        revision_record("B", value="125", filed_on=date(2024, 6, 1)),
    )
    clean = focused_snapshot(records)
    with pytest.raises(q.NoEligibleRevisionOverwriteTargetsError):
        q.inject_revision_overwrite(
            clean,
            records,
            q.RevisionOverwriteInjectionConfig(severity="low", seed=0),
        )


def test_delayed_clean_availability_is_not_guessed() -> None:
    historical = revision_record(
        "D#r1",
        value="100",
        filed_on=date(2024, 4, 10),
        available_on=date(2024, 4, 11),
        accession_number="D1",
    )
    later = revision_record(
        "D#r2",
        value="125",
        filed_on=date(2024, 6, 1),
        accession_number="D2",
    )
    clean = focused_snapshot((historical, later))
    with pytest.raises(q.NoEligibleRevisionOverwriteTargetsError):
        q.inject_revision_overwrite(
            clean,
            (historical, later),
            q.RevisionOverwriteInjectionConfig(severity="low", seed=0),
        )


@pytest.mark.parametrize(
    "changed_field",
    [
        "entity_id",
        "concept_namespace",
        "concept",
        "unit",
        "dimensions",
        "period_start",
        "period_end",
    ],
)
def test_changed_economic_context_is_rejected_as_ambiguous(changed_field: str) -> None:
    historical, later = focused_history()
    updates: dict[str, object] = {
        "entity_id": "ENTITY-2",
        "concept_namespace": "custom-gaap",
        "concept": "Assets",
        "unit": "EUR",
        "dimensions": (q.Dimension(axis="Segment", member="Other"),),
        "period_start": date(2024, 1, 2),
        "period_end": date(2024, 3, 30),
    }
    altered = later.model_copy(update={changed_field: updates[changed_field]})
    with pytest.raises(q.AmbiguousRevisionHistoryError):
        focused_snapshot((historical, altered))


def test_changed_period_shape_is_rejected_as_ambiguous() -> None:
    historical, later = focused_history()
    altered = later.model_copy(update={"period_type": "instant", "period_start": None})
    with pytest.raises(q.AmbiguousRevisionHistoryError):
        focused_snapshot((historical, altered))


@pytest.mark.parametrize("changed_context", ["entity_name", "source_name"])
def test_changed_controlled_context_is_rejected_as_ambiguous(
    changed_context: str,
) -> None:
    historical, later = focused_history()
    if changed_context == "entity_name":
        altered = later.model_copy(update={"entity_name": "Different Legal Entity"})
    else:
        altered = later.model_copy(
            update={"source": later.source.model_copy(update={"source_name": "other-source"})}
        )
    clean = focused_snapshot((historical, altered))
    with pytest.raises(q.AmbiguousRevisionHistoryError):
        q.inject_revision_overwrite(
            clean,
            (historical, altered),
            q.RevisionOverwriteInjectionConfig(severity="low", seed=0),
        )


def test_reused_accession_is_ineligible() -> None:
    historical, later = focused_history()
    altered = later.model_copy(update={"accession_number": historical.accession_number})
    clean = focused_snapshot((historical, altered))
    with pytest.raises(q.NoEligibleRevisionOverwriteTargetsError):
        q.inject_revision_overwrite(
            clean,
            (historical, altered),
            q.RevisionOverwriteInjectionConfig(severity="low", seed=0),
        )


def test_malformed_lineage_marker_is_an_independent_ineligible_occurrence() -> None:
    malformed = revision_record(
        "MALFORMED#r0",
        value="125",
        filed_on=date(2024, 6, 1),
    )
    clean = focused_snapshot((malformed,))
    with pytest.raises(q.NoEligibleRevisionOverwriteTargetsError):
        q.inject_revision_overwrite(
            clean,
            (malformed,),
            q.RevisionOverwriteInjectionConfig(severity="low", seed=0),
        )


def test_nonmonotonic_declared_revision_order_is_rejected() -> None:
    historical, later = focused_history()
    contradictory = later.model_copy(
        update={"filed_on": date(2024, 4, 10), "available_on": date(2024, 4, 10)}
    )
    with pytest.raises(q.AmbiguousRevisionHistoryError):
        focused_snapshot((historical, contradictory))


def test_same_day_revision_cannot_be_an_earlier_state_overwrite() -> None:
    records = focused_history(
        historical_filed_on=date(2024, 4, 15),
        later_filed_on=date(2024, 4, 15),
    )
    clean = focused_snapshot(records)
    assert clean.records == (records[1],)
    with pytest.raises(q.NoEligibleRevisionOverwriteTargetsError):
        q.inject_revision_overwrite(
            clean,
            records,
            q.RevisionOverwriteInjectionConfig(severity="low", seed=0),
        )


def test_duplicate_declared_sequence_is_rejected() -> None:
    historical, _later = focused_history()
    duplicate = historical.model_copy(
        update={
            "record_id": q.source_record_id(
                source_name="revision-focused-fixture",
                source_locator="other-locator",
                source_row_key="FOCUSED-Q1#r1",
            ),
            "value": Decimal("125"),
            "filed_on": date(2024, 6, 1),
            "available_on": date(2024, 6, 1),
        }
    )
    with pytest.raises(q.AmbiguousRevisionHistoryError):
        focused_snapshot((historical, duplicate))


def test_input_order_and_repeated_runs_preserve_all_artifacts() -> None:
    records = focused_history()
    clean = focused_snapshot(records)
    reversed_clean = focused_snapshot(tuple(reversed(records)))
    config = q.RevisionOverwriteInjectionConfig(severity="high", seed=99)
    first = q.inject_revision_overwrite(clean, records, config)
    second = q.inject_revision_overwrite(reversed_clean, tuple(reversed(records)), config)
    repeated = q.inject_revision_overwrite(clean, records, config)
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(repeated)


def test_target_count_uses_decimal_ceiling_minimum_one_and_cap() -> None:
    assert (
        q.revision_overwrite_target_count(
            eligible_count=1, target_fraction=Decimal("0.02"), max_targets=100
        )
        == 1
    )
    assert (
        q.revision_overwrite_target_count(
            eligible_count=101, target_fraction=Decimal("0.10"), max_targets=7
        )
        == 7
    )
    assert (
        q.revision_overwrite_target_count(
            eligible_count=0, target_fraction=Decimal("0.10"), max_targets=7
        )
        == 0
    )


def test_modified_record_and_fault_identities_are_dedicated_and_deterministic() -> None:
    case = reviewed_revision_overwrite_case()
    entry = case.manifest.entries[0]
    assert entry.corrupted_record.record_id.startswith("rec_")
    assert entry.corrupted_record.record_id != entry.mutation.later_record_id
    assert entry.fault_id.startswith("fault_")
    assert q.revision_overwrite_manifest_identity_matches(case.manifest)
