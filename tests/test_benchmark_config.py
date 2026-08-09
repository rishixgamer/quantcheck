"""Strict benchmark configuration, seed classification, and case expansion."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.benchmark_support import (
    duplicate_profile,
    lookahead_profile,
    revision_overwrite_profile,
    single_profile_config,
    unit_drift_profile,
)


def test_strict_configuration_normalizes_and_derives_a_stable_identifier() -> None:
    config = single_profile_config(lookahead_profile(seeds=(0, 100)))
    assert config.spec_version == q.BENCHMARK_SPEC_VERSION
    assert q.BENCHMARK_ID_PATTERN.fullmatch(config.benchmark_id)
    assert q.benchmark_config_identity_matches(config)


def test_configuration_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        q.BenchmarkFixtureConfig(
            fixture_id=q.REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=date(2024, 4, 30),
            output_dir="/tmp/benchmark",  # type: ignore[call-arg]
        )


def test_configuration_rejects_an_unsupported_fixture_identifier() -> None:
    with pytest.raises(ValidationError):
        q.BenchmarkFixtureConfig(
            fixture_id="quantcheck/some-other-fixture/v1",  # type: ignore[arg-type]
            dataset_name="reviewed",
            as_of_date=date(2024, 4, 30),
        )


def test_configuration_rejects_an_unsupported_severity() -> None:
    with pytest.raises(ValidationError, match="unsupported severity"):
        lookahead_profile(severities=("catastrophic",))


def test_configuration_rejects_duplicate_severities_and_seeds() -> None:
    with pytest.raises(ValidationError, match="duplicates"):
        lookahead_profile(severities=("medium", "medium"))
    with pytest.raises(ValidationError, match="duplicates"):
        lookahead_profile(seeds=(0, 0))


def test_configuration_rejects_an_empty_severity_or_seed_dimension() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        lookahead_profile(severities=())
    with pytest.raises(ValidationError, match="must not be empty"):
        lookahead_profile(seeds=())


def test_configuration_rejects_an_empty_benchmark_matrix() -> None:
    with pytest.raises(q.BenchmarkConfigurationError, match="at least one fault profile"):
        q.build_benchmark_config(benchmark_name="empty", profiles=())


def test_configuration_rejects_the_same_fault_profile_twice() -> None:
    with pytest.raises(ValidationError, match="configured twice"):
        q.build_benchmark_config(
            benchmark_name="doubled",
            profiles=(lookahead_profile(), lookahead_profile(seeds=(1,))),
        )


def test_configuration_rejects_an_incompatible_profile_and_fixture_combination() -> None:
    incompatible = q.BenchmarkUnitDriftProfile(
        fixture=q.BenchmarkFixtureConfig(
            fixture_id=q.REVIEWED_FIXTURE_ID,
            dataset_name="reviewed",
            as_of_date=date(2024, 12, 31),
        ),
        severities=("medium",),
        seeds=(0,),
        research=q.BenchmarkUnitDriftResearch(research_as_of_date=date(2024, 12, 31)),
    )
    with pytest.raises(q.BenchmarkConfigurationError, match="not supported on fixture"):
        single_profile_config(incompatible)


def test_configuration_rejects_a_clean_control_outside_its_own_dimensions() -> None:
    with pytest.raises(ValidationError, match="configured seeds"):
        single_profile_config(
            lookahead_profile(
                seeds=(0,), control=q.BenchmarkCleanControl(severity="medium", seed=1)
            )
        )
    with pytest.raises(ValidationError, match="configured severities"):
        single_profile_config(
            lookahead_profile(
                severities=("medium",),
                control=q.BenchmarkCleanControl(severity="low", seed=0),
            )
        )


@pytest.mark.parametrize("seed", [0, 5, 9])
def test_development_seeds_are_allowed(seed: int) -> None:
    assert q.classify_benchmark_seed(seed) == "development"


@pytest.mark.parametrize("seed", [100, 105, 109])
def test_validation_seeds_are_allowed(seed: int) -> None:
    assert q.classify_benchmark_seed(seed) == "validation"


@pytest.mark.parametrize("seed", [1000, 1005, 1009])
def test_final_release_seeds_remain_prohibited(seed: int) -> None:
    """A reserved seed can never be executed through an ordinary path.

    Milestone 11 moved where this is enforced. It used to be refused when a
    *profile* was constructed; it is now refused when a benchmark is built,
    expanded, or dispatched — because released held-out artifacts have to stay
    deserializable by the public reader and the presentation surfaces, which
    execute nothing. The prohibition itself is unchanged and is asserted here
    at every point that can actually run a case.
    """
    assert q.is_final_seed(seed)
    with pytest.raises(q.BenchmarkSeedClassError, match="reserved"):
        q.classify_benchmark_seed(seed)
    with pytest.raises(q.BenchmarkSeedClassError, match="not authorized"):
        q.require_seed_execution_authorized(seed)
    with pytest.raises(q.BenchmarkSeedClassError, match="not authorized"):
        q.build_benchmark_config(
            benchmark_name="prohibited",
            profiles=(lookahead_profile(seeds=(seed,)),),
        )


@pytest.mark.parametrize("seed", [10, 99, 110, 999, 1010])
def test_unclassified_seeds_are_rejected_rather_than_guessed(seed: int) -> None:
    with pytest.raises(q.BenchmarkSeedClassError, match="unclassified"):
        q.classify_benchmark_seed(seed)


def test_milestone8_exposes_no_release_seed_escape_hatch() -> None:
    """No benchmark entry point offers an override that admits a held-out seed."""
    import inspect

    modules = (
        q.benchmark_contract,
        q.benchmark_expansion,
        q.benchmark_dispatch,
        q.benchmark_runner,
    )
    forbidden = {"allow_final_seeds", "authorize_final_seeds", "held_out", "release", "force"}
    for module in modules:
        for name, function in inspect.getmembers(module, inspect.isfunction):
            if function.__module__ != module.__name__:
                continue
            overlap = forbidden.intersection(inspect.signature(function).parameters)
            assert not overlap, f"{module.__name__}.{name} exposes {sorted(overlap)}"
    assert tuple(q.FINAL_SEED_RANGE) == tuple(range(1000, 1010))
    for seed in q.FINAL_SEED_RANGE:
        # Enforced at the execution boundary since Milestone 11 (see
        # ``test_final_release_seeds_remain_prohibited``); still no parameter,
        # flag, or keyword anywhere that would admit one.
        with pytest.raises((q.BenchmarkSeedClassError, ValidationError)):
            q.build_benchmark_config(
                benchmark_name="escape-hatch",
                profiles=(lookahead_profile(seeds=(seed,)),),
            )


def test_expansion_covers_every_severity_seed_and_control_cell() -> None:
    config = q.build_benchmark_config(
        benchmark_name="expansion",
        profiles=(
            lookahead_profile(
                severities=("low", "medium"),
                seeds=(0, 100),
                control=q.BenchmarkCleanControl(severity="medium", seed=0),
            ),
            duplicate_profile(seeds=(0,)),
        ),
    )
    matrix = q.expand_benchmark_cases(config)
    assert matrix.case_count == len(matrix.cases) == 6
    faults = [case for case in matrix.cases if case.case_kind == "fault"]
    controls = [case for case in matrix.cases if case.case_kind == "clean_control"]
    assert len(faults) == 5
    assert len(controls) == 1
    assert {
        (case.severity, case.seed) for case in faults if case.fault_profile == "lookahead_timestamp"
    } == {
        ("low", 0),
        ("low", 100),
        ("medium", 0),
        ("medium", 100),
    }


def test_expansion_supports_all_four_fault_profiles() -> None:
    config = q.build_benchmark_config(
        benchmark_name="all-four",
        profiles=(
            lookahead_profile(),
            unit_drift_profile(),
            duplicate_profile(),
            revision_overwrite_profile(),
        ),
    )
    matrix = q.expand_benchmark_cases(config)
    assert {case.fault_profile for case in matrix.cases} == set(q.BENCHMARK_FAULT_PROFILES)


def test_expansion_is_deterministic_and_lexicographically_ordered() -> None:
    config = single_profile_config(lookahead_profile(severities=("low", "medium"), seeds=(0, 100)))
    first = q.expand_benchmark_cases(config)
    second = q.expand_benchmark_cases(config)
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)
    identifiers = [case.benchmark_case_id for case in first.cases]
    assert identifiers == sorted(identifiers)


def test_reordered_logically_equivalent_lists_produce_the_same_identity() -> None:
    forward = q.build_benchmark_config(
        benchmark_name="ordering",
        profiles=(
            lookahead_profile(severities=("low", "medium"), seeds=(0, 100)),
            duplicate_profile(),
        ),
    )
    reversed_config = q.build_benchmark_config(
        benchmark_name="ordering",
        profiles=(
            duplicate_profile(),
            lookahead_profile(severities=("medium", "low"), seeds=(100, 0)),
        ),
    )
    assert forward.benchmark_id == reversed_config.benchmark_id
    assert q.canonical_json_bytes(forward) == q.canonical_json_bytes(reversed_config)
    assert q.canonical_json_bytes(q.expand_benchmark_cases(forward)) == q.canonical_json_bytes(
        q.expand_benchmark_cases(reversed_config)
    )


def test_case_identities_are_stable_and_verifiable() -> None:
    config = single_profile_config(
        lookahead_profile(control=q.BenchmarkCleanControl(severity="medium", seed=0))
    )
    for case in q.expand_benchmark_cases(config).cases:
        assert q.BENCHMARK_CASE_ID_PATTERN.fullmatch(case.benchmark_case_id)
        assert q.benchmark_case_identity_matches(case)


def test_a_control_and_its_fault_sibling_have_distinct_identities() -> None:
    config = single_profile_config(
        lookahead_profile(control=q.BenchmarkCleanControl(severity="medium", seed=0))
    )
    cases = q.expand_benchmark_cases(config).cases
    identifiers = {case.case_kind: case.benchmark_case_id for case in cases}
    assert identifiers["fault"] != identifiers["clean_control"]


def test_case_identity_changes_with_every_scientific_input() -> None:
    base = single_profile_config(lookahead_profile(severities=("medium",), seeds=(0,)))
    variants = {
        "severity": single_profile_config(lookahead_profile(severities=("low",), seeds=(0,))),
        "seed": single_profile_config(lookahead_profile(severities=("medium",), seeds=(1,))),
        "detector": q.build_benchmark_config(
            benchmark_name="focused",
            profiles=(lookahead_profile(),),
            detector_configs=q.BenchmarkDetectorConfigs(
                unit_drift_detector=q.UnitDriftDetectorConfig(ratio_threshold=Decimal(25))
            ),
        ),
    }
    baseline = q.expand_benchmark_cases(base).cases[0].benchmark_case_id
    for label, variant in variants.items():
        changed = q.expand_benchmark_cases(variant).cases[0].benchmark_case_id
        assert changed != baseline, label


def test_logical_identity_excludes_every_runtime_and_environment_fact() -> None:
    runtime_only = {
        "output_root",
        "output_dir",
        "cwd",
        "tmpdir",
        "temp_dir",
        "username",
        "user",
        "home",
        "hostname",
        "generated_at",
        "python_version",
        "platform",
        "code_version",
    }
    assert runtime_only.isdisjoint(q.BenchmarkConfig.model_fields)
    assert runtime_only.isdisjoint(q.BenchmarkCaseConfig.model_fields)
    assert runtime_only.isdisjoint(q.BenchmarkFixtureConfig.model_fields)
    # Runtime facts live only here, and this model is not part of any identity.
    assert "generated_at" in q.RuntimeMetadata.model_fields


def test_detector_component_versions_match_the_frozen_family_contracts() -> None:
    detectors = q.BenchmarkDetectorConfigs()
    assert detectors.lookahead_detector_version == q.LOOKAHEAD_DETECTOR_VERSION
    assert detectors.unit_drift_detector_version == q.UNIT_DRIFT_DETECTOR_VERSION
    assert detectors.duplicate_detector_version == q.DUPLICATE_DETECTOR_VERSION
    assert detectors.revision_overwrite_detector_version == q.REVISION_OVERWRITE_DETECTOR_VERSION


def test_injector_component_versions_match_the_frozen_family_contracts() -> None:
    assert lookahead_profile().injector_spec_version == q.LOOKAHEAD_SPEC_VERSION
    assert unit_drift_profile().injector_spec_version == q.UNIT_DRIFT_SPEC_VERSION
    assert duplicate_profile().injector_spec_version == q.DUPLICATE_SPEC_VERSION
    assert revision_overwrite_profile().injector_spec_version == q.REVISION_OVERWRITE_SPEC_VERSION


def test_a_case_rejects_a_research_method_from_another_family() -> None:
    config = single_profile_config(lookahead_profile())
    case = q.expand_benchmark_cases(config).cases[0]
    body = {
        name: getattr(case, name)
        for name in q.BenchmarkCaseConfig.model_fields
        if name != "benchmark_case_id"
    }
    body["research"] = q.BenchmarkDuplicateResearch()
    with pytest.raises(ValidationError, match="research method"):
        q.BenchmarkCaseConfig.model_validate({"benchmark_case_id": case.benchmark_case_id, **body})


def test_a_case_rejects_an_impossible_seed_class_claim() -> None:
    config = single_profile_config(lookahead_profile(seeds=(0,)))
    case = q.expand_benchmark_cases(config).cases[0]
    body = {
        name: getattr(case, name)
        for name in q.BenchmarkCaseConfig.model_fields
        if name != "benchmark_case_id"
    }
    body["seed_class"] = "validation"
    with pytest.raises(ValidationError, match="documented partition"):
        q.BenchmarkCaseConfig.model_validate({"benchmark_case_id": case.benchmark_case_id, **body})


def test_matrix_rejects_a_case_count_that_disagrees_with_its_cases() -> None:
    matrix = q.expand_benchmark_cases(single_profile_config(lookahead_profile()))
    with pytest.raises(ValidationError, match="case_count"):
        q.BenchmarkCaseMatrix(
            benchmark_id=matrix.benchmark_id,
            cases=matrix.cases,
            case_count=matrix.case_count + 1,
        )
