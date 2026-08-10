"""Controlled expected-cohort mean sensitivity for Missing Observations."""

from __future__ import annotations

from decimal import Decimal, localcontext

from quantcheck.hashing import canonical_sha256, dataset_snapshot_identity_matches
from quantcheck.missing_observation_contract import (
    MissingObservationDetectorConfigV1,
    MissingObservationResearchImpactV1,
    MissingObservationResearchResultV1,
    detector_config_identity_matches,
    due_expectations,
    missing_impact_id,
    missing_research_result_id,
    validate_expected_record,
)
from quantcheck.schemas import DatasetSnapshot

__all__ = [
    "MissingObservationResearchError",
    "compare_missing_observation_research",
    "declared_expected_cohort_mean_v1",
]


class MissingObservationResearchError(ValueError):
    """Raised for invalid or incomparable controlled research inputs."""


def declared_expected_cohort_mean_v1(
    snapshot: DatasetSnapshot,
    detector_config: MissingObservationDetectorConfigV1,
) -> MissingObservationResearchResultV1:
    """Compute one exact Decimal mean over observed due expectations."""
    if not dataset_snapshot_identity_matches(snapshot):
        raise MissingObservationResearchError("snapshot identity is invalid")
    if not detector_config_identity_matches(detector_config):
        raise MissingObservationResearchError("detector config identity is invalid")
    expectations = due_expectations(detector_config, snapshot.as_of_date)
    observed_expectations: list[str] = []
    missing_expectations: list[str] = []
    observed_record_ids: list[str] = []
    values: list[Decimal] = []
    for expectation in expectations:
        matches = tuple(
            record for record in snapshot.records if validate_expected_record(expectation, record)
        )
        if len(matches) > 1:
            raise MissingObservationResearchError(
                "one expected cell matches multiple records; cohort mean is ambiguous"
            )
        if not matches:
            missing_expectations.append(expectation.expected_observation_id)
            continue
        record = matches[0]
        observed_expectations.append(expectation.expected_observation_id)
        observed_record_ids.append(record.record_id)
        values.append(record.value)
    aggregate = sum(values, Decimal(0))
    if values:
        with localcontext() as context:
            context.prec = 50
            mean: Decimal | None = aggregate / Decimal(len(values))
    else:
        mean = None
    body: dict[str, object] = {
        "method": "declared_expected_cohort_mean_v1",
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_content_hash": canonical_sha256(snapshot),
        "detector_config_id": detector_config.detector_config_id,
        "as_of_date": snapshot.as_of_date,
        "expected_observation_count": len(expectations),
        "observed_expectation_ids": tuple(observed_expectations),
        "missing_expectation_ids": tuple(missing_expectations),
        "observed_record_ids": tuple(sorted(observed_record_ids)),
        "observed_count": len(observed_expectations),
        "aggregate_value": aggregate,
        "cohort_mean": mean,
    }
    return MissingObservationResearchResultV1.model_validate(
        {"research_result_id": missing_research_result_id(body=body), **body}
    )


def compare_missing_observation_research(
    clean_snapshot: DatasetSnapshot,
    corrupted_snapshot: DatasetSnapshot,
    repaired_snapshot: DatasetSnapshot,
    detector_config: MissingObservationDetectorConfigV1,
) -> MissingObservationResearchImpactV1:
    """Apply exactly the same cohort calculation to clean/corrupted/repaired states."""
    shapes = {
        (snapshot.dataset_name, snapshot.as_of_date)
        for snapshot in (clean_snapshot, corrupted_snapshot, repaired_snapshot)
    }
    if len(shapes) != 1:
        raise MissingObservationResearchError("research snapshots describe different cases")
    clean = declared_expected_cohort_mean_v1(clean_snapshot, detector_config)
    corrupted = declared_expected_cohort_mean_v1(corrupted_snapshot, detector_config)
    repaired = declared_expected_cohort_mean_v1(repaired_snapshot, detector_config)
    if clean.cohort_mean is None or corrupted.cohort_mean is None:
        mean_delta = None
    else:
        mean_delta = corrupted.cohort_mean - clean.cohort_mean
    body: dict[str, object] = {
        "method": "declared_expected_cohort_mean_v1",
        "clean": clean,
        "corrupted": corrupted,
        "repaired": repaired,
        "observed_count_delta": corrupted.observed_count - clean.observed_count,
        "aggregate_value_delta": corrupted.aggregate_value - clean.aggregate_value,
        "cohort_mean_delta": mean_delta,
        "changed": (
            corrupted.observed_count != clean.observed_count
            or corrupted.aggregate_value != clean.aggregate_value
            or corrupted.cohort_mean != clean.cohort_mean
        ),
        "exact_restoration": repaired == clean,
    }
    return MissingObservationResearchImpactV1.model_validate(
        {"impact_id": missing_impact_id(body=body), **body}
    )
