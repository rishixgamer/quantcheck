"""Cross-process determinism for the Milestone 2 fixture, point-in-time, and
audit-boundary path.

Mirrors ``tests/test_determinism_subprocess.py``: each child runs in a fresh
interpreter, from a different working directory, with different environment
variables, so nothing survives from the parent process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HASH_SEEDS = ["0", "1", "987654"]

_CHILD_PROGRAM = """
import json
from datetime import date

import quantcheck as q

fixture = q.generate_reviewed_fixture()
snapshot = q.build_dataset_snapshot(fixture, dataset_name="reviewed", as_of_date=date(2024, 6, 1))
audit_input = q.sanitize_for_audit(snapshot)
rev = q.revision_id(lineage_id="E1-REV-Q1-2024", sequence=2)

print(json.dumps({
    "fixture_bytes_hex": q.canonical_json_bytes(list(fixture)).hex(),
    "fixture_sha": q.canonical_sha256(list(fixture)),
    "checked_in_fixture_bytes_hex": q.canonical_reviewed_fixture_bytes().hex(),
    "snapshot_id": snapshot.snapshot_id,
    "snapshot_sha": q.canonical_sha256(snapshot),
    "record_count": len(snapshot.records),
    "audit_input_id": audit_input.audit_input_id,
    "audit_sha": q.canonical_sha256(audit_input),
    "revision_id": rev,
}))
"""


def _run_child(
    hash_seed: str,
    cwd: Path,
    extra_env: dict[str, str] | None = None,
) -> dict[str, object]:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, "-c", _CHILD_PROGRAM],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload: dict[str, object] = json.loads(result.stdout)
    return payload


@pytest.fixture(scope="module")
def baseline(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    return _run_child("0", tmp_path_factory.mktemp("baseline"))


@pytest.mark.parametrize("hash_seed", _HASH_SEEDS)
def test_canonical_output_is_identical_across_hash_seeds(
    hash_seed: str, baseline: dict[str, object], tmp_path: Path
) -> None:
    assert _run_child(hash_seed, tmp_path) == baseline


def test_checked_in_fixture_bytes_match_across_processes(
    baseline: dict[str, object], tmp_path: Path
) -> None:
    for seed in _HASH_SEEDS:
        child = _run_child(seed, tmp_path)
        assert child["checked_in_fixture_bytes_hex"] == baseline["checked_in_fixture_bytes_hex"]


def test_working_directory_does_not_affect_logical_identity(
    baseline: dict[str, object], tmp_path: Path
) -> None:
    deep = tmp_path / "a" / "deeply" / "nested" / "output-root"
    deep.mkdir(parents=True)
    assert _run_child("0", deep) == baseline


def test_output_and_temp_directory_environment_does_not_affect_identity(
    baseline: dict[str, object], tmp_path: Path
) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()
    child = _run_child(
        "0",
        other,
        extra_env={
            "TMPDIR": str(other),
            "QUANTCHECK_OUTPUT_DIR": str(other / "artifacts"),
            "USER": "someone-else",
            "LOGNAME": "someone-else",
        },
    )
    assert child == baseline


def test_repeated_identical_child_runs_agree(tmp_path: Path) -> None:
    first = _run_child("1", tmp_path)
    second = _run_child("1", tmp_path)
    assert first == second


def test_identifiers_contain_no_local_path_fragments(baseline: dict[str, object]) -> None:
    for key in ("snapshot_id", "audit_input_id", "revision_id"):
        value = baseline[key]
        assert isinstance(value, str)
        assert "/" not in value
        assert "\\" not in value
        assert not any(marker in value for marker in ("Users", "home", "tmp", "var"))
