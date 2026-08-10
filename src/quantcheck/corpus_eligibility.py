"""The v0.2 eligible-unit census.

This module answers, from clean data alone and before any detector is run, the
question the v0.1 held-out benchmark could only answer afterwards: *is every
intended fault/severity cell actually measurable on this corpus?*

It computes nothing of its own. Every count comes from calling the **frozen
v0.1 eligibility computation** — the same function the injector uses to choose
targets and the same one ``benchmark_dispatch.eligible_clean_denominator`` uses
to build a clean control's denominator:

* ``lookahead_timestamp`` — ``lookahead_contract.is_eligible_lookahead_target``
* ``unit_drift`` — ``unit_drift_series.build_comparable_observations``
* ``duplicate_observation`` — singleton groups from
  ``duplicate_fingerprint.build_duplicate_groups``
* ``revision_overwrite`` — ``revision_overwrite_series.build_revision_history_units``

So a v0.2 denominator is directly comparable with a v0.1 one, and a cell that
comes out empty is a statement about the *data*, never about a relaxed rule. No
threshold is touched anywhere in this module.
"""

from __future__ import annotations

from quantcheck.corpus_contract import (
    CORPUS_ELIGIBILITY_UNIT_KINDS,
    CORPUS_FAULT_PROFILES,
    CORPUS_SEVERITIES,
    MINIMUM_CELL_ELIGIBLE_UNITS,
    MINIMUM_PARTITION_ELIGIBLE_UNITS,
)
from quantcheck.corpus_schemas import (
    CorpusDefinition,
    CorpusEligibilityCell,
    CorpusEligibilityCensus,
    CorpusEligibilityRollup,
    CorpusUnitSpec,
)
from quantcheck.duplicate_fingerprint import build_duplicate_groups
from quantcheck.hashing import stable_id
from quantcheck.lookahead_contract import is_eligible_lookahead_target
from quantcheck.point_in_time import build_dataset_snapshot
from quantcheck.revision_overwrite_contract import revision_overwrite_severity_profile
from quantcheck.revision_overwrite_series import build_revision_history_units
from quantcheck.schemas import DatasetSnapshot, FinancialFact, LookAheadInjectionConfig
from quantcheck.unit_drift_series import build_comparable_observations

__all__ = [
    "CENSUS_NAMESPACE",
    "build_census",
    "census_identity_matches",
    "eligible_unit_count",
    "unit_snapshot",
]

CENSUS_NAMESPACE = "quantcheck/corpus-census/v2"

#: The seed the census passes to the frozen Look-Ahead eligibility config.
#:
#: Eligibility does not depend on it — ``is_eligible_lookahead_target`` reads
#: only the severity profile and the research date — but the frozen config
#: requires one. Zero is used so a census can never be mistaken for having
#: explored the seed dimension.
_CENSUS_SEED = 0


def unit_snapshot(
    unit: CorpusUnitSpec,
    records: tuple[FinancialFact, ...],
) -> DatasetSnapshot:
    """Build one unit's clean point-in-time snapshot at its declared horizon."""
    return build_dataset_snapshot(
        records,
        dataset_name=unit.audit_dataset_name,
        as_of_date=unit.horizon.snapshot_as_of_date,
    )


def eligible_unit_count(
    *,
    fault_profile: str,
    severity: str,
    unit: CorpusUnitSpec,
    records: tuple[FinancialFact, ...],
    snapshot: DatasetSnapshot,
) -> int:
    """Count eligible units for one profile/severity on one corpus unit.

    Each branch calls the frozen v0.1 computation and does nothing else. Unit
    Drift and Duplicate Observations take no severity-dependent eligibility
    rule, so their counts are identical across the three severities; that is a
    property of the frozen contracts, not a shortcut taken here.
    """
    if fault_profile == "lookahead_timestamp":
        config = LookAheadInjectionConfig(
            severity=severity,  # type: ignore[arg-type]
            seed=_CENSUS_SEED,
            research_as_of_date=unit.horizon.research_as_of_date,
        )
        return sum(1 for record in snapshot.records if is_eligible_lookahead_target(record, config))
    if fault_profile == "unit_drift":
        return len(build_comparable_observations(snapshot.records, as_of_date=snapshot.as_of_date))
    if fault_profile == "duplicate_observation":
        groups = build_duplicate_groups(snapshot.records, as_of_date=snapshot.as_of_date)
        return sum(1 for group in groups.values() if len(group.records) == 1)
    if fault_profile == "revision_overwrite":
        profile = revision_overwrite_severity_profile(severity)  # type: ignore[arg-type]
        units = build_revision_history_units(
            records,
            clean_snapshot=snapshot,
            minimum_relative_revision_size=profile.minimum_relative_revision_size,
        )
        return len(units)
    raise ValueError(f"unsupported fault profile: {fault_profile!r}")


def _cells_for_unit(
    unit: CorpusUnitSpec,
    records: tuple[FinancialFact, ...],
) -> tuple[CorpusEligibilityCell, ...]:
    snapshot = unit_snapshot(unit, records)
    return tuple(
        CorpusEligibilityCell(
            partition=unit.partition,
            corpus_unit_id=unit.corpus_unit_id,
            fault_profile=profile,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            eligibility_unit_kind=CORPUS_ELIGIBILITY_UNIT_KINDS[profile],
            eligible_unit_count=eligible_unit_count(
                fault_profile=profile,
                severity=severity,
                unit=unit,
                records=records,
                snapshot=snapshot,
            ),
            snapshot_record_count=len(snapshot.records),
        )
        for profile in CORPUS_FAULT_PROFILES
        for severity in CORPUS_SEVERITIES
    )


