"""The production ingestion path is additive, offline, and benchmark-isolated."""

from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
from pathlib import Path

from quantcheck.external_dataset_audit import (
    audit_external_file,
    audit_external_rows,
    audit_normalized_dataset,
)
from quantcheck.release_checksums import verify_checksums_document
from quantcheck.release_contract import FROZEN_SOURCE_FILES

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULES = (
    REPO_ROOT / "src" / "quantcheck" / "external_dataset_contract.py",
    REPO_ROOT / "src" / "quantcheck" / "external_dataset_ingestion.py",
    REPO_ROOT / "src" / "quantcheck" / "external_dataset_audit.py",
    REPO_ROOT / "src" / "quantcheck" / "external_dataset_policy_contract.py",
    REPO_ROOT / "src" / "quantcheck" / "external_dataset_policy.py",
    REPO_ROOT / "src" / "quantcheck" / "external_dataset_policy_examples.py",
)


def test_v01_checksum_manifest_remains_current() -> None:
    assert verify_checksums_document(repo_root=REPO_ROOT) == ()


def test_no_frozen_v01_module_imports_the_external_dataset_path() -> None:
    offenders = []
    for relative in FROZEN_SOURCE_FILES:
        if (
            relative.endswith(".py")
            and "quantcheck.external_dataset" in (REPO_ROOT / relative).read_text()
        ):
            offenders.append(relative)
    assert offenders == []


def test_external_path_imports_no_injector_manifest_or_network_client() -> None:
    forbidden_fragments = ("_injection", "_manifest", "httpx", "requests", "urllib")
    for path in MODULES:
        tree = ast.parse(path.read_text())
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.append(node.module)
        assert not [
            name for name in imported if any(fragment in name for fragment in forbidden_fragments)
        ]


def test_audit_boundaries_have_no_private_truth_parameter() -> None:
    for function in (audit_external_file, audit_external_rows, audit_normalized_dataset):
        parameters = set(inspect.signature(function).parameters)
        assert not parameters & {
            "manifest",
            "clean_snapshot",
            "seed",
            "severity",
            "target_count",
            "fault_profile",
        }
        assert "policy" in parameters


def test_importing_ingestion_does_not_import_pyarrow() -> None:
    script = (
        "import sys\n"
        "import quantcheck.external_dataset_ingestion\n"
        "print('pyarrow' in sys.modules)\n"
    )
    environment = os.environ.copy()
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "False"


def test_frozen_cli_and_benchmark_dispatch_do_not_route_to_external_dataset() -> None:
    for relative in (
        "src/quantcheck/cli.py",
        "src/quantcheck/benchmark_dispatch.py",
        "src/quantcheck/benchmark_runner.py",
        "src/quantcheck/release_run.py",
    ):
        assert "external_dataset" not in (REPO_ROOT / relative).read_text()
