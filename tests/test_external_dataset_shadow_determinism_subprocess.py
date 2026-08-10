"""Cross-process determinism for the shadow-mode evidence package."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from quantcheck.external_dataset_audit import audit_external_rows
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import mapping, policy, row


def _report_path(root: Path) -> Path:
    rows = (
        row("row-a", concept="DeterministicPilotConcept"),
        row("row-b", concept="DeterministicPilotConcept"),
    )
    report = audit_external_rows(
        rows,
        mapping=mapping(),
        as_of_date=date(2024, 12, 31),
        policy=policy(enabled_detectors=("duplicate_observation",)),
    ).public_report
    path = root / "audit-report.json"
    path.write_bytes(canonical_json_bytes(report))
    return path


def _prepare(
    *, report_path: Path, output_path: Path, working_directory: Path, hash_seed: str
) -> bytes:
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONHASHSEED": hash_seed,
            "TMPDIR": str(working_directory),
            "USER": f"shadow-user-{hash_seed}",
            "LOGNAME": f"shadow-log-{hash_seed}",
        }
    )
    completed = subprocess.run(
        (
            sys.executable,
            "-m",
            "quantcheck.external_dataset_shadow",
            "prepare",
            "--audit-report",
            str(report_path),
            "--dataset-key",
            "design-partner-dataset-001",
            "--quantcheck-version",
            "0.2.0-design-partner",
            "--code-revision",
            "a" * 40,
            "--runtime-ns",
            "123456789",
            "--output-directory",
            str(output_path),
        ),
        cwd=working_directory,
        env=environment,
        check=True,
        capture_output=True,
    )
    assert completed.stderr == b""
    return completed.stdout


def test_shadow_package_is_hash_seed_and_environment_independent(tmp_path: Path) -> None:
    report_path = _report_path(tmp_path)
    first_work = tmp_path / "first-work"
    second_work = tmp_path / "second-work"
    first_work.mkdir()
    second_work.mkdir()
    first_output = tmp_path / "first-output"
    second_output = tmp_path / "second-output"

    first_stdout = _prepare(
        report_path=report_path,
        output_path=first_output,
        working_directory=first_work,
        hash_seed="1",
    )
    second_stdout = _prepare(
        report_path=report_path,
        output_path=second_output,
        working_directory=second_work,
        hash_seed="987654",
    )

    assert first_stdout == second_stdout
    relative_paths = (
        Path("researcher_finding_bundle.json"),
        Path("adjudication_input.json"),
        Path("private/reviewer_notes_input.json"),
    )
    for relative_path in relative_paths:
        assert (first_output / relative_path).read_bytes() == (
            second_output / relative_path
        ).read_bytes()
