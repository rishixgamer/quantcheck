"""Cross-process determinism of the v0.2 corpus.

In-process repetition cannot prove that a corpus unit's bytes are free of
runtime influence, because the interpreter's hash seed, working directory, and
environment stay fixed. Each test here runs a fresh interpreter, exactly as the
v0.1 milestone determinism tests do.
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

from quantcheck.corpus_eligibility import build_census
from quantcheck.corpus_gate import held_out_corpus_units
from quantcheck.corpus_registry import (
    build_corpus_definition,
    corpus_unit_canonical_bytes,
    corpus_unit_spec,
    declared_corpus_id,
    held_out_unit_ids,
    corpus_unit_records,
    partition_unit_ids,
)
from quantcheck.serialization import canonical_json_bytes

ordinary = ("development", "validation")
units = {}
specs = {}
for partition in ordinary:
    for unit_id in partition_unit_ids(partition):
        units[unit_id] = corpus_unit_canonical_bytes(unit_id).hex()
        specs[unit_id] = canonical_json_bytes(corpus_unit_spec(unit_id)).hex()

with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
    corpus = build_corpus_definition()

records = {
    unit_id: corpus_unit_records(unit_id)
    for partition in ordinary
    for unit_id in partition_unit_ids(partition)
}
census = build_census(corpus, records_by_unit=records, partitions=ordinary)

print(json.dumps({
    "declared_corpus_id": declared_corpus_id(),
    "corpus_id": corpus.corpus_id,
    "census_id": census.census_id,
    "census": canonical_json_bytes(census).hex(),
    "units": units,
    "specs": specs,
}, sort_keys=True))
"""


def _run(hash_seed: str, cwd: Path) -> dict[str, object]:
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = hash_seed
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent / "src")
    # An external corpus must never be picked up implicitly by a determinism run.
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
    return parsed


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, object]]:
    """One corpus build per hash seed, each from a different working directory."""
    results = []
    for index, hash_seed in enumerate(_HASH_SEEDS):
        cwd = tmp_path_factory.mktemp(f"corpus-run-{index}")
        results.append(_run(hash_seed, cwd))
    return results


class TestCorpusBytesSurviveTheRuntime:
    def test_unit_bytes_are_identical_across_hash_seeds_and_directories(
        self, runs: list[dict[str, object]]
    ) -> None:
        baseline = runs[0]["units"]
        for run in runs[1:]:
            assert run["units"] == baseline

    def test_unit_specifications_are_identical(self, runs: list[dict[str, object]]) -> None:
        baseline = runs[0]["specs"]
        for run in runs[1:]:
            assert run["specs"] == baseline

    def test_corpus_and_census_identifiers_are_identical(
        self, runs: list[dict[str, object]]
    ) -> None:
        for key in ("declared_corpus_id", "corpus_id", "census_id", "census"):
            baseline = runs[0][key]
            for run in runs[1:]:
                assert run[key] == baseline, f"{key} depends on the runtime environment"

    def test_every_run_produced_the_full_ordinary_corpus(
        self, runs: list[dict[str, object]]
    ) -> None:
        for run in runs:
            units = run["units"]
            assert isinstance(units, dict)
            assert len(units) == 8
