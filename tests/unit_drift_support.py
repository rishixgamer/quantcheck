"""Shared deterministic builders for Recovery Phase 5 tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import NamedTuple

import quantcheck as q

UNIT_DRIFT_AS_OF = date(2024, 12, 31)


def unit_drift_records(
    values: tuple[str, ...] = ("100", "110", "120", "130", "140"),
    *,
    entity_id: str = "ENTITY-1",
    concept_namespace: str = "us-gaap",
    concept: str = "Revenues",
    unit: str = "USD",
    dimensions: tuple[q.Dimension, ...] = (),
    period_type: q.PeriodType = "instant",
    source_key: str = "main",
    available_on: date | None = None,
) -> tuple[q.FinancialFact, ...]:
    records: list[q.FinancialFact] = []
    first_end = date(2024, 1, 30)
    for index, value in enumerate(values):
        period_end = first_end + timedelta(days=60 * index)
        period_start = period_end - timedelta(days=29) if period_type == "duration" else None
        row_key = f"{source_key}-{index}"
        source = q.SourceReference(
            source_name="unit-drift-focused-fixture",
            source_locator="tests/unit_drift_support.py",
            source_row_key=row_key,
        )
        visible_on = available_on or period_end
        records.append(
            q.FinancialFact(
                record_id=q.source_record_id(
                    source_name=source.source_name,
                    source_locator=source.source_locator,
                    source_row_key=source.source_row_key,
                ),
                entity_id=entity_id,
                entity_name="Synthetic Unit Drift Entity",
                concept_namespace=concept_namespace,
                concept=concept,
                value=Decimal(value),
                unit=unit,
                dimensions=dimensions,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                filed_on=visible_on,
                available_on=visible_on,
                form="10-Q",
                accession_number=f"0000000001-24-{index + 1:06d}",
                source=source,
            )
        )
    return tuple(records)


def unit_drift_snapshot(
    records: tuple[q.FinancialFact, ...],
    *,
    dataset_name: str = "unit-drift-focused",
    as_of_date: date = UNIT_DRIFT_AS_OF,
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


class ReviewedUnitDriftCase(NamedTuple):
    clean: q.DatasetSnapshot
    config: q.UnitDriftInjectionConfig
    corrupted: q.DatasetSnapshot
    manifest: q.UnitDriftManifest
    audit_input: q.AuditInputSnapshot
    audit_report: q.AuditReport
    score: q.ScoreReport
    repaired: q.DatasetSnapshot
    research_config: q.UnitDriftResearchConfig
    impact: q.AggregateValueImpact


def reviewed_unit_drift_case(seed: int = 6) -> ReviewedUnitDriftCase:
    clean = unit_drift_snapshot(unit_drift_records(), dataset_name="unit-drift-reviewed")
    config = q.UnitDriftInjectionConfig(severity="medium", seed=seed)
    corrupted, manifest = q.inject_unit_drift(clean, config)
    audit_input = q.sanitize_for_audit(corrupted)
    audit_report = q.detect_unit_drift(audit_input, q.UnitDriftDetectorConfig())
    score = q.score_unit_drift(audit_report, manifest)
    repaired = q.manifest_assisted_exact_unit_drift_replay(corrupted, manifest)
    research_config = q.UnitDriftResearchConfig(
        comparable_series_key=manifest.entries[0].comparable_series_key,
        research_as_of_date=UNIT_DRIFT_AS_OF,
    )
    impact = q.compare_unit_drift_research(
        clean,
        corrupted,
        repaired,
        research_config,
    )
    return ReviewedUnitDriftCase(
        clean=clean,
        config=config,
        corrupted=corrupted,
        manifest=manifest,
        audit_input=audit_input,
        audit_report=audit_report,
        score=score,
        repaired=repaired,
        research_config=research_config,
        impact=impact,
    )


def rebuild_unit_drift_finding(finding: q.Finding, **updates: object) -> q.Finding:
    body = {name: getattr(finding, name) for name in q.Finding.model_fields if name != "finding_id"}
    body.update(updates)
    return q.Finding.model_validate(
        {
            "finding_id": q.unit_drift_finding_id(finding_body=body),
            **body,
        }
    )


def rebuild_unit_drift_report(
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
            "audit_report_id": q.unit_drift_audit_report_id(report_body=body),
            **body,
        }
    )
