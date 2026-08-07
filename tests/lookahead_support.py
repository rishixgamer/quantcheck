"""Shared builders for focused Recovery Phase 3 tests."""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

import quantcheck as q

REVIEWED_SOURCE_HORIZON = date(2024, 4, 30)
REVIEWED_RESEARCH_DATE = date(2024, 4, 14)


class ReviewedLookAheadCase(NamedTuple):
    clean: q.DatasetSnapshot
    config: q.LookAheadInjectionConfig
    corrupted: q.DatasetSnapshot
    manifest: q.FaultManifest
    audit_input: q.AuditInputSnapshot
    audit_report: q.AuditReport
    score: q.ScoreReport
    repaired: q.DatasetSnapshot
    impact: q.ResearchImpact


def reviewed_lookahead_case(seed: int = 42) -> ReviewedLookAheadCase:
    clean = q.build_dataset_snapshot(
        q.generate_reviewed_fixture(),
        dataset_name="reviewed",
        as_of_date=REVIEWED_SOURCE_HORIZON,
    )
    config = q.LookAheadInjectionConfig(
        severity="medium",
        seed=seed,
        research_as_of_date=REVIEWED_RESEARCH_DATE,
    )
    corrupted, manifest = q.inject_lookahead(clean, config)
    audit_input = q.sanitize_for_audit(corrupted)
    audit_report = q.detect_lookahead(audit_input)
    score = q.score_lookahead(audit_report, manifest)
    repaired = q.manifest_assisted_exact_replay(corrupted, manifest)
    impact = q.compare_lookahead_research(
        clean,
        corrupted,
        repaired,
        research_as_of_date=REVIEWED_RESEARCH_DATE,
    )
    return ReviewedLookAheadCase(
        clean=clean,
        config=config,
        corrupted=corrupted,
        manifest=manifest,
        audit_input=audit_input,
        audit_report=audit_report,
        score=score,
        repaired=repaired,
        impact=impact,
    )


def rebuild_audit_report(
    report: q.AuditReport,
    findings: tuple[q.Finding, ...],
) -> q.AuditReport:
    canonical_findings = tuple(sorted(findings, key=lambda finding: finding.finding_id))
    body: dict[str, object] = {
        "detector_id": report.detector_id,
        "detector_version": report.detector_version,
        "audit_input_id": report.audit_input_id,
        "dataset_name": report.dataset_name,
        "as_of_date": report.as_of_date,
        "findings": canonical_findings,
    }
    return q.AuditReport.model_validate(
        {
            "audit_report_id": q.lookahead_audit_report_id(report_body=body),
            **body,
        }
    )


def rebuild_finding(finding: q.Finding, **updates: object) -> q.Finding:
    body = {name: getattr(finding, name) for name in q.Finding.model_fields if name != "finding_id"}
    body.update(updates)
    return q.Finding.model_validate(
        {
            "finding_id": q.lookahead_finding_id(finding_body=body),
            **body,
        }
    )
