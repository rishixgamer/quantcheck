"""Deterministic exact-occurrence-copy Duplicate Observations injection.

The public detector never imports this module. It returns a corrupted
snapshot plus the private answer-key manifest as two distinct artifacts.
"""

from __future__ import annotations

from quantcheck.duplicate_contract import (
    DUPLICATE_SELECTION_NAMESPACE,
    duplicate_severity_profile,
    duplicate_target_count,
)
from quantcheck.duplicate_fingerprint import build_duplicate_groups
from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
    duplicate_created_record_id,
    duplicate_fault_id,
    duplicate_manifest_id,
)
from quantcheck.schemas import (
    DatasetSnapshot,
    DuplicateInjectionConfig,
    DuplicateManifest,
    DuplicateManifestEntry,
    DuplicateMutation,
    FinancialFact,
)

__all__ = [
    "DuplicateInjectionError",
    "NoEligibleDuplicateTargetsError",
    "inject_duplicate_observations",
]


class DuplicateInjectionError(ValueError):
    """Raised when an input is not a valid clean Duplicate source snapshot."""


class NoEligibleDuplicateTargetsError(DuplicateInjectionError):
    """Raised when the configured clean snapshot has no supported targets."""


def _validate_clean_snapshot(snapshot: DatasetSnapshot) -> None:
    if not dataset_snapshot_identity_matches(snapshot):
        raise DuplicateInjectionError("clean snapshot identity does not match its content")
    if any(record.available_on > snapshot.as_of_date for record in snapshot.records):
        raise DuplicateInjectionError(
            "clean snapshot contains a record unavailable at its as_of_date"
        )


def _selection_digest(record_id: str, config: DuplicateInjectionConfig) -> str:
    return canonical_sha256(
        {
            "namespace": DUPLICATE_SELECTION_NAMESPACE,
            "spec_version": config.spec_version,
            "seed": config.seed,
            "eligibility_unit_id": record_id,
        }
    )


def _create_copy(record: FinancialFact, config: DuplicateInjectionConfig) -> FinancialFact:
    created_id = duplicate_created_record_id(
        original_record_id=record.record_id,
        spec_version=config.spec_version,
        copy_ordinal=1,
    )
    fields = {name: getattr(record, name) for name in FinancialFact.model_fields}
    fields["record_id"] = created_id
    return FinancialFact(**fields)


def inject_duplicate_observations(
    clean_snapshot: DatasetSnapshot,
    config: DuplicateInjectionConfig,
) -> tuple[DatasetSnapshot, DuplicateManifest]:
    """Inject deterministic Duplicate faults without mutating the clean input.

    Eligible source occurrences are the clean snapshot's records that belong
    to a singleton exact-fingerprint group at the snapshot's end-of-day
    cutoff; a record already sharing its fingerprint with another clean
    record is never a target. Eligible records are ranked by the full
    SHA-256 selection digest and then stable record ID. Each selected record
    gets exactly one created copy, added to the snapshot; the original is
    never altered.
    """
    _validate_clean_snapshot(clean_snapshot)
    profile = duplicate_severity_profile(config.severity)
    groups = build_duplicate_groups(clean_snapshot.records, as_of_date=clean_snapshot.as_of_date)
    singleton_groups = [group for group in groups.values() if len(group.records) == 1]
    eligible = {group.records[0].record_id: group.records[0] for group in singleton_groups}
    fingerprint_hash_by_record_id = {
        group.records[0].record_id: group.fingerprint_hash for group in singleton_groups
    }
    if not eligible:
        raise NoEligibleDuplicateTargetsError(
            "no clean records satisfy the Duplicate singleton-fingerprint eligibility rule"
        )

    ranked = sorted(
        (_selection_digest(record_id, config), record_id, record)
        for record_id, record in eligible.items()
    )
    target_count = duplicate_target_count(
        eligible_count=len(ranked),
        target_fraction=profile.target_fraction,
        max_targets=config.max_targets,
    )

    created_records: list[FinancialFact] = []
    entries: list[DuplicateManifestEntry] = []
    for target_rank, (selection_digest, _record_id, original) in enumerate(ranked[:target_count]):
        created = _create_copy(original, config)
        created_records.append(created)
        fingerprint_hash = fingerprint_hash_by_record_id[original.record_id]
        entries.append(
            DuplicateManifestEntry(
                fault_id=duplicate_fault_id(
                    clean_snapshot_id=clean_snapshot.snapshot_id,
                    original_record_id=original.record_id,
                    created_record_id=created.record_id,
                    seed=config.seed,
                    spec_version=config.spec_version,
                ),
                severity=config.severity,
                target_rank=target_rank,
                selection_digest=selection_digest,
                eligibility_unit_id=original.record_id,
                snapshot_as_of_date=clean_snapshot.as_of_date,
                fingerprint_hash=fingerprint_hash,
                original_record=original,
                created_record=created,
                mutation=DuplicateMutation(
                    original_record_id=original.record_id,
                    created_record_id=created.record_id,
                    copy_ordinal=1,
                ),
            )
        )

    corrupted_records = clean_snapshot.records + tuple(created_records)
    corrupted_snapshot = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name=clean_snapshot.dataset_name,
            as_of_date=clean_snapshot.as_of_date,
            records=corrupted_records,
        ),
        dataset_name=clean_snapshot.dataset_name,
        as_of_date=clean_snapshot.as_of_date,
        records=corrupted_records,
    )

    manifest_body: dict[str, object] = {
        "fault_type": config.fault_type,
        "fault_subtype": config.fault_subtype,
        "spec_version": config.spec_version,
        "dataset_name": clean_snapshot.dataset_name,
        "snapshot_as_of_date": clean_snapshot.as_of_date,
        "clean_snapshot_id": clean_snapshot.snapshot_id,
        "clean_snapshot_hash": canonical_sha256(clean_snapshot),
        "corrupted_snapshot_id": corrupted_snapshot.snapshot_id,
        "corrupted_snapshot_hash": canonical_sha256(corrupted_snapshot),
        "seed": config.seed,
        "severity": config.severity,
        "target_fraction": profile.target_fraction,
        "max_targets": config.max_targets,
        "eligible_record_ids": tuple(sorted(eligible)),
        "eligible_record_count": len(eligible),
        "target_count": target_count,
        "entries": tuple(sorted(entries, key=lambda entry: entry.fault_id)),
    }
    manifest = DuplicateManifest.model_validate(
        {
            "manifest_id": duplicate_manifest_id(manifest_body=manifest_body),
            **manifest_body,
        }
    )
    return corrupted_snapshot, manifest
