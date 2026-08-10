"""Contracts and deterministic injection for Missing Observations."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from quantcheck.hashing import canonical_sha256
from quantcheck.missing_observation_contract import (
    MissingnessMechanism,
    MissingObservationDetectorConfigV1,
    MissingObservationInjectionConfigV1,
    MissingObservationManifestV1,
    detector_config_identity_matches,
    expectation_identity_matches,
)
from quantcheck.missing_observation_fixture import (
    EVALUATION_MECHANISMS,
    build_missing_observation_evaluation_case,
)
from quantcheck.missing_observation_injection import (
    MissingObservationInjectionError,
    inject_missing_observations,
)
from quantcheck.missing_observation_manifest import validate_missing_observation_manifest
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json


@pytest.mark.parametrize("mechanism", EVALUATION_MECHANISMS)
def test_each_missingness_mechanism_is_distinct_and_exact(
    mechanism: MissingnessMechanism,
) -> None:
    case = build_missing_observation_evaluation_case("development", mechanism)
    before = canonical_json_bytes(case.clean_snapshot)

    corrupted, manifest = inject_missing_observations(
        case.clean_snapshot, case.detector_config, case.injection_config
    )

    assert canonical_json_bytes(case.clean_snapshot) == before
    assert len(corrupted.records) == len(case.clean_snapshot.records) - manifest.target_count
    assert manifest.injection_config.mechanism == mechanism
    assert manifest.target_count > 0
    assert all(entry.mechanism == mechanism for entry in manifest.entries)
    assert all(
        expectation_identity_matches(entry.expected_observation) for entry in manifest.entries
    )
    validate_missing_observation_manifest(manifest)


def test_mechanism_shapes_are_not_collapsed_to_random_row_deletion() -> None:
    manifests = {}
    for mechanism in EVALUATION_MECHANISMS:
        case = build_missing_observation_evaluation_case("development", mechanism)
        _corrupted, manifests[mechanism] = inject_missing_observations(
            case.clean_snapshot, case.detector_config, case.injection_config
        )

    assert manifests["random_missingness"].target_count == 4
    periodic = manifests["periodic_reporting_gap"]
    assert periodic.target_count == 2
    assert {entry.expected_observation.period_end.month for entry in periodic.entries} <= {6, 9}

    entity = manifests["entity_dependent_missingness"]
    assert entity.target_count == 2
    assert len({entry.deleted_record.entity_id for entry in entity.entries}) == 1

    concept = manifests["concept_dependent_missingness"]
    assert concept.target_count == 2
    assert len({entry.deleted_record.concept for entry in concept.entries}) == 1

    survivorship = manifests["survivorship_like_filtering"]
    assert survivorship.target_count == 8
    assert {entry.deleted_record.entity_id for entry in survivorship.entries} == set(
        survivorship.injection_config.survivorship_entity_ids
    )

    outage = manifests["source_feed_outage"]
    assert outage.target_count == 8
    assert {entry.expected_observation.period_end.month for entry in outage.entries} == {6, 9}
    assert (
        len(
            {
                (
                    entry.deleted_record.source.source_name,
                    entry.deleted_record.source.source_locator,
                )
                for entry in outage.entries
            }
        )
        == 1
    )


def test_same_inputs_reproduce_same_corruption_and_private_truth() -> None:
    case = build_missing_observation_evaluation_case("development", "random_missingness")
    first = inject_missing_observations(
        case.clean_snapshot, case.detector_config, case.injection_config
    )
    second = inject_missing_observations(
        case.clean_snapshot, case.detector_config, case.injection_config
    )
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_seed_changes_random_selection_without_changing_eligibility() -> None:
    case = build_missing_observation_evaluation_case("development", "random_missingness")
    fields = case.injection_config.model_dump()
    fields["seed"] = case.injection_config.seed + 1
    alternate = MissingObservationInjectionConfigV1.model_validate(fields)
    _first_snapshot, first = inject_missing_observations(
        case.clean_snapshot, case.detector_config, case.injection_config
    )
    _second_snapshot, second = inject_missing_observations(
        case.clean_snapshot, case.detector_config, alternate
    )
    assert first.eligible_units == second.eligible_units
    assert {entry.deleted_record.record_id for entry in first.entries} != {
        entry.deleted_record.record_id for entry in second.entries
    }


def test_complete_scope_mechanisms_refuse_partial_cap() -> None:
    case = build_missing_observation_evaluation_case("development", "survivorship_like_filtering")
    fields = case.injection_config.model_dump()
    fields["max_targets"] = 7
    capped = MissingObservationInjectionConfigV1.model_validate(fields)
    with pytest.raises(MissingObservationInjectionError, match="partial scope is refused"):
        inject_missing_observations(case.clean_snapshot, case.detector_config, capped)


def test_configs_and_manifest_canonical_round_trip() -> None:
    case = build_missing_observation_evaluation_case("validation", "source_feed_outage")
    corrupted, manifest = inject_missing_observations(
        case.clean_snapshot, case.detector_config, case.injection_config
    )
    parsed_config = MissingObservationDetectorConfigV1.model_validate(
        parse_canonical_json(canonical_json_bytes(case.detector_config))
    )
    parsed_manifest = MissingObservationManifestV1.model_validate(
        parse_canonical_json(canonical_json_bytes(manifest))
    )
    assert parsed_config == case.detector_config
    assert parsed_manifest == manifest
    assert detector_config_identity_matches(parsed_config)
    assert canonical_sha256(parsed_manifest) == canonical_sha256(manifest)
    assert corrupted.snapshot_id == manifest.corrupted_snapshot_id


def test_unknown_config_fields_and_invalid_mechanism_specific_fields_are_rejected() -> None:
    case = build_missing_observation_evaluation_case("development", "random_missingness")
    config_payload = case.detector_config.model_dump()
    config_payload["manifest_id"] = "man_deadbeefdeadbeef"
    with pytest.raises(ValidationError):
        MissingObservationDetectorConfigV1.model_validate(config_payload)

    with pytest.raises(ValidationError, match="applies only"):
        MissingObservationInjectionConfigV1(
            mechanism="random_missingness",
            severity="low",
            seed=0,
            max_targets=1,
            survivorship_entity_ids=(),
            outage_period_start=date(2023, 1, 1),
            outage_period_end=date(2023, 2, 1),
        )
