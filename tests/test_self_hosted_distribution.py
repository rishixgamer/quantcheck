"""Static and executable gates for the self-hosted production distribution."""

from __future__ import annotations

import ast
import re
import stat
from pathlib import Path

from quantcheck.external_dataset_self_hosted import (
    load_self_hosted_config,
    run_self_hosted_audit,
)
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.serialization import canonical_json_bytes

REPO_ROOT = Path(__file__).resolve().parents[1]
FULL_SHA_ACTION = re.compile(r"^\s*(?:-\s+)?uses:\s+[^@\s]+@([0-9a-f]{40})(?:\s+#\s+\S+)?\s*$")


def test_published_smoke_bundle_is_canonical_integrity_pinned_and_executable(
    tmp_path: Path,
) -> None:
    config_path = REPO_ROOT / "deploy/smoke/config/run.json"
    input_root = REPO_ROOT / "deploy/smoke/input"
    source = input_root / "partition.csv"
    config = load_self_hosted_config(config_path)

    assert config_path.read_bytes().rstrip(b"\n") == canonical_json_bytes(config)
    partition = config.plan.partitions[0]
    assert partition.source.expected_sha256 == sha256_hex_of_bytes(source.read_bytes())
    assert partition.source.expected_size_bytes == source.stat().st_size
    assert partition.source.input_format == "csv"
    assert config.telemetry is False
    assert config.network_required is False

    output_root = tmp_path / "output"
    output_root.mkdir()
    result = run_self_hosted_audit(
        config,
        input_root=input_root,
        output_root=output_root,
    )
    assert result.finalization.status == "succeeded"
    assert result.plan.run_id == "xrun_d65eac0fa9d81e72"


def test_container_uses_only_digest_pinned_images_and_a_non_root_runtime() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    image_arguments = re.findall(r"^ARG (?:PYTHON|UV)_IMAGE=(\S+)$", dockerfile, re.MULTILINE)
    assert len(image_arguments) == 2
    assert all(re.fullmatch(r"\S+@sha256:[0-9a-f]{64}", image) for image in image_arguments)
    assert "USER 65532:65532" in dockerfile
    assert "QUANTCHECK_TELEMETRY=0" in dockerfile
    assert "DO_NOT_TRACK=1" in dockerfile
    assert "QUANTCHECK_CONFIG_PATH=/config/run.json" in dockerfile
    assert "QUANTCHECK_INPUT_DIR=/input" in dockerfile
    assert "QUANTCHECK_OUTPUT_DIR=/output" in dockerfile
    assert "QUANTCHECK_WORK_DIR=/work" in dockerfile
    assert "TMPDIR=/work" in dockerfile
    assert 'ENTRYPOINT ["/opt/quantcheck/.venv/bin/python", "-m", ' in dockerfile
    assert "quantcheck.external_dataset_self_hosted" in dockerfile
    assert not re.search(r"^\s*(?:VOLUME|EXPOSE)\b", dockerfile, re.MULTILINE)
    for forbidden in ("apt-get", "apk add", "curl ", "wget ", "--mount=type=secret"):
        assert forbidden not in dockerfile


def test_container_context_and_reproducibility_script_are_bounded() -> None:
    dockerignore = (REPO_ROOT / ".dockerignore").read_text().splitlines()
    assert dockerignore[0] == "*"
    assert "!src/**" in dockerignore
    assert "!deploy/smoke/**" in dockerignore
    assert not any("tests" in line or "reference" in line for line in dockerignore)

    script = REPO_ROOT / "scripts/verify_container_reproducibility.sh"
    assert script.stat().st_mode & stat.S_IXUSR
    text = script.read_text()
    assert text.startswith("#!/bin/sh\nset -eu\n")
    assert text.count("build_once") == 3
    assert "rewrite-timestamp=true" in text
    assert "--no-cache" in text
    assert "--provenance=false" in text
    assert "--sbom=false" in text
    assert "first" in text and "second" in text
    assert "inspect_oci_layout.py" in text
    assert "raw OCI archives differ" in text
    assert "canonical OCI identity matches" in text
    assert 'raw OCI archives differ" >&2\n  exit 1' not in text

    dockerfile = (REPO_ROOT / "Dockerfile").read_text()
    for required in (
        'find /opt/quantcheck/.venv -exec touch -h -d "@${SOURCE_DATE_EPOCH}" {} +',
        "COPY --from=builder --chown=65532:65532 /opt/quantcheck/.venv /opt/quantcheck/.venv",
    ):
        assert required in dockerfile
    assert "venv.tar" not in dockerfile


def test_all_github_actions_are_pinned_to_full_commit_shas() -> None:
    uses_lines: list[str] = []
    for workflow in sorted((REPO_ROOT / ".github/workflows").glob("*.yml")):
        for line in workflow.read_text().splitlines():
            if "uses:" in line:
                uses_lines.append(line)
                match = FULL_SHA_ACTION.fullmatch(line)
                assert match is not None, f"mutable action reference in {workflow.name}: {line}"
    assert uses_lines


def test_security_and_release_workflows_cover_required_supply_chain_gates() -> None:
    security = (REPO_ROOT / ".github/workflows/security.yml").read_text()
    release = (REPO_ROOT / ".github/workflows/publish-self-hosted.yml").read_text()

    for required in (
        "scanners: vuln",
        "scanners: secret",
        "severity: HIGH,CRITICAL",
        "exit-code: 1",
        "spdx-json",
        "verify_container_reproducibility.sh",
    ):
        assert required in security

    for required in (
        "provenance: mode=max",
        "sbom: true",
        "actions/attest@",
        "subject-digest:",
        "sbom-path:",
        "docker pull",
        "--network none",
        "--read-only",
        "--cap-drop ALL",
        "no-new-privileges",
        "65532:65532",
        "gh release upload",
    ):
        assert required in release
    assert "--clobber" not in release
    assert "rm -rf /" not in release


def test_self_hosted_entry_point_has_no_network_or_secret_client_import() -> None:
    source = (REPO_ROOT / "src/quantcheck/external_dataset_self_hosted.py").read_text()
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    )
    for forbidden in ("httpx", "requests", "socket", "urllib", "quantcheck.sec_adapter"):
        assert forbidden not in imported


def test_security_documents_cover_operations_without_certification_claims() -> None:
    documents = {
        name: (REPO_ROOT / name).read_text()
        for name in (
            "SECURITY.md",
            "docs/SELF_HOSTED_DEPLOYMENT.md",
            "docs/SELF_HOSTED_THREAT_MODEL.md",
            "docs/SUPPLY_CHAIN_SECURITY.md",
            "docs/SECURE_DEVELOPMENT_CHECKLIST.md",
        )
    }
    combined = "\n".join(documents.values()).lower()
    for required in (
        "private vulnerability",
        "read-only",
        "telemetry",
        "retention",
        "deletion",
        "sbom",
        "provenance",
        "dependency",
        "patch",
        "secret",
        "no slsa level",
        "has not obtained",
    ):
        assert required in combined
    assert "is certified" not in combined
    assert "slsa level 3" not in combined
