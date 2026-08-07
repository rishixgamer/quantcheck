"""Exact comparable-series construction shared across Unit Drift stages."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from quantcheck.schemas import (
    AuditInputRecord,
    ComparableSeriesKey,
    FinancialFact,
)
from quantcheck.serialization import canonical_json_bytes

__all__ = [
    "ComparableObservation",
    "build_comparable_observations",
    "comparable_series_key",
]


@dataclass(frozen=True, slots=True)
class ComparableObservation[RecordT: (FinancialFact, AuditInputRecord)]:
    """One eligible local-series candidate and its nearest usable neighbors."""

    key: ComparableSeriesKey
    records: tuple[RecordT, ...]
    index: int
    neighbors: tuple[tuple[str, RecordT], ...]

    @property
    def record(self) -> RecordT:
        return self.records[self.index]


def _period_length_days(record: FinancialFact | AuditInputRecord) -> int | None:
    if record.period_type == "instant":
        return None
    assert record.period_start is not None
    return (record.period_end - record.period_start).days + 1


def comparable_series_key(
    record: FinancialFact | AuditInputRecord,
) -> ComparableSeriesKey:
    """Build the exact entity/concept/unit/dimension/period-shape key."""
    return ComparableSeriesKey(
        entity_id=record.entity_id,
        concept_namespace=record.concept_namespace,
        concept=record.concept,
        unit=record.unit,
        dimensions=record.dimensions,
        period_type=record.period_type,
        period_length_days=_period_length_days(record),
    )


def _chronology_coordinate(
    record: FinancialFact | AuditInputRecord,
) -> tuple[date, date]:
    return record.period_end, record.period_start or record.period_end


def _nearest_nonzero_neighbors[RecordT: (FinancialFact, AuditInputRecord)](
    records: tuple[RecordT, ...],
    index: int,
) -> tuple[tuple[str, RecordT], ...]:
    neighbors: list[tuple[str, RecordT]] = []
    for previous_index in range(index - 1, -1, -1):
        if records[previous_index].value != 0:
            neighbors.append(("previous", records[previous_index]))
            break
    for next_index in range(index + 1, len(records)):
        if records[next_index].value != 0:
            neighbors.append(("next", records[next_index]))
            break
    return tuple(neighbors)


def build_comparable_observations[RecordT: (FinancialFact, AuditInputRecord)](
    records: Sequence[RecordT],
    *,
    as_of_date: date,
) -> dict[str, ComparableObservation[RecordT]]:
    """Return candidates meeting the exact clean/detector comparability prerequisites.

    Only end-of-day-visible records participate. A series is excluded in full
    when two records claim the same chronology coordinate, because their local
    ordering would otherwise require guessing. Eligible candidates are nonzero,
    belong to a series of at least three observations, and have at least one
    nearest previous/next nonzero comparator.
    """
    grouped: dict[ComparableSeriesKey, list[RecordT]] = {}
    for record in records:
        if record.available_on <= as_of_date:
            grouped.setdefault(comparable_series_key(record), []).append(record)

    observations: dict[str, ComparableObservation[RecordT]] = {}
    for key in sorted(grouped, key=canonical_json_bytes):
        members = grouped[key]
        coordinates = [_chronology_coordinate(record) for record in members]
        if len(set(coordinates)) != len(coordinates):
            continue
        ordered = tuple(
            sorted(
                members,
                key=lambda record: (*_chronology_coordinate(record), record.record_id),
            )
        )
        if len(ordered) < 3:
            continue
        for index, record in enumerate(ordered):
            if record.value == 0:
                continue
            neighbors = _nearest_nonzero_neighbors(ordered, index)
            if not neighbors:
                continue
            observations[record.record_id] = ComparableObservation(
                key=key,
                records=ordered,
                index=index,
                neighbors=neighbors,
            )
    return observations
