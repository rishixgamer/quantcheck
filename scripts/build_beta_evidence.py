#!/usr/bin/env python3
"""Build deterministic design-partner beta identity and supply-chain evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import quantcheck
from quantcheck.benchmark_v2_contract import (
    DETECTOR_IDENTITY_BY_KEY,
    INJECTOR_SPEC_VERSION_BY_PROFILE,
)
from quantcheck.hashing import sha256_hex_of_bytes, stable_id
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

REPO_ROOT = Path(__file__).resolve().parent.parent
FREEZE_NAME = "design_partner_beta_freeze.json"
EXCLUDED_SOURCE_FILES = {FREEZE_NAME}
EXCLUDED_SOURCE_PREFIXES = ("evidence/design_partner_beta/",)


def _run(*arguments: str, strip_output: bool = True) -> str:
    completed = subprocess.run(
        arguments,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if strip_output else completed.stdout


def _source_files() -> tuple[Path, ...]:
    output = subprocess.run(
        ("git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"),
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    relative_paths = sorted(
        path.decode("utf-8") for path in output.split(b"\0") if path and path.decode("utf-8")
    )
    return tuple(
        REPO_ROOT / relative
        for relative in relative_paths
        if relative not in EXCLUDED_SOURCE_FILES
        and not relative.startswith(EXCLUDED_SOURCE_PREFIXES)
        and (REPO_ROOT / relative).is_file()
    )


def _source_manifest() -> tuple[tuple[dict[str, object], ...], str]:
    entries: tuple[dict[str, object], ...] = tuple(
        {
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "sha256": sha256_hex_of_bytes(path.read_bytes()),
        }
        for path in _source_files()
    )
    return entries, sha256_hex_of_bytes(canonical_json_bytes(entries))


def _source_state() -> str:
    status = _run(
        "git",
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        strip_output=False,
    )
    for line in status.splitlines():
        path = line[3:]
        if path in EXCLUDED_SOURCE_FILES or path.startswith(EXCLUDED_SOURCE_PREFIXES):
            continue
        return "uncommitted_worktree"
    return "clean_commit"


def _artifact(path: Path, *, relative_to: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": path.relative_to(relative_to).as_posix(),
        "sha256": sha256_hex_of_bytes(payload),
        "size_bytes": len(payload),
    }


def _package_version_from_wheel(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        metadata_names = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise ValueError("wheel must contain exactly one METADATA file")
        metadata = archive.read(metadata_names[0]).decode("utf-8")
    match = re.search(r"^Version: (.+)$", metadata, re.MULTILINE)
    if match is None:
        raise ValueError("wheel METADATA has no Version")
    return match.group(1)


def _package_version_from_sdist(path: Path) -> str:
    with tarfile.open(path, "r:gz") as archive:
        metadata_names = [name for name in archive.getnames() if name.endswith("/PKG-INFO")]
        if len(metadata_names) != 1:
            raise ValueError("sdist must contain exactly one PKG-INFO file")
        extracted = archive.extractfile(metadata_names[0])
        if extracted is None:
            raise ValueError("sdist PKG-INFO is not a regular file")
        metadata = extracted.read().decode("utf-8")
    match = re.search(r"^Version: (.+)$", metadata, re.MULTILINE)
    if match is None:
        raise ValueError("sdist PKG-INFO has no Version")
    return match.group(1)


def _dist_artifacts(dist_dir: Path) -> tuple[Path, Path]:
    wheels = sorted(dist_dir.glob("quantcheck-*.whl"))
    sdists = sorted(dist_dir.glob("quantcheck-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("expected exactly one QuantCheck wheel and one sdist")
    wheel, sdist = wheels[0], sdists[0]
    observed = {_package_version_from_wheel(wheel), _package_version_from_sdist(sdist)}
    if observed != {quantcheck.__version__}:
        raise ValueError(f"distribution metadata does not match {quantcheck.__version__}")
    return wheel, sdist


def _spdx_id(name: str) -> str:
    return "SPDXRef-Package-" + re.sub(r"[^A-Za-z0-9.-]", "-", name)


def _created_time(source_date_epoch: int) -> str:
    return datetime.fromtimestamp(source_date_epoch, tz=UTC).isoformat().replace("+00:00", "Z")


def _build_spdx(
    *,
    wheel: Path,
    sdist: Path,
    source_tree_hash: str,
    source_date_epoch: int,
) -> dict[str, object]:
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text())
    packages: list[dict[str, object]] = [
        {
            "name": "quantcheck",
            "SPDXID": "SPDXRef-Package-quantcheck",
            "versionInfo": quantcheck.__version__,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "MIT",
            "copyrightText": "NOASSERTION",
        }
    ]
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package-quantcheck",
        }
    ]
    seen: set[tuple[str, str]] = set()
    for package in lock["package"]:
        name = str(package["name"])
        version = str(package["version"])
        if name == "quantcheck" or (name, version) in seen:
            continue
        seen.add((name, version))
        identifier = _spdx_id(f"{name}-{version}")
        packages.append(
            {
                "name": name,
                "SPDXID": identifier,
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package-quantcheck",
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": identifier,
            }
        )
    files = []
    for index, path in enumerate((wheel, sdist), start=1):
        identifier = f"SPDXRef-Artifact-{index}"
        files.append(
            {
                "fileName": path.name,
                "SPDXID": identifier,
                "checksums": [
                    {"algorithm": "SHA256", "checksumValue": sha256_hex_of_bytes(path.read_bytes())}
                ],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package-quantcheck",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": identifier,
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"quantcheck-{quantcheck.__version__}-distribution-sbom",
        "documentNamespace": (
            "https://quantcheck.invalid/spdx/"
            f"quantcheck-{quantcheck.__version__}-{source_tree_hash}"
        ),
        "creationInfo": {
            "created": _created_time(source_date_epoch),
            "creators": ["Tool: quantcheck-build-beta-evidence-v1"],
        },
        "packages": tuple(packages),
        "files": tuple(files),
        "relationships": tuple(relationships),
    }


def _build_provenance(
    *,
    artifacts: tuple[dict[str, object], ...],
    base_commit: str,
    source_tree_hash: str,
    source_date_epoch: int,
) -> dict[str, object]:
    subject = tuple(
        {"name": item["path"], "digest": {"sha256": item["sha256"]}} for item in artifacts
    )
    return {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subject,
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://quantcheck.invalid/build-types/uv-build/v1",
                "externalParameters": {
                    "package_version": quantcheck.__version__,
                    "python": "3.12",
                    "source_date_epoch": source_date_epoch,
                },
                "internalParameters": {},
                "resolvedDependencies": (
                    {
                        "uri": "git+https://github.com/rishixgamer/quantcheck",
                        "digest": {"gitCommit": base_commit, "sourceTreeSha256": source_tree_hash},
                    },
                    {
                        "uri": "file:uv.lock",
                        "digest": {
                            "sha256": sha256_hex_of_bytes((REPO_ROOT / "uv.lock").read_bytes())
                        },
                    },
                ),
            },
            "runDetails": {
                "builder": {"id": "local-untrusted://quantcheck/build_beta_evidence.py"},
                "metadata": {
                    "invocationId": stable_id(
                        prefix="inv", namespace="quantcheck/beta-build/v1", payload=subject
                    ),
                    "startedOn": _created_time(source_date_epoch),
                    "finishedOn": _created_time(source_date_epoch),
                },
            },
        },
    }


def _canonical_file(path: Path) -> dict[str, Any]:
    value = parse_canonical_json(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"expected an object in {path}")
    return value


def _benchmark_identity(root: Path) -> dict[str, object]:
    identities: dict[str, object] = {}
    for partition in ("development", "validation"):
        aggregate_path = root / "public" / f"{partition}_aggregate.json"
        matrix_path = root / "public" / f"{partition}_matrix.json"
        aggregate = _canonical_file(aggregate_path)
        matrix = _canonical_file(matrix_path)
        overall = aggregate.get("overall")
        if not isinstance(overall, dict):
            raise ValueError(f"{partition} aggregate has no overall summary")
        if (
            overall.get("configured_case_count") != 390
            or overall.get("successful_case_count") != 390
            or overall.get("failed_case_count") != 0
            or overall.get("incomplete_case_count") != 0
        ):
            raise ValueError(f"{partition} evidence is not complete and successful")
        identities[partition] = {
            "benchmark_v2_id": aggregate["benchmark_v2_id"],
            "aggregate_v2_id": aggregate["aggregate_v2_id"],
            "aggregate_sha256": sha256_hex_of_bytes(aggregate_path.read_bytes()),
            "matrix_sha256": sha256_hex_of_bytes(matrix_path.read_bytes()),
            "case_count": matrix["case_count"],
        }
    freeze_path = root / "public" / "validation_freeze.json"
    identities["validation_freeze"] = {
        "validation_freeze_id": _canonical_file(freeze_path)["validation_freeze_id"],
        "sha256": sha256_hex_of_bytes(freeze_path.read_bytes()),
    }
    return identities


def _persist_benchmark_summary(source: Path, destination: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for name in (
        "development_aggregate.json",
        "validation_aggregate.json",
        "validation_freeze.json",
    ):
        source_path = source / "public" / name
        target = destination / name
        target.write_bytes(canonical_json_bytes(_canonical_file(source_path)))
        paths.append(target)
    return tuple(paths)


def _oci_identity(path: Path | None) -> dict[str, object]:
    if path is None:
        return {
            "status": "not_verified_for_candidate",
            "archive_sha256": None,
            "manifest_digest": None,
            "config_digest": None,
            "layer_digests": (),
        }
    completed = subprocess.run(
        (sys.executable, str(REPO_ROOT / "scripts/inspect_oci_layout.py"), str(path)),
        check=True,
        capture_output=True,
        text=True,
    )
    identity = json.loads(completed.stdout)
    return {"status": "verified_single_archive", **identity}


def _security_report(path: Path, *, field: str) -> dict[str, object]:
    document = json.loads(path.read_text())
    results = document.get("Results") or []
    finding_count = sum(len(result.get(field) or []) for result in results)
    if finding_count:
        raise ValueError(f"security report {path.name} contains {finding_count} findings")
    return {
        "scanner": document.get("Trivy", {}).get("Version", "unknown"),
        "result": "pass_zero_findings",
        "finding_count": 0,
    }


def _persist_external_json(source: Path, destination: Path) -> Path:
    document = json.loads(source.read_text())
    destination.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return destination


def _syft_report(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text())
    if document.get("spdxVersion") != "SPDX-2.3" or not document.get("packages"):
        raise ValueError("independent Syft report is not a populated SPDX 2.3 document")
    return {
        "tool": "syft-1.50.0",
        "result": "pass_spdx_2_3",
        "package_count": len(document["packages"]),
    }


def _write_checksums(path: Path, artifacts: tuple[dict[str, object], ...]) -> None:
    lines = [
        "# QuantCheck design-partner beta evidence checksums",
        "",
        (
            "These SHA-256 values cover the locally generated candidate evidence; "
            "they are not signatures."
        ),
        "",
        "```text",
    ]
    lines.extend(f"{item['sha256']}  {item['path']}" for item in artifacts)
    lines.extend(("```", ""))
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path, default=REPO_ROOT / "dist")
    parser.add_argument(
        "--benchmark-evidence",
        type=Path,
        default=REPO_ROOT / "benchmark_evidence_v0_2",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "evidence" / "design_partner_beta",
    )
    parser.add_argument("--oci-archive", type=Path)
    parser.add_argument("--trivy-vulnerability-report", type=Path)
    parser.add_argument("--trivy-secret-report", type=Path)
    parser.add_argument("--syft-sbom", type=Path)
    parser.add_argument("--freeze", type=Path, default=REPO_ROOT / FREEZE_NAME)
    args = parser.parse_args()

    for name in (
        "dist_dir",
        "benchmark_evidence",
        "output",
        "freeze",
        "oci_archive",
        "trivy_vulnerability_report",
        "trivy_secret_report",
        "syft_sbom",
    ):
        value = getattr(args, name)
        if value is not None and not value.is_absolute():
            setattr(args, name, REPO_ROOT / value)

    wheel, sdist = _dist_artifacts(args.dist_dir)
    args.output.mkdir(parents=True, exist_ok=True)
    base_commit = _run("git", "rev-parse", "HEAD")
    source_date_epoch = int(_run("git", "log", "-1", "--format=%ct"))
    source_entries, source_tree_hash = _source_manifest()
    distributions = tuple(_artifact(path, relative_to=REPO_ROOT) for path in (wheel, sdist))

    sbom = _build_spdx(
        wheel=wheel,
        sdist=sdist,
        source_tree_hash=source_tree_hash,
        source_date_epoch=source_date_epoch,
    )
    sbom_path = args.output / "quantcheck-distribution.spdx.json"
    sbom_path.write_bytes(canonical_json_bytes(sbom))
    provenance = _build_provenance(
        artifacts=distributions,
        base_commit=base_commit,
        source_tree_hash=source_tree_hash,
        source_date_epoch=source_date_epoch,
    )
    provenance_path = args.output / "quantcheck-distribution.intoto.json"
    provenance_path.write_bytes(canonical_json_bytes(provenance))

    benchmark_summaries = _persist_benchmark_summary(args.benchmark_evidence, args.output)

    external_evidence: list[Path] = []
    local_security: dict[str, object] = {"status": "not_run"}
    if args.trivy_vulnerability_report is not None and args.trivy_secret_report is not None:
        vulnerability = _security_report(args.trivy_vulnerability_report, field="Vulnerabilities")
        secret = _security_report(args.trivy_secret_report, field="Secrets")
        external_evidence.extend(
            (
                _persist_external_json(
                    args.trivy_vulnerability_report,
                    args.output / "trivy-vulnerability.json",
                ),
                _persist_external_json(
                    args.trivy_secret_report,
                    args.output / "trivy-secret.json",
                ),
            )
        )
        local_security = {
            "status": "pass",
            "locked_dependency_scan": vulnerability,
            "repository_secret_scan": secret,
            "reports": tuple(_artifact(path, relative_to=REPO_ROOT) for path in external_evidence),
        }
    elif args.trivy_vulnerability_report is not None or args.trivy_secret_report is not None:
        raise ValueError("both Trivy reports are required together")

    independent_syft: dict[str, object] = {"status": "not_run"}
    if args.syft_sbom is not None:
        independent_syft = _syft_report(args.syft_sbom)
        syft_path = _persist_external_json(
            args.syft_sbom, args.output / "quantcheck-wheel.syft.spdx.json"
        )
        external_evidence.append(syft_path)
        independent_syft["report"] = _artifact(syft_path, relative_to=REPO_ROOT)

    generated = tuple(
        _artifact(path, relative_to=REPO_ROOT)
        for path in (sbom_path, provenance_path, *benchmark_summaries, *external_evidence)
    )
    checksum_artifacts = distributions + generated
    checksums_path = args.output / "BETA_CHECKSUMS.md"
    _write_checksums(checksums_path, checksum_artifacts)
    checksums = _artifact(checksums_path, relative_to=REPO_ROOT)

    body = {
        "spec_version": "quantcheck/design-partner-beta-freeze/v1",
        "release_role": "design_partner_beta_candidate",
        "package_version": quantcheck.__version__,
        "source": {
            "base_commit": base_commit,
            "state": _source_state(),
            "source_tree_sha256": source_tree_hash,
            "files": source_entries,
        },
        "corpus": {
            "corpus_id": "corp_a55d14a60c2f89d6",
            "corpus_census_id": "cens_4512c0c8f3fdb747",
            "corpus_freeze_id": "cfrz_040ae8f12d864289",
        },
        "benchmark_evidence": _benchmark_identity(args.benchmark_evidence),
        "detectors": dict(sorted(DETECTOR_IDENTITY_BY_KEY.items())),
        "injector_specs": dict(sorted(INJECTOR_SPEC_VERSION_BY_PROFILE.items())),
        "distributions": distributions,
        "oci": _oci_identity(args.oci_archive),
        "supply_chain": {
            "spdx_sbom": generated[0],
            "provenance_statement": generated[1],
            "independent_syft_validation": independent_syft,
            "checksums": checksums,
            "attestation": {
                "status": "not_created",
                "reason": "local provenance has no trusted CI identity or signature",
                "required_path": ".github/workflows/publish-self-hosted.yml",
            },
        },
        "security_workflow": {
            "candidate_source_run": "not_run",
            "local_equivalent_scans": local_security,
            "historical_run_id": "31368451109",
            "historical_result": "failed_oci_reproducibility_only",
        },
        "claims": {
            "synthetic_evidence_only": True,
            "design_partner_data_used": False,
            "customer_validation_claimed": False,
            "production_validation_claimed": False,
        },
    }
    freeze = {
        "beta_freeze_id": stable_id(
            prefix="bfrz", namespace="quantcheck/design-partner-beta-freeze/v1", payload=body
        ),
        **body,
    }
    args.freeze.write_bytes(canonical_json_bytes(freeze))
    print(canonical_json_bytes(freeze).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
