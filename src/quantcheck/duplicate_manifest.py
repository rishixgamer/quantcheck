"""Private Duplicate manifest integrity validation."""

from __future__ import annotations

from quantcheck.duplicate_contract import (
    DUPLICATE_SELECTION_NAMESPACE,
    duplicate_severity_profile,
    duplicate_target_count,
)
from quantcheck.duplicate_fingerprint import duplicate_fingerprint, duplicate_fingerprint_hash
from quantcheck.hashing import (
    canonical_sha256,
    duplicate_created_record_id,
    duplicate_fault_id,
    duplicate_manifest_id,
)
from quantcheck.schemas import DuplicateManifest

__all__ = [
    "DuplicateManifestIntegrityError",
    "duplicate_manifest_identity_matches",
    "validate_duplicate_manifest",
]


class DuplicateManifestIntegrityError(ValueError):
    """Raised when private Duplicate truth is inconsistent or forged."""


def _manifest_body(manifest: DuplicateManifest) -> dict[str, object]:
    return {
        name: getattr(manifest, name)
        for name in DuplicateManifest.model_fields
        if name != "manifest_id"
    }


def duplicate_manifest_identity_matches(manifest: DuplicateManifest) -> bool:
    """Report whether the manifest ID covers every other manifest field."""
    return manifest.manifest_id == duplicate_manifest_id(manifest_body=_manifest_body(manifest))


def _selection_digest(record_id: str, manifest: DuplicateManifest) -> str:
    return canonical_sha256(
        {
            "namespace": DUPLICATE_SELECTION_NAMESPACE,
            "spec_version": manifest.spec_version,
            "seed": manifest.seed,
            "eligibility_unit_id": record_id,
        }
    )


def validate_duplicate_manifest(manifest: DuplicateManifest) -> None:
    """Validate identity, severity, selection, fingerprint, and fault identities."""
    if not duplicate_manifest_identity_matches(manifest):
        raise DuplicateManifestIntegrityError("manifest identity does not match its content")

    profile = duplicate_severity_profile(manifest.severity)
    if manifest.target_fraction != profile.target_fraction:
        raise DuplicateManifestIntegrityError("manifest severity profile is inconsistent")
    expected_count = duplicate_target_count(
        eligible_count=manifest.eligible_record_count,
        target_fraction=manifest.target_fraction,
        max_targets=manifest.max_targets,
    )
    if manifest.target_count != expected_count:
        raise DuplicateManifestIntegrityError("manifest target_count is inconsistent")

    ranked = sorted(
        (_selection_digest(record_id, manifest), record_id)
        for record_id in manifest.eligible_record_ids
    )
    selected_by_rank = sorted(manifest.entries, key=lambda entry: entry.target_rank)
    expected_selected_ids = [record_id for _digest, record_id in ranked[: manifest.target_count]]
    actual_selected_ids = [entry.original_record.record_id for entry in selected_by_rank]
    if actual_selected_ids != expected_selected_ids:
        raise DuplicateManifestIntegrityError("manifest selected targets do not match SHA-256 rank")

    for entry in manifest.entries:
        expected_digest = _selection_digest(entry.original_record.record_id, manifest)
        if entry.selection_digest != expected_digest:
            raise DuplicateManifestIntegrityError("manifest selection digest is inconsistent")

        expected_fingerprint_hash = duplicate_fingerprint_hash(
            duplicate_fingerprint(entry.original_record)
        )
        if entry.fingerprint_hash != expected_fingerprint_hash:
            raise DuplicateManifestIntegrityError("manifest fingerprint hash is inconsistent")
        if duplicate_fingerprint_hash(duplicate_fingerprint(entry.created_record)) != (
            expected_fingerprint_hash
        ):
            raise DuplicateManifestIntegrityError(
                "created record does not share the original's fingerprint"
            )

        expected_created_id = duplicate_created_record_id(
            original_record_id=entry.original_record.record_id,
            spec_version=entry.spec_version,
            copy_ordinal=entry.mutation.copy_ordinal,
        )
        if entry.created_record.record_id != expected_created_id:
            raise DuplicateManifestIntegrityError("created record identity is inconsistent")

        expected_fault_id = duplicate_fault_id(
            clean_snapshot_id=manifest.clean_snapshot_id,
            original_record_id=entry.original_record.record_id,
            created_record_id=entry.created_record.record_id,
            seed=manifest.seed,
            spec_version=manifest.spec_version,
        )
        if entry.fault_id != expected_fault_id:
            raise DuplicateManifestIntegrityError("fault identity is inconsistent")
