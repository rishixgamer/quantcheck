"""The closed registry of clean sources a benchmark case may start from.

Every entry is a deterministic, offline, in-package factory. A benchmark
configuration names a fixture by identifier, never by path, so a benchmark's
logical identity cannot pick up a directory on this machine.

Two fixtures exist in v0.1:

``quantcheck/reviewed-fixture/v1``
    The checked-in 26-record reviewed synthetic fixture from Milestone 2. It
    supports Look-Ahead, Duplicate Observations, and Revision Overwrite.

``quantcheck/benchmark-unit-drift-series/v1``
    A five-observation single-entity series added for Milestone 8. Unit Drift
    requires a comparable series of at least three observations with a nonzero
    neighbor (``quantcheck.unit_drift_series``), and the reviewed fixture is
    deliberately a two-period *insufficient-history control* for Unit Drift —
    it has no eligible target at any severity or horizon. Rather than weaken
    the frozen Unit Drift comparability rule to make the benchmark run, the
    benchmark supplies a second named clean source that satisfies it. No
    reviewed-fixture byte, injector rule, detector rule, or scoring rule
    changed to accommodate this.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from quantcheck.hashing import source_record_id
from quantcheck.schemas import BenchmarkFixtureId, FinancialFact, SourceReference

__all__ = [
    "BENCHMARK_FIXTURE_IDS",
    "UNIT_DRIFT_SERIES_FIXTURE_ID",
    "UNIT_DRIFT_SERIES_LOCATOR",
    "UNIT_DRIFT_SERIES_NAME",
    "UNIT_DRIFT_SERIES_RECORD_COUNT",
    "UnknownBenchmarkFixtureError",
    "benchmark_fixture_records",
    "unit_drift_series_records",
]

REVIEWED_FIXTURE_ID: BenchmarkFixtureId = "quantcheck/reviewed-fixture/v1"
UNIT_DRIFT_SERIES_FIXTURE_ID: BenchmarkFixtureId = "quantcheck/benchmark-unit-drift-series/v1"

BENCHMARK_FIXTURE_IDS: tuple[BenchmarkFixtureId, ...] = (
    UNIT_DRIFT_SERIES_FIXTURE_ID,
    REVIEWED_FIXTURE_ID,
)

UNIT_DRIFT_SERIES_NAME = "quantcheck-benchmark-unit-drift-series"
UNIT_DRIFT_SERIES_LOCATOR = "quantcheck/benchmark-unit-drift-series/v1"
UNIT_DRIFT_SERIES_RECORD_COUNT = 5

_SERIES_ENTITY_ID = "CIK0000000009"
_SERIES_ENTITY_NAME = "Meridian Series Holdings Inc"
_SERIES_CONCEPT_NAMESPACE = "us-gaap"
_SERIES_CONCEPT = "Revenues"
_SERIES_UNIT = "USD"
_SERIES_FIRST_PERIOD_END = date(2024, 1, 30)
_SERIES_PERIOD_STEP_DAYS = 60
_SERIES_VALUES = ("100.00", "110.00", "120.00", "130.00", "140.00")


class UnknownBenchmarkFixtureError(ValueError):
    """Raised for a fixture identifier the benchmark does not support."""


def unit_drift_series_records() -> tuple[FinancialFact, ...]:
    """Build the deterministic Unit Drift benchmark series.

    Five instant observations of one concept for one entity, 60 days apart,
    each available on its own period end. The values rise smoothly, so every
    adjacent local ratio is far below the frozen detector threshold and the
    clean series produces no finding; a scaled value therefore shows up as a
    genuine local discontinuity rather than as pre-baked corruption.

    This is a pure factory: no filesystem, no clock, no randomness.
    """
    records: list[FinancialFact] = []
    for index, value in enumerate(_SERIES_VALUES):
        period_end = _SERIES_FIRST_PERIOD_END + timedelta(days=_SERIES_PERIOD_STEP_DAYS * index)
        row_key = f"BSERIES-{index:02d}"
        source = SourceReference(
            source_name=UNIT_DRIFT_SERIES_NAME,
            source_locator=UNIT_DRIFT_SERIES_LOCATOR,
            source_row_key=row_key,
        )
        records.append(
            FinancialFact(
                record_id=source_record_id(
                    source_name=source.source_name,
                    source_locator=source.source_locator,
                    source_row_key=source.source_row_key,
                ),
                entity_id=_SERIES_ENTITY_ID,
                entity_name=_SERIES_ENTITY_NAME,
                concept_namespace=_SERIES_CONCEPT_NAMESPACE,
                concept=_SERIES_CONCEPT,
                value=Decimal(value),
                unit=_SERIES_UNIT,
                dimensions=(),
                period_type="instant",
                period_start=None,
                period_end=period_end,
                filed_on=period_end,
                available_on=period_end,
                form="10-Q",
                accession_number=f"0000000009-24-{index + 1:06d}",
                source=source,
            )
        )
    return tuple(records)


def benchmark_fixture_records(fixture_id: str) -> tuple[FinancialFact, ...]:
    """Return the clean source records for one supported fixture identifier.

    Raises:
        UnknownBenchmarkFixtureError: for any unsupported identifier. The
            benchmark rejects an unknown fixture rather than guessing one.
    """
    if fixture_id == REVIEWED_FIXTURE_ID:
        # Imported lazily so this registry stays a thin dispatch table and the
        # reviewed fixture module keeps its single documented entry point.
        from quantcheck.fixtures import generate_reviewed_fixture

        return generate_reviewed_fixture()
    if fixture_id == UNIT_DRIFT_SERIES_FIXTURE_ID:
        return unit_drift_series_records()
    raise UnknownBenchmarkFixtureError(f"unsupported benchmark fixture: {fixture_id!r}")
