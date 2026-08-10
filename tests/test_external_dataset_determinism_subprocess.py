"""Fresh-process determinism for normalized external datasets and audits."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

SCRIPT = r"""
import json
from datetime import date
from quantcheck.external_dataset_audit import audit_external_rows
from quantcheck.external_dataset_ingestion import normalize_external_rows
from quantcheck.hashing import canonical_sha256
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import mapping, policy, reviewed_rows, explicit_revision_rows

rows = reviewed_rows() + explicit_revision_rows()
normalized = normalize_external_rows(list(reversed(rows)), mapping())
artifacts = audit_external_rows(
    rows,
    mapping=mapping(),
    as_of_date=date(2024, 12, 31),
    policy=policy(enabled_detectors=("duplicate_observation", "lookahead_timestamp")),
)
print(json.dumps({
    "normalized_id": normalized.normalized_dataset_id,
    "normalized_sha": canonical_sha256(normalized),
    "normalized_bytes": canonical_json_bytes(normalized).hex(),
    "audit_id": artifacts.public_report.external_audit_report_id,
    "audit_sha": canonical_sha256(artifacts.public_report),
    "audit_bytes": canonical_json_bytes(artifacts.public_report).hex(),
}, sort_keys=True))
"""


def _run(seed: str, cwd: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONHASHSEED": seed,
            "PYTHONPATH": str(REPO_ROOT),
            "TMPDIR": str(cwd / "different-temp"),
            "QUANTCHECK_OUTPUT_DIR": str(cwd / "different-output"),
            "USER": f"external-user-{seed}",
            "LOGNAME": f"external-logname-{seed}",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=cwd,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return cast(dict[str, str], json.loads(completed.stdout))


@pytest.fixture(scope="module")
def process_results(tmp_path_factory: pytest.TempPathFactory) -> list[dict[str, str]]:
    return [
        _run(seed, tmp_path_factory.mktemp(f"external-{seed}")) for seed in ("0", "1", "987654")
    ]


def test_normalized_output_is_byte_identical_across_hash_seeds(
    process_results: list[dict[str, str]],
) -> None:
    assert process_results[1:] == [process_results[0], process_results[0]]


def test_outputs_contain_no_runtime_or_working_directory(
    process_results: list[dict[str, str]],
    tmp_path: Path,
) -> None:
    serialized = json.dumps(process_results)
    assert str(tmp_path) not in serialized
    assert "different-temp" not in serialized
    assert "external-user" not in serialized
