"""Private Duplicate replay and controlled occurrence/double-counting sensitivity."""

from __future__ import annotations

from decimal import Decimal

import pytest

import quantcheck as q
from tests.duplicate_support import duplicate_snapshot, reviewed_duplicate_case


def test_replay_restores_exact_clean_bytes_identity_hash_and_records() -> None:
    case = reviewed_duplicate_case()
    assert case.repaired.snapshot_id == case.clean.snapshot_id
    assert q.canonical_sha256(case.repaired) == q.canonical_sha256(case.clean)
    assert q.canonical_json_bytes(case.repaired) == q.canonical_json_bytes(case.clean)


def test_replay_is_idempotent_for_already_restored_snapshot() -> None:
    case = reviewed_duplicate_case()
    again = q.manifest_assisted_exact_duplicate_replay(case.repaired, case.manifest)
    assert again is case.repaired
    assert q.canonical_json_bytes(again) == q.canonical_json_bytes(case.clean)


def test_replay_research_and_scoring_do_not_mutate_inputs() -> None:
    case = reviewed_duplicate_case()
    before = tuple(
        q.canonical_json_bytes(model)
        for model in (case.clean, case.corrupted, case.manifest, case.audit_report)
    )
    q.manifest_assisted_exact_duplicate_replay(case.corrupted, case.manifest)
    q.compare_duplicate_record_count(case.clean, case.corrupted, case.repaired)
    q.score_duplicate_observations(case.audit_report, case.manifest)
    after = tuple(
        q.canonical_json_bytes(model)
        for model in (case.clean, case.corrupted, case.manifest, case.audit_report)
    )
    assert after == before


def test_replay_preserves_originals_and_legitimate_natural_duplicate_group() -> None:
    case = reviewed_duplicate_case()
    created_ids = {entry.created_record.record_id for entry in case.manifest.entries}
    before = {
        record.record_id: q.canonical_json_bytes(record)
        for record in case.corrupted.records
        if record.record_id not in created_ids
    }
    after = {record.record_id: q.canonical_json_bytes(record) for record in case.repaired.records}
    assert after == before
    # The Milestone 2 fixture's natural duplicate pair is untouched by injection
    # and must survive replay exactly.
    assert "rec_521e565b7cad2f3b" in after
    assert "rec_a3eb29080d7921dc" in after


def test_replay_rejects_missing_changed_or_forged_corrupted_artifact() -> None:
    case = reviewed_duplicate_case()
    target_id = case.manifest.entries[0].created_record.record_id
    missing_records = tuple(
        record for record in case.corrupted.records if record.record_id != target_id
    )
    missing = duplicate_snapshot(
        missing_records,
        dataset_name=case.corrupted.dataset_name,
        as_of_date=case.corrupted.as_of_date,
    )
    with pytest.raises(q.DuplicateReplayError, match="neither"):
        q.manifest_assisted_exact_duplicate_replay(missing, case.manifest)

    target = case.manifest.entries[0].created_record
    changed_target = target.model_copy(update={"value": target.value + 1})
    changed_records = tuple(
        changed_target if record.record_id == target_id else record
        for record in case.corrupted.records
    )
    changed = duplicate_snapshot(
        changed_records,
        dataset_name=case.corrupted.dataset_name,
        as_of_date=case.corrupted.as_of_date,
    )
    with pytest.raises(q.DuplicateReplayError, match="neither"):
        q.manifest_assisted_exact_duplicate_replay(changed, case.manifest)

    forged = case.corrupted.model_copy(update={"snapshot_id": "snap_0000000000000000"})
    with pytest.raises(q.DuplicateReplayError, match="identity"):
        q.manifest_assisted_exact_duplicate_replay(forged, case.manifest)


