"""The explicit trust boundary between a clean snapshot and a detector.

:func:`sanitize_for_audit` is the only supported way to produce an
:class:`~quantcheck.schemas.AuditInputSnapshot`. It reads only the fields
:class:`~quantcheck.schemas.AuditInputRecord` declares, so it cannot carry a
fixture seed, a revision-lineage marker, an entity's free-text name, a
source's internal row key, or any other field ``AuditInputRecord`` does not
list. It is a projection, not a filter: every hard decision (which revision
is visible, which records are eligible) has already been made by
:mod:`quantcheck.point_in_time`.
"""

from __future__ import annotations

from quantcheck.hashing import audit_input_snapshot_id
from quantcheck.schemas import AuditInputRecord, AuditInputSnapshot, DatasetSnapshot, FinancialFact

__all__ = ["sanitize_for_audit"]


def _sanitize_record(record: FinancialFact) -> AuditInputRecord:
    return AuditInputRecord(
        record_id=record.record_id,
        entity_id=record.entity_id,
        concept_namespace=record.concept_namespace,
        concept=record.concept,
        value=record.value,
        unit=record.unit,
        dimensions=record.dimensions,
        period_type=record.period_type,
        period_start=record.period_start,
        period_end=record.period_end,
        filed_on=record.filed_on,
        available_on=record.available_on,
        form=record.form,
        accession_number=record.accession_number,
        source_name=record.source.source_name,
        source_locator=record.source.source_locator,
    )


def sanitize_for_audit(snapshot: DatasetSnapshot) -> AuditInputSnapshot:
    """Convert a clean :class:`DatasetSnapshot` into a sanitized audit input.

    Only reads ``snapshot``; never mutates it. The resulting records carry no
    ``entity_name`` and no ``source_row_key`` — in particular, this drops any
    revision-lineage marker declared there, since that marker is exactly the
    kind of answer-key information a manifest-blind detector must not see.
    Record order is deterministic regardless of the input order, because
    both ``DatasetSnapshot.records`` and ``AuditInputSnapshot.records`` are
    sorted by ``record_id`` during validation.
    """
    records = tuple(_sanitize_record(record) for record in snapshot.records)
    audit_input_id = audit_input_snapshot_id(
        dataset_name=snapshot.dataset_name,
        as_of_date=snapshot.as_of_date,
        records=records,
    )
    return AuditInputSnapshot(
        audit_input_id=audit_input_id,
        dataset_name=snapshot.dataset_name,
        as_of_date=snapshot.as_of_date,
        records=records,
    )
