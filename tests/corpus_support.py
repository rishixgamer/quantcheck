"""Shared helpers for the v0.2 corpus tests.

Materializing a partition is the expensive part of these tests, so the ordinary
partitions are built once per session and reused. Held-out units are never
touched here: any test that needs them opens the gate explicitly, which is the
behaviour under test.
"""

from __future__ import annotations

from functools import cache

from quantcheck.corpus_eligibility import unit_snapshot
from quantcheck.corpus_registry import (
    corpus_unit_records,
    corpus_unit_spec,
    partition_unit_ids,
)
from quantcheck.corpus_schemas import CorpusUnitSpec
from quantcheck.schemas import DatasetSnapshot, FinancialFact

#: The partitions an ordinary test may materialize with no authorization.
ORDINARY_PARTITIONS: tuple[str, ...] = ("development", "validation")


@cache
def ordinary_unit_ids() -> tuple[str, ...]:
    """Every development and validation unit identifier, sorted."""
    return tuple(
        sorted(
            unit_id
            for partition in ORDINARY_PARTITIONS
            for unit_id in partition_unit_ids(partition)
        )
    )


@cache
def unit_bundle(unit_id: str) -> tuple[CorpusUnitSpec, tuple[FinancialFact, ...], DatasetSnapshot]:
    """One unit's specification, records, and clean point-in-time snapshot."""
    spec = corpus_unit_spec(unit_id)
    records = corpus_unit_records(unit_id)
    return spec, records, unit_snapshot(spec, records)


def unit_by_role(partition: str, role: str) -> str:
    """Find one unit identifier by its human-readable role."""
    for unit_id in partition_unit_ids(partition):
        if corpus_unit_spec(unit_id).unit_name == f"{partition}-{role}":
            return unit_id
    raise AssertionError(f"no {role!r} unit in partition {partition!r}")
