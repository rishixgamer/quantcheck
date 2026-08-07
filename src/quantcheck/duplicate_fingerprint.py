"""Exact duplicate-fingerprint construction and grouping.

One canonical fingerprint representation (:class:`DuplicateFingerprint`) is
shared by injection eligibility and manifest-blind detection, so a generated
copy's record ID can never prevent it from grouping with its source
occurrence, and injection eligibility never diverges from what the detector
can actually observe.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from quantcheck.duplicate_contract import DUPLICATE_FINGERPRINT_NAMESPACE, DUPLICATE_SPEC_VERSION
from quantcheck.hashing import canonical_sha256
from quantcheck.schemas import AuditInputRecord, DuplicateFingerprint, FinancialFact

__all__ = [
    "DuplicateGroup",
    "build_duplicate_groups",
    "duplicate_fingerprint",
    "duplicate_fingerprint_hash",
]


def _source_name(record: FinancialFact | AuditInputRecord) -> str:
    if isinstance(record, FinancialFact):
        return record.source.source_name
    return record.source_name


def _source_locator(record: FinancialFact | AuditInputRecord) -> str:
    if isinstance(record, FinancialFact):
        return record.source.source_locator
    return record.source_locator


def duplicate_fingerprint(record: FinancialFact | AuditInputRecord) -> DuplicateFingerprint:
    """Build the exact semantic fingerprint shared by injection and detection."""
    return DuplicateFingerprint(
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
        accession_number=record.accession_number,
        source_name=_source_name(record),
        source_locator=_source_locator(record),
    )


def duplicate_fingerprint_hash(fingerprint: DuplicateFingerprint) -> str:
    """Return the full SHA-256 hash of one canonical fingerprint."""
    return canonical_sha256(
        {
            "namespace": DUPLICATE_FINGERPRINT_NAMESPACE,
            "spec_version": DUPLICATE_SPEC_VERSION,
            "fingerprint": fingerprint,
        }
    )


@dataclass(frozen=True, slots=True)
class DuplicateGroup[RecordT: (FinancialFact, AuditInputRecord)]:
    """All visible records sharing one exact fingerprint."""

    fingerprint: DuplicateFingerprint
    fingerprint_hash: str
    records: tuple[RecordT, ...]


def build_duplicate_groups[RecordT: (FinancialFact, AuditInputRecord)](
    records: Sequence[RecordT],
    *,
    as_of_date: date,
) -> dict[str, DuplicateGroup[RecordT]]:
    """Group end-of-day-visible records by exact fingerprint hash.

    Grouping keys on the fingerprint hash rather than record position, so the
    result is independent of input order. Members within a group are sorted
    by ``record_id``.
    """
    grouped: dict[str, list[RecordT]] = {}
    fingerprints: dict[str, DuplicateFingerprint] = {}
    for record in records:
        if record.available_on > as_of_date:
            continue
        fingerprint = duplicate_fingerprint(record)
        fingerprint_hash = duplicate_fingerprint_hash(fingerprint)
        grouped.setdefault(fingerprint_hash, []).append(record)
        fingerprints[fingerprint_hash] = fingerprint

    return {
        fingerprint_hash: DuplicateGroup(
            fingerprint=fingerprints[fingerprint_hash],
            fingerprint_hash=fingerprint_hash,
            records=tuple(sorted(members, key=lambda record: record.record_id)),
        )
        for fingerprint_hash, members in sorted(grouped.items(), key=lambda item: item[0])
    }
