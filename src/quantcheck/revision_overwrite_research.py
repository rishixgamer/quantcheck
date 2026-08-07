"""Controlled frozen-vintage growth-ranking sensitivity for Revision Overwrite."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, localcontext

from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
    revision_overwrite_impact_id,
    revision_overwrite_research_result_id,
)
from quantcheck.point_in_time import build_dataset_snapshot
from quantcheck.schemas import (
    DatasetSnapshot,
    FinancialFact,
    GrowthRankingConfig,
    GrowthRankingEntry,
    GrowthRankingImpact,
    GrowthRankingResult,
)

__all__ = [
    "RevisionOverwriteResearchError",
    "build_frozen_vintage_growth_snapshot",
    "compare_revision_overwrite_research",
    "growth_ranking_v0_1",
    "revision_overwrite_impact_identity_matches",
    "revision_overwrite_research_result_identity_matches",
]


class RevisionOverwriteResearchError(ValueError):
    """Raised when controlled growth inputs are invalid or ambiguous."""


def revision_overwrite_research_result_identity_matches(
    result: GrowthRankingResult,
) -> bool:
    body = {
        name: getattr(result, name)
        for name in GrowthRankingResult.model_fields
        if name != "research_result_id"
    }
    return result.research_result_id == revision_overwrite_research_result_id(result_body=body)


def revision_overwrite_impact_identity_matches(impact: GrowthRankingImpact) -> bool:
    body = {
        name: getattr(impact, name)
        for name in GrowthRankingImpact.model_fields
        if name != "impact_id"
    }
    return impact.impact_id == revision_overwrite_impact_id(impact_body=body)


def _matches_context(record: FinancialFact, config: GrowthRankingConfig) -> bool:
    return (
        record.concept_namespace == config.concept_namespace
        and record.concept == config.concept
        and record.unit == config.unit
        and record.dimensions == config.dimensions
        and record.period_type == config.period_type
    )


def _period_role(record: FinancialFact, config: GrowthRankingConfig) -> str | None:
    if (
        record.period_start == config.prior_period_start
        and record.period_end == config.prior_period_end
    ):
        return "prior"
    if (
        record.period_start == config.current_period_start
        and record.period_end == config.current_period_end
    ):
        return "current"
    return None


def build_frozen_vintage_growth_snapshot(
    historical_snapshot: DatasetSnapshot,
    source_records: Sequence[FinancialFact],
    config: GrowthRankingConfig,
) -> DatasetSnapshot:
    """Combine an earlier frozen state with later current-period observations.

    Revision Overwrite concerns what an earlier state contained. A later
    two-period research comparison therefore freezes the prior-period rows
    from ``historical_snapshot`` and adds only the correctly selected current
    period from the same full source history at ``research_as_of_date``. The
    operation is pure and identical for clean, corrupted, and replayed input.
    """
    if not dataset_snapshot_identity_matches(historical_snapshot):
        raise RevisionOverwriteResearchError(
            "historical snapshot identity does not match its content"
        )
    if historical_snapshot.as_of_date >= config.research_as_of_date:
        raise RevisionOverwriteResearchError(
            "frozen historical cutoff must precede the growth research cutoff"
        )
    later_snapshot = build_dataset_snapshot(
        source_records,
        dataset_name=historical_snapshot.dataset_name,
        as_of_date=config.research_as_of_date,
    )
    current_records = tuple(
        record
        for record in later_snapshot.records
        if _matches_context(record, config) and _period_role(record, config) == "current"
    )
    historical_current_ids = {
        record.record_id
        for record in historical_snapshot.records
        if _matches_context(record, config) and _period_role(record, config) == "current"
    }
    if historical_current_ids:
        raise RevisionOverwriteResearchError(
            "historical snapshot already contains configured current-period records"
        )
    records = historical_snapshot.records + current_records
    return DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name=historical_snapshot.dataset_name,
            as_of_date=config.research_as_of_date,
            records=records,
        ),
        dataset_name=historical_snapshot.dataset_name,
        as_of_date=config.research_as_of_date,
        records=records,
    )


def growth_ranking_v0_1(
    snapshot: DatasetSnapshot,
    config: GrowthRankingConfig,
) -> GrowthRankingResult:
    """Rank exact two-period Decimal growth across eligible entities."""
    if not dataset_snapshot_identity_matches(snapshot):
        raise RevisionOverwriteResearchError("snapshot identity does not match its content")
    if config.research_as_of_date > snapshot.as_of_date:
        raise RevisionOverwriteResearchError(
            "research_as_of_date must not follow the snapshot cutoff"
        )

    by_entity: dict[str, dict[str, list[FinancialFact]]] = {}
    for record in snapshot.records:
        if record.available_on > config.research_as_of_date:
            continue
        if not _matches_context(record, config):
            continue
        role = _period_role(record, config)
        if role is None:
            continue
        by_entity.setdefault(record.entity_id, {}).setdefault(role, []).append(record)

    raw_entries: list[tuple[str, FinancialFact, FinancialFact, Decimal]] = []
    excluded_zero: list[str] = []
    for entity_id in sorted(by_entity):
        roles = by_entity[entity_id]
        if "prior" not in roles or "current" not in roles:
            continue
        if len(roles["prior"]) != 1 or len(roles["current"]) != 1:
            raise RevisionOverwriteResearchError(
                f"entity {entity_id!r} has ambiguous observations for a configured period"
            )
        prior = roles["prior"][0]
        current = roles["current"][0]
        if prior.value == 0:
            excluded_zero.append(entity_id)
            continue
        with localcontext() as context:
            context.prec = 50
            growth = (current.value - prior.value) / abs(prior.value)
        raw_entries.append((entity_id, prior, current, growth))

    raw_entries.sort(key=lambda item: item[0])
    raw_entries.sort(key=lambda item: item[3], reverse=True)
    rankings = tuple(
        GrowthRankingEntry(
            rank=rank,
            entity_id=entity_id,
            prior_record_id=prior.record_id,
            current_record_id=current.record_id,
            prior_value=prior.value,
            current_value=current.value,
            growth=growth,
        )
        for rank, (entity_id, prior, current, growth) in enumerate(raw_entries, start=1)
    )
    body: dict[str, object] = {
        "method": config.method,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_content_hash": canonical_sha256(snapshot),
        "config": config,
        "rankings": rankings,
        "eligible_entity_count": len(rankings),
        "top_entity_ids": tuple(entry.entity_id for entry in rankings[: config.top_n]),
        "excluded_zero_prior_entity_ids": tuple(excluded_zero),
    }
    return GrowthRankingResult.model_validate(
        {
            "research_result_id": revision_overwrite_research_result_id(result_body=body),
            **body,
        }
    )


def compare_revision_overwrite_research(
    clean_snapshot: DatasetSnapshot,
    corrupted_snapshot: DatasetSnapshot,
    repaired_snapshot: DatasetSnapshot,
    config: GrowthRankingConfig,
) -> GrowthRankingImpact:
    """Apply the identical pure ranking to clean, corrupted, and repaired states."""
    case_shapes = {
        (snapshot.dataset_name, snapshot.as_of_date)
        for snapshot in (clean_snapshot, corrupted_snapshot, repaired_snapshot)
    }
    if len(case_shapes) != 1:
        raise RevisionOverwriteResearchError(
            "research snapshots must share dataset and historical cutoff"
        )
    clean = growth_ranking_v0_1(clean_snapshot, config)
    corrupted = growth_ranking_v0_1(corrupted_snapshot, config)
    repaired = growth_ranking_v0_1(repaired_snapshot, config)
    clean_growth = {entry.entity_id: entry.growth for entry in clean.rankings}
    corrupted_growth = {entry.entity_id: entry.growth for entry in corrupted.rankings}
    changed_entity_ids = tuple(
        sorted(
            entity_id
            for entity_id in set(clean_growth) | set(corrupted_growth)
            if clean_growth.get(entity_id) != corrupted_growth.get(entity_id)
        )
    )
    common = set(clean_growth) & set(corrupted_growth)
    with localcontext() as context:
        context.prec = 50
        maximum_change = max(
            (abs(corrupted_growth[entity] - clean_growth[entity]) for entity in common),
            default=Decimal(0),
        )
    clean_order = tuple(entry.entity_id for entry in clean.rankings)
    corrupted_order = tuple(entry.entity_id for entry in corrupted.rankings)
    body: dict[str, object] = {
        "method": config.method,
        "config": config,
        "clean": clean,
        "corrupted": corrupted,
        "repaired": repaired,
        "changed_entity_ids": changed_entity_ids,
        "maximum_absolute_growth_change": maximum_change,
        "ranking_changed": clean_order != corrupted_order,
        "top_membership_changed": set(clean.top_entity_ids) != set(corrupted.top_entity_ids),
        "changed": bool(changed_entity_ids) or clean_order != corrupted_order,
        "exact_restoration": repaired == clean,
    }
    return GrowthRankingImpact.model_validate(
        {
            "impact_id": revision_overwrite_impact_id(impact_body=body),
            **body,
        }
    )
