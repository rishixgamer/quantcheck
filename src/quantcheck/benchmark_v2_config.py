"""Normalization and expansion of a corpus-backed ``quantcheck/benchmark/v2``."""

from __future__ import annotations

from collections.abc import Sequence

from quantcheck.benchmark_contract import classify_benchmark_seed
from quantcheck.benchmark_v2_contract import (
    BENCHMARK_V2_CASE_NAMESPACE,
    BENCHMARK_V2_CONFIG_NAMESPACE,
    BENCHMARK_V2_SPEC_VERSION,
    INJECTOR_SPEC_VERSION_BY_PROFILE,
    V2_DEVELOPMENT_PARTITIONS,
    BenchmarkV2ContractError,
)
from quantcheck.benchmark_v2_schemas import (
    BenchmarkV2CaseConfig,
    BenchmarkV2CaseMatrix,
    BenchmarkV2Config,
    BenchmarkV2Profile,
    DetectorExecutionConfigV2,
)
from quantcheck.corpus_eligibility import census_identity_matches
from quantcheck.corpus_freeze import CorpusFreezeRecord
from quantcheck.corpus_registry import corpus_definition_identity_matches
from quantcheck.corpus_schemas import CorpusEligibilityCell, CorpusUnitSpec
from quantcheck.hashing import stable_id

__all__ = [
    "benchmark_v2_case_identity_matches",
    "benchmark_v2_config_identity_matches",
    "build_benchmark_v2_config",
    "expand_benchmark_v2_cases",
]


def _units_by_id(freeze: CorpusFreezeRecord) -> dict[str, CorpusUnitSpec]:
    return {
        unit.corpus_unit_id: unit
        for partition in freeze.corpus.partitions
        for unit in partition.units
    }


def _cells_by_key(
    freeze: CorpusFreezeRecord,
) -> dict[tuple[str, str, str], CorpusEligibilityCell]:
    return {
        (cell.corpus_unit_id, cell.fault_profile, cell.severity): cell
        for cell in freeze.census.cells
    }


def _validate_freeze(freeze: CorpusFreezeRecord) -> None:
    if not corpus_definition_identity_matches(freeze.corpus):
        raise BenchmarkV2ContractError("corpus identity does not match its frozen content")
    if not census_identity_matches(freeze.census):
        raise BenchmarkV2ContractError("corpus census identity does not match its content")
    if freeze.census.corpus_id != freeze.corpus.corpus_id:
        raise BenchmarkV2ContractError("corpus freeze and census identities disagree")


def _validate_profiles(
    freeze: CorpusFreezeRecord,
    profiles: Sequence[BenchmarkV2Profile],
) -> None:
    units = _units_by_id(freeze)
    cells = _cells_by_key(freeze)
    for profile in profiles:
        for unit_id in profile.corpus_unit_ids:
            try:
                unit = units[unit_id]
            except KeyError as exc:
                raise BenchmarkV2ContractError(
                    f"unsupported frozen corpus unit: {unit_id!r}"
                ) from exc
            if unit.partition not in V2_DEVELOPMENT_PARTITIONS:
                raise BenchmarkV2ContractError(
                    "v0.2 development evidence may use only development/validation corpus units"
                )
            if profile.fault_profile not in unit.supported_fault_profiles:
                raise BenchmarkV2ContractError(
                    f"corpus unit {unit_id} does not support {profile.fault_profile}"
                )
            if unit.content_hash is None:
                raise BenchmarkV2ContractError("a runnable corpus unit requires a content hash")
            for severity in profile.severities:
                cell = cells.get((unit_id, profile.fault_profile, severity))
                if cell is None or cell.eligible_unit_count == 0:
                    raise BenchmarkV2ContractError(
                        f"corpus unit {unit_id} has no eligible {profile.fault_profile}/"
                        f"{severity} target"
                    )
        for seed in profile.seeds:
            seed_class = classify_benchmark_seed(seed)
            if seed_class not in V2_DEVELOPMENT_PARTITIONS:
                raise BenchmarkV2ContractError(
                    "v0.2 development evidence may use only development/validation seeds"
                )


def _config_body(
    *,
    benchmark_name: str,
    freeze: CorpusFreezeRecord,
    detector_execution: DetectorExecutionConfigV2,
    profiles: Sequence[BenchmarkV2Profile],
) -> dict[str, object]:
    return {
        "spec_version": BENCHMARK_V2_SPEC_VERSION,
        "benchmark_name": benchmark_name,
        "corpus_id": freeze.corpus.corpus_id,
        "corpus_freeze_id": freeze.freeze_id,
        "corpus_census_id": freeze.census.census_id,
        "detector_execution": detector_execution,
        "profiles": tuple(profiles),
    }


