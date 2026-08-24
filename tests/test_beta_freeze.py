"""The beta candidate has a distinct, internally consistent evidence freeze."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

from scripts import build_beta_evidence

from quantcheck.hashing import sha256_hex_of_bytes, stable_id
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

REPO_ROOT = Path(__file__).resolve().parent.parent
FREEZE_PATH = REPO_ROOT / "design_partner_beta_freeze.json"
EVIDENCE_ROOT = REPO_ROOT / "evidence/design_partner_beta"


def _object(path: Path) -> dict[str, object]:
    value = parse_canonical_json(path.read_bytes())
    assert isinstance(value, dict)
    return value


def test_source_state_ignores_excluded_only_modifications(monkeypatch) -> None:
    status = " M design_partner_beta_freeze.json\n M evidence/design_partner_beta/run.json\n"
    monkeypatch.setattr(
        build_beta_evidence.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=status),
    )

    assert build_beta_evidence._source_state() == "clean_commit"


def test_beta_freeze_identity_source_hashes_and_claim_boundaries() -> None:
    freeze = _object(FREEZE_PATH)
    identity = freeze.pop("beta_freeze_id")
    assert identity == stable_id(
        prefix="bfrz",
        namespace="quantcheck/design-partner-beta-freeze/v1",
        payload=freeze,
    )
    assert freeze["package_version"] == "0.2.0.dev0"
    source = freeze["source"]
    assert isinstance(source, dict)
    files = source["files"]
    assert isinstance(files, list)
    for entry in files:
        assert isinstance(entry, dict)
        path = entry["path"]
        assert isinstance(path, str) and not path.startswith("/") and ".." not in path.split("/")
        assert entry["sha256"] == sha256_hex_of_bytes((REPO_ROOT / path).read_bytes())
    assert source["source_tree_sha256"] == sha256_hex_of_bytes(canonical_json_bytes(files))
    claims = freeze["claims"]
    assert claims == {
        "synthetic_evidence_only": True,
        "design_partner_data_used": False,
        "customer_validation_claimed": False,
        "production_validation_claimed": False,
    }


def test_persisted_aggregates_and_validation_freeze_are_complete() -> None:
    freeze = _object(FREEZE_PATH)
    evidence = freeze["benchmark_evidence"]
    assert isinstance(evidence, dict)
    for partition in ("development", "validation"):
        aggregate_path = EVIDENCE_ROOT / f"{partition}_aggregate.json"
        aggregate = _object(aggregate_path)
        overall = aggregate["overall"]
        assert isinstance(overall, dict)
        assert overall["configured_case_count"] == 390
        assert overall["successful_case_count"] == 390
        assert overall["failed_case_count"] == 0
        assert overall["incomplete_case_count"] == 0
        identity = evidence[partition]
        assert isinstance(identity, dict)
        assert identity["aggregate_v2_id"] == aggregate["aggregate_v2_id"]
        assert identity["aggregate_sha256"] == sha256_hex_of_bytes(aggregate_path.read_bytes())
    validation_freeze = _object(EVIDENCE_ROOT / "validation_freeze.json")
    recorded = evidence["validation_freeze"]
    assert isinstance(recorded, dict)
    assert recorded["validation_freeze_id"] == validation_freeze["validation_freeze_id"]


def test_current_sbom_and_provenance_bind_built_distribution_hashes() -> None:
    freeze = _object(FREEZE_PATH)
    distributions = freeze["distributions"]
    assert isinstance(distributions, list) and len(distributions) == 2
    expected = {item["path"]: item["sha256"] for item in distributions if isinstance(item, dict)}
    sbom = _object(EVIDENCE_ROOT / "quantcheck-distribution.spdx.json")
    assert sbom["spdxVersion"] == "SPDX-2.3"
    files = sbom["files"]
    assert isinstance(files, list)
    sbom_hashes = {
        item["fileName"]: item["checksums"][0]["checksumValue"]
        for item in files
        if isinstance(item, dict) and isinstance(item.get("checksums"), list)
    }
    assert {Path(path).name: digest for path, digest in expected.items()} == sbom_hashes

    provenance = _object(EVIDENCE_ROOT / "quantcheck-distribution.intoto.json")
    assert provenance["predicateType"] == "https://slsa.dev/provenance/v1"
    subjects = provenance["subject"]
    assert isinstance(subjects, list)
    assert {item["name"]: item["digest"]["sha256"] for item in subjects} == expected
    supply_chain = freeze["supply_chain"]
    assert isinstance(supply_chain, dict)
    attestation = supply_chain["attestation"]
    assert isinstance(attestation, dict)
    assert attestation["status"] == "not_created"
    syft = supply_chain["independent_syft_validation"]
    assert isinstance(syft, dict)
    assert syft["result"] == "pass_spdx_2_3"

    security = freeze["security_workflow"]
    assert isinstance(security, dict)
    local_scans = security["local_equivalent_scans"]
    assert isinstance(local_scans, dict)
    assert local_scans["status"] == "pass"
    for name in ("locked_dependency_scan", "repository_secret_scan"):
        scan = local_scans[name]
        assert isinstance(scan, dict)
        assert scan["result"] == "pass_zero_findings"
        assert scan["finding_count"] == 0


def test_beta_checksums_cover_every_persisted_evidence_file() -> None:
    checksums = (EVIDENCE_ROOT / "BETA_CHECKSUMS.md").read_text()
    recorded = {
        match.group("path"): match.group("digest")
        for match in re.finditer(
            r"^(?P<digest>[0-9a-f]{64})  (?P<path>\S+)$",
            checksums,
            re.MULTILINE,
        )
    }
    for path in sorted(EVIDENCE_ROOT.glob("*.json")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        assert recorded[relative] == hashlib.sha256(path.read_bytes()).hexdigest()
