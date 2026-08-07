"""Explicit adjacent revision-history construction for Revision Overwrite."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal, localcontext

from quantcheck.hashing import canonical_sha256, revision_history_unit_id, revision_id
from quantcheck.point_in_time import (
    AmbiguousRevisionHistoryError,
    parse_declared_revision_lineage,
)
from quantcheck.revision_overwrite_contract import (
    REVISION_OVERWRITE_PROVENANCE_NAMESPACE,
    REVISION_OVERWRITE_SPEC_VERSION,
)
from quantcheck.schemas import (
    AuditInputRecord,
    DatasetSnapshot,
    EconomicFactKey,
    FinancialFact,
    RevisionHistoryUnit,
)

__all__ = [
    "build_revision_history_units",
    "economic_fact_key",
    "public_revision_provenance_hash",
    "revision_history_unit_body",
]


def economic_fact_key(record: FinancialFact | AuditInputRecord) -> EconomicFactKey:
    """Return the exact context already enforced by point-in-time lineage selection."""
    return EconomicFactKey(
        entity_id=record.entity_id,
        concept_namespace=record.concept_namespace,
        concept=record.concept,
        unit=record.unit,
        dimensions=record.dimensions,
        period_type=record.period_type,
        period_start=record.period_start,
        period_end=record.period_end,
    )


def public_revision_provenance_hash(record: FinancialFact | AuditInputRecord) -> str:
    """Hash only provenance fields available on the sanitized audit boundary."""
    source_name = (
        record.source.source_name if isinstance(record, FinancialFact) else record.source_name
    )
    source_locator = (
        record.source.source_locator if isinstance(record, FinancialFact) else record.source_locator
    )
    return canonical_sha256(
        {
            "namespace": REVISION_OVERWRITE_PROVENANCE_NAMESPACE,
            "spec_version": REVISION_OVERWRITE_SPEC_VERSION,
            "record_id": record.record_id,
            "economic_fact_key": economic_fact_key(record),
            "observed_value": record.value,
            "available_on": record.available_on,
            "filed_on": record.filed_on,
            "accession_number": record.accession_number,
            "form": record.form,
            "source_name": source_name,
            "source_locator": source_locator,
        }
    )


def revision_history_unit_body(
    *,
    lineage_id: str,
    economic_key: EconomicFactKey,
    snapshot_as_of_date: date,
    historical_sequence: int,
    later_sequence: int,
    historical_revision_id: str,
    later_revision_id: str,
    historical_record: FinancialFact,
    later_record: FinancialFact,
    relative_revision_size: Decimal,
) -> dict[str, object]:
    """Canonical body covered by a revision history-unit identity."""
    return {
        "lineage_id": lineage_id,
        "economic_fact_key": economic_key,
        "snapshot_as_of_date": snapshot_as_of_date,
        "historical_sequence": historical_sequence,
        "later_sequence": later_sequence,
        "historical_revision_id": historical_revision_id,
        "later_revision_id": later_revision_id,
        "historical_record": historical_record,
        "later_record": later_record,
        "relative_revision_size": relative_revision_size,
    }


def _validate_lineage(
    lineage_id: str,
    members: list[tuple[int, FinancialFact]],
) -> tuple[tuple[int, FinancialFact], ...]:
    sequences = [sequence for sequence, _record in members]
    if len(set(sequences)) != len(sequences):
        raise AmbiguousRevisionHistoryError(
            f"revision lineage {lineage_id!r} declares duplicate sequence numbers"
        )
    ordered = tuple(sorted(members, key=lambda item: item[0]))
    reference_key = economic_fact_key(ordered[0][1])
    reference_entity_name = ordered[0][1].entity_name
    reference_source_name = ordered[0][1].source.source_name
    previous_available: date | None = None
    previous_filed: date | None = None
    for sequence, record in ordered:
        if economic_fact_key(record) != reference_key:
            raise AmbiguousRevisionHistoryError(
                f"revision lineage {lineage_id!r} mixes different economic facts"
            )
        if record.entity_name != reference_entity_name:
            raise AmbiguousRevisionHistoryError(
                f"revision lineage {lineage_id!r} changes entity_name"
            )
        if record.source.source_name != reference_source_name:
            raise AmbiguousRevisionHistoryError(
                f"revision lineage {lineage_id!r} changes source_name"
            )
        if previous_available is not None and record.available_on < previous_available:
            raise AmbiguousRevisionHistoryError(
                f"revision lineage {lineage_id!r} sequence {sequence} "
                "has non-monotonic availability"
            )
        if previous_filed is not None and record.filed_on < previous_filed:
            raise AmbiguousRevisionHistoryError(
                f"revision lineage {lineage_id!r} sequence {sequence} has non-monotonic filing"
            )
        previous_available = record.available_on
        previous_filed = record.filed_on
    return ordered


def build_revision_history_units(
    source_records: Sequence[FinancialFact],
    *,
    clean_snapshot: DatasetSnapshot,
    minimum_relative_revision_size: Decimal,
) -> tuple[RevisionHistoryUnit, ...]:
    """Build exact eligible historical/next-revision pairs.

    Independent occurrences are ignored. A declared history is rejected when
    its source order is ambiguous; unsupported but unambiguous pairs are
    simply ineligible. The caller-owned source sequence and models are never
    modified.
    """
    record_ids = [record.record_id for record in source_records]
    if len(set(record_ids)) != len(record_ids):
        raise AmbiguousRevisionHistoryError("full source history has duplicate record IDs")

    grouped: dict[str, list[tuple[int, FinancialFact]]] = {}
    for record in source_records:
        lineage = parse_declared_revision_lineage(record.source.source_row_key)
        if lineage is not None:
            grouped.setdefault(lineage.lineage_id, []).append((lineage.sequence, record))

    clean_by_id = {record.record_id: record for record in clean_snapshot.records}
    units: list[RevisionHistoryUnit] = []
    for lineage_id in sorted(grouped):
        ordered = _validate_lineage(lineage_id, grouped[lineage_id])
        visible_indexes = [
            index
            for index, (_sequence, record) in enumerate(ordered)
            if record.available_on <= clean_snapshot.as_of_date
        ]
        if not visible_indexes:
            continue
        historical_index = visible_indexes[-1]
        later_index = historical_index + 1
        if later_index >= len(ordered):
            continue
        historical_sequence, historical = ordered[historical_index]
        later_sequence, later = ordered[later_index]

        if historical_sequence + 1 != later_sequence:
            continue
        if clean_by_id.get(historical.record_id) != historical:
            raise AmbiguousRevisionHistoryError(
                f"clean snapshot does not contain the expected visible revision for {lineage_id!r}"
            )
        if later.record_id in clean_by_id:
            raise AmbiguousRevisionHistoryError(
                f"clean snapshot already contains the unavailable later revision for {lineage_id!r}"
            )
        if historical.available_on != historical.filed_on:
            continue
        if later.available_on != later.filed_on:
            continue
        if not historical.available_on <= clean_snapshot.as_of_date < later.available_on:
            continue
        if later.available_on <= historical.available_on:
            continue
        if later.filed_on <= historical.filed_on:
            continue
        if historical.accession_number is None or later.accession_number is None:
            continue
        if historical.accession_number == later.accession_number:
            continue
        if historical.source.source_row_key == later.source.source_row_key:
            continue
        if historical.value == 0 or historical.value == later.value:
            continue

        with localcontext() as context:
            context.prec = 50
            relative_size = abs(later.value - historical.value) / abs(historical.value)
        if relative_size < minimum_relative_revision_size:
            continue

        economic_key = economic_fact_key(historical)
        historical_revision = revision_id(lineage_id=lineage_id, sequence=historical_sequence)
        later_revision = revision_id(lineage_id=lineage_id, sequence=later_sequence)
        body = revision_history_unit_body(
            lineage_id=lineage_id,
            economic_key=economic_key,
            snapshot_as_of_date=clean_snapshot.as_of_date,
            historical_sequence=historical_sequence,
            later_sequence=later_sequence,
            historical_revision_id=historical_revision,
            later_revision_id=later_revision,
            historical_record=historical,
            later_record=later,
            relative_revision_size=relative_size,
        )
        units.append(
            RevisionHistoryUnit.model_validate(
                {
                    "eligibility_unit_id": revision_history_unit_id(unit_body=body),
                    **body,
                }
            )
        )
    return tuple(sorted(units, key=lambda unit: unit.eligibility_unit_id))
