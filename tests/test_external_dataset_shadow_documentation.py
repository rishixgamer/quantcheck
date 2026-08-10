"""Documentation and isolation gates for design-partner shadow mode."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _normalized_document() -> str:
    return " ".join((REPO_ROOT / "docs" / "DESIGN_PARTNER_SHADOW_MODE.md").read_text().split())


def test_shadow_guide_documents_nonblocking_copy_only_workflow() -> None:
    text = _normalized_document()
    for phrase in (
        "copy or snapshot",
        "production_blocking_used=false",
        "customer's production research system remains the system of record",
        "read-only export",
        "A failed validation, partition, or audit stops only this copied shadow run",
        "must not be wired to a production job's success condition",
    ):
        assert phrase in text


def test_shadow_guide_documents_every_required_artifact_and_disposition() -> None:
    text = _normalized_document()
    for phrase in (
        "quantcheck/dataset-mapping/v1",
        "quantcheck/audit-policy/v1",
        "quantcheck/shadow-pilot-report/v1",
        "researcher_finding_bundle.json",
        "adjudication_export.json",
        "reviewer_notes.json",
        "confirmed_issue",
        "legitimate_data_condition",
        "accepted_exception",
        "duplicate_correlated_signal",
        "unresolved",
        "customer_independently_confirmed",
        "exact_evidence_key_no_fuzzy_matching",
    ):
        assert phrase in text


def test_evaluation_template_covers_required_factual_measures_without_numbers() -> None:
    text = _normalized_document()
    for field in (
        "Datasets audited",
        "Records audited",
        "Runtime",
        "Findings by detector",
        "Findings investigated",
        "Confirmed issues",
        "Legitimate exceptions",
        "Unexplained/noisy alerts",
        "Issues affecting a research decision",
        "Researcher time reviewing findings",
    ):
        assert field in text
    assert "Supplied pilot result | |" in text
    assert "contains no design-partner data" in text
    assert not tuple(REPO_ROOT.glob("**/pilot-report.json"))


def test_shadow_adr_freezes_evidence_human_state_and_reporting_boundaries() -> None:
    text = " ".join((REPO_ROOT / "docs" / "DECISIONS_V0_2.md").read_text().split())
    assert "ADR-V2-017 — Shadow evaluation separates immutable evidence" in text
    for phrase in (
        "customer-controlled copy/snapshot",
        "Store dispositions in a complete sanitized adjudication export",
        "distinct private artifact",
        "Generate pilot metrics only from exactly one complete",
        "contains no pilot inputs or results",
    ):
        assert phrase in text


def test_shadow_packaging_has_no_source_ingestion_audit_execution_or_network_import() -> None:
    module = REPO_ROOT / "src" / "quantcheck" / "external_dataset_shadow.py"
    tree = ast.parse(module.read_text())
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    prohibited = {
        "httpx",
        "socket",
        "quantcheck.external_dataset_audit",
        "quantcheck.external_dataset_execution",
        "quantcheck.external_dataset_ingestion",
    }
    assert prohibited.isdisjoint(imports)


def test_frozen_v01_modules_cannot_reach_shadow_mode() -> None:
    source = REPO_ROOT / "src" / "quantcheck"
    frozen_paths = {
        line.split("  ", 1)[1]
        for line in (REPO_ROOT / "CHECKSUMS.md").read_text().splitlines()
        if "  src/quantcheck/" in line
    }
    assert frozen_paths
    for relative_path in frozen_paths:
        text = (REPO_ROOT / relative_path).read_text()
        assert "quantcheck.external_dataset_shadow" not in text
    assert (source / "external_dataset_shadow.py").is_file()
