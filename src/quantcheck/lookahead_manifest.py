"""Private manifest integrity checks shared by scoring and exact replay."""

from __future__ import annotations

from quantcheck.hashing import (
    canonical_sha256,
    fault_manifest_id,
    lookahead_fault_id,
    lookahead_modified_record_id,
)
from quantcheck.lookahead_contract import (
    LOOKAHEAD_SELECTION_NAMESPACE,
    lookahead_severity_profile,
    lookahead_target_count,
)
from quantcheck.schemas import FaultManifest

__all__ = [
    "LookAheadManifestIntegrityError",
    "manifest_identity_matches",
    "validate_lookahead_manifest",
]


class LookAheadManifestIntegrityError(ValueError):
    """Raised when private truth is internally inconsistent or forged."""


def _manifest_body(manifest: FaultManifest) -> dict[str, object]:
    return {
        name: getattr(manifest, name)
        for name in FaultManifest.model_fields
        if name != "manifest_id"
    }


def manifest_identity_matches(manifest: FaultManifest) -> bool:
    return manifest.manifest_id == fault_manifest_id(manifest_body=_manifest_body(manifest))


def _selection_digest(record_id: str, manifest: FaultManifest) -> str:
    return canonical_sha256(
        {
            "namespace": LOOKAHEAD_SELECTION_NAMESPACE,
            "spec_version": manifest.spec_version,
            "seed": manifest.seed,
            "eligibility_unit_id": record_id,
        }
    )


def validate_lookahead_manifest(manifest: FaultManifest) -> None:
    """Validate identity, severity, selection, mutation, and fault IDs."""
    if not manifest_identity_matches(manifest):
        raise LookAheadManifestIntegrityError("manifest identity does not match its content")

    profile = lookahead_severity_profile(manifest.severity)
    if (
        manifest.target_fraction != profile.target_fraction
        or manifest.minimum_lag_days != profile.minimum_lag_days
    ):
        raise LookAheadManifestIntegrityError("manifest severity profile is inconsistent")
    expected_count = lookahead_target_count(
        eligible_count=manifest.eligible_record_count,
        target_fraction=manifest.target_fraction,
        max_targets=manifest.max_targets,
    )
    if manifest.target_count != expected_count:
        raise LookAheadManifestIntegrityError("manifest target_count is inconsistent")

    ranked = sorted(
        (
            _selection_digest(record_id, manifest),
            record_id,
        )
        for record_id in manifest.eligible_record_ids
    )
    selected_by_rank = sorted(manifest.entries, key=lambda entry: entry.target_rank)
    expected_selected_ids = [record_id for _digest, record_id in ranked[: manifest.target_count]]
    actual_selected_ids = [entry.original_record.record_id for entry in selected_by_rank]
    if actual_selected_ids != expected_selected_ids:
        raise LookAheadManifestIntegrityError("manifest selected targets do not match SHA-256 rank")

    for entry in manifest.entries:
        expected_digest = _selection_digest(entry.original_record.record_id, manifest)
        if entry.selection_digest != expected_digest:
            raise LookAheadManifestIntegrityError("manifest selection digest is inconsistent")
        expected_modified_id = lookahead_modified_record_id(
            original_record_id=entry.original_record.record_id,
            spec_version=entry.spec_version,
            true_available_on=entry.original_record.available_on,
            corrupted_available_on=entry.corrupted_record.available_on,
        )
        if entry.corrupted_record.record_id != expected_modified_id:
            raise LookAheadManifestIntegrityError("modified record identity is inconsistent")
        expected_fault_id = lookahead_fault_id(
            clean_snapshot_id=manifest.clean_snapshot_id,
            original_record_id=entry.original_record.record_id,
            corrupted_record_id=entry.corrupted_record.record_id,
            seed=manifest.seed,
            spec_version=manifest.spec_version,
        )
        if entry.fault_id != expected_fault_id:
            raise LookAheadManifestIntegrityError("fault identity is inconsistent")
