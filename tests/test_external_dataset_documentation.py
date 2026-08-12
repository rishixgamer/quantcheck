"""The external production contract states its semantic and claim boundaries."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _contract_text() -> str:
    return " ".join((REPO_ROOT / "docs" / "EXTERNAL_DATASETS.md").read_text().split())


def test_contract_documents_every_versioned_artifact_and_format() -> None:
    text = _contract_text()
    for token in (
        "quantcheck/dataset-mapping/v1",
        "quantcheck/dataset-validation-profile/v1",
        "quantcheck/normalized-dataset/v1",
        "quantcheck/external-audit/v1",
        "quantcheck/audit-policy/v1",
        "quantcheck/external-audit/v2",
        "Parquet",
        "Arrow IPC file",
        "Arrow IPC stream",
        "CSV",
        "Iterable[Mapping[str, object]]",
    ):
        assert token in text


def test_contract_documents_no_guess_semantics_and_exact_values() -> None:
    text = _contract_text()
    for token in (
        "No fallback sets availability equal to filing",
        "No timestamp is truncated to a date",
        "never create a lineage",
        "Python `float`",
        "Arrow float/double",
        "never input row position",
    ):
        assert token in text


def test_contract_documents_dry_run_and_public_report_boundaries() -> None:
    text = _contract_text()
    for token in (
        "audit_claim=false",
        "benchmark_claim=false",
        "network_used=false",
        "manifest_used=false",
        "contains no full normalized record set",
        "cannot produce benchmark precision/recall",
    ):
        assert token in text


def test_v2_decisions_record_mapping_and_pyarrow_packaging_choices() -> None:
    text = (REPO_ROOT / "docs" / "DECISIONS_V0_2.md").read_text()
    assert "ADR-V2-012 — External production audits require an explicit mapping contract" in text
    assert "ADR-V2-013 — PyArrow remains lazy and is declared by v0.2 package metadata" in text
    assert "ADR-V2-014 — Production policies are versioned overlays" in text


def test_policy_contract_documents_precedence_provenance_and_no_global_default() -> None:
    text = " ".join((REPO_ROOT / "docs" / "PRODUCTION_AUDIT_POLICIES.md").read_text().split())
    for token in (
        "policy_content_hash",
        "greatest number of exact scope predicates",
        "Equally specific matches",
        "malformed input",
        "there is no active module-level policy",
        "ExternalDatasetAuditReportV2",
        "not recommendations or active defaults",
    ):
        assert token in text
