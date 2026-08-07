"""Duplicate fingerprint eligibility, deterministic selection, and injection."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

import quantcheck as q
from tests.duplicate_support import (
    duplicate_record,
    duplicate_snapshot,
    reviewed_duplicate_case,
)


def test_eligibility_excludes_a_preexisting_natural_duplicate_group() -> None:
    a = duplicate_record("row-a")
    b = duplicate_record("row-b")  # identical fingerprint fields, distinct source row key
    clean = duplicate_snapshot((a, b))
    groups = q.build_duplicate_groups(clean.records, as_of_date=clean.as_of_date)
    assert len(groups) == 1
    with pytest.raises(q.NoEligibleDuplicateTargetsError):
        q.inject_duplicate_observations(clean, q.DuplicateInjectionConfig(severity="low", seed=1))


def test_eligibility_includes_singleton_records_only() -> None:
    a = duplicate_record("row-a")
    b = duplicate_record("row-b")  # natural duplicate of a
    c = duplicate_record("row-c", concept="Assets")  # singleton
    clean = duplicate_snapshot((a, b, c))
    _corrupted, manifest = q.inject_duplicate_observations(
        clean, q.DuplicateInjectionConfig(severity="low", seed=1)
    )
    assert manifest.eligible_record_count == 1
    assert manifest.eligible_record_ids == (c.record_id,)


def test_only_end_of_day_visible_records_participate_in_grouping() -> None:
    later = date(2024, 5, 2)
    a = duplicate_record("row-a", available_on=later, filed_on=later)
    b = duplicate_record("row-b", available_on=later, filed_on=later)
    before_visible = q.build_duplicate_groups((a, b), as_of_date=date(2024, 5, 1))
    assert before_visible == {}
    after_visible = q.build_duplicate_groups((a, b), as_of_date=later)
    assert len(after_visible) == 1
    assert len(next(iter(after_visible.values())).records) == 2


def test_repeated_seed_produces_byte_identical_snapshot_and_manifest() -> None:
    first = reviewed_duplicate_case(seed=7)
    second = reviewed_duplicate_case(seed=7)
    assert q.canonical_json_bytes(first.corrupted) == q.canonical_json_bytes(second.corrupted)
    assert q.canonical_json_bytes(first.manifest) == q.canonical_json_bytes(second.manifest)


def test_seed_changes_selection_without_randomness_when_candidates_exist() -> None:
    selected = {
        reviewed_duplicate_case(seed=seed).manifest.entries[0].original_record.record_id
        for seed in range(12)
    }
    assert len(selected) > 1


def test_reversing_clean_records_does_not_change_selection_or_artifacts() -> None:
    case = reviewed_duplicate_case()
    reversed_clean = q.DatasetSnapshot(
        snapshot_id=case.clean.snapshot_id,
        dataset_name=case.clean.dataset_name,
        as_of_date=case.clean.as_of_date,
        records=tuple(reversed(case.clean.records)),
    )
    corrupted, manifest = q.inject_duplicate_observations(reversed_clean, case.config)
    assert q.canonical_json_bytes(corrupted) == q.canonical_json_bytes(case.corrupted)
    assert q.canonical_json_bytes(manifest) == q.canonical_json_bytes(case.manifest)


def test_adding_an_unrelated_natural_duplicate_group_does_not_change_selected_targets() -> None:
    case = reviewed_duplicate_case()
    unrelated_a = duplicate_record(
        "unrelated-a", entity_id="UNRELATED", available_on=case.clean.as_of_date
    )
    unrelated_b = duplicate_record(
        "unrelated-b", entity_id="UNRELATED", available_on=case.clean.as_of_date
    )
    expanded = duplicate_snapshot(
        case.clean.records + (unrelated_a, unrelated_b),
        dataset_name=case.clean.dataset_name,
        as_of_date=case.clean.as_of_date,
    )
    _corrupted, manifest = q.inject_duplicate_observations(expanded, case.config)
    assert manifest.entries[0].original_record.record_id == (
        case.manifest.entries[0].original_record.record_id
    )
    assert manifest.entries[0].selection_digest == case.manifest.entries[0].selection_digest
    assert manifest.eligible_record_count == case.manifest.eligible_record_count


def test_injection_changes_only_record_id() -> None:
    entry = reviewed_duplicate_case().manifest.entries[0]
    changed = {
        name
        for name in q.FinancialFact.model_fields
        if getattr(entry.original_record, name) != getattr(entry.created_record, name)
    }
    assert changed == {"record_id"}


def test_unselected_records_are_byte_identical_and_clean_input_is_not_mutated() -> None:
    case = reviewed_duplicate_case()
    before = q.canonical_json_bytes(case.clean)
    q.inject_duplicate_observations(case.clean, case.config)
    assert q.canonical_json_bytes(case.clean) == before
    corrupted_ids = {record.record_id for record in case.corrupted.records}
    clean_ids = {record.record_id for record in case.clean.records}
    assert clean_ids <= corrupted_ids
    for record in case.clean.records:
        assert record in case.corrupted.records


def test_created_copies_are_appended_and_originals_survive() -> None:
    case = reviewed_duplicate_case()
    assert len(case.corrupted.records) == len(case.clean.records) + len(case.manifest.entries)
    created_ids = {entry.created_record.record_id for entry in case.manifest.entries}
    original_ids = {entry.original_record.record_id for entry in case.manifest.entries}
    corrupted_ids = {record.record_id for record in case.corrupted.records}
    assert created_ids <= corrupted_ids
    assert original_ids <= corrupted_ids
    assert created_ids.isdisjoint(original_ids)


def test_invalid_snapshot_identity_and_unavailable_record_are_rejected() -> None:
    case = reviewed_duplicate_case()
    forged = case.clean.model_copy(update={"snapshot_id": "snap_0000000000000000"})
    with pytest.raises(q.DuplicateInjectionError, match="identity"):
        q.inject_duplicate_observations(forged, case.config)

    future_record = case.clean.records[0].model_copy(
        update={"available_on": case.clean.as_of_date + timedelta(days=1)}
    )
    invalid = duplicate_snapshot(
        (future_record,) + case.clean.records[1:],
        dataset_name=case.clean.dataset_name,
        as_of_date=case.clean.as_of_date,
    )
    with pytest.raises(q.DuplicateInjectionError, match="unavailable"):
        q.inject_duplicate_observations(invalid, case.config)


def test_manifest_validation_rejects_forged_selection_digest() -> None:
    case = reviewed_duplicate_case()
    forged_entry = case.manifest.entries[0].model_copy(update={"selection_digest": "0" * 64})
    body = {
        name: getattr(case.manifest, name)
        for name in q.DuplicateManifest.model_fields
        if name != "manifest_id"
    }
    body["entries"] = (forged_entry, *case.manifest.entries[1:])
    forged = q.DuplicateManifest.model_validate(
        {
            "manifest_id": q.duplicate_manifest_id(manifest_body=body),
            **body,
        }
    )
    with pytest.raises(q.DuplicateManifestIntegrityError, match="selection digest"):
        q.validate_duplicate_manifest(forged)


def test_manifest_validation_rejects_forged_fingerprint_hash() -> None:
    case = reviewed_duplicate_case()
    forged_entry = case.manifest.entries[0].model_copy(update={"fingerprint_hash": "0" * 64})
    body = {
        name: getattr(case.manifest, name)
        for name in q.DuplicateManifest.model_fields
        if name != "manifest_id"
    }
    body["entries"] = (forged_entry, *case.manifest.entries[1:])
    forged = q.DuplicateManifest.model_validate(
        {
            "manifest_id": q.duplicate_manifest_id(manifest_body=body),
            **body,
        }
    )
    with pytest.raises(q.DuplicateManifestIntegrityError, match="fingerprint hash"):
        q.validate_duplicate_manifest(forged)


def test_manifest_records_complete_reversible_private_evidence() -> None:
    case = reviewed_duplicate_case()
    entry = case.manifest.entries[0]
    assert entry.mutation.original_record_id == entry.original_record.record_id
    assert entry.mutation.created_record_id == entry.created_record.record_id
    assert entry.mutation.copy_ordinal == 1
    assert entry.selection_digest
    assert entry.fingerprint_hash == q.duplicate_fingerprint_hash(
        q.duplicate_fingerprint(entry.original_record)
    )
    assert case.manifest.clean_snapshot_hash == q.canonical_sha256(case.clean)
    assert case.manifest.corrupted_snapshot_hash == q.canonical_sha256(case.corrupted)
