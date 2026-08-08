"""Deterministic normalization and expansion of a logical benchmark.

One logical configuration expands into explicit immutable benchmark cases.
Expansion is a pure function of the normalized configuration: the same logical
configuration always produces the same case identifiers and the same execution
order, regardless of the order lists were written in, the output root, the
clock, the working directory, or ``PYTHONHASHSEED``.
"""

from __future__ import annotations

from collections.abc import Sequence

from quantcheck.benchmark_contract import (
    BENCHMARK_SPEC_VERSION,
    classify_benchmark_seed,
)
from quantcheck.benchmark_fixtures import (
    BENCHMARK_FIXTURE_IDS,
    UnknownBenchmarkFixtureError,
)
from quantcheck.hashing import (
    benchmark_clean_control_case_id,
    benchmark_config_id,
    benchmark_fault_case_id,
)
from quantcheck.schemas import (
    BenchmarkCaseConfig,
    BenchmarkCaseMatrix,
    BenchmarkConfig,
    BenchmarkDetectorConfigs,
    BenchmarkProfile,
)

__all__ = [
    "BenchmarkConfigurationError",
    "build_benchmark_config",
    "benchmark_config_identity_matches",
    "benchmark_case_identity_matches",
    "expand_benchmark_cases",
]

#: Which fixtures each fault profile may legitimately be configured against.
#: Look-Ahead, Duplicate, and Revision Overwrite operate on the reviewed
#: fixture; Unit Drift needs a comparable series of at least three observations
#: and therefore requires the benchmark series fixture (see
#: ``quantcheck.benchmark_fixtures``). Anything else is an incompatible
#: component combination and is rejected rather than attempted.
_SUPPORTED_FIXTURES_BY_PROFILE: dict[str, frozenset[str]] = {
    "lookahead_timestamp": frozenset({"quantcheck/reviewed-fixture/v1"}),
    "duplicate_observation": frozenset({"quantcheck/reviewed-fixture/v1"}),
    "revision_overwrite": frozenset({"quantcheck/reviewed-fixture/v1"}),
    "unit_drift": frozenset({"quantcheck/benchmark-unit-drift-series/v1"}),
}


class BenchmarkConfigurationError(ValueError):
    """Raised when a benchmark configuration cannot be normalized safely."""


def _check_component_compatibility(profiles: Sequence[BenchmarkProfile]) -> None:
    for profile in profiles:
        fixture_id = profile.fixture.fixture_id
        if fixture_id not in BENCHMARK_FIXTURE_IDS:
            raise UnknownBenchmarkFixtureError(f"unsupported benchmark fixture: {fixture_id!r}")
        supported = _SUPPORTED_FIXTURES_BY_PROFILE[profile.fault_profile]
        if fixture_id not in supported:
            raise BenchmarkConfigurationError(
                f"fault profile {profile.fault_profile!r} is not supported on fixture "
                f"{fixture_id!r}"
            )
        for seed in profile.seeds:
            classify_benchmark_seed(seed)


def _config_body(
    *,
    benchmark_name: str,
    detector_configs: BenchmarkDetectorConfigs,
    profiles: Sequence[BenchmarkProfile],
) -> dict[str, object]:
    return {
        "spec_version": BENCHMARK_SPEC_VERSION,
        "benchmark_name": benchmark_name,
        "detector_configs": detector_configs,
        "profiles": tuple(profiles),
    }


def build_benchmark_config(
    *,
    benchmark_name: str,
    profiles: Sequence[BenchmarkProfile],
    detector_configs: BenchmarkDetectorConfigs | None = None,
) -> BenchmarkConfig:
    """Normalize one logical benchmark and derive its stable identifier.

    Normalization sorts severities, seeds, and profiles, so two configurations
    that differ only in the order their lists were written produce identical
    bytes and therefore an identical ``benchmark_id``.
    """
    if not profiles:
        raise BenchmarkConfigurationError(
            "a benchmark matrix must configure at least one fault profile"
        )
    resolved_detectors = detector_configs or BenchmarkDetectorConfigs()
    _check_component_compatibility(profiles)

    # Validate once to obtain the normalized (sorted, deduplicated) form, then
    # hash that normalized form rather than the caller's ordering.
    normalized = BenchmarkConfig.model_validate(
        {
            "benchmark_id": benchmark_config_id(
                config_body=_config_body(
                    benchmark_name=benchmark_name,
                    detector_configs=resolved_detectors,
                    profiles=profiles,
                )
            ),
            **_config_body(
                benchmark_name=benchmark_name,
                detector_configs=resolved_detectors,
                profiles=profiles,
            ),
        }
    )
    body = _config_body(
        benchmark_name=normalized.benchmark_name,
        detector_configs=normalized.detector_configs,
        profiles=normalized.profiles,
    )
    return BenchmarkConfig.model_validate(
        {"benchmark_id": benchmark_config_id(config_body=body), **body}
    )


