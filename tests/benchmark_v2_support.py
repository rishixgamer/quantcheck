"""Shared deterministic builders for the additive v0.2 tests."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Literal

from quantcheck.benchmark_v2_case import BenchmarkV2CaseArtifacts, run_benchmark_v2_case
from quantcheck.benchmark_v2_config import (
    build_benchmark_v2_config,
    expand_benchmark_v2_cases,
)
from quantcheck.benchmark_v2_contract import ALL_V2_DETECTORS, DetectorKeyV2
from quantcheck.benchmark_v2_schemas import (
    BenchmarkV2CaseConfig,
    BenchmarkV2Profile,
    DetectorExecutionConfigV2,
)
from quantcheck.corpus_freeze import CorpusFreezeRecord, load_corpus_freeze_record
from quantcheck.corpus_schemas import CorpusUnitSpec

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_FREEZE_PATH = REPO_ROOT / "corpus_freeze_v0_2.json"


@cache
def corpus_freeze() -> CorpusFreezeRecord:
    return load_corpus_freeze_record(CORPUS_FREEZE_PATH)


def unit_named(name: str) -> CorpusUnitSpec:
    return next(
        unit
        for partition in corpus_freeze().corpus.partitions
        for unit in partition.units
        if unit.unit_name == name
    )


def case_for(
    fault_profile: DetectorKeyV2,
    *,
    unit_name: str | None = None,
    severity: Literal["low", "medium", "high"] = "low",
    seed: int = 0,
    selected_detectors: tuple[DetectorKeyV2, ...] = ALL_V2_DETECTORS,
) -> BenchmarkV2CaseConfig:
    role = unit_name
    if role is None:
        role = (
            "development-revisions"
            if fault_profile == "revision_overwrite"
            else "development-broad"
        )
    unit = unit_named(role)
    profile = BenchmarkV2Profile(
        fault_profile=fault_profile,
        corpus_unit_ids=(unit.corpus_unit_id,),
        severities=(severity,),
        seeds=(seed,),
    )
    execution = DetectorExecutionConfigV2(selected_detectors=selected_detectors)
    config = build_benchmark_v2_config(
        benchmark_name=f"test-{fault_profile}",
        corpus_freeze=corpus_freeze(),
        profiles=(profile,),
        detector_execution=execution,
    )
    matrix = expand_benchmark_v2_cases(config, corpus_freeze=corpus_freeze())
    assert matrix.case_count == 1
    return matrix.cases[0]


@cache
def case_result(
    fault_profile: DetectorKeyV2,
    unit_name: str,
    severity: Literal["low", "medium", "high"] = "low",
    seed: int = 0,
) -> BenchmarkV2CaseArtifacts:
    return run_benchmark_v2_case(
        case_for(
            fault_profile,
            unit_name=unit_name,
            severity=severity,
            seed=seed,
        )
    )
