"""The offline Milestone 8 smoke benchmark.

Twelve cases: four fault profiles at one development seed (``0``), the same
four at one validation seed (``100``), and one clean control per profile. It
exercises the four-family dispatcher, the four-detector run, public/private
persistence, resume, and public-only aggregation, entirely offline.

Two configuration choices are forced by current repository behavior rather than
chosen for convenience, and both are recorded in ``docs/DECISIONS.md``:

* **Unit Drift runs on the benchmark series fixture, not the reviewed one.**
  Unit Drift eligibility requires a comparable series of at least three
  observations (``quantcheck.unit_drift_series``); the reviewed fixture has two
  periods per series and is a documented *insufficient-history control* with no
  eligible target at any severity or horizon.
* **Revision Overwrite runs at ``low`` severity.** The reviewed fixture's only
  source-supported adjacent history has a 2% relative revision, which clears
  the ``low`` threshold (1%) but not ``medium`` (5%). Every other profile runs
  at ``medium``.

No headline metric is hard-coded here. The smoke's numbers are whatever the
rebuilt implementation produces.
"""

from __future__ import annotations

from datetime import date

from quantcheck.benchmark_expansion import build_benchmark_config
from quantcheck.benchmark_fixtures import (
    REVIEWED_FIXTURE_ID,
    UNIT_DRIFT_SERIES_FIXTURE_ID,
)
from quantcheck.schemas import (
    BenchmarkCleanControl,
    BenchmarkConfig,
    BenchmarkDuplicateProfile,
    BenchmarkDuplicateResearch,
    BenchmarkFixtureConfig,
    BenchmarkLookAheadProfile,
    BenchmarkLookAheadResearch,
    BenchmarkRevisionOverwriteProfile,
    BenchmarkRevisionOverwriteResearch,
    BenchmarkUnitDriftProfile,
    BenchmarkUnitDriftResearch,
    GrowthRankingConfig,
)

__all__ = [
    "SMOKE_BENCHMARK_NAME",
    "SMOKE_CASE_COUNT",
    "SMOKE_DEVELOPMENT_SEED",
    "SMOKE_VALIDATION_SEED",
    "smoke_benchmark_config",
]

SMOKE_BENCHMARK_NAME = "quantcheck-milestone8-smoke"
SMOKE_DEVELOPMENT_SEED = 0
SMOKE_VALIDATION_SEED = 100
SMOKE_CASE_COUNT = 12

_SMOKE_SEEDS = (SMOKE_DEVELOPMENT_SEED, SMOKE_VALIDATION_SEED)

#: The reviewed fixture's Q1 historical cutoff: the state in which a later Q1
#: vintage can still be substituted, and in which Look-Ahead's period-end
#: substitution has visible targets.
_REVIEWED_HISTORICAL_HORIZON = date(2024, 4, 30)
#: A later reviewed horizon where the full duplicate-eligible population exists.
_REVIEWED_LATER_HORIZON = date(2024, 8, 31)
_UNIT_DRIFT_HORIZON = date(2024, 12, 31)


def smoke_benchmark_config() -> BenchmarkConfig:
    """Build the normalized 12-case offline smoke benchmark configuration."""
    lookahead = BenchmarkLookAheadProfile(
        fixture=BenchmarkFixtureConfig(
            fixture_id=REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=_REVIEWED_HISTORICAL_HORIZON,
        ),
        severities=("medium",),
        seeds=_SMOKE_SEEDS,
        research=BenchmarkLookAheadResearch(research_as_of_date=date(2024, 4, 14)),
        clean_control=BenchmarkCleanControl(severity="medium", seed=SMOKE_DEVELOPMENT_SEED),
    )
    unit_drift = BenchmarkUnitDriftProfile(
        fixture=BenchmarkFixtureConfig(
            fixture_id=UNIT_DRIFT_SERIES_FIXTURE_ID,
            dataset_name="benchmark-unit-drift-series",
            as_of_date=_UNIT_DRIFT_HORIZON,
        ),
        severities=("medium",),
        seeds=_SMOKE_SEEDS,
        research=BenchmarkUnitDriftResearch(research_as_of_date=_UNIT_DRIFT_HORIZON),
        clean_control=BenchmarkCleanControl(severity="medium", seed=SMOKE_DEVELOPMENT_SEED),
    )
    duplicate = BenchmarkDuplicateProfile(
        fixture=BenchmarkFixtureConfig(
            fixture_id=REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=_REVIEWED_LATER_HORIZON,
        ),
        severities=("medium",),
        seeds=_SMOKE_SEEDS,
        research=BenchmarkDuplicateResearch(),
        clean_control=BenchmarkCleanControl(severity="medium", seed=SMOKE_DEVELOPMENT_SEED),
    )
    revision_overwrite = BenchmarkRevisionOverwriteProfile(
        fixture=BenchmarkFixtureConfig(
            fixture_id=REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=_REVIEWED_HISTORICAL_HORIZON,
        ),
        severities=("low",),
        seeds=_SMOKE_SEEDS,
        research=BenchmarkRevisionOverwriteResearch(
            growth_ranking_config=GrowthRankingConfig(
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
        clean_control=BenchmarkCleanControl(severity="low", seed=SMOKE_DEVELOPMENT_SEED),
    )
    return build_benchmark_config(
        benchmark_name=SMOKE_BENCHMARK_NAME,
        profiles=(lookahead, unit_drift, duplicate, revision_overwrite),
    )
