"""Deterministic point-in-time snapshot construction with explicit revision ordering.

The core operation is :func:`build_dataset_snapshot`: given the full clean set
of source records and a research date, it answers what a researcher could
have known on that date, using exactly the end-of-day rule
``available_on <= as_of_date``.

Revision ordering is deliberately narrow. Two records only belong to the same
revision history when a source explicitly says so through a declared
lineage marker in :attr:`~quantcheck.schemas.SourceReference.source_row_key`
(see :func:`parse_declared_revision_lineage`); nothing here infers a revision
relationship from matching business-key fields (entity, concept, period,
unit, dimensions) alone. Records without a declared lineage marker are
independent source occurrences: every one of them that is available on the
research date is preserved, without deduplication. This module does not
implement general restatement detection — only correct selection among a
*known, source-declared* clean revision history.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import NamedTuple

from quantcheck.hashing import dataset_snapshot_id
from quantcheck.schemas import DatasetSnapshot, FinancialFact

__all__ = [
    "AmbiguousRevisionHistoryError",
    "RevisionLineage",
    "build_dataset_snapshot",
    "parse_declared_revision_lineage",
]

#: A declared revision-lineage marker inside a source-defined ``source_row_key``:
#: ``"<lineage_id>#r<sequence>"``, where ``sequence`` is a positive integer with
#: no leading zero. Rows without this suffix are independent source occurrences.
_REVISION_LINEAGE_PATTERN = re.compile(r"^(?P<lineage_id>.+)#r(?P<sequence>[1-9][0-9]*)$")


class AmbiguousRevisionHistoryError(ValueError):
    """Raised when a declared revision lineage is contradictory or ambiguous.

    Raised when a lineage's members disagree on the economic fact they
    describe, repeat a sequence number, or are not consistently ordered by
    both declared sequence and source-supported date. Point-in-time
    selection rejects these histories rather than guessing at intent.
    """


class RevisionLineage(NamedTuple):
    """A parsed, source-declared revision-lineage marker."""

    lineage_id: str
    sequence: int


def parse_declared_revision_lineage(source_row_key: str) -> RevisionLineage | None:
    """Parse a declared revision-lineage marker out of a source row key.

    Returns ``None`` when the key carries no such marker, meaning the record
    is an independent source occurrence rather than part of a revision
    history. This is the only signal this module uses to decide whether two
    records are revisions of one another; it never falls back to comparing
    business-key fields or values.
    """
    match = _REVISION_LINEAGE_PATTERN.fullmatch(source_row_key)
    if match is None:
        return None
    return RevisionLineage(
        lineage_id=match.group("lineage_id"),
        sequence=int(match.group("sequence")),
    )


def _economic_identity(fact: FinancialFact) -> tuple[object, ...]:
    """The business-key fields that must match across one lineage's members."""
    return (
        fact.entity_id,
        fact.concept_namespace,
        fact.concept,
        fact.unit,
        tuple((dimension.axis, dimension.member) for dimension in fact.dimensions),
        fact.period_type,
        fact.period_start,
        fact.period_end,
    )


def _resolve_lineage_group(
    lineage_id: str,
    members: Sequence[tuple[int, FinancialFact]],
    as_of_date: date,
) -> list[FinancialFact]:
    sequences = [sequence for sequence, _ in members]
    if len(set(sequences)) != len(sequences):
        raise AmbiguousRevisionHistoryError(
            f"revision lineage {lineage_id!r} declares duplicate sequence numbers: "
            f"{sorted(sequences)}"
        )

    ordered = sorted(members, key=lambda item: item[0])

    reference_identity = _economic_identity(ordered[0][1])
    for _, fact in ordered[1:]:
        if _economic_identity(fact) != reference_identity:
            raise AmbiguousRevisionHistoryError(
                f"revision lineage {lineage_id!r} mixes records that describe "
                "different economic facts"
            )

    previous_available: date | None = None
    previous_filed: date | None = None
    for sequence, fact in ordered:
        if previous_available is not None and fact.available_on < previous_available:
            raise AmbiguousRevisionHistoryError(
                f"revision lineage {lineage_id!r} sequence {sequence} is available "
                f"({fact.available_on.isoformat()}) before an earlier sequence "
                f"({previous_available.isoformat()})"
            )
        if previous_filed is not None and fact.filed_on < previous_filed:
            raise AmbiguousRevisionHistoryError(
                f"revision lineage {lineage_id!r} sequence {sequence} is filed "
                f"({fact.filed_on.isoformat()}) before an earlier sequence "
                f"({previous_filed.isoformat()})"
            )
        previous_available, previous_filed = fact.available_on, fact.filed_on

    visible = [fact for _, fact in ordered if fact.available_on <= as_of_date]
    if not visible:
        return []
    # `ordered` is sorted ascending by declared sequence, and availability was
    # just proven monotonic in that same order, so the last visible entry is
    # both the highest sequence and the latest available_on that qualifies.
    return [visible[-1]]


def _select_visible_records(
    records: Sequence[FinancialFact],
    as_of_date: date,
) -> list[FinancialFact]:
    independent: list[FinancialFact] = []
    lineage_groups: dict[str, list[tuple[int, FinancialFact]]] = {}

    for fact in records:
        lineage = parse_declared_revision_lineage(fact.source.source_row_key)
        if lineage is None:
            independent.append(fact)
            continue
        lineage_groups.setdefault(lineage.lineage_id, []).append((lineage.sequence, fact))

    selected = [fact for fact in independent if fact.available_on <= as_of_date]
    for lineage_id in sorted(lineage_groups):
        selected.extend(_resolve_lineage_group(lineage_id, lineage_groups[lineage_id], as_of_date))
    return selected


def build_dataset_snapshot(
    records: Sequence[FinancialFact],
    *,
    dataset_name: str,
    as_of_date: date,
) -> DatasetSnapshot:
    """Build the immutable set of facts a researcher could know on ``as_of_date``.

    Applies exactly the end-of-day availability rule
    ``record.available_on <= as_of_date``, resolves every declared revision
    lineage to its correct latest-visible member, and leaves every
    independent source occurrence and duplicate candidate untouched and
    unmerged. The input sequence is never mutated, and the result does not
    depend on the order records were supplied in: :class:`DatasetSnapshot`
    sorts its records by ``record_id`` during validation, and the snapshot
    identifier is computed the same way.

    Raises:
        AmbiguousRevisionHistoryError: if a declared revision lineage is
            contradictory (mismatched economic identity, a repeated sequence
            number, or availability/filing dates that disagree with the
            declared sequence order).
    """
    selected = _select_visible_records(records, as_of_date)
    snapshot_id = dataset_snapshot_id(
        dataset_name=dataset_name,
        as_of_date=as_of_date,
        records=selected,
    )
    return DatasetSnapshot(
        snapshot_id=snapshot_id,
        dataset_name=dataset_name,
        as_of_date=as_of_date,
        records=tuple(selected),
    )
