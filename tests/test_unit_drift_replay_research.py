"""Private Unit Drift replay and controlled aggregate-value sensitivity."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

import quantcheck as q
from tests.unit_drift_support import (
    UNIT_DRIFT_AS_OF,
    reviewed_unit_drift_case,
    unit_drift_records,
    unit_drift_snapshot,
)


def test_replay_restores_exact_clean_bytes_identity_hash_and_records() -> None:
    case = reviewed_unit_drift_case()
    assert case.repaired.snapshot_id == case.clean.snapshot_id
    assert q.canonical_sha256(case.repaired) == q.canonical_sha256(case.clean)
    assert q.canonical_json_bytes(case.repaired) == q.canonical_json_bytes(case.clean)


def test_replay_is_idempotent_for_already_restored_snapshot() -> None:
    case = reviewed_unit_drift_case()
    again = q.manifest_assisted_exact_unit_drift_replay(case.repaired, case.manifest)
    assert again is case.repaired
    assert q.canonical_json_bytes(again) == q.canonical_json_bytes(case.clean)


def test_replay_research_and_scoring_do_not_mutate_inputs() -> None:
    case = reviewed_unit_drift_case()
    before = tuple(
        q.canonical_json_bytes(model)
        for model in (case.clean, case.corrupted, case.manifest, case.audit_report)
    )
    q.manifest_assisted_exact_unit_drift_replay(case.corrupted, case.manifest)
    q.compare_unit_drift_research(
        case.clean,
        case.corrupted,
        case.repaired,
        case.research_config,
    )
    q.score_unit_drift(case.audit_report, case.manifest)
    after = tuple(
        q.canonical_json_bytes(model)
        for model in (case.clean, case.corrupted, case.manifest, case.audit_report)
    )
    assert after == before


def test_replay_preserves_every_unrelated_record_byte_for_byte() -> None:
    case = reviewed_unit_drift_case()
    targets = {entry.corrupted_record.record_id for entry in case.manifest.entries}
    before = {
        record.record_id: q.canonical_json_bytes(record)
        for record in case.corrupted.records
        if record.record_id not in targets
    }
    after = {
        record.record_id: q.canonical_json_bytes(record)
        for record in case.repaired.records
        if record.record_id in before
    }
    assert after == before


def test_replay_rejects_missing_changed_or_forged_corrupted_artifact() -> None:
    case = reviewed_unit_drift_case()
    target_id = case.manifest.entries[0].corrupted_record.record_id
    missing_records = tuple(
        record for record in case.corrupted.records if record.record_id != target_id
    )
    missing = unit_drift_snapshot(
        missing_records,
        dataset_name=case.corrupted.dataset_name,
    )
    with pytest.raises(q.UnitDriftReplayError, match="neither"):
        q.manifest_assisted_exact_unit_drift_replay(missing, case.manifest)

    target = case.manifest.entries[0].corrupted_record
    changed_target = target.model_copy(update={"value": target.value + 1})
    changed_records = tuple(
        changed_target if record.record_id == target_id else record
        for record in case.corrupted.records
    )
    changed = unit_drift_snapshot(
        changed_records,
        dataset_name=case.corrupted.dataset_name,
    )
    with pytest.raises(q.UnitDriftReplayError, match="neither"):
        q.manifest_assisted_exact_unit_drift_replay(changed, case.manifest)

    forged = case.corrupted.model_copy(update={"snapshot_id": "snap_0000000000000000"})
    with pytest.raises(q.UnitDriftReplayError, match="identity"):
        q.manifest_assisted_exact_unit_drift_replay(forged, case.manifest)


def test_replay_rejects_manifest_with_recomputed_identity_but_wrong_profile() -> None:
    case = reviewed_unit_drift_case()
    body = {
        name: getattr(case.manifest, name)
        for name in q.UnitDriftManifest.model_fields
        if name != "manifest_id"
    }
    body["scale_factor"] = Decimal("100")
    forged = case.manifest.model_copy(
        update={
            "scale_factor": Decimal("100"),
            "manifest_id": q.unit_drift_manifest_id(manifest_body=body),
        }
    )
    with pytest.raises(q.UnitDriftManifestIntegrityError, match="severity profile"):
        q.manifest_assisted_exact_unit_drift_replay(case.corrupted, forged)


def test_same_pure_aggregate_calculation_is_used_for_all_three_snapshots() -> None:
    case = reviewed_unit_drift_case()
    expected = tuple(
        q.aggregate_value_v0_1(snapshot, case.research_config)
        for snapshot in (case.clean, case.corrupted, case.repaired)
    )
    assert expected == (case.impact.clean, case.impact.corrupted, case.impact.repaired)


def test_controlled_aggregate_changes_and_then_restores_exactly() -> None:
    impact = reviewed_unit_drift_case().impact
    assert impact.clean.aggregate_value == Decimal("600")
    assert impact.corrupted.aggregate_value == Decimal("120480")
    assert impact.repaired.aggregate_value == Decimal("600")
    assert impact.signed_change == Decimal("119880")
    assert impact.absolute_change == Decimal("119880")
    assert impact.relative_change == Decimal("199.8")
    assert impact.clean.record_count == impact.corrupted.record_count == 5
    assert impact.changed
    assert impact.exact_restoration


def test_aggregate_uses_inclusive_end_of_day_and_one_exact_group() -> None:
    case = reviewed_unit_drift_case()
    first = min(case.clean.records, key=lambda record: record.period_end)
    config = q.UnitDriftResearchConfig(
        comparable_series_key=case.research_config.comparable_series_key,
        research_as_of_date=first.available_on,
    )
    result = q.aggregate_value_v0_1(case.clean, config)
    assert result.record_count == 1
    assert result.included_record_ids == (first.record_id,)

    unrelated = unit_drift_records(values=("999",), entity_id="OTHER", source_key="research-other")[
        0
    ]
    expanded = unit_drift_snapshot(
        case.clean.records + (unrelated,), dataset_name=case.clean.dataset_name
    )
    expanded_result = q.aggregate_value_v0_1(expanded, case.research_config)
    assert expanded_result.aggregate_value == case.impact.clean.aggregate_value
    assert unrelated.record_id not in expanded_result.included_record_ids


def test_zero_clean_baseline_makes_relative_change_explicitly_null() -> None:
    clean = unit_drift_snapshot(unit_drift_records(values=("-100", "100", "0")))
    negative = next(record for record in clean.records if record.value == Decimal("-100"))
    changed_record = negative.model_copy(
        update={"record_id": "rec_ffffffffffffffff", "value": Decimal("0")}
    )
    corrupted_records = tuple(
        changed_record if record.record_id == negative.record_id else record
        for record in clean.records
    )
    corrupted = unit_drift_snapshot(corrupted_records)
    config = q.UnitDriftResearchConfig(
        comparable_series_key=q.comparable_series_key(negative),
        research_as_of_date=UNIT_DRIFT_AS_OF,
    )
    impact = q.compare_unit_drift_research(clean, corrupted, clean, config)
    assert impact.clean.aggregate_value == 0
    assert impact.corrupted.aggregate_value == Decimal("100")
    assert impact.relative_change is None
    assert impact.changed
    assert impact.exact_restoration


def test_research_results_and_impact_are_stable_and_order_independent() -> None:
    first = reviewed_unit_drift_case().impact
    second = reviewed_unit_drift_case().impact
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)

    case = reviewed_unit_drift_case()
    reordered = q.DatasetSnapshot(
        snapshot_id=case.corrupted.snapshot_id,
        dataset_name=case.corrupted.dataset_name,
        as_of_date=case.corrupted.as_of_date,
        records=tuple(reversed(case.corrupted.records)),
    )
    assert q.canonical_json_bytes(
        q.aggregate_value_v0_1(reordered, case.research_config)
    ) == q.canonical_json_bytes(case.impact.corrupted)


def test_research_rejects_future_cutoff_and_incomparable_snapshots() -> None:
    case = reviewed_unit_drift_case()
    future = q.UnitDriftResearchConfig(
        comparable_series_key=case.research_config.comparable_series_key,
        research_as_of_date=date(2025, 1, 1),
    )
    with pytest.raises(q.UnitDriftResearchError, match="must not follow"):
        q.aggregate_value_v0_1(case.clean, future)

    mismatched = unit_drift_snapshot(
        case.repaired.records,
        dataset_name="other-dataset",
    )
    with pytest.raises(q.UnitDriftResearchError, match="must share"):
        q.compare_unit_drift_research(
            case.clean,
            case.corrupted,
            mismatched,
            case.research_config,
        )