def benchmark_config_identity_matches(config: BenchmarkConfig) -> bool:
    """Report whether a benchmark's stored identifier matches its content."""
    body = _config_body(
        benchmark_name=config.benchmark_name,
        detector_configs=config.detector_configs,
        profiles=config.profiles,
    )
    return config.benchmark_id == benchmark_config_id(config_body=body)


def _case_body(
    *,
    benchmark_id: str,
    case_kind: str,
    profile: BenchmarkProfile,
    detector_configs: BenchmarkDetectorConfigs,
    severity: str,
    seed: int,
) -> dict[str, object]:
    return {
        "benchmark_id": benchmark_id,
        "spec_version": BENCHMARK_SPEC_VERSION,
        "case_kind": case_kind,
        "fault_profile": profile.fault_profile,
        "injector_spec_version": profile.injector_spec_version,
        "fixture": profile.fixture,
        "detector_configs": detector_configs,
        "severity": severity,
        "seed": seed,
        "seed_class": classify_benchmark_seed(seed),
        "max_targets": profile.max_targets,
        "research": profile.research,
    }


def _build_case(
    *,
    benchmark_id: str,
    case_kind: str,
    profile: BenchmarkProfile,
    detector_configs: BenchmarkDetectorConfigs,
    severity: str,
    seed: int,
) -> BenchmarkCaseConfig:
    body = _case_body(
        benchmark_id=benchmark_id,
        case_kind=case_kind,
        profile=profile,
        detector_configs=detector_configs,
        severity=severity,
        seed=seed,
    )
    identifier = (
        benchmark_fault_case_id(case_body=body)
        if case_kind == "fault"
        else benchmark_clean_control_case_id(case_body=body)
    )
    return BenchmarkCaseConfig.model_validate({"benchmark_case_id": identifier, **body})


def benchmark_case_identity_matches(case: BenchmarkCaseConfig) -> bool:
    """Report whether an expanded case's stored identifier matches its content."""
    body = {
        name: getattr(case, name)
        for name in BenchmarkCaseConfig.model_fields
        if name != "benchmark_case_id"
    }
    expected = (
        benchmark_fault_case_id(case_body=body)
        if case.case_kind == "fault"
        else benchmark_clean_control_case_id(case_body=body)
    )
    return case.benchmark_case_id == expected


def expand_benchmark_cases(config: BenchmarkConfig) -> BenchmarkCaseMatrix:
    """Expand a normalized benchmark into its explicit immutable case matrix.

    The matrix is sorted by ``benchmark_case_id``, which is also the execution
    order: lexicographic, stable, and independent of how the configuration was
    written or of anything about the machine running it.
    """
    if not benchmark_config_identity_matches(config):
        raise BenchmarkConfigurationError(
            "benchmark configuration identity does not match its content"
        )
    _check_component_compatibility(config.profiles)

    cases: list[BenchmarkCaseConfig] = []
    for profile in config.profiles:
        for severity in profile.severities:
            for seed in profile.seeds:
                cases.append(
                    _build_case(
                        benchmark_id=config.benchmark_id,
                        case_kind="fault",
                        profile=profile,
                        detector_configs=config.detector_configs,
                        severity=severity,
                        seed=seed,
                    )
                )
        control = profile.clean_control
        if control is not None:
            cases.append(
                _build_case(
                    benchmark_id=config.benchmark_id,
                    case_kind="clean_control",
                    profile=profile,
                    detector_configs=config.detector_configs,
                    severity=control.severity,
                    seed=control.seed,
                )
            )

    identifiers = [case.benchmark_case_id for case in cases]
    if len(set(identifiers)) != len(identifiers):
        raise BenchmarkConfigurationError("benchmark expansion produced duplicate case identities")
    return BenchmarkCaseMatrix(
        benchmark_id=config.benchmark_id,
        spec_version=BENCHMARK_SPEC_VERSION,
        cases=tuple(cases),
        case_count=len(cases),
    )
