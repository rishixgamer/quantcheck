"""Private integrity validation for Missing Observations manifests."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal

from quantcheck.hashing import canonical_sha256
from quantcheck.missing_observation_contract import (
    MISSING_OBSERVATION_SPEC_VERSION,
    MissingObservationManifestV1,
    detector_config_identity_matches,
    expectation_context_for_mechanism,
    injection_severity_profile,
    missing_fault_id,
    missing_manifest_id,
    validate_expected_record,
)

__all__ = ["MissingObservationManifestError", "validate_missing_observation_manifest"]

_SELECTION_NAMESPACE = "quantcheck/missing-observation-target-selection/v1"


class MissingObservationManifestError(ValueError):
    """Raised when private answer-key relationships fail recomputation."""


def _selection_digest(manifest: MissingObservationManifestV1, expectation_id: str) -> str:
    config = manifest.injection_config
    return canonical_sha256(
        {
            "namespace": _SELECTION_NAMESPACE,
            "spec_version": MISSING_OBSERVATION_SPEC_VERSION,
            "mechanism": config.mechanism,
            "severity": config.severity,
            "seed": config.seed,
            "expected_observation_id": expectation_id,
        }
    )


def _expected_target_count(manifest: MissingObservationManifestV1) -> int:
    count = manifest.eligible_unit_count
    if manifest.injection_config.mechanism in (
        "survivorship_like_filtering",
        "source_feed_outage",
    ):
        return count
    raw = Decimal(count) * manifest.target_fraction
    return min(
        count,
        manifest.injection_config.max_targets,
        max(1, int(raw.to_integral_value(rounding=ROUND_CEILING))),
    )


def validate_missing_observation_manifest(manifest: MissingObservationManifestV1) -> None:
    """Recompute every deterministic private relationship available in the manifest."""
    body = {
        name: getattr(manifest, name)
        for name in MissingObservationManifestV1.model_fields
        if name != "manifest_id"
    }
    if manifest.manifest_id != missing_manifest_id(body=body):
        raise MissingObservationManifestError("manifest identity does not match its content")
    if not detector_config_identity_matches(manifest.detector_config):
        raise MissingObservationManifestError("detector config identity is invalid")
    if canonical_sha256(manifest.detector_config) != manifest.detector_config_hash:
        raise MissingObservationManifestError("detector config hash is invalid")
    profile = injection_severity_profile(manifest.injection_config.severity)
    if profile.target_fraction != manifest.target_fraction:
        raise MissingObservationManifestError("severity target fraction is invalid")
    if manifest.target_count != _expected_target_count(manifest):
        raise MissingObservationManifestError("target count is invalid")

    config_expectations = {
        expectation.expected_observation_id: expectation
        for expectation in manifest.detector_config.expectations
    }
    required_context = expectation_context_for_mechanism(manifest.injection_config.mechanism)
    units_by_expectation = {}
    for unit in manifest.eligible_units:
        expectation = unit.expected_observation
        if config_expectations.get(expectation.expected_observation_id) != expectation:
            raise MissingObservationManifestError(
                "eligible expectation is not in the detector configuration"
            )
        if expectation.context != required_context:
            raise MissingObservationManifestError(
                "eligible expectation context does not match the mechanism"
            )
        if not validate_expected_record(expectation, unit.original_record):
            raise MissingObservationManifestError(
                "eligible clean record does not satisfy its expectation"
            )
        units_by_expectation[expectation.expected_observation_id] = unit

    ranked_ids = [
        expectation_id
        for _digest, expectation_id in sorted(
            (
                _selection_digest(manifest, expectation_id),
                expectation_id,
            )
            for expectation_id in units_by_expectation
        )
    ]
    selected_ids = set(ranked_ids[: manifest.target_count])
    for entry in manifest.entries:
        expectation_id = entry.expected_observation.expected_observation_id
        selected_unit = units_by_expectation.get(expectation_id)
        if selected_unit is None or expectation_id not in selected_ids:
            raise MissingObservationManifestError("entry is not a deterministically selected unit")
        if entry.deleted_record != selected_unit.original_record:
            raise MissingObservationManifestError("deleted record is not the eligible clean record")
        if entry.expected_evidence.audit_as_of_date != manifest.snapshot_as_of_date:
            raise MissingObservationManifestError("entry evidence cutoff is invalid")
        expected_digest = _selection_digest(manifest, expectation_id)
        if entry.selection_digest != expected_digest:
            raise MissingObservationManifestError("selection digest is invalid")
        expected_rank = ranked_ids[: manifest.target_count].index(expectation_id)
        if entry.target_rank != expected_rank:
            raise MissingObservationManifestError("target rank is invalid")
        expected_fault_id = missing_fault_id(
            body={
                "clean_snapshot_id": manifest.clean_snapshot_id,
                "expected_observation_id": expectation_id,
                "deleted_record_id": entry.deleted_record.record_id,
                "mechanism": manifest.injection_config.mechanism,
                "seed": manifest.injection_config.seed,
                "spec_version": manifest.injection_config.spec_version,
            }
        )
        if entry.fault_id != expected_fault_id:
            raise MissingObservationManifestError("fault identity is invalid")
