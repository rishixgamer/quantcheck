"""Unit Drift comparable series, eligibility, deterministic selection, and injection."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

import quantcheck as q
from tests.support import financial_fact
from tests.unit_drift_support import (
    UNIT_DRIFT_AS_OF,
    reviewed_unit_drift_case,
    unit_drift_records,
    unit_drift_snapshot,
)


@pytest.mark.parametrize(
    ("eligible", "fraction", "cap", "expected"),
    [
        (0, Decimal("0.05"), 100, 0),
        (1, Decimal("0.02"), 100, 1),
        (20, Decimal("0.05"), 100, 1),
        (21, Decimal("0.05"), 100, 2),
        (1000, Decimal("0.10"), 3, 3),
    ],
)
def test_target_count_uses_decimal_ceiling_minimum_one_and_cap(
    eligible: int,
    fraction: Decimal,
    cap: int,
    expected: int,
) -> None:
    assert (
        q.unit_drift_target_count(
            eligible_count=eligible,
            target_fraction=fraction,
            max_targets=cap,
        )
        == expected
    )


def test_exact_comparable_key_separates_every_supported_economic_context() -> None:
    base = unit_drift_records(values=("1",))[0]
    variants = (
        base.model_copy(update={"entity_id": "OTHER"}),
        base.model_copy(update={"concept_namespace": "ifrs-full"}),
        base.model_copy(update={"concept": "Assets"}),
        base.model_copy(update={"unit": "EUR"}),
        base.model_copy(update={"dimensions": (q.Dimension(axis="Segment", member="Cloud"),)}),
        financial_fact(
            record_id="rec_aaaaaaaaaaaaaaaa",
            entity_id=base.entity_id,
            concept_namespace=base.concept_namespace,
            concept=base.concept,
            unit=base.unit,
            dimensions=base.dimensions,
            period_type="duration",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 30),
        ),
    )
    base_key = q.comparable_series_key(base)
    assert all(q.comparable_series_key(variant) != base_key for variant in variants)


def test_duration_period_length_is_part_of_exact_comparable_key() -> None:
    records = unit_drift_records(period_type="duration", values=("1",))
    thirty_day = records[0]
    thirty_one_day = thirty_day.model_copy(
        update={"period_start": thirty_day.period_start - timedelta(days=1)}  # type: ignore[operator]
    )
    assert q.comparable_series_key(thirty_day).period_length_days == 30
    assert q.comparable_series_key(thirty_one_day).period_length_days == 31
    assert q.comparable_series_key(thirty_day) != q.comparable_series_key(thirty_one_day)


def test_eligibility_requires_three_visible_chronological_observations() -> None:
    two = unit_drift_snapshot(unit_drift_records(values=("1", "2")))
    with pytest.raises(q.NoEligibleUnitDriftTargetsError):
        q.inject_unit_drift(two, q.UnitDriftInjectionConfig(severity="low", seed=1))

    boundary = date(2024, 5, 29)
    records = unit_drift_records(values=("1", "2", "3"))
    clean = q.build_dataset_snapshot(records, dataset_name="boundary", as_of_date=boundary)
    assert len(clean.records) == 3
    _corrupted, manifest = q.inject_unit_drift(
        clean, q.UnitDriftInjectionConfig(severity="low", seed=1)
    )
    assert manifest.eligible_record_count == 3


def test_zero_is_ineligible_but_negative_nonzero_values_are_eligible() -> None:
    clean = unit_drift_snapshot(unit_drift_records(values=("-100", "0", "-120", "-130")))
    observations = q.build_comparable_observations(
        clean.records,
        as_of_date=clean.as_of_date,
    )
    values_by_id = {record.record_id: record.value for record in clean.records}
    assert {values_by_id[record_id] for record_id in observations} == {
        Decimal("-100"),
        Decimal("-120"),
        Decimal("-130"),
    }


def test_ambiguous_duplicate_chronology_is_excluded_not_guessed() -> None:
    records = list(unit_drift_records(values=("100", "110", "120")))
    duplicate = records[1].model_copy(
        update={
            "record_id": "rec_ffffffffffffffff",
            "source": records[1].source.model_copy(update={"source_row_key": "duplicate"}),
        }
    )
    clean = unit_drift_snapshot(tuple(records + [duplicate]))
    assert q.build_comparable_observations(clean.records, as_of_date=clean.as_of_date) == {}
    with pytest.raises(q.NoEligibleUnitDriftTargetsError):
        q.inject_unit_drift(clean, q.UnitDriftInjectionConfig(severity="low", seed=1))


def test_repeated_seed_produces_byte_identical_snapshot_and_manifest() -> None:
    first = reviewed_unit_drift_case(seed=6)
    second = reviewed_unit_drift_case(seed=6)
    assert q.canonical_json_bytes(first.corrupted) == q.canonical_json_bytes(second.corrupted)
    assert q.canonical_json_bytes(first.manifest) == q.canonical_json_bytes(second.manifest)


def test_seed_changes_selection_without_randomness_when_candidates_exist() -> None:
    selected = {
        reviewed_unit_drift_case(seed=seed).manifest.entries[0].original_record.record_id
        for seed in range(12)
    }
    assert len(selected) > 1


def test_reversing_clean_records_does_not_change_selection_or_artifacts() -> None:
    case = reviewed_unit_drift_case()
    reversed_clean = q.DatasetSnapshot(
        snapshot_id=case.clean.snapshot_id,
        dataset_name=case.clean.dataset_name,
        as_of_date=case.clean.as_of_date,
        records=tuple(reversed(case.clean.records)),
    )
    corrupted, manifest = q.inject_unit_drift(reversed_clean, case.config)
    assert q.canonical_json_bytes(corrupted) == q.canonical_json_bytes(case.corrupted)
    assert q.canonical_json_bytes(manifest) == q.canonical_json_bytes(case.manifest)


def test_adding_an_unrelated_ineligible_record_does_not_change_selected_target() -> None:
    case = reviewed_unit_drift_case()
    unrelated = unit_drift_records(
        values=("999",),
        entity_id="UNRELATED",
        source_key="unrelated",
    )[0]
    expanded = unit_drift_snapshot(
        case.clean.records + (unrelated,),
        dataset_name=case.clean.dataset_name,
    )
    _corrupted, manifest = q.inject_unit_drift(expanded, case.config)
    assert manifest.entries[0].original_record.record_id == (
        case.manifest.entries[0].original_record.record_id
    )
    assert manifest.entries[0].selection_digest == case.manifest.entries[0].selection_digest


def test_injection_changes_only_record_id_and_value_and_keeps_unit_unchanged() -> None:
    entry = reviewed_unit_drift_case().manifest.entries[0]
    changed = {
        name
        for name in q.FinancialFact.model_fields
        if getattr(entry.original_record, name) != getattr(entry.corrupted_record, name)
    }
    assert changed == {"record_id", "value"}
    assert entry.corrupted_record.value == entry.original_record.value * Decimal("1000")
    assert entry.corrupted_record.unit == entry.original_record.unit == "USD"


def test_unselected_records_are_byte_identical_and_clean_input_is_not_mutated() -> None:
    case = reviewed_unit_drift_case()
    before = q.canonical_json_bytes(case.clean)
    q.inject_unit_drift(case.clean, case.config)
    assert q.canonical_json_bytes(case.clean) == before
    selected = {entry.original_record.record_id for entry in case.manifest.entries}
    replacements = {entry.corrupted_record.record_id for entry in case.manifest.entries}
    clean_unselected = [record for record in case.clean.records if record.record_id not in selected]
    corrupted_unselected = [
        record for record in case.corrupted.records if record.record_id not in replacements
    ]
    assert q.canonical_json_bytes(clean_unselected) == q.canonical_json_bytes(corrupted_unselected)


def test_invalid_snapshot_identity_and_unavailable_record_are_rejected() -> None:
    case = reviewed_unit_drift_case()
    forged = case.clean.model_copy(update={"snapshot_id": "snap_0000000000000000"})
    with pytest.raises(q.UnitDriftInjectionError, match="identity"):
        q.inject_unit_drift(forged, case.config)

    future_record = case.clean.records[0].model_copy(
        update={"available_on": UNIT_DRIFT_AS_OF + timedelta(days=1)}
    )
    invalid = unit_drift_snapshot(
        (future_record,) + case.clean.records[1:],
        dataset_name=case.clean.dataset_name,
    )
    with pytest.raises(q.UnitDriftInjectionError, match="unavailable"):
        q.inject_unit_drift(invalid, case.config)


def test_manifest_validation_rejects_recomputed_id_with_forged_selection_digest() -> None:
    case = reviewed_unit_drift_case()
    forged_entry = case.manifest.entries[0].model_copy(update={"selection_digest": "0" * 64})
    body = {
        name: getattr(case.manifest, name)
        for name in q.UnitDriftManifest.model_fields
        if name != "manifest_id"
    }
    body["entries"] = (forged_entry,)
    forged = q.UnitDriftManifest.model_validate(
        {
            "manifest_id": q.unit_drift_manifest_id(manifest_body=body),
            **body,
        }
    )
    with pytest.raises(q.UnitDriftManifestIntegrityError, match="selection digest"):
        q.validate_unit_drift_manifest(forged)


def test_manifest_records_complete_reversible_private_evidence() -> None:
    case = reviewed_unit_drift_case()
    entry = case.manifest.entries[0]
    assert entry.original_record.value == entry.mutation.original_value
    assert entry.corrupted_record.value == entry.mutation.corrupted_value
    assert entry.mutation.scale_factor == Decimal("1000")
    assert entry.series_record_ids
    assert entry.eligible_neighbor_record_ids
    assert entry.selection_digest
    assert case.manifest.clean_snapshot_hash == q.canonical_sha256(case.clean)
    assert case.manifest.corrupted_snapshot_hash == q.canonical_sha256(case.corrupted)
