"""Deterministic row-deletion injection for six Missing Observations mechanisms."""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_CEILING, Decimal

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
)
from quantcheck.missing_observation_contract import (
    MISSING_OBSERVATION_SPEC_VERSION,
    ExpectedObservationV1,
    MissingObservationDetectorConfigV1,
    MissingObservationEligibilityUnitV1,
    MissingObservationInjectionConfigV1,
    MissingObservationManifestEntryV1,
    MissingObservationManifestV1,
    MissingObservationSeriesKeyV1,
    detector_config_identity_matches,
    expectation_context_for_mechanism,
    injection_severity_profile,
    missing_fault_id,
    missing_manifest_id,
    validate_expected_record,
)
from quantcheck.missing_observation_expectations import build_missing_evidence
from quantcheck.schemas import DatasetSnapshot

__all__ = [
    "AmbiguousMissingObservationEligibilityError",
    "MissingObservationInjectionError",
    "NoEligibleMissingObservationTargetsError",
    "inject_missing_observations",
]

_SELECTION_NAMESPACE = "quantcheck/missing-observation-target-selection/v1"
_GROUP_SELECTION_NAMESPACE = "quantcheck/missing-observation-group-selection/v1"


class MissingObservationInjectionError(ValueError):
    """Raised when clean/configuration inputs cannot support controlled deletion."""


class NoEligibleMissingObservationTargetsError(MissingObservationInjectionError):
    """Raised when no expected clean cell is eligible for the selected mechanism."""


class AmbiguousMissingObservationEligibilityError(MissingObservationInjectionError):
    """Raised when more than one clean occurrence satisfies one exact expectation."""


def _validate_inputs(
    clean_snapshot: DatasetSnapshot,
    detector_config: MissingObservationDetectorConfigV1,
) -> None:
    if not dataset_snapshot_identity_matches(clean_snapshot):
        raise MissingObservationInjectionError("clean snapshot identity is invalid")
    if any(record.available_on > clean_snapshot.as_of_date for record in clean_snapshot.records):
        raise MissingObservationInjectionError(
            "clean snapshot contains a record unavailable at its cutoff"
        )
    if not detector_config_identity_matches(detector_config):
        raise MissingObservationInjectionError("detector config identity is invalid")


def _all_eligible_units(
    clean_snapshot: DatasetSnapshot,
    detector_config: MissingObservationDetectorConfigV1,
    injection_config: MissingObservationInjectionConfigV1,
) -> tuple[MissingObservationEligibilityUnitV1, ...]:
    required_context = expectation_context_for_mechanism(injection_config.mechanism)
    units: list[MissingObservationEligibilityUnitV1] = []
    for expectation in detector_config.expectations:
        if (
            expectation.context != required_context
            or expectation.expected_by > clean_snapshot.as_of_date
        ):
            continue
        matches = tuple(
            record
            for record in clean_snapshot.records
            if validate_expected_record(expectation, record)
        )
        if len(matches) > 1:
            raise AmbiguousMissingObservationEligibilityError(
                "one expected cell matches multiple clean occurrences"
            )
        if len(matches) == 1:
            units.append(
                MissingObservationEligibilityUnitV1(
                    expected_observation=expectation,
                    original_record=matches[0],
                )
            )
    return tuple(
        sorted(
            units,
            key=lambda unit: unit.expected_observation.expected_observation_id,
        )
    )


def _group_digest(*, key: object, injection_config: MissingObservationInjectionConfigV1) -> str:
    return canonical_sha256(
        {
            "namespace": _GROUP_SELECTION_NAMESPACE,
            "spec_version": MISSING_OBSERVATION_SPEC_VERSION,
            "mechanism": injection_config.mechanism,
            "seed": injection_config.seed,
            "group": key,
        }
    )


def _pick_one_group(
    units: tuple[MissingObservationEligibilityUnitV1, ...],
    *,
    key: Callable[[MissingObservationEligibilityUnitV1], object],
    injection_config: MissingObservationInjectionConfigV1,
) -> tuple[MissingObservationEligibilityUnitV1, ...]:
    groups: dict[object, list[MissingObservationEligibilityUnitV1]] = {}
    for unit in units:
        groups.setdefault(key(unit), []).append(unit)
    if not groups:
        return ()
    selected_key = min(
        groups,
        key=lambda group_key: (
            _group_digest(key=group_key, injection_config=injection_config),
            str(group_key),
        ),
    )
    return tuple(groups[selected_key])


def _periodic_interior_units(
    units: tuple[MissingObservationEligibilityUnitV1, ...],
) -> tuple[MissingObservationEligibilityUnitV1, ...]:
    by_series: dict[MissingObservationSeriesKeyV1, list[MissingObservationEligibilityUnitV1]] = {}
    for unit in units:
        by_series.setdefault(unit.expected_observation.series, []).append(unit)
    interior: list[MissingObservationEligibilityUnitV1] = []
    for series_units in by_series.values():
        ordered = sorted(
            series_units,
            key=lambda unit: (
                unit.expected_observation.period_end,
                unit.expected_observation.expected_observation_id,
            ),
        )
        interior.extend(ordered[1:-1])
    return tuple(interior)