def test_replay_rejects_manifest_with_recomputed_identity_but_wrong_profile() -> None:
    case = reviewed_duplicate_case()
    body = {
        name: getattr(case.manifest, name)
        for name in q.DuplicateManifest.model_fields
        if name != "manifest_id"
    }
    body["target_fraction"] = Decimal("0.99")
    forged = case.manifest.model_copy(
        update={
            "target_fraction": Decimal("0.99"),
            "manifest_id": q.duplicate_manifest_id(manifest_body=body),
        }
    )
    with pytest.raises(q.DuplicateManifestIntegrityError, match="severity profile"):
        q.manifest_assisted_exact_duplicate_replay(case.corrupted, forged)


def test_record_count_v0_1_matches_manual_calculation() -> None:
    case = reviewed_duplicate_case()
    result = q.record_count_v0_1(case.clean)
    assert result.total_record_count == len(case.clean.records)
    groups = q.build_duplicate_groups(case.clean.records, as_of_date=case.clean.as_of_date)
    assert result.duplicate_group_count == sum(1 for g in groups.values() if len(g.records) >= 2)


def test_controlled_record_count_changes_by_target_count_and_then_restores() -> None:
    case = reviewed_duplicate_case()
    impact = case.record_count_impact
    target_count = case.manifest.target_count
    assert impact.clean.total_record_count + target_count == impact.corrupted.total_record_count
    assert impact.corrupted.duplicate_group_count == (
        impact.clean.duplicate_group_count + target_count
    )
    assert impact.total_count_delta == target_count
    assert impact.duplicate_group_count_delta == target_count
    assert impact.changed
    assert impact.exact_restoration
    assert impact.repaired.total_record_count == impact.clean.total_record_count
    assert impact.repaired.duplicate_group_count == impact.clean.duplicate_group_count


def test_same_pure_double_counting_calculation_applies_to_all_three_snapshots() -> None:
    """Reuses the existing generic aggregate_value_v0_1 unmodified per the
    authoritative instruction to reuse rather than duplicate the calculation."""
    case = reviewed_duplicate_case()
    entry = case.manifest.entries[0]
    key = q.comparable_series_key(entry.original_record)
    config = q.UnitDriftResearchConfig(
        comparable_series_key=key,
        research_as_of_date=case.clean.as_of_date,
    )
    clean_result = q.aggregate_value_v0_1(case.clean, config)
    corrupted_result = q.aggregate_value_v0_1(case.corrupted, config)
    repaired_result = q.aggregate_value_v0_1(case.repaired, config)
    assert (
        corrupted_result.aggregate_value
        == clean_result.aggregate_value + entry.original_record.value
    )
    assert repaired_result.aggregate_value == clean_result.aggregate_value

    impact = q.compare_unit_drift_research(case.clean, case.corrupted, case.repaired, config)
    assert impact.changed
    assert impact.exact_restoration
    assert impact.signed_change == entry.original_record.value


def test_research_results_and_impact_are_stable_and_order_independent() -> None:
    first = reviewed_duplicate_case().record_count_impact
    second = reviewed_duplicate_case().record_count_impact
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)

    case = reviewed_duplicate_case()
    reordered = q.DatasetSnapshot(
        snapshot_id=case.corrupted.snapshot_id,
        dataset_name=case.corrupted.dataset_name,
        as_of_date=case.corrupted.as_of_date,
        records=tuple(reversed(case.corrupted.records)),
    )
    assert q.canonical_json_bytes(q.record_count_v0_1(reordered)) == q.canonical_json_bytes(
        case.record_count_impact.corrupted
    )


def test_research_rejects_forged_identity_and_incomparable_snapshots() -> None:
    case = reviewed_duplicate_case()
    forged = case.clean.model_copy(update={"snapshot_id": "snap_0000000000000000"})
    with pytest.raises(q.DuplicateResearchError, match="identity"):
        q.record_count_v0_1(forged)

    mismatched = duplicate_snapshot(
        case.repaired.records,
        dataset_name="other-dataset",
        as_of_date=case.repaired.as_of_date,
    )
    with pytest.raises(q.DuplicateResearchError, match="must share"):
        q.compare_duplicate_record_count(case.clean, case.corrupted, mismatched)
