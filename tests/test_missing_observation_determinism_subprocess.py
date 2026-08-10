"""Cross-process determinism for the complete Missing Observations evaluation."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_CHILD = r"""
from quantcheck.hashing import canonical_sha256
from quantcheck.missing_observation_evaluation import run_missing_observation_evaluation
from quantcheck.missing_observation_fixture import (
    MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
    evaluation_case_ids,
)
from quantcheck.missing_observation_gate import heldout_missing_observation_cases

with heldout_missing_observation_cases(
    freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
    case_ids=evaluation_case_ids("heldout"),
):
    evidence = run_missing_observation_evaluation()
print(canonical_sha256(evidence))
"""


def _run(hash_seed: str, cwd: Path) -> str:
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONHASHSEED": hash_seed,
            "TMPDIR": str(cwd),
            "QUANTCHECK_OUTPUT_DIR": str(cwd / "unused-output"),
            "USER": f"missing-user-{hash_seed}",
            "LOGNAME": f"missing-log-{hash_seed}",
        }
    )
    result = subprocess.run(
        (sys.executable, "-c", _CHILD),
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    return result.stdout.strip()


@pytest.fixture(scope="module")
def baseline(tmp_path_factory: pytest.TempPathFactory) -> str:
    return _run("0", tmp_path_factory.mktemp("missing-evaluation-baseline"))


@pytest.mark.parametrize("hash_seed", ("0", "1", "987654"))
def test_complete_evaluation_is_hash_seed_independent(
    hash_seed: str, baseline: str, tmp_path: Path
) -> None:
    assert _run(hash_seed, tmp_path) == baseline


def test_working_directory_and_runtime_environment_are_not_logical_inputs(
    baseline: str, tmp_path: Path
) -> None:
    working = tmp_path / "different" / "working" / "directory"
    working.mkdir(parents=True)
    assert _run("987654", working) == baseline