def build_benchmark_v2_config(
    *,
    benchmark_name: str,
    corpus_freeze: CorpusFreezeRecord,
    profiles: Sequence[BenchmarkV2Profile],
    detector_execution: DetectorExecutionConfigV2 | None = None,
) -> BenchmarkV2Config:
    """Build the one canonical config used by both Python and the v0.2 CLI."""
    _validate_freeze(corpus_freeze)
    if not profiles:
        raise BenchmarkV2ContractError("a v0.2 benchmark requires at least one profile")
    resolved_execution = detector_execution or DetectorExecutionConfigV2()
    _validate_profiles(corpus_freeze, profiles)
    provisional_body = _config_body(
        benchmark_name=benchmark_name,
        freeze=corpus_freeze,
        detector_execution=resolved_execution,
        profiles=profiles,
    )
    normalized = BenchmarkV2Config.model_validate(
        {
            "benchmark_v2_id": stable_id(
                prefix="bench2",
                namespace=BENCHMARK_V2_CONFIG_NAMESPACE,
                payload=provisional_body,
            ),
            **provisional_body,
        }
    )
    settled_body = _config_body(
        benchmark_name=normalized.benchmark_name,
        freeze=corpus_freeze,
        detector_execution=normalized.detector_execution,
        profiles=normalized.profiles,
    )
    return BenchmarkV2Config.model_validate(
        {
            "benchmark_v2_id": stable_id(
                prefix="bench2",
                namespace=BENCHMARK_V2_CONFIG_NAMESPACE,
                payload=settled_body,
            ),
            **settled_body,
        }
    )


def benchmark_v2_config_identity_matches(config: BenchmarkV2Config) -> bool:
    body = {
        name: getattr(config, name)
        for name in BenchmarkV2Config.model_fields
        if name != "benchmark_v2_id"
    }
    return config.benchmark_v2_id == stable_id(
        prefix="bench2",
        namespace=BENCHMARK_V2_CONFIG_NAMESPACE,
        payload=body,
    )


def _case_body(
    *,
    config: BenchmarkV2Config,
    unit: CorpusUnitSpec,
    profile: BenchmarkV2Profile,
    severity: str,
    seed: int,
    eligible_unit_count: int,
) -> dict[str, object]:
    assert unit.content_hash is not None
    return {
        "benchmark_v2_id": config.benchmark_v2_id,
        "spec_version": BENCHMARK_V2_SPEC_VERSION,
        "corpus_id": config.corpus_id,
        "corpus_freeze_id": config.corpus_freeze_id,
        "corpus_census_id": config.corpus_census_id,
        "corpus_unit_id": unit.corpus_unit_id,
        "corpus_unit_content_hash": unit.content_hash,
        "partition": unit.partition,
        "audit_dataset_name": unit.audit_dataset_name,
        "horizon": unit.horizon,
        "fault_profile": profile.fault_profile,
        "injector_spec_version": INJECTOR_SPEC_VERSION_BY_PROFILE[profile.fault_profile],
        "severity": severity,
        "seed": seed,
        "seed_class": classify_benchmark_seed(seed),
        "max_targets": profile.max_targets,
        "detector_execution": config.detector_execution,
        "paired_clean_control": True,
        "eligible_unit_count": eligible_unit_count,
    }


def expand_benchmark_v2_cases(
    config: BenchmarkV2Config,
    *,
    corpus_freeze: CorpusFreezeRecord,
) -> BenchmarkV2CaseMatrix:
    """Expand corpus unit x severity x seed into deterministic paired-control cases."""
    if not benchmark_v2_config_identity_matches(config):
        raise BenchmarkV2ContractError("v0.2 benchmark identity does not match its content")
    _validate_freeze(corpus_freeze)
    if (
        config.corpus_id != corpus_freeze.corpus.corpus_id
        or config.corpus_freeze_id != corpus_freeze.freeze_id
        or config.corpus_census_id != corpus_freeze.census.census_id
    ):
        raise BenchmarkV2ContractError("configuration names a different corpus freeze")
    _validate_profiles(corpus_freeze, config.profiles)
    units = _units_by_id(corpus_freeze)
    cells = _cells_by_key(corpus_freeze)
    cases: list[BenchmarkV2CaseConfig] = []
    for profile in config.profiles:
        for unit_id in profile.corpus_unit_ids:
            unit = units[unit_id]
            for severity in profile.severities:
                cell = cells[(unit_id, profile.fault_profile, severity)]
                for seed in profile.seeds:
                    body = _case_body(
                        config=config,
                        unit=unit,
                        profile=profile,
                        severity=severity,
                        seed=seed,
                        eligible_unit_count=cell.eligible_unit_count,
                    )
                    cases.append(
                        BenchmarkV2CaseConfig.model_validate(
                            {
                                "benchmark_v2_case_id": stable_id(
                                    prefix="bcase2",
                                    namespace=BENCHMARK_V2_CASE_NAMESPACE,
                                    payload=body,
                                ),
                                **body,
                            }
                        )
                    )
    return BenchmarkV2CaseMatrix(
        benchmark_v2_id=config.benchmark_v2_id,
        cases=tuple(cases),
        case_count=len(cases),
    )


def benchmark_v2_case_identity_matches(case: BenchmarkV2CaseConfig) -> bool:
    body = {
        name: getattr(case, name)
        for name in BenchmarkV2CaseConfig.model_fields
        if name != "benchmark_v2_case_id"
    }
    return case.benchmark_v2_case_id == stable_id(
        prefix="bcase2",
        namespace=BENCHMARK_V2_CASE_NAMESPACE,
        payload=body,
    )
