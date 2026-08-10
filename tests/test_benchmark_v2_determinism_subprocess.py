"""Cross-process byte determinism for v0.2 config, execution, and evaluation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HASH_SEEDS = ("0", "1", "987654")
_REPO_ROOT = Path(__file__).resolve().parent.parent

_CHILD_PROGRAM = r"""
import json
import os
from pathlib import Path

from quantcheck.benchmark_v2_case import run_benchmark_v2_case
from quantcheck.benchmark_v2_config import build_benchmark_v2_config, expand_benchmark_v2_cases
from quantcheck.benchmark_v2_schemas import BenchmarkV2Profile
from quantcheck.corpus_freeze import load_corpus_freeze_record
from quantcheck.serialization import canonical_json_bytes

freeze = load_corpus_freeze_record(Path(os.environ["QUANTCHECK_V2_FREEZE_PATH"]))
unit = next(
    unit
    for partition in freeze.corpus.partitions
    for unit in partition.units
    if unit.unit_name == "development-stress"
)
profile = BenchmarkV2Profile(
    fault_profile="lookahead_timestamp",
    corpus_unit_ids=(unit.corpus_unit_id,),
    severities=("low",),
    seeds=(0,),
)
config = build_benchmark_v2_config(
    benchmark_name="subprocess-determinism",
    corpus_freeze=freeze,
    profiles=(profile,),
)
matrix = expand_benchmark_v2_cases(config, corpus_freeze=freeze)
case = matrix.cases[0]
result = run_benchmark_v2_case(case)
artifacts = {
    "config": config,
    "matrix": matrix,
    "case": case,
    "clean_execution": result.clean_control_execution,
    "corrupted_execution": result.corrupted_execution,
    "evaluation": result.evaluation,
}
print(json.dumps({
    name: canonical_json_bytes(artifact).hex()
    for name, artifact in artifacts.items()
}, sort_keys=True))
"""


def _run(hash_seed: str, cwd: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = hash_seed
    environment["PYTHONPATH"] = str(_REPO_ROOT / "src")
    environment["QUANTCHECK_V2_FREEZE_PATH"] = str(_REPO_ROOT / "corpus_freeze_v0_2.json")
    environment.pop("QUANTCHECK_EXTERNAL_CORPUS_ROOT", None)
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD_PROGRAM],
        capture_output=True,
        text=True,
        check=True,
        env=environment,
        cwd=cwd,
    )
    parsed = json.loads(completed.stdout)
    assert isinstance(parsed, dict)
    assert all(isinstance(key, str) and isinstance(value, str) for key, value in parsed.items())
    return parsed


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, str]]:
    return [
        _run(hash_seed, tmp_path_factory.mktemp(f"benchmark-v2-run-{index}"))
        for index, hash_seed in enumerate(_HASH_SEEDS)
    ]


def test_every_v2_artifact_is_byte_identical_across_hash_seeds_and_directories(
    runs: list[dict[str, str]],
) -> None:
    assert set(runs[0]) == {
        "case",
        "clean_execution",
        "config",
        "corrupted_execution",
        "evaluation",
        "matrix",
    }
    for run in runs[1:]:
        assert run == runs[0]


def test_v2_identity_bearing_artifacts_are_nonempty(runs: list[dict[str, str]]) -> None:
    for payload in runs[0].values():
        assert len(bytes.fromhex(payload)) > 100
