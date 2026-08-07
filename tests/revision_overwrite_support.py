"""Shared deterministic builders for Recovery Phase 7 tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NamedTuple

import quantcheck as q

REVIEWED_HISTORICAL_CUTOFF = date(2024, 4, 30)
REVIEWED_RESEARCH_CUTOFF = date(2024, 8, 31)
REVIEWED_SEED = 7


def revision_record(
    row_key: str,
    *,
    value: str,
    filed_on: date,
    available_on: date | None = None,
    entity_id: str = "ENTITY-1",
    entity_name: str = "Synthetic Revision Entity",
    concept_namespace: str = "us-gaap",
    concept: str = "Revenues",
    unit: str = "USD",
    dimensions: tuple[q.Dimension, ...] = (),
    period_type: q.PeriodType = "duration",
    period_start: date | None = date(2024, 1, 1),
    period_end: date = date(2024, 3, 31),
    form: str | None = "10-Q",
    accession_number: str | None = None,
    source_name: str = "revision-focused-fixture",
    source_locator: str = "logical-revision-source",
) -> q.FinancialFact:
    accession = accession_number or f"ACC-{row_key.replace('#', '-')}"
    source = q.SourceReference(
        source_name=source_name,
        source_locator=source_locator,
        source_row_key=row_key,
    )
    return q.FinancialFact(
        record_id=q.source_record_id(
            source_name=source_name,
            source_locator=source_locator,
            source_row_key=row_key,
        ),
        entity_id=entity_id,
        entity_name=entity_name,
        concept_namespace=concept_namespace,
        concept=concept,
        value=Decimal(value),
        unit=unit,
        dimensions=dimensions,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        filed_on=filed_on,
        available_on=available_on or filed_on,
        form=form,
        accession_number=accession,
        source=source,
    )


def focused_history(
    *,
    historical_value: str = "100",
    later_value: str = "125",
    historical_filed_on: date = date(2024, 4, 15),
    later_filed_on: date = date(2024, 6, 1),
) -> tuple[q.FinancialFact, q.FinancialFact]:
    return (
        revision_record(
            "FOCUSED-Q1#r1",
            value=historical_value,
            filed_on=historical_filed_on,
            accession_number="ACC-R1",
        ),
        revision_record(
            "FOCUSED-Q1#r2",
            value=later_value,
            filed_on=later_filed_on,
            form="10-Q/A",
            accession_number="ACC-R2",
            source_locator="logical-revision-source-amended",
        ),
    )


def focused_snapshot(
    records: tuple[q.FinancialFact, ...],
    *,
    as_of_date: date = date(2024, 4, 30),
    dataset_name: str = "revision-focused",
) -> q.DatasetSnapshot:
    return q.build_dataset_snapshot(
        records,
        dataset_name=dataset_name,
        as_of_date=as_of_date,
    )


class ReviewedRevisionOverwriteCase(NamedTuple):
    source_records: tuple[q.FinancialFact, ...]
    clean: q.DatasetSnapshot
    config: q.RevisionOverwriteInjectionConfig
    corrupted: q.DatasetSnapshot
    manifest: q.RevisionOverwriteManifest
    audit_input: q.AuditInputSnapshot
    audit_report: q.AuditReport
    score: q.ScoreReport
    repaired: q.DatasetSnapshot
    research_impact: q.GrowthRankingImpact


def reviewed_revision_overwrite_case(
    seed: int = REVIEWED_SEED,
) -> ReviewedRevisionOverwriteCase:
    source_records = q.generate_reviewed_fixture()
    clean = q.build_dataset_snapshot(
        source_records,
        dataset_name="revision-reviewed",
        as_of_date=REVIEWED_HISTORICAL_CUTOFF,
    )
    config = q.RevisionOverwriteInjectionConfig(severity="low", seed=seed)
    corrupted, manifest = q.inject_revision_overwrite(clean, source_records, config)
    audit_input = q.sanitize_for_audit(corrupted)
    audit_report = q.detect_revision_overwrite(audit_input, q.RevisionOverwriteDetectorConfig())
    score = q.score_revision_overwrite(audit_report, manifest)
    repaired = q.manifest_assisted_exact_revision_overwrite_replay(corrupted, manifest)
    research_config = q.GrowthRankingConfig(
        concept_namespace="us-gaap",
        concept="NetIncomeLoss",
        unit="USD",
        prior_period_start=date(2024, 1, 1),
        prior_period_end=date(2024, 3, 31),
        current_period_start=date(2024, 4, 1),
        current_period_end=date(2024, 6, 30),
        research_as_of_date=REVIEWED_RESEARCH_CUTOFF,
        top_n=1,
    )
    clean_research_input, corrupted_research_input, repaired_research_input = (
        q.build_frozen_vintage_growth_snapshot(snapshot, source_records, research_config)
        for snapshot in (clean, corrupted, repaired)
    )
    research_impact = q.compare_revision_overwrite_research(
        clean_research_input,
        corrupted_research_input,
        repaired_research_input,
        research_config,
    )
    return ReviewedRevisionOverwriteCase(
        source_records=source_records,
        clean=clean,
        config=config,
        corrupted=corrupted,
        manifest=manifest,
        audit_input=audit_input,
        audit_report=audit_report,
        score=score,
        repaired=repaired,
        research_impact=research_impact,
    )


def rebuild_revision_finding(finding: q.Finding, **updates: object) -> q.Finding:
    body = {name: getattr(finding, name) for name in q.Finding.model_fields if name != "finding_id"}
    body.update(updates)
    return q.Finding.model_validate(
        {
            "finding_id": q.revision_overwrite_finding_id(finding_body=body),
            **body,
        }
    )


def rebuild_revision_report(
    report: q.AuditReport,
    findings: tuple[q.Finding, ...],
) -> q.AuditReport:
    body: dict[str, object] = {
        "detector_id": report.detector_id,
        "detector_version": report.detector_version,
        "audit_input_id": report.audit_input_id,
        "dataset_name": report.dataset_name,
        "as_of_date": report.as_of_date,
        "findings": tuple(sorted(findings, key=lambda finding: finding.finding_id)),
    }
    return q.AuditReport.model_validate(
        {
            "audit_report_id": q.revision_overwrite_audit_report_id(report_body=body),
            **body,
        }
    )
