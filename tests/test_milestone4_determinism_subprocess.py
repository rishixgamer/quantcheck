"""Fresh-process determinism for SEC normalization, snapshot, and audit output."""

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

payload = q.reviewed_sec_fixture_payload()
if os.environ.get("QUANTCHECK_REVERSE_SEC_INPUT") == "1":
    payload["facts"]["us-gaap"]["Assets"]["units"]["USD"].reverse()
raw = q.canonical_json_bytes(payload)
cache = q.SecRawCache(os.environ["QUANTCHECK_SEC_CACHE_DIR"])
cache.accept(320193, url=q.companyfacts_url(320193), raw_bytes=raw)
replayed = cache.load(320193)
normalized = q.normalize_companyfacts(replayed.raw_bytes, q.reviewed_sec_normalization_config())
snapshot = q.build_sec_snapshot(
    normalized,
    dataset_name="sec-reviewed",
    as_of_date=date(2024, 12, 31),
)
audit = q.sanitize_for_audit(snapshot)
exclusions = [
    {
        "reason": item.reason,
        "taxonomy": item.taxonomy,
        "concept": item.concept,
        "unit": item.unit,
        "source_row_key": item.source_row_key,
    }
    for item in normalized.exclusions
]
print(json.dumps({
    "records_bytes": q.canonical_json_bytes(normalized.records).hex(),
    "records_sha": q.canonical_sha256(normalized.records),
    "source_rows": [record.source.source_row_key for record in normalized.records],
    "exclusions_bytes": q.canonical_json_bytes(exclusions).hex(),
    "snapshot_id": snapshot.snapshot_id,
    "snapshot_sha": q.canonical_sha256(snapshot),
    "audit_id": audit.audit_input_id,
    "audit_sha": q.canonical_sha256(audit),
}, sort_keys=True))
"""


def _run_child(
    hash_seed: str,
    cwd: Path,
    cache_dir: Path,
    extra_env: dict[str, str] | None = None,
) -> dict[str, object]:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = hash_seed
    env["QUANTCHECK_SEC_CACHE_DIR"] = str(cache_dir)
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
    payload: dict[str, object] = json.loads(result.stdout)
    return payload


@pytest.fixture(scope="module")
def baseline(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("sec-subprocess-baseline")
    return _run_child("0", root, root / "cache")


@pytest.mark.parametrize("hash_seed", _HASH_SEEDS)
def test_sec_logical_output_is_identical_across_python_hash_seeds(
    hash_seed: str,
    baseline: dict[str, object],
    tmp_path: Path,
) -> None:
    assert _run_child(hash_seed, tmp_path, tmp_path / f"cache-{hash_seed}") == baseline


def test_source_list_reversal_does_not_change_sec_logical_output(
    baseline: dict[str, object],
    tmp_path: Path,
) -> None:
    assert (
        _run_child(
            "1",
            tmp_path,
            tmp_path / "reversed-cache",
            {"QUANTCHECK_REVERSE_SEC_INPUT": "1"},
        )
        == baseline
    )


def test_cache_working_temp_output_and_user_environment_do_not_change_output(
    baseline: dict[str, object],
    tmp_path: Path,
) -> None:
    deep = tmp_path / "different" / "working" / "directory"
    deep.mkdir(parents=True)
    result = _run_child(
        "987654",
        deep,
        tmp_path / "elsewhere" / "companyfacts-cache",
        {
            "TMPDIR": str(tmp_path / "alternate-temp"),
            "QUANTCHECK_OUTPUT_DIR": str(tmp_path / "alternate-output"),
            "USER": "different-user",
            "LOGNAME": "different-user",
        },
    )
    assert result == baseline


def test_repeated_fresh_sec_processes_are_identical(tmp_path: Path) -> None:
    first = _run_child("0", tmp_path, tmp_path / "first-cache")
    second = _run_child("0", tmp_path, tmp_path / "second-cache")
    assert first == second


def test_sec_logical_output_contains_no_local_path_or_runtime_user(
    baseline: dict[str, object],
) -> None:
    serialized = json.dumps(baseline)
    assert "/Users/" not in serialized
    assert "/home/" not in serialized
    assert "different-user" not in serialized
