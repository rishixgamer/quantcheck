"""Cross-process Unit Drift determinism under runtime-environment changes."""

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
from datetime import date, timedelta
from decimal import Decimal

import quantcheck as q

records = []
for index, value in enumerate(("100", "110", "120", "130", "140")):
    period_end = date(2024, 1, 30) + timedelta(days=60 * index)
    row_key = f"subprocess-{index}"
    source = q.SourceReference(
        source_name="unit-drift-subprocess",
        source_locator="logical-fixture",
        source_row_key=row_key,
    )
    records.append(q.FinancialFact(
        record_id=q.source_record_id(
            source_name=source.source_name,
            source_locator=source.source_locator,
            source_row_key=source.source_row_key,
        ),
        entity_id="ENTITY-1",
        concept_namespace="us-gaap",
        concept="Revenues",
        value=Decimal(value),
        unit="USD",
        period_type="instant",
        period_end=period_end,
        filed_on=period_end,
        available_on=period_end,
        source=source,
    ))
if os.environ.get("UNIT_DRIFT_REVERSE") == "1":
    records.reverse()
as_of = date(2024, 12, 31)
clean = q.DatasetSnapshot(
    snapshot_id=q.dataset_snapshot_id(
        dataset_name="unit-drift-subprocess", as_of_date=as_of, records=records
    ),
    dataset_name="unit-drift-subprocess",
    as_of_date=as_of,
    records=tuple(records),
)
config = q.UnitDriftInjectionConfig(severity="medium", seed=6)
corrupted, manifest = q.inject_unit_drift(clean, config)
audit_input = q.sanitize_for_audit(corrupted)
audit_report = q.detect_unit_drift(audit_input, q.UnitDriftDetectorConfig())
score = q.score_unit_drift(audit_report, manifest)
repaired = q.manifest_assisted_exact_unit_drift_replay(corrupted, manifest)
research_config = q.UnitDriftResearchConfig(
    comparable_series_key=manifest.entries[0].comparable_series_key,
    research_as_of_date=as_of,
)
impact = q.compare_unit_drift_research(
    clean, corrupted, repaired, research_config
)
print(json.dumps({
    "clean": q.canonical_json_bytes(clean).hex(),
    "corrupted": q.canonical_json_bytes(corrupted).hex(),
    "manifest": q.canonical_json_bytes(manifest).hex(),
    "audit_input": q.canonical_json_bytes(audit_input).hex(),
    "audit_report": q.canonical_json_bytes(audit_report).hex(),
    "score": q.canonical_json_bytes(score).hex(),
    "repaired": q.canonical_json_bytes(repaired).hex(),
    "impact": q.canonical_json_bytes(impact).hex(),
}, sort_keys=True))
"""


def _run_child(
    hash_seed: str,
    cwd: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        [sys.executable, "-c", _CHILD_PROGRAM],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload: dict[str, str] = json.loads(result.stdout)
    return payload


@pytest.fixture(scope="module")
def baseline(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return _run_child("0", tmp_path_factory.mktemp("unit-drift-baseline"))


@pytest.mark.parametrize("hash_seed", _HASH_SEEDS)
def test_all_artifacts_are_identical_across_required_hash_seeds(
    hash_seed: str,
    baseline: dict[str, str],
    tmp_path: Path,
) -> None:
    assert _run_child(hash_seed, tmp_path) == baseline


def test_working_temp_output_and_user_environment_do_not_change_artifacts(
    baseline: dict[str, str],
    tmp_path: Path,
) -> None:
    working = tmp_path / "different" / "working" / "directory"
    working.mkdir(parents=True)
    assert (
        _run_child(
            "987654",
            working,
            extra_env={
                "TMPDIR": str(tmp_path / "temporary"),
                "QUANTCHECK_OUTPUT_DIR": str(tmp_path / "output"),
                "USER": "different-user",
                "LOGNAME": "different-user",
            },
        )
        == baseline
    )


def test_reversed_source_order_is_identical_in_a_fresh_process(
    baseline: dict[str, str],
    tmp_path: Path,
) -> None:
    assert (
        _run_child(
            "1",
            tmp_path,
            extra_env={"UNIT_DRIFT_REVERSE": "1"},
        )
        == baseline
    )


def test_repeated_fresh_processes_are_identical(tmp_path: Path) -> None:
    assert _run_child("1", tmp_path) == _run_child("1", tmp_path)
