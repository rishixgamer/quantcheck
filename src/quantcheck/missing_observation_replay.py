"""Private manifest-assisted exact replay for Missing Observations."""

from __future__ import annotations

from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
)
from quantcheck.missing_observation_contract import MissingObservationManifestV1
from quantcheck.missing_observation_manifest import validate_missing_observation_manifest
from quantcheck.schemas import DatasetSnapshot

__all__ = [
    "MissingObservationReplayError",
    "manifest_assisted_exact_missing_observation_replay",
]


class MissingObservationReplayError(ValueError):
    """Raised when replay does not receive an exact clean or corrupted artifact."""


def manifest_assisted_exact_missing_observation_replay(
    snapshot: DatasetSnapshot,
    manifest: MissingObservationManifestV1,
) -> DatasetSnapshot:
    """Reinsert only the exact rows retained in private manifest truth."""
    validate_missing_observation_manifest(manifest)
    if not dataset_snapshot_identity_matches(snapshot):
        raise MissingObservationReplayError("snapshot identity is invalid")
    if (
        snapshot.dataset_name != manifest.dataset_name
        or snapshot.as_of_date != manifest.snapshot_as_of_date
    ):
        raise MissingObservationReplayError("snapshot and manifest describe different cases")
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
        raise MissingObservationReplayError(
            "snapshot is neither the exact corrupted nor clean artifact"
        )

    records_by_id = {record.record_id: record for record in snapshot.records}
    for entry in manifest.entries:
        if entry.deleted_record.record_id in records_by_id:
            raise MissingObservationReplayError(
                "corrupted snapshot already contains a supposedly deleted record"
            )
    repaired_records = tuple(snapshot.records) + tuple(
        entry.deleted_record for entry in manifest.entries
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
        raise MissingObservationReplayError("replay did not restore the exact clean snapshot")
    return repaired
