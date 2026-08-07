"""Controlled aggregate-value sensitivity comparison for Unit Drift."""

from __future__ import annotations

from decimal import Decimal, localcontext

from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_identity_matches,
    unit_drift_impact_id,
    unit_drift_research_result_id,
)
from quantcheck.schemas import (
    AggregateValueImpact,
    AggregateValueResult,
    DatasetSnapshot,
    UnitDriftResearchConfig,
)
from quantcheck.unit_drift_series import comparable_series_key

__all__ = [
    "UnitDriftResearchError",
    "aggregate_value_v0_1",
    "compare_unit_drift_research",
    "unit_drift_impact_identity_matches",
    "unit_drift_research_result_identity_matches",
]


class UnitDriftResearchError(ValueError):
    """Raised when controlled aggregate inputs are invalid or incomparable."""


def unit_drift_research_result_identity_matches(result: AggregateValueResult) -> bool:
    """Report whether an aggregate result ID covers every other field."""
    body = {
        name: getattr(result, name)
        for name in AggregateValueResult.model_fields
        if name != "research_result_id"
    }
    return result.research_result_id == unit_drift_research_result_id(result_body=body)


def unit_drift_impact_identity_matches(impact: AggregateValueImpact) -> bool:
    """Report whether an aggregate impact ID covers every other field."""
    body = {
        name: getattr(impact, name)
        for name in AggregateValueImpact.model_fields
        if name != "impact_id"
    }
    return impact.impact_id == unit_drift_impact_id(impact_body=body)


def aggregate_value_v0_1(
    snapshot: DatasetSnapshot,
    config: UnitDriftResearchConfig,
) -> AggregateValueResult:
    """Sum visible values in one exact comparable-series group."""
    if not dataset_snapshot_identity_matches(snapshot):
        raise UnitDriftResearchError("snapshot identity does not match its content")
    if config.research_as_of_date > snapshot.as_of_date:
        raise UnitDriftResearchError(
            "research_as_of_date must not follow the snapshot's source horizon"
        )
    included = tuple(
        record
        for record in snapshot.records
        if record.available_on <= config.research_as_of_date
        and comparable_series_key(record) == config.comparable_series_key
    )
    aggregate = sum((record.value for record in included), Decimal(0))
    result_body: dict[str, object] = {
        "method": config.method,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_content_hash": canonical_sha256(snapshot),
        "research_as_of_date": config.research_as_of_date,
        "comparable_series_key": config.comparable_series_key,
        "included_record_ids": tuple(record.record_id for record in included),
        "record_count": len(included),
        "aggregate_value": aggregate,
    }
    return AggregateValueResult.model_validate(
        {
            "research_result_id": unit_drift_research_result_id(result_body=result_body),
            **result_body,
        }
    )


def compare_unit_drift_research(
    clean_snapshot: DatasetSnapshot,
    corrupted_snapshot: DatasetSnapshot,
    repaired_snapshot: DatasetSnapshot,
    config: UnitDriftResearchConfig,
) -> AggregateValueImpact:
    """Apply exactly the same pure aggregate to clean, corrupted, and repaired data."""
    case_shapes = {
        (snapshot.dataset_name, snapshot.as_of_date)
        for snapshot in (clean_snapshot, corrupted_snapshot, repaired_snapshot)
    }
    if len(case_shapes) != 1:
        raise UnitDriftResearchError("research snapshots must share dataset and source horizon")
    clean = aggregate_value_v0_1(clean_snapshot, config)
    corrupted = aggregate_value_v0_1(corrupted_snapshot, config)
    repaired = aggregate_value_v0_1(repaired_snapshot, config)
    signed_change = corrupted.aggregate_value - clean.aggregate_value
    with localcontext() as context:
        context.prec = 50
        relative_change = (
            None if clean.aggregate_value == 0 else signed_change / abs(clean.aggregate_value)
        )
    impact_body: dict[str, object] = {
        "method": config.method,
        "research_as_of_date": config.research_as_of_date,
        "comparable_series_key": config.comparable_series_key,
        "clean": clean,
        "corrupted": corrupted,
        "repaired": repaired,
        "signed_change": signed_change,
        "absolute_change": abs(signed_change),
        "relative_change": relative_change,
        "changed": signed_change != 0,
        "exact_restoration": repaired == clean,
    }
    return AggregateValueImpact.model_validate(
        {
            "impact_id": unit_drift_impact_id(impact_body=impact_body),
            **impact_body,
        }
    )
