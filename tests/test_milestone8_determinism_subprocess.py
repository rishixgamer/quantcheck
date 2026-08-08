"""Cross-process benchmark determinism under runtime-environment changes.

In-process repetition cannot prove that a logical identity is free of runtime
influence, because the interpreter's hash seed, working directory, and
environment stay fixed. Each test here runs a fresh interpreter.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HASH_SEEDS = ("0", "1", "987654")

_CHILD_PROGRAM = r"""
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import quantcheck as q

runtime = q.RuntimeMetadata(
    code_version="quantcheck-0.1.0.dev0",
    python_version="3.12.13",
    platform="test-platform",
    generated_at=datetime(2026, 8, 7, 12, 0, 0, tzinfo=UTC),
)

config = q.smoke_benchmark_config()
output_root = Path(os.environ["BENCHMARK_OUTPUT_ROOT"])
result = q.run_benchmark(config, output_root=output_root, runtime=runtime)

public_root = output_root / q.PUBLIC_ROOT_NAME
rebuilt = q.aggregate_from_public_root(output_root)

case_bytes = {}
for status in result.statuses:
    directory = public_root / "cases" / status.benchmark_case_id
    for name in sorted(path.name for path in directory.iterdir()):
        case_bytes[f"{status.benchmark_case_id}/{name}"] = (directory / name).read_bytes().hex()

print(json.dumps({
    "benchmark_id": config.benchmark_id,
    "config": q.canonical_json_bytes(config).hex(),
    "matrix": q.canonical_json_bytes(result.matrix).hex(),
    "aggregate": q.canonical_json_bytes(result.aggregate).hex(),
    "rebuilt_aggregate": q.canonical_json_bytes(rebuilt).hex(),
    "case_bytes": case_bytes,
}, sort_keys=True))
"""

_REVERSED_CONFIG_PROGRAM = r"""
import json
from datetime import date

import quantcheck as q

reviewed = q.BenchmarkFixtureConfig(
    fixture_id=q.REVIEWED_FIXTURE_ID,
    dataset_name="reviewed",
    as_of_date=date(2024, 4, 30),
)
lookahead = q.BenchmarkLookAheadProfile(
    fixture=reviewed,
    severities=("low", "medium"),
    seeds=(0, 100),
    research=q.BenchmarkLookAheadResearch(research_as_of_date=date(2024, 4, 14)),
)
lookahead_reversed = q.BenchmarkLookAheadProfile(
    fixture=reviewed,
    severities=("medium", "low"),
    seeds=(100, 0),
    research=q.BenchmarkLookAheadResearch(research_as_of_date=date(2024, 4, 14)),
)
duplicate = q.BenchmarkDuplicateProfile(
    fixture=q.BenchmarkFixtureConfig(
        fixture_id=q.REVIEWED_FIXTURE_ID,
        dataset_name="reviewed",
        as_of_date=date(2024, 8, 31),
    ),
    severities=("medium",),
    seeds=(0,),
    research=q.BenchmarkDuplicateResearch(),
)
forward = q.build_benchmark_config(benchmark_name="order", profiles=(lookahead, duplicate))
backward = q.build_benchmark_config(
    benchmark_name="order", profiles=(duplicate, lookahead_reversed)
)
print(json.dumps({
    "forward": q.canonical_json_bytes(q.expand_benchmark_cases(forward)).hex(),
    "backward": q.canonical_json_bytes(q.expand_benchmark_cases(backward)).hex(),
}, sort_keys=True))
"""


def _run_child(
    program: str,
    hash_seed: str,
    cwd: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> dict[str, object]:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload: dict[str, object] = json.loads(result.stdout)
    return payload


def _run_benchmark_child(
    hash_seed: str,
    cwd: Path,
    output_root: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> dict[str, object]:
    env = {"BENCHMARK_OUTPUT_ROOT": str(output_root)}
    env.update(extra_env or {})
    return _run_child(_CHILD_PROGRAM, hash_seed, cwd, extra_env=env)


@pytest.fixture(scope="module")
def baseline(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    working = tmp_path_factory.mktemp("milestone8-baseline-cwd")
    output = tmp_path_factory.mktemp("milestone8-baseline-out")
    return _run_benchmark_child("0", working, output)


@pytest.mark.parametrize("hash_seed", _HASH_SEEDS)
def test_the_whole_benchmark_is_identical_across_required_hash_seeds(
    hash_seed: str,
    baseline: dict[str, object],
    tmp_path: Path,
) -> None:
    assert _run_benchmark_child(hash_seed, tmp_path, tmp_path / "output") == baseline


def test_a_different_output_root_does_not_change_any_logical_byte(
    baseline: dict[str, object],
    tmp_path: Path,
) -> None:
    deep = tmp_path / "a" / "deeply" / "nested" / "output" / "root"
    assert _run_benchmark_child("1", tmp_path, deep) == baseline


def test_working_temp_and_user_environment_do_not_change_any_logical_byte(
    baseline: dict[str, object],
    tmp_path: Path,
) -> None:
    working = tmp_path / "different" / "working" / "directory"
    working.mkdir(parents=True)
    assert (
        _run_benchmark_child(
            "987654",
            working,
            tmp_path / "output",
            extra_env={
                "TMPDIR": str(tmp_path / "temporary"),
                "QUANTCHECK_OUTPUT_DIR": str(tmp_path / "elsewhere"),
                "USER": "different-user",
                "LOGNAME": "different-user",
                "HOSTNAME": "different-host",
            },
        )
        == baseline
    )


def test_an_unrelated_parent_directory_file_changes_nothing(
    baseline: dict[str, object],
    tmp_path: Path,
) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "unrelated.json").write_text('{"not":"ours"}')
    (parent / "notes.txt").write_text("scratch")
    assert _run_benchmark_child("1", tmp_path, parent / "run") == baseline


def test_repeated_fresh_processes_are_identical(tmp_path: Path) -> None:
    first = _run_benchmark_child("1", tmp_path, tmp_path / "first")
    second = _run_benchmark_child("1", tmp_path, tmp_path / "second")
    assert first == second


def test_the_public_only_rebuild_matches_the_run_aggregate_in_a_fresh_process(
    baseline: dict[str, object],
) -> None:
    assert baseline["rebuilt_aggregate"] == baseline["aggregate"]


@pytest.mark.parametrize("hash_seed", _HASH_SEEDS)
def test_reversed_configuration_lists_expand_identically_in_a_fresh_process(
    hash_seed: str,
    tmp_path: Path,
) -> None:
    payload = _run_child(_REVERSED_CONFIG_PROGRAM, hash_seed, tmp_path)
    assert payload["forward"] == payload["backward"]
