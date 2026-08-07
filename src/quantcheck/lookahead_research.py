"""Controlled availability-count research comparison for Look-Ahead faults."""

from __future__ import annotations

from datetime import date

from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_identity_matches,
    lookahead_impact_id,
    lookahead_research_result_id,
)
from quantcheck.schemas import AvailabilityCountResult, DatasetSnapshot, ResearchImpact

__all__ = [
    "LookAheadResearchError",
    "availability_count_v0_1",
    "compare_lookahead_research",
    "research_impact_identity_matches",
    "research_result_identity_matches",
]


class LookAheadResearchError(ValueError):
    """Raised when controlled research inputs are not comparable."""


def research_result_identity_matches(result: AvailabilityCountResult) -> bool:
    body = {
        name: getattr(result, name)
        for name in AvailabilityCountResult.model_fields
        if name != "research_result_id"
    }
    return result.research_result_id == lookahead_research_result_id(result_body=body)


def research_impact_identity_matches(impact: ResearchImpact) -> bool:
    body = {
        name: getattr(impact, name) for name in ResearchImpact.model_fields if name != "impact_id"
    }
    return impact.impact_id == lookahead_impact_id(impact_body=body)


def availability_count_v0_1(
    snapshot: DatasetSnapshot,
    *,
    research_as_of_date: date,
) -> AvailabilityCountResult:
    """Count occurrences visible under ``available_on <= research_as_of_date``."""
    if not dataset_snapshot_identity_matches(snapshot):
        raise LookAheadResearchError("snapshot identity does not match its content")
    if research_as_of_date > snapshot.as_of_date:
        raise LookAheadResearchError(
            "research_as_of_date must not follow the snapshot's source horizon"
        )
    available_ids = tuple(
        record.record_id
        for record in snapshot.records
        if record.available_on <= research_as_of_date
    )
    result_body: dict[str, object] = {
        "method": "availability_count_v0_1",
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_content_hash": canonical_sha256(snapshot),
        "research_as_of_date": research_as_of_date,
        "available_record_ids": available_ids,
        "availability_count": len(available_ids),
    }
    return AvailabilityCountResult.model_validate(
        {
            "research_result_id": lookahead_research_result_id(result_body=result_body),
            **result_body,
        }
    )


def compare_lookahead_research(
    clean_snapshot: DatasetSnapshot,
    corrupted_snapshot: DatasetSnapshot,
    repaired_snapshot: DatasetSnapshot,
    *,
    research_as_of_date: date,
) -> ResearchImpact:
    """Apply exactly the same pure count to clean, corrupted, and repaired data."""
    case_shapes = {
        (snapshot.dataset_name, snapshot.as_of_date)
        for snapshot in (clean_snapshot, corrupted_snapshot, repaired_snapshot)
    }
    if len(case_shapes) != 1:
        raise LookAheadResearchError("research snapshots must share dataset and source horizon")

    clean = availability_count_v0_1(clean_snapshot, research_as_of_date=research_as_of_date)
    corrupted = availability_count_v0_1(corrupted_snapshot, research_as_of_date=research_as_of_date)
    repaired = availability_count_v0_1(repaired_snapshot, research_as_of_date=research_as_of_date)
    delta = corrupted.availability_count - clean.availability_count
    exact_restoration = (
        repaired_snapshot.snapshot_id == clean_snapshot.snapshot_id
        and canonical_sha256(repaired_snapshot) == canonical_sha256(clean_snapshot)
    )
    impact_body: dict[str, object] = {
        "method": "availability_count_v0_1",
        "research_as_of_date": research_as_of_date,
        "clean": clean,
        "corrupted": corrupted,
        "repaired": repaired,
        "corruption_delta": delta,
        "changed": delta != 0,
        "exact_restoration": exact_restoration,
    }
    return ResearchImpact.model_validate(
        {
            "impact_id": lookahead_impact_id(impact_body=impact_body),
            **impact_body,
        }
    )
