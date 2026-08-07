"""Private, manifest-assisted exact replay for Duplicate Observations faults.

Unlike Look-Ahead and Unit Drift, Duplicate injection *adds* records rather
than replacing them, so replay removes exactly the injected created copies
instead of substituting stored originals back in.
"""

from __future__ import annotations

from quantcheck.duplicate_manifest import validate_duplicate_manifest
from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
)
from quantcheck.schemas import DatasetSnapshot, DuplicateManifest

__all__ = ["DuplicateReplayError", "manifest_assisted_exact_duplicate_replay"]


class DuplicateReplayError(ValueError):
    """Raised when replay inputs do not exactly match private manifest truth."""


def manifest_assisted_exact_duplicate_replay(
    snapshot: DatasetSnapshot,
    manifest: DuplicateManifest,
) -> DatasetSnapshot:
    """Remove exactly the injected created copies, or return a clean input as-is.

    This is explicitly private answer-key replay. It is not detector-only or
    automatic remediation: only the manifest knows which occurrence in each
    duplicate pair was manufactured.
    """
    validate_duplicate_manifest(manifest)
    if not dataset_snapshot_identity_matches(snapshot):
        raise DuplicateReplayError("snapshot identity does not match its content")
    if (
        snapshot.dataset_name != manifest.dataset_name
        or snapshot.as_of_date != manifest.snapshot_as_of_date
    ):
        raise DuplicateReplayError("snapshot and manifest describe different cases")

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
        raise DuplicateReplayError("snapshot is neither the exact corrupted nor clean artifact")

    snapshot_by_id = {record.record_id: record for record in snapshot.records}
    for entry in manifest.entries:
        actual_original = snapshot_by_id.get(entry.original_record.record_id)
        if actual_original != entry.original_record:
            raise DuplicateReplayError("original record does not match manifest truth")
        actual_created = snapshot_by_id.get(entry.created_record.record_id)
        if actual_created != entry.created_record:
            raise DuplicateReplayError("created record does not match manifest truth")

    created_ids = {entry.created_record.record_id for entry in manifest.entries}
    repaired_records = tuple(
        record for record in snapshot.records if record.record_id not in created_ids
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
        raise DuplicateReplayError("replay did not restore the exact clean snapshot")
    return repaired
