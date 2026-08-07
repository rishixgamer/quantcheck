"""Private Unit Drift manifest integrity validation."""

from __future__ import annotations

from quantcheck.hashing import (
    canonical_sha256,
    unit_drift_fault_id,
    unit_drift_manifest_id,
    unit_drift_modified_record_id,
)
from quantcheck.schemas import UnitDriftManifest
from quantcheck.unit_drift_contract import (
    UNIT_DRIFT_SELECTION_NAMESPACE,
    unit_drift_severity_profile,
    unit_drift_target_count,
)
from quantcheck.unit_drift_series import comparable_series_key

__all__ = [
    "UnitDriftManifestIntegrityError",
    "unit_drift_manifest_identity_matches",
    "validate_unit_drift_manifest",
]


class UnitDriftManifestIntegrityError(ValueError):
    """Raised when private Unit Drift truth is inconsistent or forged."""


def _manifest_body(manifest: UnitDriftManifest) -> dict[str, object]:
    return {
        name: getattr(manifest, name)
        for name in UnitDriftManifest.model_fields
        if name != "manifest_id"
    }


def unit_drift_manifest_identity_matches(manifest: UnitDriftManifest) -> bool:
    """Report whether the manifest ID covers every other manifest field."""
    return manifest.manifest_id == unit_drift_manifest_id(manifest_body=_manifest_body(manifest))


def _selection_digest(record_id: str, manifest: UnitDriftManifest) -> str:
    return canonical_sha256(
        {
            "namespace": UNIT_DRIFT_SELECTION_NAMESPACE,
            "spec_version": manifest.spec_version,
            "seed": manifest.seed,
            "eligibility_unit_id": record_id,
        }
    )


def validate_unit_drift_manifest(manifest: UnitDriftManifest) -> None:
    """Validate identity, profile, selection, mutation, and fault identities."""
    if not unit_drift_manifest_identity_matches(manifest):
        raise UnitDriftManifestIntegrityError("manifest identity does not match its content")

    profile = unit_drift_severity_profile(manifest.severity)
    if (
        manifest.scale_factor != profile.scale_factor
        or manifest.target_fraction != profile.target_fraction
    ):
        raise UnitDriftManifestIntegrityError("manifest severity profile is inconsistent")
    expected_count = unit_drift_target_count(
        eligible_count=manifest.eligible_record_count,
        target_fraction=manifest.target_fraction,
        max_targets=manifest.max_targets,
    )
    if manifest.target_count != expected_count:
        raise UnitDriftManifestIntegrityError("manifest target_count is inconsistent")

    ranked = sorted(
        (_selection_digest(record_id, manifest), record_id)
        for record_id in manifest.eligible_record_ids
    )
    selected_by_rank = sorted(manifest.entries, key=lambda entry: entry.target_rank)
    expected_selected_ids = [record_id for _digest, record_id in ranked[: manifest.target_count]]
    actual_selected_ids = [entry.original_record.record_id for entry in selected_by_rank]
    if actual_selected_ids != expected_selected_ids:
        raise UnitDriftManifestIntegrityError("manifest selected targets do not match SHA-256 rank")

    for entry in manifest.entries:
        expected_digest = _selection_digest(entry.original_record.record_id, manifest)
        if entry.selection_digest != expected_digest:
            raise UnitDriftManifestIntegrityError("manifest selection digest is inconsistent")
        if entry.comparable_series_key != comparable_series_key(entry.original_record):
            raise UnitDriftManifestIntegrityError("manifest comparable-series key is inconsistent")
        expected_modified_id = unit_drift_modified_record_id(
            original_record_id=entry.original_record.record_id,
            spec_version=entry.spec_version,
            original_value=entry.original_record.value,
            corrupted_value=entry.corrupted_record.value,
            scale_factor=entry.mutation.scale_factor,
        )
        if entry.corrupted_record.record_id != expected_modified_id:
            raise UnitDriftManifestIntegrityError("modified record identity is inconsistent")
        expected_fault_id = unit_drift_fault_id(
            clean_snapshot_id=manifest.clean_snapshot_id,
            original_record_id=entry.original_record.record_id,
            corrupted_record_id=entry.corrupted_record.record_id,
            seed=manifest.seed,
            spec_version=manifest.spec_version,
        )
        if entry.fault_id != expected_fault_id:
            raise UnitDriftManifestIntegrityError("fault identity is inconsistent")
