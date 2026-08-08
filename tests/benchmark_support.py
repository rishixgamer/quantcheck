"""Shared deterministic builders for Recovery Phase 8 tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import quantcheck as q

#: A fixed runtime record. Milestone 8 never reads the clock inside the
#: library, so tests can hold every execution fact constant and still exercise
#: the real persistence path.
FIXED_RUNTIME = q.RuntimeMetadata(
    code_version="quantcheck-0.1.0.dev0",
    python_version="3.12.13",
    platform="test-platform",
    generated_at=datetime(2026, 8, 7, 12, 0, 0, tzinfo=UTC),
)

REVIEWED_HISTORICAL_HORIZON = date(2024, 4, 30)
REVIEWED_LATER_HORIZON = date(2024, 8, 31)
UNIT_DRIFT_HORIZON = date(2024, 12, 31)


def lookahead_profile(
    *,
    severities: tuple[str, ...] = ("medium",),
    seeds: tuple[int, ...] = (0,),
    control: q.BenchmarkCleanControl | None = None,
) -> q.BenchmarkLookAheadProfile:
    return q.BenchmarkLookAheadProfile(
        fixture=q.BenchmarkFixtureConfig(
            fixture_id=q.REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=REVIEWED_HISTORICAL_HORIZON,
        ),
        severities=severities,
        seeds=seeds,
        research=q.BenchmarkLookAheadResearch(research_as_of_date=date(2024, 4, 14)),
        clean_control=control,
    )


def unit_drift_profile(
    *,
    severities: tuple[str, ...] = ("medium",),
    seeds: tuple[int, ...] = (0,),
    control: q.BenchmarkCleanControl | None = None,
) -> q.BenchmarkUnitDriftProfile:
    return q.BenchmarkUnitDriftProfile(
        fixture=q.BenchmarkFixtureConfig(
            fixture_id=q.UNIT_DRIFT_SERIES_FIXTURE_ID,
            dataset_name="benchmark-unit-drift-series",
            as_of_date=UNIT_DRIFT_HORIZON,
        ),
        severities=severities,
        seeds=seeds,
        research=q.BenchmarkUnitDriftResearch(research_as_of_date=UNIT_DRIFT_HORIZON),
        clean_control=control,
    )


def duplicate_profile(
    *,
    severities: tuple[str, ...] = ("medium",),
    seeds: tuple[int, ...] = (0,),
    control: q.BenchmarkCleanControl | None = None,
) -> q.BenchmarkDuplicateProfile:
    return q.BenchmarkDuplicateProfile(
        fixture=q.BenchmarkFixtureConfig(
            fixture_id=q.REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=REVIEWED_LATER_HORIZON,
        ),
        severities=severities,
        seeds=seeds,
        research=q.BenchmarkDuplicateResearch(),
        clean_control=control,
    )


def revision_overwrite_profile(
    *,
    severities: tuple[str, ...] = ("low",),
    seeds: tuple[int, ...] = (0,),
    control: q.BenchmarkCleanControl | None = None,
) -> q.BenchmarkRevisionOverwriteProfile:
    return q.BenchmarkRevisionOverwriteProfile(
        fixture=q.BenchmarkFixtureConfig(
            fixture_id=q.REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=REVIEWED_HISTORICAL_HORIZON,
        ),
        severities=severities,
        seeds=seeds,
        research=q.BenchmarkRevisionOverwriteResearch(
            growth_ranking_config=q.GrowthRankingConfig(
                concept_namespace="us-gaap",
                concept="NetIncomeLoss",
                unit="USD",
                prior_period_start=date(2024, 1, 1),
                prior_period_end=date(2024, 3, 31),
                current_period_start=date(2024, 4, 1),
                current_period_end=date(2024, 6, 30),
                research_as_of_date=date(2024, 8, 31),
                top_n=1,
            )
        ),
        clean_control=control,
    )


def single_profile_config(profile: q.BenchmarkProfile, name: str = "focused") -> q.BenchmarkConfig:
    return q.build_benchmark_config(benchmark_name=name, profiles=(profile,))


def case_of(
    config: q.BenchmarkConfig, fault_profile: str, kind: str = "fault"
) -> q.BenchmarkCaseConfig:
    """Return the single expanded case matching one profile and kind."""
    matrix = q.expand_benchmark_cases(config)
    matches = [
        case
        for case in matrix.cases
        if case.fault_profile == fault_profile and case.case_kind == kind
    ]
    assert len(matches) == 1, matches
    return matches[0]


def public_root(output_root: Path) -> Path:
    return Path(output_root) / q.PUBLIC_ROOT_NAME


def private_root(output_root: Path) -> Path:
    return Path(output_root) / q.PRIVATE_ROOT_NAME


def public_bytes(output_root: Path) -> bytes:
    """Concatenate every persisted public byte, for serialized-content scans.

    Privacy assertions run against these bytes rather than against Python
    attributes, because what leaks is what was written to disk.
    """
    chunks = [
        path.read_bytes()
        for path in sorted(public_root(output_root).rglob("*.json"))
        if path.is_file()
    ]
    return b"\n".join(chunks)
