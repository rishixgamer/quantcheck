"""The complete offline Milestone 8 smoke benchmark and its determinism.

No headline metric is asserted as a literal. These tests check the smoke's
*shape* and its invariants; the actual precision, recall, F1, and
false-positive rate are whatever the rebuilt implementation produces and are
recorded in the saved benchmark artifacts and current status notes.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import quantcheck as q
from tests.benchmark_support import FIXED_RUNTIME, public_root


@pytest.fixture(scope="module")
def smoke(tmp_path_factory: pytest.TempPathFactory) -> tuple[q.BenchmarkRunResult, Path]:
    root = tmp_path_factory.mktemp("benchmark-smoke")
    config = q.smoke_benchmark_config()
    return q.run_benchmark(config, output_root=root, runtime=FIXED_RUNTIME), root


def test_the_smoke_matrix_is_the_documented_twelve_cases(
    smoke: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = smoke
    assert result.matrix.case_count == q.SMOKE_CASE_COUNT == 12
    faults = [case for case in result.matrix.cases if case.case_kind == "fault"]
    controls = [case for case in result.matrix.cases if case.case_kind == "clean_control"]
    assert len(faults) == 8
    assert len(controls) == 4
    assert {case.fault_profile for case in controls} == set(q.BENCHMARK_FAULT_PROFILES)
    assert {case.seed for case in faults} == {
        q.SMOKE_DEVELOPMENT_SEED,
        q.SMOKE_VALIDATION_SEED,
    }


def test_the_smoke_exercises_both_a_development_and_a_validation_seed(
    smoke: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = smoke
    classes = {case.seed_class for case in result.matrix.cases}
    assert classes == {"development", "validation"}


def test_the_smoke_uses_no_held_out_release_seed(
    smoke: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = smoke
    assert all(not q.is_final_seed(case.seed) for case in result.matrix.cases)


def test_every_smoke_case_succeeds_offline(
    smoke: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = smoke
    failures = [status for status in result.statuses if status.status != "succeeded"]
    assert failures == []
    assert result.aggregate.overall.successful_case_count == 12
    assert result.aggregate.overall.failed_case_count == 0
    assert result.aggregate.overall.incomplete_case_count == 0


def test_the_smoke_injects_faults_and_finds_them_all(
    smoke: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = smoke
    overall = result.aggregate.overall
    assert overall.injected_faults > 0
    assert overall.false_negative_faults == 0
    assert overall.recall == 1
    assert overall.true_positive_findings == overall.true_positive_faults


def test_the_smoke_retains_cross_detector_false_positives(
    smoke: tuple[q.BenchmarkRunResult, Path],
) -> None:
    """Precision below one is the honest consequence of not suppressing them."""
    result, _ = smoke
    overall = result.aggregate.overall
    assert overall.false_positive_findings > 0
    assert overall.precision is not None
    assert overall.precision < 1
    assert overall.findings > overall.injected_faults


def test_the_smoke_reports_a_research_outcome_for_every_fault_case(
    smoke: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = smoke
    overall = result.aggregate.overall
    assert overall.research_summary_count == 8
    assert overall.research_changed_count == 8
    assert overall.replay_restored_count == 8


def test_every_smoke_group_is_present(smoke: tuple[q.BenchmarkRunResult, Path]) -> None:
    result, _ = smoke
    assert len(result.aggregate.by_fault_profile) == 4
    assert {g.key for g in result.aggregate.by_seed} == {"0", "100"}
    assert {g.key for g in result.aggregate.by_seed_class} == {"development", "validation"}


def test_a_repeated_smoke_run_reuses_every_case_and_reproduces_the_aggregate(
    smoke: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, root = smoke
    again = q.run_benchmark(q.smoke_benchmark_config(), output_root=root, runtime=FIXED_RUNTIME)
    assert len(again.reused_case_ids) == 12
    assert again.dispatched_case_ids == ()
    assert q.canonical_json_bytes(again.aggregate) == q.canonical_json_bytes(result.aggregate)


def test_a_different_output_root_produces_identical_logical_bytes(
    smoke: tuple[q.BenchmarkRunResult, Path], tmp_path: Path
) -> None:
    result, root = smoke
    other = q.run_benchmark(
        q.smoke_benchmark_config(),
        output_root=tmp_path / "elsewhere",
        runtime=FIXED_RUNTIME,
    )
    assert other.config.benchmark_id == result.config.benchmark_id
    assert q.canonical_json_bytes(other.matrix) == q.canonical_json_bytes(result.matrix)
    assert q.canonical_json_bytes(other.aggregate) == q.canonical_json_bytes(result.aggregate)
    for status in result.statuses:
        left = (public_root(root) / "cases" / status.benchmark_case_id / "score.json").read_bytes()
        right = (
            public_root(tmp_path / "elsewhere") / "cases" / status.benchmark_case_id / "score.json"
        ).read_bytes()
        assert left == right


def test_an_unrelated_file_beside_the_output_root_changes_nothing(
    smoke: tuple[q.BenchmarkRunResult, Path], tmp_path: Path
) -> None:
    result, _ = smoke
    parent = tmp_path / "noisy"
    parent.mkdir()
    (parent / "unrelated.txt").write_text("this file has nothing to do with the benchmark")
    other = q.run_benchmark(
        q.smoke_benchmark_config(), output_root=parent / "run", runtime=FIXED_RUNTIME
    )
    assert q.canonical_json_bytes(other.aggregate) == q.canonical_json_bytes(result.aggregate)


def test_the_public_only_rebuild_reproduces_the_saved_smoke_aggregate(
    smoke: tuple[q.BenchmarkRunResult, Path], tmp_path: Path
) -> None:
    _, root = smoke
    isolated = tmp_path / "public-only"
    shutil.copytree(public_root(root), isolated / "public")
    rebuilt = q.aggregate_from_public_root(isolated)
    assert (
        q.canonical_json_bytes(rebuilt)
        == (public_root(root) / "aggregate_report.json").read_bytes()
    )


def test_a_canonical_reload_of_every_public_artifact_round_trips(
    smoke: tuple[q.BenchmarkRunResult, Path],
) -> None:
    _, root = smoke
    for path in sorted(public_root(root).rglob("*.json")):
        payload = path.read_bytes()
        assert q.canonical_json_bytes(q.parse_canonical_json(payload)) == payload


def test_the_smoke_configuration_is_normalized_and_self_verifying() -> None:
    config = q.smoke_benchmark_config()
    assert q.benchmark_config_identity_matches(config)
    assert config.benchmark_name == q.SMOKE_BENCHMARK_NAME
    assert q.smoke_benchmark_config().benchmark_id == config.benchmark_id
    for case in q.expand_benchmark_cases(config).cases:
        assert q.benchmark_case_identity_matches(case)
