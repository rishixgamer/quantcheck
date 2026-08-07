"""Cross-process determinism for the complete Look-Ahead vertical slice."""

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
import os
from datetime import date

import quantcheck as q

records = q.generate_reviewed_fixture()
if os.environ.get("QUANTCHECK_REVERSE_INPUT") == "1":
    records = tuple(reversed(records))
clean = q.build_dataset_snapshot(
    records, dataset_name="reviewed", as_of_date=date(2024, 4, 30)
)
config = q.LookAheadInjectionConfig(
    severity="medium", seed=42, research_as_of_date=date(2024, 4, 14)
)
corrupted, manifest = q.inject_lookahead(clean, config)
audit_input = q.sanitize_for_audit(corrupted)
audit_report = q.detect_lookahead(audit_input)
score = q.score_lookahead(audit_report, manifest)
repaired = q.manifest_assisted_exact_replay(corrupted, manifest)
impact = q.compare_lookahead_research(
    clean, corrupted, repaired, research_as_of_date=config.research_as_of_date
)
print(json.dumps({
    "clean_id": clean.snapshot_id,
    "clean_hash": q.canonical_sha256(clean),
    "corrupted_id": corrupted.snapshot_id,
    "corrupted_hash": q.canonical_sha256(corrupted),
    "manifest_id": manifest.manifest_id,
    "manifest_hash": q.canonical_sha256(manifest),
    "audit_input_id": audit_input.audit_input_id,
    "audit_report_id": audit_report.audit_report_id,
    "score_id": score.score_report_id,
    "impact_id": impact.impact_id,
    "artifact_bytes": q.canonical_json_bytes({
        "manifest": manifest,
        "audit_report": audit_report,
        "score": score,
        "impact": impact,
    }).hex(),
}, sort_keys=True))
"""


def _run_child(
    hash_seed: str,
    cwd: Path,
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
    return _run_child("0", tmp_path_factory.mktemp("lookahead-baseline"))


@pytest.mark.parametrize("hash_seed", _HASH_SEEDS)
def test_full_artifacts_are_identical_across_python_hash_seeds(
    hash_seed: str,
    baseline: dict[str, str],
    tmp_path: Path,
) -> None:
    assert _run_child(hash_seed, tmp_path) == baseline


def test_source_order_reversal_does_not_change_full_artifacts(
    baseline: dict[str, str],
    tmp_path: Path,
) -> None:
    assert _run_child("1", tmp_path, {"QUANTCHECK_REVERSE_INPUT": "1"}) == baseline


def test_working_directory_and_environment_paths_do_not_change_artifacts(
    baseline: dict[str, str],
    tmp_path: Path,
) -> None:
    deep = tmp_path / "different" / "working" / "directory"
    deep.mkdir(parents=True)
    result = _run_child(
        "987654",
        deep,
        {
            "TMPDIR": str(deep / "tmp"),
            "QUANTCHECK_OUTPUT_DIR": str(deep / "artifacts"),
            "USER": "different-user",
            "LOGNAME": "different-user",
        },
    )
    assert result == baseline


def test_repeated_fresh_interpreters_produce_identical_bytes(tmp_path: Path) -> None:
    assert _run_child("0", tmp_path) == _run_child("0", tmp_path)


def test_identifiers_and_artifacts_contain_no_environment_path(
    baseline: dict[str, str],
) -> None:
    serialized = json.dumps(baseline)
    assert "/Users/" not in serialized
    assert "/home/" not in serialized
    assert "different-user" not in serialized
