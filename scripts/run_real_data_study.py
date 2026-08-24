"""Run the frozen real-public-data study without changing QuantCheck behavior.

The protocol is ``docs/research/REAL_DATA_STUDY_PROTOCOL.md``.  This script only orchestrates
existing SEC normalization, point-in-time selection, audit-boundary, and
detector-execution APIs; it does not construct a manifest or run a benchmark.
"""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.benchmark_v2_execution import run_selected_detectors_v2
from quantcheck.benchmark_v2_schemas import DetectorExecutionConfigV2
from quantcheck.sec_adapter import (
    SecClientConfig,
    SecCompanyFactsAdapter,
    SecConceptSpec,
    SecNormalizationConfig,
    build_sec_snapshot,
)
from quantcheck.serialization import canonical_json_bytes

STUDY_ROOT = Path("evidence/real_data_study")
RESEARCH_ROOT = Path("docs/research")
PROTOCOL_PATH = RESEARCH_ROOT / "REAL_DATA_STUDY_PROTOCOL.md"
FINDINGS_PATH = RESEARCH_ROOT / "REAL_DATA_FINDINGS.csv"
USER_AGENT = "QuantCheck-real-data-validation/0.2 rishihaldar@umass.edu"
FILED_FROM = date(2021, 1, 1)
FILED_THROUGH = date(2024, 12, 31)
AS_OF_DATE = date(2024, 12, 31)
COMPANIES: tuple[tuple[str, str, str], ...] = (
    ("apple", "Apple Inc.", "0000320193"),
    ("microsoft", "Microsoft Corporation", "0000789019"),
    ("alphabet", "Alphabet Inc.", "0001652044"),
    ("amazon", "Amazon.com, Inc.", "0001018724"),
    ("jpmorgan", "JPMorgan Chase & Co.", "0000019617"),
)
CONCEPTS = (
    SecConceptSpec("us-gaap", "Assets", "USD", "instant"),
    SecConceptSpec("us-gaap", "NetIncomeLoss", "USD", "duration"),
)
EXECUTION_CONFIG = DetectorExecutionConfigV2()


def write_canonical(path: Path, value: object) -> None:
    content = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise SystemExit(f"refusing to replace non-identical study artifact: {path}")
        return
    path.write_bytes(content)


def git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def protocol_sha256() -> str:
    import hashlib

    return hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest()


def main() -> None:
    if (STUDY_ROOT / "study_run.json").exists() or FINDINGS_PATH.exists():
        raise SystemExit("refusing to overwrite a completed or findings-bearing study")
    cache_dir = STUDY_ROOT / "sec_cache"
    adapter = SecCompanyFactsAdapter(SecClientConfig(user_agent=USER_AGENT, cache_dir=cache_dir))
    all_findings: list[dict[str, str]] = []
    company_rows: list[dict[str, object]] = []

    for slug, company, cik in COMPANIES:
        fetched = adapter.fetch(cik)
        normalized = adapter.normalize(
            fetched,
            SecNormalizationConfig(
                cik=cik,
                concepts=CONCEPTS,
                forms=("10-K", "10-Q"),
                filed_from=FILED_FROM,
                filed_through=FILED_THROUGH,
            ),
        )
        snapshot = build_sec_snapshot(
            normalized,
            dataset_name=f"real-public-data-study-{slug}",
            as_of_date=AS_OF_DATE,
        )
        audit_input = sanitize_for_audit(snapshot)
        execution = run_selected_detectors_v2(audit_input, EXECUTION_CONFIG)
        company_root = STUDY_ROOT / "companies" / slug
        write_canonical(
            company_root / "source.json",
            {
                "company": company,
                "cik": cik,
                "source_url": fetched.url,
                "raw_sha256": fetched.raw_sha256,
            },
        )
        write_canonical(
            company_root / "normalized.json",
            {
                "canonical_cik": normalized.canonical_cik,
                "source_locator": normalized.source_locator,
                "records": normalized.records,
                "exclusions": tuple(
                    {
                        "reason": exclusion.reason,
                        "taxonomy": exclusion.taxonomy,
                        "concept": exclusion.concept,
                        "unit": exclusion.unit,
                        "source_row_key": exclusion.source_row_key,
                    }
                    for exclusion in normalized.exclusions
                ),
            },
        )
        write_canonical(company_root / "snapshot.json", snapshot)
        write_canonical(company_root / "audit_input.json", audit_input)
        write_canonical(company_root / "detector_execution.json", execution)
        finding_counts = {run.detector: len(run.report.findings) for run in execution.runs}
        company_rows.append(
            {
                "company": company,
                "cik": cik,
                "source_url": fetched.url,
                "raw_sha256": fetched.raw_sha256,
                "normalized_record_count": len(normalized.records),
                "excluded_record_count": len(normalized.exclusions),
                "snapshot_record_count": len(snapshot.records),
                "audit_input_record_count": len(audit_input.records),
                "detector_execution_id": execution.detector_execution_id,
                "finding_counts": finding_counts,
            }
        )
        for run in execution.runs:
            for finding in run.report.findings:
                all_findings.append(
                    {
                        "company": company,
                        "cik": cik,
                        "source_raw_sha256": fetched.raw_sha256,
                        "detector": run.detector,
                        "finding_id": finding.finding_id,
                        "rule_id": finding.rule_id,
                        "severity": finding.severity,
                        "confidence": finding.confidence,
                        "affected_record_ids": json.dumps(
                            list(finding.affected_record_ids), separators=(",", ":")
                        ),
                        "evidence_json": canonical_json_bytes(finding.evidence).decode("utf-8"),
                    }
                )

    fieldnames = (
        "company",
        "cik",
        "source_raw_sha256",
        "detector",
        "finding_id",
        "rule_id",
        "severity",
        "confidence",
        "affected_record_ids",
        "evidence_json",
    )
    with FINDINGS_PATH.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(all_findings, key=lambda row: row["finding_id"]))

    write_canonical(
        STUDY_ROOT / "study_run.json",
        {
            "study": "quantcheck-real-public-data-validation/v1",
            "protocol_sha256": protocol_sha256(),
            "quantcheck_version": "0.2.0.dev0",
            "git_revision": git_revision(),
            "retrieved_at_utc": datetime.now(UTC).replace(microsecond=0),
            "filed_from": FILED_FROM,
            "filed_through": FILED_THROUGH,
            "as_of_date": AS_OF_DATE,
            "detector_execution_config": EXECUTION_CONFIG,
            "companies": company_rows,
            "finding_count": len(all_findings),
            "manifest_used": False,
            "fault_injection_used": False,
            "benchmark_claim": False,
        },
    )


if __name__ == "__main__":
    main()
