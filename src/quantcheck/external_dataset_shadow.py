"""Design-partner shadow-mode packaging, adjudication, and factual reporting.

This module reads already-finalized public external-audit reports.  It never
opens or writes the customer source dataset and it has no path to injection,
manifest scoring, detector execution, or production blocking.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from pydantic import BaseModel, ValidationError

from quantcheck.benchmark_v2_contract import ALL_V2_DETECTORS
from quantcheck.external_dataset_contract import (
    EXTERNAL_AUDIT_V2_NAMESPACE,
    ExternalDatasetAuditReportV2,
)
from quantcheck.external_dataset_shadow_contract import (
    ADJUDICATION_EXPORT_SPEC_VERSION,
    FINDING_BUNDLE_SPEC_VERSION,
    PILOT_REPORT_SPEC_VERSION,
    RERUN_COMPARISON_SPEC_VERSION,
    REVIEWER_NOTES_SPEC_VERSION,
    AdjudicationEntryInputV1,
    AdjudicationEntryV1,
    AdjudicationExportV1,
    AdjudicationInputV1,
    AuditReportEvidenceV1,
    DetectorPilotMetricV1,
    FindingRerunComparisonV1,
    PilotArtifactReferenceV1,
    PilotReportV1,
    RerunComparisonV1,
    ReviewerNotesInputV1,
    ReviewerNotesV1,
    ReviewerNoteV1,
    ShadowFindingBundleV1,
    ShadowFindingV1,
    adjudication_export_identity_matches,
    build_adjudication_export_identity,
    build_audit_context_id,
    build_finding_bundle_identity,
    build_pilot_report_identity,
    build_rerun_comparison_identity,
    build_reviewer_note_id,
    build_reviewer_notes_identity,
    build_shadow_audit_id,
    finding_bundle_identity_matches,
    reviewer_notes_identity_matches,
    shadow_finding_key,
)
from quantcheck.hashing import canonical_sha256, stable_id
from quantcheck.json_types import CanonicalizationError
from quantcheck.serialization import (
    canonical_json_bytes,
    canonical_json_text,
    parse_canonical_json,
)

__all__ = [
    "ShadowModeError",
    "build_adjudication_input_template",
    "build_pilot_report",
    "build_reviewer_notes",
    "build_reviewer_notes_input_template",
    "build_rerun_comparison",
    "build_shadow_finding_bundle",
    "finalize_adjudication_export",
    "main",
    "prepare_shadow_package",
]

_MAX_ARTIFACT_BYTES = 256 * 1024 * 1024


class ShadowModeError(ValueError):
    """Raised when shadow-mode evidence is incomplete, inconsistent, or mutable."""


def _external_report_identity_matches(report: ExternalDatasetAuditReportV2) -> bool:
    body = {
        name: getattr(report, name)
        for name in type(report).model_fields
        if name != "external_audit_report_id"
    }
    return report.external_audit_report_id == stable_id(
        prefix="xaudit2",
        namespace=EXTERNAL_AUDIT_V2_NAMESPACE,
        payload=body,
    )


def _bundle_audit_context_payload(
    *, dataset_key: str, reports: tuple[ExternalDatasetAuditReportV2, ...]
) -> dict[str, object]:
    first = reports[0]
    return {
        "dataset_key": dataset_key,
        "mapping_id": first.mapping_id,
        "policy_id": first.policy_id,
        "policy_content_hash": first.policy_content_hash,
        "as_of_date": first.as_of_date,
        "report_contexts": tuple(
            sorted(
                (
                    report.normalized_dataset_hash,
                    report.snapshot_hash,
                    report.audit_input_hash,
                    report.source_record_count,
                    report.snapshot_record_count,
                )
                for report in reports
            )
        ),
    }


def _validate_reports(
    reports: tuple[ExternalDatasetAuditReportV2, ...],
) -> tuple[ExternalDatasetAuditReportV2, ...]:
    if not reports:
        raise ShadowModeError("at least one public audit report is required")
    ordered = tuple(sorted(reports, key=lambda item: item.external_audit_report_id))
    if len({item.external_audit_report_id for item in ordered}) != len(ordered):
        raise ShadowModeError("public audit report identifiers must be unique")
    first = ordered[0]
    for report in ordered:
        if not _external_report_identity_matches(report):
            raise ShadowModeError("public audit report identity mismatch")
        if (
            report.dataset_name != first.dataset_name
            or report.mapping_id != first.mapping_id
            or report.policy_id != first.policy_id
            or report.policy_content_hash != first.policy_content_hash
            or report.as_of_date != first.as_of_date
        ):
            raise ShadowModeError("public audit reports do not describe one audit context")
    return ordered


def _finding_policy_result(
    report: ExternalDatasetAuditReportV2, finding_id: str
) -> tuple[str, str, str | None, bool]:
    matches = tuple(
        result
        for result in report.policy_results
        if result.evidence.kind == "detector_finding" and result.evidence.finding_id == finding_id
    )
    if len(matches) != 1:
        raise ShadowModeError("each detector finding must have exactly one policy result")
    result = matches[0]
    return (
        result.policy_result_id,
        result.base_action,
        result.effective_action,
        result.disposition == "exception_applied",
    )


def build_shadow_finding_bundle(
    *,
    dataset_key: str,
    quantcheck_version: str,
    code_revision: str,
    runtime_ns: int,
    reports: tuple[ExternalDatasetAuditReportV2, ...],
    execution_run_id: str | None = None,
    execution_finalization_id: str | None = None,
) -> ShadowFindingBundleV1:
    """Bind unchanged public findings to one reproducible shadow audit identity."""
    ordered_reports = _validate_reports(reports)
    first = ordered_reports[0]
    report_evidence = tuple(
        AuditReportEvidenceV1(report=report, report_content_hash=canonical_sha256(report))
        for report in ordered_reports
    )
    findings: list[ShadowFindingV1] = []
    for report in ordered_reports:
        for run in report.detector_runs:
            for finding in run.report.findings:
                result_id, base_action, effective_action, exception_applied = (
                    _finding_policy_result(report, finding.finding_id)
                )
                findings.append(
                    ShadowFindingV1(
                        finding_key=shadow_finding_key(detector=run.detector, finding=finding),
                        detector=run.detector,
                        source_report_id=report.external_audit_report_id,
                        finding=finding,
                        finding_content_hash=canonical_sha256(finding),
                        policy_result_id=result_id,
                        base_action=base_action,  # type: ignore[arg-type]
                        effective_action=effective_action,  # type: ignore[arg-type]
                        policy_exception_applied=exception_applied,
                    )
                )
    ordered_findings = tuple(sorted(findings, key=lambda item: item.finding.finding_id))
    audit_context_payload = _bundle_audit_context_payload(
        dataset_key=dataset_key,
        reports=ordered_reports,
    )
    audit_context_id = build_audit_context_id(audit_context_payload)
    shadow_audit_payload = {
        "spec_version": FINDING_BUNDLE_SPEC_VERSION,
        "dataset_key": dataset_key,
        "quantcheck_version": quantcheck_version,
        "code_revision": code_revision,
        "execution_run_id": execution_run_id,
        "execution_finalization_id": execution_finalization_id,
        "audit_context_id": audit_context_id,
        "audit_reports": tuple(
            (item.report.external_audit_report_id, item.report_content_hash)
            for item in report_evidence
        ),
    }
    body: dict[str, object] = {
        "spec_version": FINDING_BUNDLE_SPEC_VERSION,
        "shadow_audit_id": build_shadow_audit_id(shadow_audit_payload),
        "audit_context_id": audit_context_id,
        "dataset_key": dataset_key,
        "quantcheck_version": quantcheck_version,
        "code_revision": code_revision,
        "execution_run_id": execution_run_id,
        "execution_finalization_id": execution_finalization_id,
        "runtime_ns": runtime_ns,
        "mapping_id": first.mapping_id,
        "policy_id": first.policy_id,
        "policy_content_hash": first.policy_content_hash,
        "as_of_date": first.as_of_date,
        "source_record_count": sum(report.source_record_count for report in ordered_reports),
        "records_audited": sum(report.snapshot_record_count for report in ordered_reports),
        "audit_reports": report_evidence,
        "findings": ordered_findings,
        "finding_count": len(ordered_findings),
        "shadow_mode": True,
        "source_modified": False,
        "production_blocking_used": False,
        "manifest_used": False,
        "benchmark_claim": False,
    }
    bundle_id, bundle_hash = build_finding_bundle_identity(body)
    bundle = ShadowFindingBundleV1.model_validate(
        {
            "finding_bundle_id": bundle_id,
            "bundle_content_hash": bundle_hash,
            **body,
        }
    )
    if not finding_bundle_identity_matches(bundle):
        raise ShadowModeError("constructed finding bundle identity mismatch")
    return bundle


def build_adjudication_input_template(bundle: ShadowFindingBundleV1) -> AdjudicationInputV1:
    """Create a complete, unresolved template without copying finding evidence."""
    if not finding_bundle_identity_matches(bundle):
        raise ShadowModeError("finding bundle identity mismatch")
    return AdjudicationInputV1(
        finding_bundle_id=bundle.finding_bundle_id,
        finding_bundle_hash=bundle.bundle_content_hash,
        entries=tuple(
            AdjudicationEntryInputV1(
                finding_id=item.finding.finding_id,
                finding_content_hash=item.finding_content_hash,
                investigation_status="not_started",
                disposition="unresolved",
                decision_impact="not_assessed",
                researcher_review_seconds=0,
            )
            for item in bundle.findings
        ),
    )


def finalize_adjudication_export(
    bundle: ShadowFindingBundleV1,
    supplied: AdjudicationInputV1,
) -> AdjudicationExportV1:
    """Validate complete supplied decisions and emit a sanitized, hash-linked export."""
    if not finding_bundle_identity_matches(bundle):
        raise ShadowModeError("finding bundle identity mismatch")
    if (
        supplied.finding_bundle_id != bundle.finding_bundle_id
        or supplied.finding_bundle_hash != bundle.bundle_content_hash
    ):
        raise ShadowModeError("adjudication input does not link to the finding bundle")
    findings_by_id = {item.finding.finding_id: item for item in bundle.findings}
    entries_by_id = {item.finding_id: item for item in supplied.entries}
    if set(entries_by_id) != set(findings_by_id):
        raise ShadowModeError("adjudication must cover every finding exactly once")
    finalized: list[AdjudicationEntryV1] = []
    for finding_id in sorted(findings_by_id):
        finding = findings_by_id[finding_id]
        entry = entries_by_id[finding_id]
        if entry.finding_content_hash != finding.finding_content_hash:
            raise ShadowModeError("adjudication finding hash mismatch")
        finalized.append(
            AdjudicationEntryV1(
                **entry.model_dump(mode="python"),
                detector=finding.detector,
            )
        )
    body: dict[str, object] = {
        "spec_version": ADJUDICATION_EXPORT_SPEC_VERSION,
        "shadow_audit_id": bundle.shadow_audit_id,
        "finding_bundle_id": bundle.finding_bundle_id,
        "finding_bundle_hash": bundle.bundle_content_hash,
        "entries": tuple(finalized),
        "sanitized": True,
        "finding_evidence_included": False,
        "reviewer_notes_included": False,
        "customer_record_ids_included": False,
        "customer_values_included": False,
    }
    export_id, export_hash = build_adjudication_export_identity(body)
    export = AdjudicationExportV1.model_validate(
        {
            "adjudication_export_id": export_id,
            "export_content_hash": export_hash,
            **body,
        }
    )
    if not adjudication_export_identity_matches(export):
        raise ShadowModeError("constructed adjudication export identity mismatch")
    return export


def build_reviewer_notes_input_template(bundle: ShadowFindingBundleV1) -> ReviewerNotesInputV1:
    """Create a deliberately separate private note template."""
    if not finding_bundle_identity_matches(bundle):
        raise ShadowModeError("finding bundle identity mismatch")
    return ReviewerNotesInputV1(
        finding_bundle_id=bundle.finding_bundle_id,
        finding_bundle_hash=bundle.bundle_content_hash,
        notes=(),
    )


def build_reviewer_notes(
    bundle: ShadowFindingBundleV1,
    supplied: ReviewerNotesInputV1,
) -> ReviewerNotesV1:
    """Finalize private notes without reading or changing adjudication or findings."""
    if not finding_bundle_identity_matches(bundle):
        raise ShadowModeError("finding bundle identity mismatch")
    if (
        supplied.finding_bundle_id != bundle.finding_bundle_id
        or supplied.finding_bundle_hash != bundle.bundle_content_hash
    ):
        raise ShadowModeError("reviewer notes do not link to the finding bundle")
    findings_by_id = {item.finding.finding_id: item for item in bundle.findings}
    notes: list[ReviewerNoteV1] = []
    for note in supplied.notes:
        finding = findings_by_id.get(note.finding_id)
        if finding is None:
            raise ShadowModeError("reviewer note names an unknown finding")
        note_body = {
            "finding_id": note.finding_id,
            "finding_content_hash": finding.finding_content_hash,
            "note_revision": note.note_revision,
            "reviewer_role": note.reviewer_role,
            "note": note.note,
        }
        notes.append(
            ReviewerNoteV1(
                reviewer_note_id=build_reviewer_note_id(note_body),
                finding_id=note.finding_id,
                finding_content_hash=finding.finding_content_hash,
                note_revision=note.note_revision,
                reviewer_role=note.reviewer_role,
                note=note.note,
            )
        )
    body: dict[str, object] = {
        "spec_version": REVIEWER_NOTES_SPEC_VERSION,
        "finding_bundle_id": bundle.finding_bundle_id,
        "finding_bundle_hash": bundle.bundle_content_hash,
        "notes": tuple(notes),
        "private": True,
        "included_in_pilot_metrics": False,
    }
    notes_id, notes_hash = build_reviewer_notes_identity(body)
    result = ReviewerNotesV1.model_validate(
        {
            "reviewer_notes_id": notes_id,
            "notes_content_hash": notes_hash,
            **body,
        }
    )
    if not reviewer_notes_identity_matches(result):
        raise ShadowModeError("constructed reviewer notes identity mismatch")
    return result


def build_rerun_comparison(
    baseline: ShadowFindingBundleV1,
    candidate: ShadowFindingBundleV1,
) -> RerunComparisonV1:
    """Compare exact finding/evidence keys while preserving both source bundles."""
    if not finding_bundle_identity_matches(baseline) or not finding_bundle_identity_matches(
        candidate
    ):
        raise ShadowModeError("finding bundle identity mismatch")
    if baseline.dataset_key != candidate.dataset_key:
        raise ShadowModeError("rerun comparison requires the same pseudonymous dataset key")
    baseline_by_key = {item.finding_key: item for item in baseline.findings}
    candidate_by_key = {item.finding_key: item for item in candidate.findings}
    comparisons: list[FindingRerunComparisonV1] = []
    for finding_key in sorted(set(baseline_by_key) | set(candidate_by_key)):
        old = baseline_by_key.get(finding_key)
        new = candidate_by_key.get(finding_key)
        source = old if old is not None else new
        if source is None:  # pragma: no cover - set union proves a source exists
            raise AssertionError("comparison key has no source finding")
        if old is None:
            status = "added"
        elif new is None:
            status = "removed"
        elif old.finding_content_hash == new.finding_content_hash:
            status = "unchanged"
        else:
            status = "changed"
        comparisons.append(
            FindingRerunComparisonV1(
                finding_key=finding_key,
                detector=source.detector,
                rule_id=source.finding.rule_id,
                status=status,  # type: ignore[arg-type]
                baseline_finding_id=old.finding.finding_id if old else None,
                baseline_finding_hash=old.finding_content_hash if old else None,
                candidate_finding_id=new.finding.finding_id if new else None,
                candidate_finding_hash=new.finding_content_hash if new else None,
            )
        )
    body: dict[str, object] = {
        "spec_version": RERUN_COMPARISON_SPEC_VERSION,
        "baseline_finding_bundle_id": baseline.finding_bundle_id,
        "baseline_finding_bundle_hash": baseline.bundle_content_hash,
        "baseline_shadow_audit_id": baseline.shadow_audit_id,
        "baseline_quantcheck_version": baseline.quantcheck_version,
        "baseline_code_revision": baseline.code_revision,
        "candidate_finding_bundle_id": candidate.finding_bundle_id,
        "candidate_finding_bundle_hash": candidate.bundle_content_hash,
        "candidate_shadow_audit_id": candidate.shadow_audit_id,
        "candidate_quantcheck_version": candidate.quantcheck_version,
        "candidate_code_revision": candidate.code_revision,
        "baseline_audit_context_id": baseline.audit_context_id,
        "candidate_audit_context_id": candidate.audit_context_id,
        "audit_context_matches": baseline.audit_context_id == candidate.audit_context_id,
        "comparisons": tuple(comparisons),
        "unchanged_count": sum(item.status == "unchanged" for item in comparisons),
        "changed_count": sum(item.status == "changed" for item in comparisons),
        "added_count": sum(item.status == "added" for item in comparisons),
        "removed_count": sum(item.status == "removed" for item in comparisons),
        "comparison_method": "exact_evidence_key_no_fuzzy_matching",
        "original_evidence_modified": False,
    }
    comparison_id, comparison_hash = build_rerun_comparison_identity(body)
    return RerunComparisonV1.model_validate(
        {
            "rerun_comparison_id": comparison_id,
            "comparison_content_hash": comparison_hash,
            **body,
        }
    )


def _validated_bundle_export_pairs(
    bundles: tuple[ShadowFindingBundleV1, ...],
    exports: tuple[AdjudicationExportV1, ...],
) -> tuple[tuple[ShadowFindingBundleV1, AdjudicationExportV1], ...]:
    if not bundles:
        raise ShadowModeError("pilot reporting requires at least one supplied dataset")
    by_bundle_id = {item.finding_bundle_id: item for item in bundles}
    export_by_bundle_id = {item.finding_bundle_id: item for item in exports}
    if len(by_bundle_id) != len(bundles) or len(export_by_bundle_id) != len(exports):
        raise ShadowModeError("pilot inputs contain duplicate source artifacts")
    if set(by_bundle_id) != set(export_by_bundle_id):
        raise ShadowModeError("every finding bundle requires exactly one adjudication export")
    dataset_keys = [item.dataset_key for item in bundles]
    if len(set(dataset_keys)) != len(dataset_keys):
        raise ShadowModeError("pilot reporting accepts one evaluated bundle per dataset key")
    pairs: list[tuple[ShadowFindingBundleV1, AdjudicationExportV1]] = []
    for bundle_id in sorted(by_bundle_id):
        bundle = by_bundle_id[bundle_id]
        export = export_by_bundle_id[bundle_id]
        if not finding_bundle_identity_matches(bundle) or not adjudication_export_identity_matches(
            export
        ):
            raise ShadowModeError("pilot source artifact identity mismatch")
        if (
            export.shadow_audit_id != bundle.shadow_audit_id
            or export.finding_bundle_hash != bundle.bundle_content_hash
        ):
            raise ShadowModeError("adjudication export does not link to its finding bundle")
        findings = {item.finding.finding_id: item for item in bundle.findings}
        entries = {item.finding_id: item for item in export.entries}
        if set(findings) != set(entries):
            raise ShadowModeError("pilot adjudication coverage is incomplete")
        for finding_id, entry in entries.items():
            finding = findings[finding_id]
            if (
                entry.finding_content_hash != finding.finding_content_hash
                or entry.detector != finding.detector
            ):
                raise ShadowModeError("pilot adjudication changed finding linkage")
        pairs.append((bundle, export))
    return tuple(pairs)


def build_pilot_report(
    *,
    pilot_key: str,
    bundles: tuple[ShadowFindingBundleV1, ...],
    adjudication_exports: tuple[AdjudicationExportV1, ...],
) -> PilotReportV1:
    """Derive aggregate pilot metrics solely from complete supplied adjudications."""
    pairs = _validated_bundle_export_pairs(bundles, adjudication_exports)
    entries = tuple(entry for _, export in pairs for entry in export.entries)
    detector_counts = {
        detector: sum(entry.detector == detector for entry in entries)
        for detector in ALL_V2_DETECTORS
    }
    investigated = tuple(entry for entry in entries if entry.investigation_status == "investigated")
    disposition_count = {
        disposition: sum(entry.disposition == disposition for entry in entries)
        for disposition in (
            "confirmed_issue",
            "legitimate_data_condition",
            "accepted_exception",
            "duplicate_correlated_signal",
        )
    }
    unresolved_investigated = sum(entry.disposition == "unresolved" for entry in investigated)
    sources = tuple(
        PilotArtifactReferenceV1(
            shadow_audit_id=bundle.shadow_audit_id,
            finding_bundle_id=bundle.finding_bundle_id,
            finding_bundle_hash=bundle.bundle_content_hash,
            adjudication_export_id=export.adjudication_export_id,
            adjudication_export_hash=export.export_content_hash,
        )
        for bundle, export in pairs
    )
    body: dict[str, object] = {
        "spec_version": PILOT_REPORT_SPEC_VERSION,
        "pilot_key": pilot_key,
        "source_artifacts": sources,
        "datasets_audited": len(pairs),
        "records_audited": sum(bundle.records_audited for bundle, _ in pairs),
        "runtime_ns": sum(bundle.runtime_ns for bundle, _ in pairs),
        "total_findings": len(entries),
        "findings_by_detector": tuple(
            DetectorPilotMetricV1(detector=detector, finding_count=detector_counts[detector])
            for detector in ALL_V2_DETECTORS
        ),
        "findings_investigated": len(investigated),
        "confirmed_issues": disposition_count["confirmed_issue"],
        "legitimate_data_conditions": disposition_count["legitimate_data_condition"],
        "accepted_exceptions": disposition_count["accepted_exception"],
        "legitimate_exceptions": (
            disposition_count["legitimate_data_condition"] + disposition_count["accepted_exception"]
        ),
        "duplicate_correlated_signals": disposition_count["duplicate_correlated_signal"],
        "unresolved_investigated_alerts": unresolved_investigated,
        "findings_not_investigated": len(entries) - len(investigated),
        "unexplained_or_noisy_alerts": (
            disposition_count["duplicate_correlated_signal"] + unresolved_investigated
        ),
        "customer_confirmed_research_decision_issues": sum(
            entry.decision_impact == "customer_independently_confirmed" for entry in entries
        ),
        "researcher_review_seconds": sum(entry.researcher_review_seconds for entry in entries),
        "aggregate_only": True,
        "customer_names_included": False,
        "dataset_names_included": False,
        "finding_evidence_included": False,
        "reviewer_notes_included": False,
        "customer_values_included": False,
        "customer_decision_confirmation_required": True,
        "manufactured_numbers": False,
    }
    report_id, report_hash = build_pilot_report_identity(body)
    return PilotReportV1.model_validate(
        {"pilot_report_id": report_id, "report_content_hash": report_hash, **body}
    )


def _read_model[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_ARTIFACT_BYTES:
            raise ShadowModeError("shadow artifact is unavailable or too large")
        return model.model_validate(parse_canonical_json(path.read_bytes()))
    except (OSError, ValidationError, CanonicalizationError) as exc:
        raise ShadowModeError("shadow artifact failed canonical validation") from exc


def _write_new(path: Path, artifact: BaseModel) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(canonical_json_bytes(artifact))
    except FileExistsError as exc:
        raise ShadowModeError("shadow output already exists") from exc
    except OSError as exc:
        raise ShadowModeError("shadow output could not be written") from exc


def prepare_shadow_package(
    *,
    output_directory: Path,
    dataset_key: str,
    quantcheck_version: str,
    code_revision: str,
    runtime_ns: int,
    reports: tuple[ExternalDatasetAuditReportV2, ...],
    execution_run_id: str | None = None,
    execution_finalization_id: str | None = None,
) -> ShadowFindingBundleV1:
    """Write separate immutable findings, editable adjudication, and private note templates."""
    bundle = build_shadow_finding_bundle(
        dataset_key=dataset_key,
        quantcheck_version=quantcheck_version,
        code_revision=code_revision,
        runtime_ns=runtime_ns,
        reports=reports,
        execution_run_id=execution_run_id,
        execution_finalization_id=execution_finalization_id,
    )
    output = Path(output_directory)
    _write_new(output / "researcher_finding_bundle.json", bundle)
    _write_new(output / "adjudication_input.json", build_adjudication_input_template(bundle))
    _write_new(
        output / "private" / "reviewer_notes_input.json",
        build_reviewer_notes_input_template(bundle),
    )
    return bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m quantcheck.external_dataset_shadow",
        description="Package and report a local, non-blocking QuantCheck shadow evaluation.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    prepare = subcommands.add_parser("prepare", help="Create a researcher review package.")
    prepare.add_argument("--audit-report", action="append", required=True)
    prepare.add_argument("--dataset-key", required=True)
    prepare.add_argument("--quantcheck-version", required=True)
    prepare.add_argument("--code-revision", required=True)
    prepare.add_argument("--runtime-ns", type=int, required=True)
    prepare.add_argument("--execution-run-id")
    prepare.add_argument("--execution-finalization-id")
    prepare.add_argument("--output-directory", required=True)

    adjudicate = subcommands.add_parser("adjudicate", help="Finalize sanitized adjudication.")
    adjudicate.add_argument("--bundle", required=True)
    adjudicate.add_argument("--input", required=True)
    adjudicate.add_argument("--output", required=True)

    notes = subcommands.add_parser("notes", help="Finalize separate private reviewer notes.")
    notes.add_argument("--bundle", required=True)
    notes.add_argument("--input", required=True)
    notes.add_argument("--output", required=True)

    compare = subcommands.add_parser("compare", help="Compare two QuantCheck-version bundles.")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--output", required=True)

    report = subcommands.add_parser("report", help="Generate aggregate factual pilot metrics.")
    report.add_argument("--pilot-key", required=True)
    report.add_argument("--bundle", action="append", required=True)
    report.add_argument("--adjudication", action="append", required=True)
    report.add_argument("--output", required=True)
    return parser


def _emit(stream: TextIO, *, event: str, artifact_id: str | None = None) -> None:
    payload: dict[str, object] = {"event": event, "redacted": True}
    if artifact_id is not None:
        payload["artifact_id"] = artifact_id
    stream.write(canonical_json_text(payload) + "\n")


def main(argv: Sequence[str] | None = None, *, stdout: TextIO | None = None) -> int:
    """Run the additive module CLI without changing the frozen root CLI."""
    stream = sys.stdout if stdout is None else stdout
    try:
        arguments = _parser().parse_args(tuple(sys.argv[1:] if argv is None else argv))
        if arguments.command == "prepare":
            reports = tuple(
                _read_model(Path(path), ExternalDatasetAuditReportV2)
                for path in arguments.audit_report
            )
            bundle_artifact = prepare_shadow_package(
                output_directory=Path(arguments.output_directory),
                dataset_key=arguments.dataset_key,
                quantcheck_version=arguments.quantcheck_version,
                code_revision=arguments.code_revision,
                runtime_ns=arguments.runtime_ns,
                reports=reports,
                execution_run_id=arguments.execution_run_id,
                execution_finalization_id=arguments.execution_finalization_id,
            )
            artifact_id = bundle_artifact.finding_bundle_id
        elif arguments.command == "adjudicate":
            bundle = _read_model(Path(arguments.bundle), ShadowFindingBundleV1)
            adjudication_input = _read_model(Path(arguments.input), AdjudicationInputV1)
            adjudication_artifact = finalize_adjudication_export(bundle, adjudication_input)
            _write_new(Path(arguments.output), adjudication_artifact)
            artifact_id = adjudication_artifact.adjudication_export_id
        elif arguments.command == "notes":
            bundle = _read_model(Path(arguments.bundle), ShadowFindingBundleV1)
            reviewer_notes_input = _read_model(Path(arguments.input), ReviewerNotesInputV1)
            reviewer_notes_artifact = build_reviewer_notes(bundle, reviewer_notes_input)
            _write_new(Path(arguments.output), reviewer_notes_artifact)
            artifact_id = reviewer_notes_artifact.reviewer_notes_id
        elif arguments.command == "compare":
            baseline = _read_model(Path(arguments.baseline), ShadowFindingBundleV1)
            candidate = _read_model(Path(arguments.candidate), ShadowFindingBundleV1)
            comparison_artifact = build_rerun_comparison(baseline, candidate)
            _write_new(Path(arguments.output), comparison_artifact)
            artifact_id = comparison_artifact.rerun_comparison_id
        else:
            bundles = tuple(
                _read_model(Path(path), ShadowFindingBundleV1) for path in arguments.bundle
            )
            exports = tuple(
                _read_model(Path(path), AdjudicationExportV1) for path in arguments.adjudication
            )
            report_artifact = build_pilot_report(
                pilot_key=arguments.pilot_key,
                bundles=bundles,
                adjudication_exports=exports,
            )
            _write_new(Path(arguments.output), report_artifact)
            artifact_id = report_artifact.pilot_report_id
    except (ShadowModeError, ValidationError, CanonicalizationError, OSError, ValueError):
        _emit(stream, event="shadow_command_failed")
        return 2
    _emit(stream, event="shadow_command_completed", artifact_id=artifact_id)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through subprocess tests
    raise SystemExit(main())
