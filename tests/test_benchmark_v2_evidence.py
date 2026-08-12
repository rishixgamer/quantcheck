"""Persisted v0.2 development/validation evidence and freeze gates."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

import pytest

from quantcheck.benchmark_v2_config import (
    build_benchmark_v2_config,
    expand_benchmark_v2_cases,
)
from quantcheck.benchmark_v2_evidence import (
    BenchmarkV2EvidenceError,
    aggregate_v2_from_public_root,
    build_design_partner_beta_matrices,
    run_v2_partition,
    verify_v2_validation_freeze,
    write_v2_validation_freeze,
)
from quantcheck.benchmark_v2_schemas import (
    BenchmarkV2CaseMatrix,
    BenchmarkV2Config,
    BenchmarkV2Profile,
)
from quantcheck.serialization import canonical_json_bytes
from tests.benchmark_v2_support import corpus_freeze, unit_named


def _partition_case(
    partition: Literal["development", "validation"],
) -> tuple[BenchmarkV2Config, BenchmarkV2CaseMatrix]:
    unit = unit_named(f"{partition}-broad")
    seed = 0 if partition == "development" else 100
    profile = BenchmarkV2Profile(
        fault_profile="duplicate_observation",
        corpus_unit_ids=(unit.corpus_unit_id,),
        severities=("low",),
        seeds=(seed,),
    )
    config = build_benchmark_v2_config(
        benchmark_name=f"evidence-test-{partition}",
        corpus_freeze=corpus_freeze(),
        profiles=(profile,),
    )
    return config, expand_benchmark_v2_cases(config, corpus_freeze=corpus_freeze())


def test_design_partner_matrices_preregister_all_supported_cells() -> None:
    development, validation = build_design_partner_beta_matrices(corpus_freeze())
    for partition, (_, matrix) in (
        ("development", development),
        ("validation", validation),
    ):
        assert matrix.case_count == 390
        assert {case.partition for case in matrix.cases} == {partition}
        assert {case.seed_class for case in matrix.cases} == {partition}
        assert {case.severity for case in matrix.cases} == {"low", "medium", "high"}
        assert {case.fault_profile for case in matrix.cases} == {
            "duplicate_observation",
            "lookahead_timestamp",
            "revision_overwrite",
            "unit_drift",
        }
        assert all(case.paired_clean_control for case in matrix.cases)


def test_public_only_aggregate_is_byte_identical_and_private_independent(
    tmp_path: Path,
) -> None:
    config, matrix = _partition_case("development")
    aggregate = run_v2_partition(
        config,
        matrix,
        output_root=tmp_path,
        partition="development",
    )
    saved = (tmp_path / "public/development_aggregate.json").read_bytes()
    assert saved == canonical_json_bytes(aggregate)
    shutil.rmtree(tmp_path / "private")
    rebuilt = aggregate_v2_from_public_root(tmp_path, "development")
    assert canonical_json_bytes(rebuilt) == saved
    overall = rebuilt["overall"]
    assert isinstance(overall, dict)
    assert overall["successful_case_count"] == 1
    assert overall["failed_case_count"] == 0
    assert overall["incomplete_case_count"] == 0


def test_validation_is_refused_until_development_freeze_exists(tmp_path: Path) -> None:
    config, matrix = _partition_case("validation")
    with pytest.raises(Exception, match="validation_freeze.json"):
        run_v2_partition(
            config,
            matrix,
            output_root=tmp_path,
            partition="validation",
        )


def test_development_then_freeze_then_validation_is_reproducible(tmp_path: Path) -> None:
    development_config, development_matrix = _partition_case("development")
    validation_config, validation_matrix = _partition_case("validation")
    run_v2_partition(
        development_config,
        development_matrix,
        output_root=tmp_path,
        partition="development",
    )
    freeze = write_v2_validation_freeze(
        tmp_path,
        development_config=development_config,
        development_matrix=development_matrix,
        validation_config=validation_config,
        validation_matrix=validation_matrix,
        source_hashes={"science.py": "0" * 64},
    )
    assert verify_v2_validation_freeze(tmp_path) == freeze
    validation = run_v2_partition(
        validation_config,
        validation_matrix,
        output_root=tmp_path,
        partition="validation",
    )
    assert validation["partition"] == "validation"

    # A resumed run reuses byte-identical immutable evidence.
    before = (tmp_path / "public/index.json").read_bytes()
    resumed = run_v2_partition(
        validation_config,
        validation_matrix,
        output_root=tmp_path,
        partition="validation",
    )
    assert canonical_json_bytes(resumed) == canonical_json_bytes(validation)
    assert (tmp_path / "public/index.json").read_bytes() == before


def test_incomplete_development_cannot_unseal_validation(tmp_path: Path) -> None:
    development_config, development_matrix = _partition_case("development")
    validation_config, validation_matrix = _partition_case("validation")
    public = tmp_path / "public"
    public.mkdir()
    (public / "development_matrix.json").write_bytes(canonical_json_bytes(development_matrix))
    with pytest.raises(BenchmarkV2EvidenceError, match="not complete"):
        write_v2_validation_freeze(
            tmp_path,
            development_config=development_config,
            development_matrix=development_matrix,
            validation_config=validation_config,
            validation_matrix=validation_matrix,
            source_hashes={},
        )