def _mechanism_scope(
    units: tuple[MissingObservationEligibilityUnitV1, ...],
    config: MissingObservationInjectionConfigV1,
) -> tuple[MissingObservationEligibilityUnitV1, ...]:
    if config.mechanism == "random_missingness":
        return units
    if config.mechanism == "periodic_reporting_gap":
        return _periodic_interior_units(units)
    if config.mechanism == "entity_dependent_missingness":
        return _pick_one_group(
            units,
            key=lambda unit: unit.expected_observation.series.entity_id,
            injection_config=config,
        )
    if config.mechanism == "concept_dependent_missingness":
        return _pick_one_group(
            units,
            key=lambda unit: (
                unit.expected_observation.series.concept_namespace,
                unit.expected_observation.series.concept,
            ),
            injection_config=config,
        )
    if config.mechanism == "survivorship_like_filtering":
        entities = set(config.survivorship_entity_ids)
        return tuple(
            unit for unit in units if unit.expected_observation.series.entity_id in entities
        )
    assert config.mechanism == "source_feed_outage"
    assert config.outage_period_start is not None
    assert config.outage_period_end is not None
    in_window = tuple(
        unit
        for unit in units
        if config.outage_period_start
        <= unit.expected_observation.period_end
        <= config.outage_period_end
    )
    return _pick_one_group(
        in_window,
        key=lambda unit: (
            unit.expected_observation.series.source_name,
            unit.expected_observation.series.source_locator,
        ),
        injection_config=config,
    )


def _selection_digest(
    expectation: ExpectedObservationV1,
    config: MissingObservationInjectionConfigV1,
) -> str:
    return canonical_sha256(
        {
            "namespace": _SELECTION_NAMESPACE,
            "spec_version": MISSING_OBSERVATION_SPEC_VERSION,
            "mechanism": config.mechanism,
            "severity": config.severity,
            "seed": config.seed,
            "expected_observation_id": expectation.expected_observation_id,
        }
    )


def _target_count(
    eligible_count: int,
    config: MissingObservationInjectionConfigV1,
) -> int:
    if eligible_count == 0:
        return 0
    if config.mechanism in ("survivorship_like_filtering", "source_feed_outage"):
        if eligible_count > config.max_targets:
            raise MissingObservationInjectionError(
                "complete survivorship/outage scope exceeds max_targets; partial scope is refused"
            )
        return eligible_count
    fraction = injection_severity_profile(config.severity).target_fraction
    raw = Decimal(eligible_count) * fraction
    return min(
        eligible_count,
        config.max_targets,
        max(1, int(raw.to_integral_value(rounding=ROUND_CEILING))),
    )


def inject_missing_observations(
    clean_snapshot: DatasetSnapshot,
    detector_config: MissingObservationDetectorConfigV1,
    injection_config: MissingObservationInjectionConfigV1,
) -> tuple[DatasetSnapshot, MissingObservationManifestV1]:
    """Delete deterministic expected cells while retaining exact private truth."""
    if not isinstance(injection_config, MissingObservationInjectionConfigV1):
        raise MissingObservationInjectionError(
            "injection_config must be a strict MissingObservationInjectionConfigV1"
        )
    _validate_inputs(clean_snapshot, detector_config)
    all_units = _all_eligible_units(clean_snapshot, detector_config, injection_config)
    scoped_units = _mechanism_scope(all_units, injection_config)
    if not scoped_units:
        raise NoEligibleMissingObservationTargetsError(
            "no explicit due expectation supports the selected missingness mechanism"
        )
    ranked = sorted(
        (
            _selection_digest(unit.expected_observation, injection_config),
            unit.expected_observation.expected_observation_id,
            unit,
        )
        for unit in scoped_units
    )
    target_count = _target_count(len(ranked), injection_config)
    selected = ranked[:target_count]
    deleted_ids = {unit.original_record.record_id for _, _, unit in selected}
    corrupted_records = tuple(
        record for record in clean_snapshot.records if record.record_id not in deleted_ids
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
    audit_input = sanitize_for_audit(corrupted_snapshot)
    entries: list[MissingObservationManifestEntryV1] = []
    for target_rank, (selection_digest, _expectation_id, unit) in enumerate(selected):
        fault_body = {
            "clean_snapshot_id": clean_snapshot.snapshot_id,
            "expected_observation_id": unit.expected_observation.expected_observation_id,
            "deleted_record_id": unit.original_record.record_id,
            "mechanism": injection_config.mechanism,
            "seed": injection_config.seed,
            "spec_version": injection_config.spec_version,
        }
        entries.append(
            MissingObservationManifestEntryV1(
                fault_id=missing_fault_id(body=fault_body),
                mechanism=injection_config.mechanism,
                severity=injection_config.severity,
                target_rank=target_rank,
                selection_digest=selection_digest,
                expected_observation=unit.expected_observation,
                deleted_record=unit.original_record,
                expected_evidence=build_missing_evidence(audit_input, unit.expected_observation),
            )
        )
    profile = injection_severity_profile(injection_config.severity)
    normalized_units = tuple(
        sorted(
            scoped_units,
            key=lambda unit: unit.expected_observation.expected_observation_id,
        )
    )
    normalized_entries = tuple(sorted(entries, key=lambda entry: entry.fault_id))
    manifest_body: dict[str, object] = {
        "spec_version": MISSING_OBSERVATION_SPEC_VERSION,
        "dataset_name": clean_snapshot.dataset_name,
        "snapshot_as_of_date": clean_snapshot.as_of_date,
        "clean_snapshot_id": clean_snapshot.snapshot_id,
        "clean_snapshot_hash": canonical_sha256(clean_snapshot),
        "corrupted_snapshot_id": corrupted_snapshot.snapshot_id,
        "corrupted_snapshot_hash": canonical_sha256(corrupted_snapshot),
        "detector_config": detector_config,
        "detector_config_hash": canonical_sha256(detector_config),
        "injection_config": injection_config,
        "target_fraction": profile.target_fraction,
        "eligible_units": normalized_units,
        "eligible_unit_count": len(scoped_units),
        "target_count": target_count,
        "entries": normalized_entries,
    }
    manifest = MissingObservationManifestV1.model_validate(
        {"manifest_id": missing_manifest_id(body=manifest_body), **manifest_body}
    )
    return corrupted_snapshot, manifest
