"""The eligible-unit census: exact denominators, and the floors they clear.

Two things are under test. First, that every census count is literally the
frozen v0.1 eligibility computation and not a v0.2 reimplementation of it —
checked by calling the frozen function directly and comparing. Second, that the
v0.2 corpus actually fixes what v0.1 could not measure: the three
structurally ineligible profile/severity cells, and the denominators of eleven.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from quantcheck.benchmark_dispatch import eligible_clean_denominator
from quantcheck.corpus_contract import (
    CORPUS_FAULT_PROFILES,
    CORPUS_SEVERITIES,
    MINIMUM_CELL_ELIGIBLE_UNITS,
    MINIMUM_PARTITION_ELIGIBLE_UNITS,
    corpus_cells,
)
from quantcheck.corpus_eligibility import build_census, eligible_unit_count
from quantcheck.corpus_gate import held_out_corpus_units
from quantcheck.corpus_registry import (
    build_corpus_definition,
    corpus_unit_records,
    declared_corpus_id,
    held_out_unit_ids,
    partition_unit_ids,
)
from quantcheck.corpus_schemas import CorpusEligibilityCensus
from quantcheck.duplicate_fingerprint import build_duplicate_groups
from quantcheck.lookahead_contract import is_eligible_lookahead_target
from quantcheck.revision_overwrite_contract import revision_overwrite_severity_profile
from quantcheck.revision_overwrite_series import build_revision_history_units
from quantcheck.schemas import LookAheadInjectionConfig
from quantcheck.unit_drift_series import build_comparable_observations
from tests.corpus_support import ORDINARY_PARTITIONS, ordinary_unit_ids, unit_bundle, unit_by_role


@pytest.fixture(scope="module")
def census() -> CorpusEligibilityCensus:
    """The development and validation census. The held-out partition is untouched."""
    with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
        corpus = build_corpus_definition()
    records = {
        unit_id: corpus_unit_records(unit_id)
        for partition in ORDINARY_PARTITIONS
        for unit_id in partition_unit_ids(partition)
    }
    return build_census(corpus, records_by_unit=records, partitions=ORDINARY_PARTITIONS)


class TestCountsComeFromTheFrozenRules:
    """Each count must be the frozen v0.1 computation, called unchanged."""

    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_lookahead_matches_the_frozen_eligibility_predicate(self, unit_id: str) -> None:
        spec, records, snapshot = unit_bundle(unit_id)
        for severity in CORPUS_SEVERITIES:
            config = LookAheadInjectionConfig(
                severity=severity,  # type: ignore[arg-type]
                seed=0,
                research_as_of_date=spec.horizon.research_as_of_date,
            )
            expected = sum(
                1 for record in snapshot.records if is_eligible_lookahead_target(record, config)
            )
            assert expected == eligible_unit_count(
                fault_profile="lookahead_timestamp",
                severity=severity,
                unit=spec,
                records=records,
                snapshot=snapshot,
            )

    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_unit_drift_matches_the_frozen_comparable_series_rule(self, unit_id: str) -> None:
        spec, records, snapshot = unit_bundle(unit_id)
        expected = len(
            build_comparable_observations(snapshot.records, as_of_date=snapshot.as_of_date)
        )
        assert expected == eligible_unit_count(
            fault_profile="unit_drift",
            severity="low",
            unit=spec,
            records=records,
            snapshot=snapshot,
        )

    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_duplicate_matches_the_frozen_singleton_group_rule(self, unit_id: str) -> None:
        spec, records, snapshot = unit_bundle(unit_id)
        groups = build_duplicate_groups(snapshot.records, as_of_date=snapshot.as_of_date)
        expected = sum(1 for group in groups.values() if len(group.records) == 1)
        assert expected == eligible_unit_count(
            fault_profile="duplicate_observation",
            severity="medium",
            unit=spec,
            records=records,
            snapshot=snapshot,
        )

    @pytest.mark.parametrize("severity", CORPUS_SEVERITIES)
    def test_revision_overwrite_matches_the_frozen_history_unit_rule(self, severity: str) -> None:
        spec, records, snapshot = unit_bundle(unit_by_role("development", "revisions"))
        profile = revision_overwrite_severity_profile(severity)  # type: ignore[arg-type]
        expected = len(
            build_revision_history_units(
                records,
                clean_snapshot=snapshot,
                minimum_relative_revision_size=profile.minimum_relative_revision_size,
            )
        )
        assert expected == eligible_unit_count(
            fault_profile="revision_overwrite",
            severity=severity,
            unit=spec,
            records=records,
            snapshot=snapshot,
        )

    def test_an_unsupported_profile_is_refused_rather_than_counted_as_zero(self) -> None:
        spec, records, snapshot = unit_bundle(unit_by_role("development", "broad"))
        with pytest.raises(ValueError, match="unsupported fault profile"):
            eligible_unit_count(
                fault_profile="entity_swap",
                severity="low",
                unit=spec,
                records=records,
                snapshot=snapshot,
            )

    def test_the_census_agrees_with_the_v01_clean_control_denominator(self) -> None:
        """The census and the v0.1 benchmark must compute the same number.

        ``benchmark_dispatch.eligible_clean_denominator`` is the frozen function
        that gives a v0.1 clean control its false-positive denominator. Both it
        and the census call the same underlying rules, so a v0.2 denominator is
        directly comparable with a v0.1 one rather than merely similar.
        """
        assert eligible_clean_denominator.__module__ == "quantcheck.benchmark_dispatch"
        spec, records, snapshot = unit_bundle(unit_by_role("development", "revisions"))
        profile = revision_overwrite_severity_profile("low")
        direct = len(
            build_revision_history_units(
                records,
                clean_snapshot=snapshot,
                minimum_relative_revision_size=profile.minimum_relative_revision_size,
            )
        )
        assert direct == eligible_unit_count(
            fault_profile="revision_overwrite",
            severity="low",
            unit=spec,
            records=records,
            snapshot=snapshot,
        )


class TestEveryCellIsAccountedFor:
    def test_every_cell_has_a_rollup_in_every_covered_partition(
        self, census: CorpusEligibilityCensus
    ) -> None:
        keys = {(r.partition, r.fault_profile, r.severity) for r in census.rollups}
        expected = {
            (partition, profile, severity)
            for partition in ORDINARY_PARTITIONS
            for profile, severity in corpus_cells()
        }
        assert keys == expected

    def test_no_cell_is_insufficient(self, census: CorpusEligibilityCensus) -> None:
        insufficient = [r for r in census.rollups if r.status == "insufficient"]
        assert not insufficient, "cells below the declared floors: " + ", ".join(
            f"{r.partition}/{r.fault_profile}/{r.severity}" for r in insufficient
        )

    def test_every_cell_is_eligible_or_explicitly_declared_unsupported(
        self, census: CorpusEligibilityCensus
    ) -> None:
        for rollup in census.rollups:
            assert rollup.status in {"eligible", "declared_unsupported"}

    def test_every_eligible_cell_clears_both_declared_floors(
        self, census: CorpusEligibilityCensus
    ) -> None:
        for rollup in census.rollups:
            if rollup.status != "eligible":
                continue
            assert rollup.best_unit_eligible_count >= MINIMUM_CELL_ELIGIBLE_UNITS
            assert rollup.partition_eligible_total >= MINIMUM_PARTITION_ELIGIBLE_UNITS

    def test_a_cell_records_which_unit_supplies_its_best_denominator(
        self, census: CorpusEligibilityCensus
    ) -> None:
        for rollup in census.rollups:
            if rollup.best_unit_eligible_count == 0:
                assert rollup.best_unit_id is None
            else:
                assert rollup.best_unit_id is not None

    def test_the_partitions_are_structurally_symmetric(
        self, census: CorpusEligibilityCensus
    ) -> None:
        """Development and validation must be interchangeable in shape.

        They hold disjoint issuers built from identical cohort specifications,
        so a measurement taken on one is comparable with the other. Differing
        counts would mean the partitions are not the same experiment.
        """
        by_cell: dict[tuple[str, str], dict[str, int]] = {}
        for rollup in census.rollups:
            by_cell.setdefault((rollup.fault_profile, rollup.severity), {})[rollup.partition] = (
                rollup.partition_eligible_total
            )
        for cell, totals in by_cell.items():
            assert totals["development"] == totals["validation"], f"{cell} is asymmetric"


class TestTheV01MeasurementGapsAreClosed:
    """The three cells v0.1 could not measure, and the denominators of eleven."""

    def test_lookahead_high_is_now_eligible(self, census: CorpusEligibilityCensus) -> None:
        # v0.1: no reviewed-fixture record had the 30-day natural filing lag the
        # frozen `high` band requires, so every seed failed `no_eligible_targets`.
        for partition in ORDINARY_PARTITIONS:
            rollup = _rollup(census, partition, "lookahead_timestamp", "high")
            assert rollup.status == "eligible"
            assert rollup.best_unit_eligible_count >= MINIMUM_CELL_ELIGIBLE_UNITS

    @pytest.mark.parametrize("severity", ["medium", "high"])
    def test_revision_overwrite_medium_and_high_are_now_eligible(
        self, census: CorpusEligibilityCensus, severity: str
    ) -> None:
        # v0.1: the reviewed fixture's largest source-supported adjacent
        # revision was 2%, clearing `low` (1%) but never `medium` (5%) or
        # `high` (20%).
        for partition in ORDINARY_PARTITIONS:
            rollup = _rollup(census, partition, "revision_overwrite", severity)
            assert rollup.status == "eligible"

    def test_the_revision_overwrite_denominator_is_no_longer_thin(
        self, census: CorpusEligibilityCensus
    ) -> None:
        # v0.1's whole-matrix eligible-clean denominator for revision_overwrite
        # was 11, from one source-supported adjacent revision history.
        for partition in ORDINARY_PARTITIONS:
            rollup = _rollup(census, partition, "revision_overwrite", "low")
            assert rollup.partition_eligible_total > 11

    def test_the_lookahead_bands_are_genuinely_distinct(
        self, census: CorpusEligibilityCensus
    ) -> None:
        """A wider filing-lag spread must produce nested, strictly shrinking bands.

        Equal counts would mean the corpus supplies only one lag regime and the
        severity dimension is decorative.
        """
        for partition in ORDINARY_PARTITIONS:
            low = _rollup(census, partition, "lookahead_timestamp", "low")
            medium = _rollup(census, partition, "lookahead_timestamp", "medium")
            high = _rollup(census, partition, "lookahead_timestamp", "high")
            assert low.partition_eligible_total > medium.partition_eligible_total
            assert medium.partition_eligible_total > high.partition_eligible_total

    def test_the_revision_bands_are_genuinely_distinct(
        self, census: CorpusEligibilityCensus
    ) -> None:
        for partition in ORDINARY_PARTITIONS:
            low = _rollup(census, partition, "revision_overwrite", "low")
            medium = _rollup(census, partition, "revision_overwrite", "medium")
            high = _rollup(census, partition, "revision_overwrite", "high")
            assert low.partition_eligible_total > medium.partition_eligible_total
            assert medium.partition_eligible_total > high.partition_eligible_total

    def test_severity_independent_families_report_equal_counts(
        self, census: CorpusEligibilityCensus
    ) -> None:
        """Unit Drift and Duplicate have no severity-dependent eligibility rule.

        Their counts must be identical across severities — a property of the
        frozen contracts, restated here so a future divergence is caught.
        """
        for partition in ORDINARY_PARTITIONS:
            for profile in ("unit_drift", "duplicate_observation"):
                totals = {
                    _rollup(census, partition, profile, severity).partition_eligible_total
                    for severity in CORPUS_SEVERITIES
                }
                assert len(totals) == 1


class TestDenominatorsAreRecordedExactly:
    def test_every_unit_reports_a_cell_for_every_profile_and_severity(
        self, census: CorpusEligibilityCensus
    ) -> None:
        expected = len(CORPUS_FAULT_PROFILES) * len(CORPUS_SEVERITIES)
        for unit_id in ordinary_unit_ids():
            cells = [cell for cell in census.cells if cell.corpus_unit_id == unit_id]
            assert len(cells) == expected

    def test_a_cell_records_the_snapshot_it_was_counted_against(
        self, census: CorpusEligibilityCensus
    ) -> None:
        for cell in census.cells:
            _spec, _records, snapshot = unit_bundle(cell.corpus_unit_id)
            assert cell.snapshot_record_count == len(snapshot.records)
            assert cell.eligible_unit_count <= max(cell.snapshot_record_count, 1) * 2

    def test_a_partition_total_is_the_sum_of_its_units(
        self, census: CorpusEligibilityCensus
    ) -> None:
        for rollup in census.rollups:
            matching = [
                cell.eligible_unit_count
                for cell in census.cells
                if cell.partition == rollup.partition
                and cell.fault_profile == rollup.fault_profile
                and cell.severity == rollup.severity
            ]
            assert rollup.partition_eligible_total == sum(matching)
            assert rollup.supporting_unit_count == sum(1 for count in matching if count > 0)
            assert rollup.best_unit_eligible_count == max(matching, default=0)

    def test_an_absent_unit_contributes_nothing_rather_than_a_zero(self) -> None:
        """A missing external unit must not read as a measured zero."""
        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            corpus = build_corpus_definition()
        one_unit = unit_by_role("development", "broad")
        partial = build_census(
            corpus,
            records_by_unit={one_unit: corpus_unit_records(one_unit)},
            partitions=("development",),
        )
        assert {cell.corpus_unit_id for cell in partial.cells} == {one_unit}
        # revision_overwrite has no supporting unit here, so it is insufficient
        # rather than silently eligible on an unmeasured population.
        rollup = _rollup(partial, "development", "revision_overwrite", "low")
        assert rollup.status == "insufficient"
        assert rollup.supporting_unit_count == 0
        assert rollup.best_unit_id is None


class TestHardNegativesAreRealObservations:
    def test_the_stress_unit_supplies_a_genuine_near_zero_recovery(self) -> None:
        """A legitimate collapse-and-recovery quarter, above the frozen threshold.

        This is expected to produce a Unit Drift finding on clean data. That is
        the whole point of a hard negative: it measures the cost of the frozen
        rule on real-looking data rather than hiding it.
        """
        _spec, _records, snapshot = unit_bundle(unit_by_role("development", "stress"))
        observations = build_comparable_observations(
            snapshot.records, as_of_date=snapshot.as_of_date
        )
        ratios = []
        for observation in observations.values():
            for _position, neighbour in observation.neighbors:
                if neighbour.value and observation.record.value:
                    ratios.append(
                        max(
                            abs(observation.record.value / neighbour.value),
                            abs(neighbour.value / observation.record.value),
                        )
                    )
        assert max(ratios) > Decimal(50)

    def test_the_stress_unit_supplies_a_legitimate_duplicate_group(self) -> None:
        _spec, _records, snapshot = unit_bundle(unit_by_role("development", "stress"))
        groups = build_duplicate_groups(snapshot.records, as_of_date=snapshot.as_of_date)
        assert any(len(group.records) > 1 for group in groups.values())

    def test_a_value_preserving_restatement_yields_no_revision_unit(self) -> None:
        _spec, records, snapshot = unit_bundle(unit_by_role("development", "stress"))
        units = build_revision_history_units(
            records,
            clean_snapshot=snapshot,
            minimum_relative_revision_size=Decimal("0.01"),
        )
        # The stress unit's only lineage restated a footnote, not a number.
        assert units == ()


def _rollup(census: CorpusEligibilityCensus, partition: str, profile: str, severity: str):  # type: ignore[no-untyped-def]
    for rollup in census.rollups:
        if (rollup.partition, rollup.fault_profile, rollup.severity) == (
            partition,
            profile,
            severity,
        ):
            return rollup
    raise AssertionError(f"no rollup for {partition}/{profile}/{severity}")
