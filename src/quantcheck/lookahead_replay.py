"""Private, manifest-assisted exact replay for Look-Ahead faults."""

from __future__ import annotations

from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
)
from quantcheck.lookahead_manifest import validate_lookahead_manifest
from quantcheck.schemas import DatasetSnapshot, FaultManifest

__all__ = ["LookAheadReplayError", "manifest_assisted_exact_replay"]


class LookAheadReplayError(ValueError):
    """Raised when replay inputs do not exactly match private manifest truth."""


def manifest_assisted_exact_replay(
    snapshot: DatasetSnapshot,
    manifest: FaultManifest,
) -> DatasetSnapshot:
    """Restore the exact clean snapshot, or return an already-restored input.

    This is explicitly private answer-key replay.  It is not detector-only or
    automatic remediation.
    """
    validate_lookahead_manifest(manifest)
    if not dataset_snapshot_identity_matches(snapshot):
        raise LookAheadReplayError("snapshot identity does not match its content")
    if (
        snapshot.dataset_name != manifest.dataset_name
        or snapshot.as_of_date != manifest.snapshot_as_of_date
    ):
        raise LookAheadReplayError("snapshot and manifest describe different cases")

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
        raise LookAheadReplayError("snapshot is neither the exact corrupted nor clean artifact")

    by_corrupted_id = {entry.corrupted_record.record_id: entry for entry in manifest.entries}
    snapshot_by_id = {record.record_id: record for record in snapshot.records}
    for entry in manifest.entries:
        actual = snapshot_by_id.get(entry.corrupted_record.record_id)
        if actual != entry.corrupted_record:
            raise LookAheadReplayError("corrupted record does not match manifest truth")
        if entry.original_record.record_id in snapshot_by_id:
            raise LookAheadReplayError("corrupted snapshot contains both original and replacement")

    repaired_records = tuple(
        by_corrupted_id[record.record_id].original_record
        if record.record_id in by_corrupted_id
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
        raise LookAheadReplayError("replay did not restore the exact clean snapshot")
    return repaired
