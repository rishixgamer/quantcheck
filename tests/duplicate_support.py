"""Shared deterministic builders for Recovery Phase 6 tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NamedTuple

import quantcheck as q

REVIEWED_SOURCE_HORIZON = date(2024, 8, 31)
REVIEWED_SEED = 7
REVIEWED_SEVERITY: q.DuplicateSeverity = "high"


def duplicate_record(
    row_key: str,
    *,
    entity_id: str = "ENTITY-1",
    concept_namespace: str = "us-gaap",
    concept: str = "Revenues",
    value: str = "100",
    unit: str = "USD",
    dimensions: tuple[q.Dimension, ...] = (),
    period_type: q.PeriodType = "instant",
    period_start: date | None = None,
    period_end: date = date(2024, 3, 31),
    filed_on: date = date(2024, 4, 15),
    available_on: date = date(2024, 4, 15),
    form: str | None = "10-Q",
    accession_number: str | None = "0000000001-24-000001",
    source_name: str = "duplicate-focused-fixture",
    source_locator: str = "tests/duplicate_support.py",
    entity_name: str = "Synthetic Duplicate Entity",
) -> q.FinancialFact:
    """Build one synthetic ``FinancialFact`` with fully overridable fields."""
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
        available_on=available_on,
        form=form,
        accession_number=accession_number,
        source=q.SourceReference(
            source_name=source_name,
            source_locator=source_locator,
            source_row_key=row_key,
        ),
    )


def duplicate_snapshot(
    records: tuple[q.FinancialFact, ...],
    *,
    dataset_name: str = "duplicate-focused",
    as_of_date: date = date(2024, 12, 31),
) -> q.DatasetSnapshot:
    return q.DatasetSnapshot(
        snapshot_id=q.dataset_snapshot_id(
            dataset_name=dataset_name,
            as_of_date=as_of_date,
            records=records,
        ),
        dataset_name=dataset_name,
        as_of_date=as_of_date,
        records=records,
    )


class ReviewedDuplicateCase(NamedTuple):
    clean: q.DatasetSnapshot
    config: q.DuplicateInjectionConfig
    corrupted: q.DatasetSnapshot
    manifest: q.DuplicateManifest
    audit_input: q.AuditInputSnapshot
    audit_report: q.AuditReport
    score: q.ScoreReport
    repaired: q.DatasetSnapshot
    record_count_impact: q.RecordCountImpact


def reviewed_duplicate_case(
    seed: int = REVIEWED_SEED,
    severity: q.DuplicateSeverity = REVIEWED_SEVERITY,
) -> ReviewedDuplicateCase:
    clean = q.build_dataset_snapshot(
        q.generate_reviewed_fixture(),
        dataset_name="reviewed",
        as_of_date=REVIEWED_SOURCE_HORIZON,
    )
    config = q.DuplicateInjectionConfig(severity=severity, seed=seed)
    corrupted, manifest = q.inject_duplicate_observations(clean, config)
    audit_input = q.sanitize_for_audit(corrupted)
    audit_report = q.detect_duplicate_observations(audit_input)
    score = q.score_duplicate_observations(audit_report, manifest)
    repaired = q.manifest_assisted_exact_duplicate_replay(corrupted, manifest)
    record_count_impact = q.compare_duplicate_record_count(clean, corrupted, repaired)
    return ReviewedDuplicateCase(
        clean=clean,
        config=config,
        corrupted=corrupted,
        manifest=manifest,
        audit_input=audit_input,
        audit_report=audit_report,
        score=score,
        repaired=repaired,
        record_count_impact=record_count_impact,
    )


def rebuild_duplicate_finding(finding: q.Finding, **updates: object) -> q.Finding:
    body = {name: getattr(finding, name) for name in q.Finding.model_fields if name != "finding_id"}
    body.update(updates)
    return q.Finding.model_validate(
        {
            "finding_id": q.duplicate_finding_id(finding_body=body),
            **body,
        }
    )


def rebuild_duplicate_report(
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
            "audit_report_id": q.duplicate_audit_report_id(report_body=body),
            **body,
        }
    )
