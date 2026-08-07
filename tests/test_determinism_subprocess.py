"""Cross-process determinism, including Python hash randomization.

These run the canonical path in a fresh interpreter so that nothing survives
from the parent: no warm caches, no shared dict ordering, no shared PRNG
state. Each child also runs from a different working directory with different
environment variables, which proves that logical identity does not depend on
where the process happens to be running.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import quantcheck as q
from tests.test_golden_vectors import GOLDEN_FACT, GOLDEN_SNAPSHOT_ID

_HASH_SEEDS = ["0", "1", "987654"]

_CHILD_PROGRAM = """
import json
from datetime import date
from decimal import Decimal

import quantcheck as q

source = q.SourceReference(
    source_name="reviewed-fixture",
    source_locator="fixture-0001",
    source_row_key="row-0001",
)
record_id = q.source_record_id(
    source_name="reviewed-fixture",
    source_locator="fixture-0001",
    source_row_key="row-0001",
)
fact = q.FinancialFact(
    record_id=record_id,
    entity_id="CIK0000320193",
    entity_name="Example Corporation",
    concept_namespace="us-gaap",
    concept="Revenues",
    value=Decimal("1234567.8900"),
    unit="USD",
    dimensions=(
        q.Dimension(axis="Segment", member="Total"),
        q.Dimension(axis="Region", member="US"),
    ),
    period_type="duration",
    period_start=date(2024, 1, 1),
    period_end=date(2024, 3, 31),
    filed_on=date(2024, 5, 2),
    available_on=date(2024, 5, 2),
    form="10-Q",
    accession_number="0000320193-24-000069",
    source=source,
)
snapshot_id = q.dataset_snapshot_id(
    dataset_name="golden-demo", as_of_date=date(2024, 6, 30), records=[fact]
)
snapshot = q.DatasetSnapshot(
    snapshot_id=snapshot_id,
    dataset_name="golden-demo",
    as_of_date=date(2024, 6, 30),
    records=(fact,),
)
case_id = q.case_config_id(
    case_name="golden-case",
    dataset_name="golden-demo",
    as_of_date=date(2024, 6, 30),
    seed=42,
    spec_version="v0.1",
)
# A mapping built in an order that Python's hash randomization can influence.
mapping = {"zeta": 1, "alpha": {"y": 2, "x": 3}, "mu": [1, 2, 3]}

print(json.dumps({
    "fact_bytes": q.canonical_json_bytes(fact).hex(),
    "fact_sha": q.canonical_sha256(fact),
    "record_id": record_id,
    "snapshot_id": snapshot_id,
    "snapshot_sha": q.canonical_sha256(snapshot),
    "case_id": case_id,
    "mapping_bytes": q.canonical_json_bytes(mapping).hex(),
    "mapping_sha": q.canonical_sha256(mapping),
}))
"""


def _run_child(
    hash_seed: str,
    cwd: Path,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
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
    payload: dict[str, str] = json.loads(result.stdout)
    return payload


@pytest.fixture(scope="module")
def baseline(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return _run_child("0", tmp_path_factory.mktemp("baseline"))


@pytest.mark.parametrize("hash_seed", _HASH_SEEDS)
def test_canonical_output_is_identical_across_hash_seeds(
    hash_seed: str,
    baseline: dict[str, str],
    tmp_path: Path,
) -> None:
    assert _run_child(hash_seed, tmp_path) == baseline


@pytest.mark.parametrize("hash_seed", ["1", "987654"])
def test_required_hash_seeds_reproduce_the_in_process_result(
    hash_seed: str, tmp_path: Path
) -> None:
    """The two seeds the recovery harness names explicitly."""
    child = _run_child(hash_seed, tmp_path)
    assert child["fact_sha"] == q.canonical_sha256(GOLDEN_FACT)
    assert child["fact_bytes"] == q.canonical_json_bytes(GOLDEN_FACT).hex()
    assert child["snapshot_id"] == GOLDEN_SNAPSHOT_ID


def test_mapping_bytes_are_stable_across_hash_seeds(
    baseline: dict[str, str], tmp_path: Path
) -> None:
    """Dict iteration order is the thing PYTHONHASHSEED can move."""
    for seed in _HASH_SEEDS:
        child = _run_child(seed, tmp_path)
        assert child["mapping_bytes"] == baseline["mapping_bytes"]
        assert child["mapping_sha"] == baseline["mapping_sha"]


def test_working_directory_does_not_affect_logical_identity(
    baseline: dict[str, str], tmp_path: Path
) -> None:
    deep = tmp_path / "a" / "deeply" / "nested" / "output-root"
    deep.mkdir(parents=True)
    assert _run_child("0", deep) == baseline


def test_output_and_temp_directory_environment_does_not_affect_identity(
    baseline: dict[str, str], tmp_path: Path
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


def test_identifiers_contain_no_local_path_fragments(baseline: dict[str, str]) -> None:
    for key in ("record_id", "snapshot_id", "case_id"):
        value = baseline[key]
        assert "/" not in value
        assert "\\" not in value
        assert not any(marker in value for marker in ("Users", "home", "tmp", "var"))
