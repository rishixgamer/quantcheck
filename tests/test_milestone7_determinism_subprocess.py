"""Cross-process Revision Overwrite determinism under runtime-environment changes."""

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
from datetime import date

import quantcheck as q

source_records = list(q.generate_reviewed_fixture())
if os.environ.get("REVISION_OVERWRITE_REVERSE") == "1":
    source_records.reverse()

clean = q.build_dataset_snapshot(
    source_records,
    dataset_name="revision-overwrite-subprocess",
    as_of_date=date(2024, 4, 30),
)
corrupted, manifest = q.inject_revision_overwrite(
    clean,
    source_records,
    q.RevisionOverwriteInjectionConfig(severity="low", seed=7),
)
audit_input = q.sanitize_for_audit(corrupted)
audit_report = q.detect_revision_overwrite(
    audit_input,
    q.RevisionOverwriteDetectorConfig(),
)
score = q.score_revision_overwrite(audit_report, manifest)
repaired = q.manifest_assisted_exact_revision_overwrite_replay(corrupted, manifest)
research_config = q.GrowthRankingConfig(
    concept_namespace="us-gaap",
    concept="NetIncomeLoss",
    unit="USD",
    prior_period_start=date(2024, 1, 1),
    prior_period_end=date(2024, 3, 31),
    current_period_start=date(2024, 4, 1),
    current_period_end=date(2024, 6, 30),
    research_as_of_date=date(2024, 8, 31),
    top_n=1,
)
clean_research = q.build_frozen_vintage_growth_snapshot(
    clean,
    source_records,
    research_config,
)
corrupted_research = q.build_frozen_vintage_growth_snapshot(
    corrupted,
    source_records,
    research_config,
)
repaired_research = q.build_frozen_vintage_growth_snapshot(
    repaired,
    source_records,
    research_config,
)
impact = q.compare_revision_overwrite_research(
    clean_research,
    corrupted_research,
    repaired_research,
    research_config,
)
print(json.dumps({
    "clean": q.canonical_json_bytes(clean).hex(),
    "corrupted": q.canonical_json_bytes(corrupted).hex(),
    "manifest": q.canonical_json_bytes(manifest).hex(),
    "audit_input": q.canonical_json_bytes(audit_input).hex(),
    "audit_report": q.canonical_json_bytes(audit_report).hex(),
    "score": q.canonical_json_bytes(score).hex(),
    "repaired": q.canonical_json_bytes(repaired).hex(),
    "clean_research": q.canonical_json_bytes(clean_research).hex(),
    "corrupted_research": q.canonical_json_bytes(corrupted_research).hex(),
    "repaired_research": q.canonical_json_bytes(repaired_research).hex(),
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
    return _run_child("0", tmp_path_factory.mktemp("revision-overwrite-baseline"))


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
            extra_env={"REVISION_OVERWRITE_REVERSE": "1"},
        )
        == baseline
    )


def test_repeated_fresh_processes_are_identical(tmp_path: Path) -> None:
    assert _run_child("1", tmp_path) == _run_child("1", tmp_path)
