"""Controlled total-occurrence research comparison for Duplicate Observations.

The double-counting demonstration required alongside this reuses the
existing ``aggregate_value_v0_1``/``compare_unit_drift_research`` pure
functions from :mod:`quantcheck.unit_drift_research` unmodified: that method
already sums visible Decimal values in one exact comparable-series group and
has no Unit-Drift-specific assumption, so Duplicate Observations calls it
directly rather than duplicating the calculation. This module adds only the
one genuinely new controlled view: total occurrence and duplicate-group
counts.
"""

from __future__ import annotations

from quantcheck.duplicate_fingerprint import build_duplicate_groups
from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_identity_matches,
    duplicate_impact_id,
    duplicate_research_result_id,
)
from quantcheck.schemas import DatasetSnapshot, RecordCountImpact, RecordCountResult

__all__ = [
    "DuplicateResearchError",
    "compare_duplicate_record_count",
    "duplicate_impact_identity_matches",
    "duplicate_research_result_identity_matches",
    "record_count_v0_1",
]


class DuplicateResearchError(ValueError):
    """Raised when controlled record-count inputs are invalid or incomparable."""


def duplicate_research_result_identity_matches(result: RecordCountResult) -> bool:
    """Report whether a record-count result ID covers every other field."""
    body = {
        name: getattr(result, name)
        for name in RecordCountResult.model_fields
        if name != "research_result_id"
    }
    return result.research_result_id == duplicate_research_result_id(result_body=body)


def duplicate_impact_identity_matches(impact: RecordCountImpact) -> bool:
    """Report whether a record-count impact ID covers every other field."""
    body = {
        name: getattr(impact, name)
        for name in RecordCountImpact.model_fields
        if name != "impact_id"
    }
    return impact.impact_id == duplicate_impact_id(impact_body=body)


def record_count_v0_1(snapshot: DatasetSnapshot) -> RecordCountResult:
    """Count total occurrences and exact-fingerprint duplicate groups."""
    if not dataset_snapshot_identity_matches(snapshot):
        raise DuplicateResearchError("snapshot identity does not match its content")

    groups = build_duplicate_groups(snapshot.records, as_of_date=snapshot.as_of_date)
    duplicate_groups = [group for group in groups.values() if len(group.records) >= 2]
    duplicate_record_ids = tuple(
        sorted(record.record_id for group in duplicate_groups for record in group.records)
    )
    result_body: dict[str, object] = {
        "method": "record_count_v0_1",
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_content_hash": canonical_sha256(snapshot),
        "total_record_count": len(snapshot.records),
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_record_ids": duplicate_record_ids,
    }
    return RecordCountResult.model_validate(
        {
            "research_result_id": duplicate_research_result_id(result_body=result_body),
            **result_body,
        }
    )


def compare_duplicate_record_count(
    clean_snapshot: DatasetSnapshot,
    corrupted_snapshot: DatasetSnapshot,
    repaired_snapshot: DatasetSnapshot,
) -> RecordCountImpact:
    """Apply exactly the same pure counts to clean, corrupted, and repaired data."""
    case_shapes = {
        (snapshot.dataset_name, snapshot.as_of_date)
        for snapshot in (clean_snapshot, corrupted_snapshot, repaired_snapshot)
    }
    if len(case_shapes) != 1:
        raise DuplicateResearchError("research snapshots must share dataset and source horizon")

    clean = record_count_v0_1(clean_snapshot)
    corrupted = record_count_v0_1(corrupted_snapshot)
    repaired = record_count_v0_1(repaired_snapshot)
    total_delta = corrupted.total_record_count - clean.total_record_count
    group_delta = corrupted.duplicate_group_count - clean.duplicate_group_count
    impact_body: dict[str, object] = {
        "method": "record_count_v0_1",
        "clean": clean,
        "corrupted": corrupted,
        "repaired": repaired,
        "total_count_delta": total_delta,
        "duplicate_group_count_delta": group_delta,
        "changed": total_delta != 0 or group_delta != 0,
        "exact_restoration": (
            repaired.snapshot_id == clean.snapshot_id
            and repaired.snapshot_content_hash == clean.snapshot_content_hash
            and repaired.total_record_count == clean.total_record_count
            and repaired.duplicate_group_count == clean.duplicate_group_count
            and repaired.duplicate_record_ids == clean.duplicate_record_ids
        ),
    }
    return RecordCountImpact.model_validate(
        {
            "impact_id": duplicate_impact_id(impact_body=impact_body),
            **impact_body,
        }
    )
