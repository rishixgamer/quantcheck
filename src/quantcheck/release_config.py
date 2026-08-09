"""The exact frozen QuantCheck 0.1 release benchmark configuration.

The release matrix is the smoke benchmark's *already reviewed* per-profile
configuration — same fixtures, same point-in-time horizons, same research
contexts, same detector configuration — expanded along exactly two dimensions:

* every severity (``low``, ``medium``, ``high``) instead of one, and
* the ten reserved final seeds instead of two ordinary ones.

Nothing else is varied. Reusing the reviewed per-profile configuration
verbatim is a deliberate anti-tuning measure: searching over fixture horizons
or research cutoffs to find a release matrix with better numbers is exactly
what a held-out benchmark exists to prevent.

Three of the twelve profile/severity cells have no eligible target on the
reviewed fixture and therefore fail at every seed with ``no_eligible_targets``:

* ``lookahead_timestamp`` at ``high`` needs a 30-day natural filing lag,
* ``revision_overwrite`` at ``medium`` needs a 5% relative revision,
* ``revision_overwrite`` at ``high`` needs a 20% relative revision.

Those are frozen fault-family thresholds meeting a small reviewed synthetic
fixture. They stay in the release matrix and their failures stay visible in
the saved evidence rather than being configured away.

The rehearsal configuration is built from the *same* profile factory with only
the seed dimension replaced, so the Phase B rehearsal and the Phase D release
cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from quantcheck.benchmark_expansion import build_benchmark_config
from quantcheck.benchmark_fixtures import (
    REVIEWED_FIXTURE_ID,
    UNIT_DRIFT_SERIES_FIXTURE_ID,
)
from quantcheck.release_contract import RELEASE_SEEDS, RELEASE_SEVERITIES
from quantcheck.schemas import (
    BenchmarkCleanControl,
    BenchmarkConfig,
    BenchmarkDuplicateProfile,
    BenchmarkDuplicateResearch,
    BenchmarkFixtureConfig,
    BenchmarkLookAheadProfile,
    BenchmarkLookAheadResearch,
    BenchmarkProfile,
    BenchmarkRevisionOverwriteProfile,
    BenchmarkRevisionOverwriteResearch,
    BenchmarkUnitDriftProfile,
    BenchmarkUnitDriftResearch,
    GrowthRankingConfig,
)

__all__ = [
    "REHEARSAL_BENCHMARK_NAME",
    "RELEASE_BENCHMARK_NAME",
    "RELEASE_CONTROL_SEED",
    "rehearsal_benchmark_config",
    "release_benchmark_config",
    "release_matrix_profiles",
]

RELEASE_BENCHMARK_NAME = "quantcheck-0.1-final-release"
REHEARSAL_BENCHMARK_NAME = "quantcheck-0.1-release-rehearsal"

#: Clean controls run at the *lowest* seed of whichever partition is in use. A
#: control injects nothing, so its seed selects no target; pinning it to one
#: seed is what keeps the control count at the frozen one-per-profile policy
#: instead of multiplying it by the seed dimension.
RELEASE_CONTROL_SEED = RELEASE_SEEDS[0]

#: The reviewed fixture's Q1 historical cutoff, reused verbatim from the
#: committed smoke configuration.
_REVIEWED_HISTORICAL_HORIZON = date(2024, 4, 30)
#: A later reviewed horizon where the full duplicate-eligible population exists.
_REVIEWED_LATER_HORIZON = date(2024, 8, 31)
_UNIT_DRIFT_HORIZON = date(2024, 12, 31)
_LOOKAHEAD_RESEARCH_DATE = date(2024, 4, 14)


def release_matrix_profiles(
    *,
    seeds: Sequence[int],
    control_seed: int,
) -> tuple[BenchmarkProfile, ...]:
    """Build the four release profiles over one permitted seed partition.

    This is the single definition of the release matrix's scientific shape.
    Both :func:`release_benchmark_config` and
    :func:`rehearsal_benchmark_config` call it, so the rehearsal exercises the
    exact configuration the release freezes.
    """
    seed_tuple = tuple(seeds)
    lookahead = BenchmarkLookAheadProfile(
        fixture=BenchmarkFixtureConfig(
            fixture_id=REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=_REVIEWED_HISTORICAL_HORIZON,
        ),
        severities=RELEASE_SEVERITIES,
        seeds=seed_tuple,
        research=BenchmarkLookAheadResearch(research_as_of_date=_LOOKAHEAD_RESEARCH_DATE),
        clean_control=BenchmarkCleanControl(severity="medium", seed=control_seed),
    )
    unit_drift = BenchmarkUnitDriftProfile(
        fixture=BenchmarkFixtureConfig(
            fixture_id=UNIT_DRIFT_SERIES_FIXTURE_ID,
            dataset_name="benchmark-unit-drift-series",
            as_of_date=_UNIT_DRIFT_HORIZON,
        ),
        severities=RELEASE_SEVERITIES,
        seeds=seed_tuple,
        research=BenchmarkUnitDriftResearch(research_as_of_date=_UNIT_DRIFT_HORIZON),
        clean_control=BenchmarkCleanControl(severity="medium", seed=control_seed),
    )
    duplicate = BenchmarkDuplicateProfile(
        fixture=BenchmarkFixtureConfig(
            fixture_id=REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=_REVIEWED_LATER_HORIZON,
        ),
        severities=RELEASE_SEVERITIES,
        seeds=seed_tuple,
        research=BenchmarkDuplicateResearch(),
        clean_control=BenchmarkCleanControl(severity="medium", seed=control_seed),
    )
    revision_overwrite = BenchmarkRevisionOverwriteProfile(
        fixture=BenchmarkFixtureConfig(
            fixture_id=REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=_REVIEWED_HISTORICAL_HORIZON,
        ),
        severities=RELEASE_SEVERITIES,
        seeds=seed_tuple,
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
        clean_control=BenchmarkCleanControl(severity="low", seed=control_seed),
    )
    return (lookahead, unit_drift, duplicate, revision_overwrite)


def release_benchmark_config() -> BenchmarkConfig:
    """Build the normalized frozen release benchmark configuration.

    Constructing this requires an active ``quantcheck.release_gate``
    authorization for the complete reserved final seed partition, because every
    profile carries the reserved seeds and the ordinary schema validators
    reject them without one.
    """
    return build_benchmark_config(
        benchmark_name=RELEASE_BENCHMARK_NAME,
        profiles=release_matrix_profiles(
            seeds=RELEASE_SEEDS,
            control_seed=RELEASE_CONTROL_SEED,
        ),
    )


def rehearsal_benchmark_config(seeds: Sequence[int]) -> BenchmarkConfig:
    """Build the release matrix shape over ordinary development/validation seeds.

    This is the Phase B rehearsal configuration: the same per-profile
    fixtures, horizons, severities, research contexts, and control policy as
    :func:`release_benchmark_config`, with the seed dimension replaced. It
    needs no authorization and can therefore run the full release shape end to
    end before any reserved seed exists in any artifact.
    """
    seed_tuple = tuple(seeds)
    if not seed_tuple:
        raise ValueError("the rehearsal requires at least one ordinary seed")
    return build_benchmark_config(
        benchmark_name=REHEARSAL_BENCHMARK_NAME,
        profiles=release_matrix_profiles(
            seeds=seed_tuple,
            control_seed=min(seed_tuple),
        ),
    )
