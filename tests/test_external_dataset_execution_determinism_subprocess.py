"""Cross-process/hash-seed proof for every supported local worker count."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SCRIPT = r"""
from __future__ import annotations

import sys
from pathlib import Path

from quantcheck.external_dataset_execution import (
    logical_execution_artifact_paths,
    run_external_audit_execution,
)
from quantcheck.external_dataset_execution_contract import (
    SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS,
)
from quantcheck.external_dataset_performance import (
    PerformanceEnvelopeV1,
    prepare_performance_corpus,
)
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.serialization import canonical_json_bytes


def main() -> None:
    root = Path(sys.argv[1])
    envelope = PerformanceEnvelopeV1(
        label="small",
        record_count=40,
        partition_count=2,
        maximum_records_per_partition=20,
    )
    prepared = prepare_performance_corpus(root / "source", envelope)
    outputs = []
    for worker_count in SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS:
        artifact_root = root / f"workers-{worker_count}"
        result = run_external_audit_execution(
            prepared.plan,
            prepared.inputs,
            output_root=artifact_root,
            worker_count=worker_count,
        )
        outputs.append(
            {
                "worker_count": worker_count,
                "finalization": result.finalization,
                "artifacts": tuple(
                    {
                        "visibility": visibility,
                        "path": path,
                        "hash": sha256_hex_of_bytes(
                            (artifact_root / visibility / path).read_bytes()
                        ),
                    }
                    for visibility, path in logical_execution_artifact_paths(result)
                ),
            }
        )
    print(canonical_json_bytes(tuple(outputs)).decode("utf-8"))


if __name__ == "__main__":
    main()
"""


def _run(tmp_path: Path, seed: str) -> bytes:
    script = tmp_path / f"execution-{seed}.py"
    script.write_text(_SCRIPT)
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = seed
    completed = subprocess.run(
        [sys.executable, str(script), str(tmp_path / f"root-{seed}")],
        check=True,
        capture_output=True,
        env=environment,
    )
    return completed.stdout


def test_worker_artifacts_are_identical_across_python_hash_seeds(tmp_path: Path) -> None:
    assert _run(tmp_path, "1") == _run(tmp_path, "987654")
