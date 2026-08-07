"""Controlled availability impact and private exact replay."""

from __future__ import annotations

from datetime import date

import pytest

import quantcheck as q
from tests.lookahead_support import REVIEWED_RESEARCH_DATE, reviewed_lookahead_case


def test_same_pure_calculation_is_used_for_all_three_snapshots() -> None:
    case = reviewed_lookahead_case()
    expected = tuple(
        q.availability_count_v0_1(
            snapshot,
            research_as_of_date=REVIEWED_RESEARCH_DATE,
        )
        for snapshot in (case.clean, case.corrupted, case.repaired)
    )
    assert expected == (case.impact.clean, case.impact.corrupted, case.impact.repaired)


def test_reviewed_controlled_count_changes_and_then_restores_exactly() -> None:
    impact = reviewed_lookahead_case().impact
    assert impact.clean.availability_count == 0
    assert impact.corrupted.availability_count == 1
    assert impact.repaired.availability_count == 0
    assert impact.corruption_delta == 1
    assert impact.changed
    assert impact.exact_restoration


def test_availability_count_uses_inclusive_end_of_day_boundary() -> None:
    case = reviewed_lookahead_case()
    boundary = case.manifest.entries[0].corrupted_record.available_on
    result = q.availability_count_v0_1(case.corrupted, research_as_of_date=boundary)
    assert case.manifest.entries[0].corrupted_record.record_id in result.available_record_ids


def test_research_results_and_impact_are_deterministic() -> None:
    first = reviewed_lookahead_case().impact
    second = reviewed_lookahead_case().impact
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)
    assert q.research_result_identity_matches(first.clean)
    assert q.research_impact_identity_matches(first)


def test_snapshot_record_order_does_not_change_research_output() -> None:
    case = reviewed_lookahead_case()
    reordered = q.DatasetSnapshot(
        snapshot_id=case.corrupted.snapshot_id,
        dataset_name=case.corrupted.dataset_name,
        as_of_date=case.corrupted.as_of_date,
        records=tuple(reversed(case.corrupted.records)),
    )
    assert q.canonical_json_bytes(
        q.availability_count_v0_1(reordered, research_as_of_date=REVIEWED_RESEARCH_DATE)
    ) == q.canonical_json_bytes(case.impact.corrupted)


def test_replay_restores_exact_clean_identity_hash_and_records() -> None:
    case = reviewed_lookahead_case()
    assert case.repaired.snapshot_id == case.clean.snapshot_id
    assert q.canonical_sha256(case.repaired) == q.canonical_sha256(case.clean)
    assert q.canonical_json_bytes(case.repaired) == q.canonical_json_bytes(case.clean)


def test_replay_is_idempotent_for_already_repaired_snapshot() -> None:
    case = reviewed_lookahead_case()
    again = q.manifest_assisted_exact_replay(case.repaired, case.manifest)
    assert again is case.repaired
    assert q.canonical_json_bytes(again) == q.canonical_json_bytes(case.clean)


def test_replay_and_research_do_not_mutate_any_input() -> None:
    case = reviewed_lookahead_case()
    clean_before = q.canonical_json_bytes(case.clean)
    corrupted_before = q.canonical_json_bytes(case.corrupted)
    manifest_before = q.canonical_json_bytes(case.manifest)
    q.manifest_assisted_exact_replay(case.corrupted, case.manifest)
    q.compare_lookahead_research(
        case.clean,
        case.corrupted,
        case.repaired,
        research_as_of_date=REVIEWED_RESEARCH_DATE,
    )
    assert q.canonical_json_bytes(case.clean) == clean_before
    assert q.canonical_json_bytes(case.corrupted) == corrupted_before
    assert q.canonical_json_bytes(case.manifest) == manifest_before


def test_replay_preserves_every_unrelated_record() -> None:
    case = reviewed_lookahead_case()
    targeted = {entry.corrupted_record.record_id for entry in case.manifest.entries}
    before = {
        record.record_id: q.canonical_json_bytes(record)
        for record in case.corrupted.records
        if record.record_id not in targeted
    }
    after = {
        record.record_id: q.canonical_json_bytes(record)
        for record in case.repaired.records
        if record.record_id in before
    }
    assert after == before


def test_forged_manifest_selection_digest_is_rejected_even_with_recomputed_id() -> None:
    case = reviewed_lookahead_case()
    entry = case.manifest.entries[0].model_copy(update={"selection_digest": "0" * 64})
    body = {
        name: getattr(case.manifest, name)
        for name in q.FaultManifest.model_fields
        if name != "manifest_id"
    }
    body["entries"] = (entry,)
    forged = q.FaultManifest.model_validate(
        {
            "manifest_id": q.fault_manifest_id(manifest_body=body),
            **body,
        }
    )
    with pytest.raises(q.LookAheadManifestIntegrityError, match="selection digest"):
        q.manifest_assisted_exact_replay(case.corrupted, forged)


def test_inconsistent_corrupted_snapshot_is_rejected() -> None:
    case = reviewed_lookahead_case()
    changed = case.corrupted.records[0].model_copy(
        update={"value": case.corrupted.records[0].value + 1}
    )
    records = (changed,) + case.corrupted.records[1:]
    inconsistent = q.DatasetSnapshot(
        snapshot_id=q.dataset_snapshot_id(
            dataset_name=case.corrupted.dataset_name,
            as_of_date=case.corrupted.as_of_date,
            records=records,
        ),
        dataset_name=case.corrupted.dataset_name,
        as_of_date=case.corrupted.as_of_date,
        records=records,
    )
    with pytest.raises(q.LookAheadReplayError, match="neither"):
        q.manifest_assisted_exact_replay(inconsistent, case.manifest)


def test_research_rejects_cutoff_after_source_horizon() -> None:
    case = reviewed_lookahead_case()
    with pytest.raises(q.LookAheadResearchError, match="must not follow"):
        q.availability_count_v0_1(
            case.clean,
            research_as_of_date=date(2025, 1, 1),
        )


def test_comparison_rejects_mismatched_dataset_or_source_horizon() -> None:
    case = reviewed_lookahead_case()
    mismatched = q.DatasetSnapshot(
        snapshot_id=q.dataset_snapshot_id(
            dataset_name="other",
            as_of_date=case.repaired.as_of_date,
            records=case.repaired.records,
        ),
        dataset_name="other",
        as_of_date=case.repaired.as_of_date,
        records=case.repaired.records,
    )
    with pytest.raises(q.LookAheadResearchError, match="must share"):
        q.compare_lookahead_research(
            case.clean,
            case.corrupted,
            mismatched,
            research_as_of_date=REVIEWED_RESEARCH_DATE,
        )
