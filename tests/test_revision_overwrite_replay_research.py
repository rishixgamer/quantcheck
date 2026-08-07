"""Exact private replay and controlled frozen-vintage growth impact."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

import quantcheck as q
from tests.revision_overwrite_support import (
    focused_snapshot,
    reviewed_revision_overwrite_case,
    revision_record,
)


def test_replay_restores_exact_clean_bytes_id_and_hash() -> None:
    case = reviewed_revision_overwrite_case()
    assert case.repaired.snapshot_id == case.clean.snapshot_id
    assert q.canonical_sha256(case.repaired) == q.canonical_sha256(case.clean)
    assert q.canonical_json_bytes(case.repaired) == q.canonical_json_bytes(case.clean)


def test_replay_is_idempotent_for_the_exact_clean_artifact() -> None:
    case = reviewed_revision_overwrite_case()
    assert (
        q.manifest_assisted_exact_revision_overwrite_replay(case.clean, case.manifest) is case.clean
    )


def test_replay_rejects_forged_manifest_identity() -> None:
    case = reviewed_revision_overwrite_case()
    fields = {
        name: getattr(case.manifest, name) for name in q.RevisionOverwriteManifest.model_fields
    }
    fields["manifest_id"] = "man_0000000000000000"
    forged = q.RevisionOverwriteManifest.model_construct(**fields)
    with pytest.raises(q.RevisionOverwriteManifestIntegrityError):
        q.manifest_assisted_exact_revision_overwrite_replay(case.corrupted, forged)


def test_replay_rejects_identity_valid_but_nonexact_corrupted_input() -> None:
    case = reviewed_revision_overwrite_case()
    target_id = case.manifest.entries[0].corrupted_record.record_id
    altered_records = tuple(
        record.model_copy(update={"value": record.value + 1})
        if record.record_id == target_id
        else record
        for record in case.corrupted.records
    )
    altered = q.DatasetSnapshot(
        snapshot_id=q.dataset_snapshot_id(
            dataset_name=case.corrupted.dataset_name,
            as_of_date=case.corrupted.as_of_date,
            records=altered_records,
        ),
        dataset_name=case.corrupted.dataset_name,
        as_of_date=case.corrupted.as_of_date,
        records=altered_records,
    )
    with pytest.raises(q.RevisionOverwriteReplayError):
        q.manifest_assisted_exact_revision_overwrite_replay(altered, case.manifest)


def test_replay_preserves_unrelated_records_and_private_later_reference() -> None:
    case = reviewed_revision_overwrite_case()
    unit = case.manifest.eligible_units[0]
    selected_original_id = unit.historical_record.record_id
    expected_unrelated = tuple(
        record for record in case.clean.records if record.record_id != selected_original_id
    )
    repaired_unrelated = tuple(
        record for record in case.repaired.records if record.record_id != selected_original_id
    )
    assert repaired_unrelated == expected_unrelated
    assert unit.later_record in case.source_records


def test_reviewed_growth_changes_exactly_and_repairs_exactly() -> None:
    impact = reviewed_revision_overwrite_case().research_impact
    clean = {entry.entity_id: entry for entry in impact.clean.rankings}
    corrupted = {entry.entity_id: entry for entry in impact.corrupted.rankings}
    assert clean["CIK0000000002"].growth == Decimal("-1.5")
    assert corrupted["CIK0000000002"].growth == Decimal(
        "-1.5102040816326530612244897959183673469387755102041"
    )
    assert impact.changed_entity_ids == ("CIK0000000002",)
    assert impact.maximum_absolute_growth_change == Decimal(
        "0.0102040816326530612244897959183673469387755102041"
    )
    assert impact.changed
    assert not impact.ranking_changed
    assert not impact.top_membership_changed
    assert impact.exact_restoration
    assert impact.repaired == impact.clean
    assert q.revision_overwrite_impact_identity_matches(impact)
    assert q.revision_overwrite_research_result_identity_matches(impact.clean)


def test_frozen_vintage_builder_uses_identical_later_current_period_for_all_states() -> None:
    case = reviewed_revision_overwrite_case()
    config = case.research_impact.config
    source_before = q.canonical_json_bytes(case.source_records)
    clean_input = q.build_frozen_vintage_growth_snapshot(case.clean, case.source_records, config)
    corrupted_input = q.build_frozen_vintage_growth_snapshot(
        case.corrupted, case.source_records, config
    )
    clean_current_ids = {
        entry.current_record_id for entry in q.growth_ranking_v0_1(clean_input, config).rankings
    }
    corrupted_current_ids = {
        entry.current_record_id for entry in q.growth_ranking_v0_1(corrupted_input, config).rankings
    }
    assert clean_current_ids == corrupted_current_ids
    assert q.canonical_json_bytes(case.source_records) == source_before


def test_growth_zero_prior_policy_is_explicit_exclusion() -> None:
    prior = revision_record(
        "ZERO-PRIOR",
        value="0",
        filed_on=date(2024, 4, 15),
        concept="NetIncomeLoss",
        entity_id="ZERO-ENTITY",
    )
    current = revision_record(
        "ZERO-CURRENT",
        value="10",
        filed_on=date(2024, 8, 1),
        concept="NetIncomeLoss",
        entity_id="ZERO-ENTITY",
        period_start=date(2024, 4, 1),
        period_end=date(2024, 6, 30),
    )
    historical = focused_snapshot((prior, current))
    config = q.GrowthRankingConfig(
        concept_namespace="us-gaap",
        concept="NetIncomeLoss",
        unit="USD",
        prior_period_start=date(2024, 1, 1),
        prior_period_end=date(2024, 3, 31),
        current_period_start=date(2024, 4, 1),
        current_period_end=date(2024, 6, 30),
        research_as_of_date=date(2024, 8, 31),
    )
    research_input = q.build_frozen_vintage_growth_snapshot(historical, (prior, current), config)
    result = q.growth_ranking_v0_1(research_input, config)
    assert result.rankings == ()
    assert result.excluded_zero_prior_entity_ids == ("ZERO-ENTITY",)


def test_growth_rejects_ambiguous_independent_occurrences() -> None:
    prior_a = revision_record(
        "PRIOR-A",
        value="100",
        filed_on=date(2024, 4, 15),
    )
    prior_b = revision_record(
        "PRIOR-B",
        value="101",
        filed_on=date(2024, 4, 15),
    )
    current = revision_record(
        "CURRENT",
        value="110",
        filed_on=date(2024, 8, 1),
        period_start=date(2024, 4, 1),
        period_end=date(2024, 6, 30),
    )
    as_of = date(2024, 8, 31)
    snapshot = q.DatasetSnapshot(
        snapshot_id=q.dataset_snapshot_id(
            dataset_name="ambiguous-growth",
            as_of_date=as_of,
            records=(prior_a, prior_b, current),
        ),
        dataset_name="ambiguous-growth",
        as_of_date=as_of,
        records=(prior_a, prior_b, current),
    )
    config = q.GrowthRankingConfig(
        concept_namespace="us-gaap",
        concept="Revenues",
        unit="USD",
        prior_period_start=date(2024, 1, 1),
        prior_period_end=date(2024, 3, 31),
        current_period_start=date(2024, 4, 1),
        current_period_end=date(2024, 6, 30),
        research_as_of_date=as_of,
    )
    with pytest.raises(q.RevisionOverwriteResearchError, match="ambiguous"):
        q.growth_ranking_v0_1(snapshot, config)
