"""Private manifest-assisted exact replay for Revision Overwrite."""

from __future__ import annotations

from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
)
from quantcheck.revision_overwrite_manifest import validate_revision_overwrite_manifest
from quantcheck.schemas import DatasetSnapshot, RevisionOverwriteManifest

__all__ = [
    "RevisionOverwriteReplayError",
    "manifest_assisted_exact_revision_overwrite_replay",
]


class RevisionOverwriteReplayError(ValueError):
    """Raised when replay inputs do not exactly match private manifest truth."""


def manifest_assisted_exact_revision_overwrite_replay(
    snapshot: DatasetSnapshot,
    manifest: RevisionOverwriteManifest,
) -> DatasetSnapshot:
    """Restore exact historical occurrences using private answer-key truth."""
    validate_revision_overwrite_manifest(manifest)
    if not dataset_snapshot_identity_matches(snapshot):
        raise RevisionOverwriteReplayError("snapshot identity does not match its content")
    if (
        snapshot.dataset_name != manifest.dataset_name
        or snapshot.as_of_date != manifest.snapshot_as_of_date
    ):
        raise RevisionOverwriteReplayError("snapshot and manifest describe different cases")

    snapshot_hash = canonical_sha256(snapshot)
    if (
        snapshot.snapshot_id == manifest.clean_snapshot_id
        and snapshot_hash == manifest.clean_snapshot_hash
    ):
        return snapshot
    if (
        snapshot.snapshot_id != manifest.corrupted_snapshot_id
        or snapshot_hash != manifest.corrupted_snapshot_hash
    ):
        raise RevisionOverwriteReplayError(
            "snapshot is neither the exact corrupted nor clean artifact"
        )

    units_by_id = {unit.eligibility_unit_id: unit for unit in manifest.eligible_units}
    entries_by_corrupted_id = {
        entry.corrupted_record.record_id: entry for entry in manifest.entries
    }
    snapshot_by_id = {record.record_id: record for record in snapshot.records}
    for entry in manifest.entries:
        unit = units_by_id[entry.eligibility_unit_id]
        if snapshot_by_id.get(entry.corrupted_record.record_id) != entry.corrupted_record:
            raise RevisionOverwriteReplayError("corrupted occurrence does not match manifest truth")
        if unit.historical_record.record_id in snapshot_by_id:
            raise RevisionOverwriteReplayError(
                "corrupted snapshot contains both historical and replacement occurrences"
            )
        if unit.later_record.record_id in snapshot_by_id:
            raise RevisionOverwriteReplayError(
                "historical state unexpectedly contains the unavailable later reference"
            )

    repaired_records = tuple(
        units_by_id[entries_by_corrupted_id[record.record_id].eligibility_unit_id].historical_record
        if record.record_id in entries_by_corrupted_id
        else record
        for record in snapshot.records
    )
    repaired = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name=snapshot.dataset_name,
            as_of_date=snapshot.as_of_date,
            records=repaired_records,
        ),
        dataset_name=snapshot.dataset_name,
        as_of_date=snapshot.as_of_date,
        records=repaired_records,
    )
    if (
        repaired.snapshot_id != manifest.clean_snapshot_id
        or canonical_sha256(repaired) != manifest.clean_snapshot_hash
    ):
        raise RevisionOverwriteReplayError("replay did not restore the exact clean snapshot")
    return repaired
