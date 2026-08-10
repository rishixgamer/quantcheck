"""Corpus-backed v0.2 configuration, expansion, and identity contracts."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError

from quantcheck.benchmark_v2_config import (
    benchmark_v2_case_identity_matches,
    benchmark_v2_config_identity_matches,
    build_benchmark_v2_config,
    expand_benchmark_v2_cases,
)
from quantcheck.benchmark_v2_contract import BenchmarkV2ContractError
from quantcheck.benchmark_v2_schemas import (
    BenchmarkV2Config,
    BenchmarkV2Profile,
    DetectorExecutionConfigV2,
)
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json
from tests.benchmark_v2_support import corpus_freeze, unit_named


def _profile(
    fault_profile: str = "lookahead_timestamp",
    *,
    unit_names: tuple[str, ...] = ("development-broad",),
    severities: tuple[Literal["low", "medium", "high"], ...] = ("low",),
    seeds: tuple[int, ...] = (0,),
) -> BenchmarkV2Profile:
    return BenchmarkV2Profile(
        fault_profile=fault_profile,  # type: ignore[arg-type]
        corpus_unit_ids=tuple(unit_named(name).corpus_unit_id for name in unit_names),
        severities=severities,
        seeds=seeds,
    )


def test_builds_one_versioned_config_over_the_frozen_corpus() -> None:
    config = build_benchmark_v2_config(
        benchmark_name="development-evidence",
        corpus_freeze=corpus_freeze(),
        profiles=(_profile(),),
    )
    assert config.spec_version == "quantcheck/benchmark/v2"
    assert config.corpus_id == corpus_freeze().corpus.corpus_id
    assert config.corpus_freeze_id == corpus_freeze().freeze_id
    assert config.corpus_census_id == corpus_freeze().census.census_id
    assert benchmark_v2_config_identity_matches(config)


def test_expansion_uses_corpus_units_and_their_declared_horizons() -> None:
    profile = _profile(
        unit_names=("development-broad", "validation-broad"),
        severities=("low", "medium"),
        seeds=(0, 100),
    )
    config = build_benchmark_v2_config(
        benchmark_name="two-partitions",
        corpus_freeze=corpus_freeze(),
        profiles=(profile,),
    )
    matrix = expand_benchmark_v2_cases(config, corpus_freeze=corpus_freeze())
    assert matrix.case_count == 8
    assert {case.partition for case in matrix.cases} == {"development", "validation"}
    for case in matrix.cases:
        unit = next(
            unit
            for partition in corpus_freeze().corpus.partitions
            for unit in partition.units
            if unit.corpus_unit_id == case.corpus_unit_id
        )
        assert case.horizon == unit.horizon
        assert case.audit_dataset_name == unit.audit_dataset_name
        assert case.corpus_unit_content_hash == unit.content_hash
        assert case.paired_clean_control is True
        assert benchmark_v2_case_identity_matches(case)


def test_logically_reordered_profiles_units_severities_and_seeds_are_identical() -> None:
    first = _profile(
        unit_names=("validation-broad", "development-broad"),
        severities=("medium", "low"),
        seeds=(100, 0),
    )
    second = _profile(
        unit_names=("development-broad", "validation-broad"),
        severities=("low", "medium"),
        seeds=(0, 100),
    )
    one = build_benchmark_v2_config(
        benchmark_name="same",
        corpus_freeze=corpus_freeze(),
        profiles=(first,),
    )
    two = build_benchmark_v2_config(
        benchmark_name="same",
        corpus_freeze=corpus_freeze(),
        profiles=(second,),
    )
    assert one == two
    assert expand_benchmark_v2_cases(one, corpus_freeze=corpus_freeze()) == (
        expand_benchmark_v2_cases(two, corpus_freeze=corpus_freeze())
    )


def test_primary_detector_must_be_inside_the_single_execution_config() -> None:
    selection = DetectorExecutionConfigV2(selected_detectors=("unit_drift",))
    with pytest.raises(ValidationError, match="primary detector"):
        build_benchmark_v2_config(
            benchmark_name="bad-selection",
            corpus_freeze=corpus_freeze(),
            profiles=(_profile(),),
            detector_execution=selection,
        )


def test_one_detector_is_a_valid_benchmark_configuration() -> None:
    selection = DetectorExecutionConfigV2(selected_detectors=("lookahead_timestamp",))
    config = build_benchmark_v2_config(
        benchmark_name="single-detector",
        corpus_freeze=corpus_freeze(),
        profiles=(_profile(),),
        detector_execution=selection,
    )
    assert config.detector_execution.selected_detectors == ("lookahead_timestamp",)


def test_heldout_corpus_units_are_rejected_before_materialization() -> None:
    profile = _profile(unit_names=("heldout-broad",))
    with pytest.raises(BenchmarkV2ContractError, match="development/validation"):
        build_benchmark_v2_config(
            benchmark_name="forbidden-heldout",
            corpus_freeze=corpus_freeze(),
            profiles=(profile,),
        )


def test_unit_declared_unsupported_for_profile_is_rejected() -> None:
    profile = _profile(
        fault_profile="revision_overwrite",
        unit_names=("development-broad",),
    )
    with pytest.raises(BenchmarkV2ContractError, match="does not support"):
        build_benchmark_v2_config(
            benchmark_name="unsupported-unit",
            corpus_freeze=corpus_freeze(),
            profiles=(profile,),
        )


@pytest.mark.parametrize("seed", (10, 999, 1000, 1009, 1010))
def test_only_development_and_validation_seeds_are_representable(seed: int) -> None:
    with pytest.raises(ValidationError, match="development/validation"):
        _profile(seeds=(seed,))


def test_configuration_and_matrix_round_trip_through_one_canonical_serializer() -> None:
    config = build_benchmark_v2_config(
        benchmark_name="round-trip",
        corpus_freeze=corpus_freeze(),
        profiles=(_profile(),),
    )
    matrix = expand_benchmark_v2_cases(config, corpus_freeze=corpus_freeze())
    parsed_config = BenchmarkV2Config.model_validate(
        parse_canonical_json(canonical_json_bytes(config))
    )
    assert parsed_config == config
    assert canonical_json_bytes(parsed_config) == canonical_json_bytes(config)
    assert canonical_json_bytes(matrix) == canonical_json_bytes(
        type(matrix).model_validate(parse_canonical_json(canonical_json_bytes(matrix)))
    )
