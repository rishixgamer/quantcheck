"""Deterministic scaled-value, unchanged-unit fault injection."""

from __future__ import annotations

from decimal import Decimal

from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
    unit_drift_fault_id,
    unit_drift_manifest_id,
    unit_drift_modified_record_id,
)
from quantcheck.schemas import (
    DatasetSnapshot,
    FinancialFact,
    UnitDriftInjectionConfig,
    UnitDriftManifest,
    UnitDriftManifestEntry,
    UnitDriftMutation,
)
from quantcheck.unit_drift_contract import (
    UNIT_DRIFT_SELECTION_NAMESPACE,
    unit_drift_severity_profile,
    unit_drift_target_count,
)
from quantcheck.unit_drift_series import (
    ComparableObservation,
    build_comparable_observations,
)

__all__ = [
    "NoEligibleUnitDriftTargetsError",
    "UnitDriftInjectionError",
    "inject_unit_drift",
]


class UnitDriftInjectionError(ValueError):
    """Raised when input is not a valid clean Unit Drift source snapshot."""


class NoEligibleUnitDriftTargetsError(UnitDriftInjectionError):
    """Raised when no record meets the frozen comparability prerequisites."""


def _validate_clean_snapshot(snapshot: DatasetSnapshot) -> None:
    if not dataset_snapshot_identity_matches(snapshot):
        raise UnitDriftInjectionError("clean snapshot identity does not match its content")
    if any(record.available_on > snapshot.as_of_date for record in snapshot.records):
        raise UnitDriftInjectionError(
            "clean snapshot contains a record unavailable at its as_of_date"
        )


def _selection_digest(record_id: str, config: UnitDriftInjectionConfig) -> str:
    return canonical_sha256(
        {
            "namespace": UNIT_DRIFT_SELECTION_NAMESPACE,
            "spec_version": config.spec_version,
            "seed": config.seed,
            "eligibility_unit_id": record_id,
        }
    )


def _corrupt_record(
    record: FinancialFact,
    config: UnitDriftInjectionConfig,
    *,
    scale_factor: Decimal,
) -> FinancialFact:
    corrupted_value = record.value * scale_factor
    modified_id = unit_drift_modified_record_id(
        original_record_id=record.record_id,
        spec_version=config.spec_version,
        original_value=record.value,
        corrupted_value=corrupted_value,
        scale_factor=scale_factor,
    )
    fields = {name: getattr(record, name) for name in FinancialFact.model_fields}
    fields["record_id"] = modified_id
    fields["value"] = corrupted_value
    return FinancialFact(**fields)


def inject_unit_drift(
    clean_snapshot: DatasetSnapshot,
    config: UnitDriftInjectionConfig,
) -> tuple[DatasetSnapshot, UnitDriftManifest]:
    """Inject deterministic Unit Drift faults without mutating clean input."""
    _validate_clean_snapshot(clean_snapshot)
    profile = unit_drift_severity_profile(config.severity)
    observations = build_comparable_observations(
        clean_snapshot.records,
        as_of_date=clean_snapshot.as_of_date,
    )
    if not observations:
        raise NoEligibleUnitDriftTargetsError(
            "no clean records satisfy the Unit Drift comparability prerequisites"
        )

    ranked = sorted(
        (
            _selection_digest(record_id, config),
            record_id,
            observation,
        )
        for record_id, observation in observations.items()
    )
    target_count = unit_drift_target_count(
        eligible_count=len(ranked),
        target_fraction=profile.target_fraction,
        max_targets=config.max_targets,
    )

    replacements: dict[str, FinancialFact] = {}
    entries: list[UnitDriftManifestEntry] = []
    for target_rank, (selection_digest, _record_id, observation) in enumerate(
        ranked[:target_count]
    ):
        typed_observation: ComparableObservation[FinancialFact] = observation
        original = typed_observation.record
        corrupted = _corrupt_record(
            original,
            config,
            scale_factor=profile.scale_factor,
        )
        replacements[original.record_id] = corrupted
        entries.append(
            UnitDriftManifestEntry(
                fault_id=unit_drift_fault_id(
                    clean_snapshot_id=clean_snapshot.snapshot_id,
                    original_record_id=original.record_id,
                    corrupted_record_id=corrupted.record_id,
                    seed=config.seed,
                    spec_version=config.spec_version,
                ),
                severity=config.severity,
                target_rank=target_rank,
                selection_digest=selection_digest,
                eligibility_unit_id=original.record_id,
                snapshot_as_of_date=clean_snapshot.as_of_date,
                comparable_series_key=typed_observation.key,
                series_record_ids=tuple(record.record_id for record in typed_observation.records),
                eligible_neighbor_record_ids=tuple(
                    record.record_id for _position, record in typed_observation.neighbors
                ),
                original_record=original,
                corrupted_record=corrupted,
                mutation=UnitDriftMutation(
                    original_value=original.value,
                    corrupted_value=corrupted.value,
                    scale_factor=profile.scale_factor,
                ),
            )
        )

    corrupted_records = tuple(
        replacements.get(record.record_id, record) for record in clean_snapshot.records
    )
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
        "scale_factor": profile.scale_factor,
        "target_fraction": profile.target_fraction,
        "max_targets": config.max_targets,
        "eligible_record_ids": tuple(sorted(observations)),
        "eligible_record_count": len(observations),
        "target_count": target_count,
        "entries": tuple(sorted(entries, key=lambda entry: entry.fault_id)),
    }
    manifest = UnitDriftManifest.model_validate(
        {
            "manifest_id": unit_drift_manifest_id(manifest_body=manifest_body),
            **manifest_body,
        }
    )
    return corrupted_snapshot, manifest