def build_census(
    corpus: CorpusDefinition,
    *,
    records_by_unit: dict[str, tuple[FinancialFact, ...]],
    partitions: tuple[str, ...] | None = None,
) -> CorpusEligibilityCensus:
    """Build the eligible-unit census over the requested partitions.

    ``records_by_unit`` is supplied by the caller rather than fetched here, so
    that a census over development and validation never needs a held-out
    authorization and a census that *does* cover the held-out partition is
    visibly the caller's decision.

    A unit whose records are absent is skipped rather than assumed empty: an
    external unit that the operator did not supply must not silently contribute
    a zero denominator that reads like a measurement.
    """
    covered = (
        partitions
        if partitions is not None
        else tuple(partition.partition for partition in corpus.partitions)
    )
    cells: list[CorpusEligibilityCell] = []
    for partition_spec in corpus.partitions:
        if partition_spec.partition not in covered:
            continue
        for unit in partition_spec.units:
            records = records_by_unit.get(unit.corpus_unit_id)
            if records is None:
                continue
            cells.extend(_cells_for_unit(unit, records))

    declared = {
        (cell.partition, cell.fault_profile, cell.severity)
        for cell in corpus.declared_unsupported_cells
    }
    rollups: list[CorpusEligibilityRollup] = []
    for partition in covered:
        for profile in CORPUS_FAULT_PROFILES:
            for severity in CORPUS_SEVERITIES:
                matching = [
                    cell
                    for cell in cells
                    if cell.partition == partition
                    and cell.fault_profile == profile
                    and cell.severity == severity
                ]
                total = sum(cell.eligible_unit_count for cell in matching)
                supporting = [cell for cell in matching if cell.eligible_unit_count > 0]
                best = max(
                    supporting,
                    key=lambda cell: (cell.eligible_unit_count, cell.corpus_unit_id),
                    default=None,
                )
                meets_floor = (
                    best is not None
                    and best.eligible_unit_count >= MINIMUM_CELL_ELIGIBLE_UNITS
                    and total >= MINIMUM_PARTITION_ELIGIBLE_UNITS
                )
                if (partition, profile, severity) in declared:
                    status = "declared_unsupported"
                elif meets_floor:
                    status = "eligible"
                else:
                    status = "insufficient"
                rollups.append(
                    CorpusEligibilityRollup(
                        partition=partition,  # type: ignore[arg-type]
                        fault_profile=profile,  # type: ignore[arg-type]
                        severity=severity,  # type: ignore[arg-type]
                        eligibility_unit_kind=CORPUS_ELIGIBILITY_UNIT_KINDS[profile],
                        best_unit_id=best.corpus_unit_id if best is not None else None,
                        best_unit_eligible_count=(
                            best.eligible_unit_count if best is not None else 0
                        ),
                        partition_eligible_total=total,
                        supporting_unit_count=len(supporting),
                        minimum_cell_eligible_units=MINIMUM_CELL_ELIGIBLE_UNITS,
                        minimum_partition_eligible_units=MINIMUM_PARTITION_ELIGIBLE_UNITS,
                        status=status,  # type: ignore[arg-type]
                    )
                )

    body = _census_body(
        corpus_id=corpus.corpus_id,
        spec_version=corpus.spec_version,
        cells=tuple(cells),
        rollups=tuple(rollups),
        covered_partitions=tuple(covered),
    )
    # Validate once to obtain the normalized (sorted) form, then hash that
    # rather than the order the loops happened to build.
    normalized = CorpusEligibilityCensus.model_validate(
        {"census_id": stable_id(prefix="cens", namespace=CENSUS_NAMESPACE, payload=body), **body}
    )
    settled = _census_body(
        corpus_id=normalized.corpus_id,
        spec_version=normalized.spec_version,
        cells=normalized.cells,
        rollups=normalized.rollups,
        covered_partitions=normalized.covered_partitions,
    )
    return CorpusEligibilityCensus.model_validate(
        {
            "census_id": stable_id(prefix="cens", namespace=CENSUS_NAMESPACE, payload=settled),
            **settled,
        }
    )


def _census_body(
    *,
    corpus_id: str,
    spec_version: str,
    cells: tuple[CorpusEligibilityCell, ...],
    rollups: tuple[CorpusEligibilityRollup, ...],
    covered_partitions: tuple[str, ...],
) -> dict[str, object]:
    return {
        "corpus_id": corpus_id,
        "spec_version": spec_version,
        "cells": cells,
        "rollups": rollups,
        "covered_partitions": covered_partitions,
    }


def census_identity_matches(census: CorpusEligibilityCensus) -> bool:
    """Report whether a census's stored identifier matches its content."""
    body = _census_body(
        corpus_id=census.corpus_id,
        spec_version=census.spec_version,
        cells=census.cells,
        rollups=census.rollups,
        covered_partitions=census.covered_partitions,
    )
    return census.census_id == stable_id(prefix="cens", namespace=CENSUS_NAMESPACE, payload=body)
