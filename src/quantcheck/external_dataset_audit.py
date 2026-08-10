"""Manifest-free production audit workflow for external financial datasets."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.benchmark_v2_execution import run_selected_detectors_v2
from quantcheck.external_dataset_contract import (
    EXTERNAL_AUDIT_V2_NAMESPACE,
    DatasetMappingV1,
    ExternalAuditArtifactsV2,
    ExternalDatasetAuditReportV2,
    ExternalDatasetFileInputV1,
    ExternalDatasetValidationProfileV1,
    NormalizedDatasetV1,
)
from quantcheck.external_dataset_ingestion import (
    dataset_mapping_id,
    load_external_file,
    load_external_rows,
    normalized_dataset_identity_matches,
)
from quantcheck.external_dataset_policy import (
    evaluate_audit_policy,
    policy_detector_configs,
    policy_detector_execution_config,
    validate_publication_lag_semantics,
)
from quantcheck.external_dataset_policy_contract import (
    AuditPolicyV1,
    audit_policy_identity_matches,
)
from quantcheck.hashing import (
    audit_input_snapshot_identity_matches,
    canonical_sha256,
    dataset_snapshot_identity_matches,
    stable_id,
)
from quantcheck.point_in_time import build_dataset_snapshot
from quantcheck.schemas import AuditInputSnapshot, DatasetSnapshot

__all__ = [
    "ExternalDatasetAuditError",
    "audit_external_file",
    "audit_external_rows",
    "audit_normalized_dataset",
    "external_audit_report_identity_matches",
]


class ExternalDatasetAuditError(ValueError):
    """Raised when already-normalized workflow evidence fails integrity checks."""


def _public_report(
    *,
    mapping: DatasetMappingV1,
    normalized: NormalizedDatasetV1,
    as_of_date: date,
    policy: AuditPolicyV1,
) -> tuple[DatasetSnapshot, AuditInputSnapshot, ExternalDatasetAuditReportV2]:
    if not audit_policy_identity_matches(policy):
        raise ExternalDatasetAuditError("audit policy identity mismatch")
    if normalized.mapping_id != dataset_mapping_id(mapping):
        raise ExternalDatasetAuditError("normalized dataset mapping identity mismatch")
    if not normalized_dataset_identity_matches(normalized):
        raise ExternalDatasetAuditError("normalized dataset identity mismatch")

    snapshot = build_dataset_snapshot(
        normalized.records,
        dataset_name=normalized.dataset_name,
        as_of_date=as_of_date,
    )
    if not dataset_snapshot_identity_matches(snapshot):
        raise ExternalDatasetAuditError("point-in-time snapshot identity mismatch")
    audit_input = sanitize_for_audit(snapshot)
    if not audit_input_snapshot_identity_matches(audit_input):
        raise ExternalDatasetAuditError("sanitized audit input identity mismatch")
    validate_publication_lag_semantics(policy, mapping)
    detector_config = policy_detector_execution_config(policy)
    detector_runs = (
        run_selected_detectors_v2(audit_input, detector_config).runs
        if detector_config is not None
        else ()
    )
    evaluation = evaluate_audit_policy(
        policy=policy,
        audit_input=audit_input,
        detector_runs=detector_runs,
    )
    blocking_count = sum(item.effective_action == "blocking" for item in evaluation.results)
    warning_count = sum(item.effective_action == "warning" for item in evaluation.results)
    informational_count = sum(
        item.effective_action == "informational" for item in evaluation.results
    )
    waived_count = sum(item.effective_action is None for item in evaluation.results)
    exception_applied_count = sum(
        item.disposition == "exception_applied" for item in evaluation.results
    )
    disposition = (
        "blocked"
        if blocking_count
        else "review_required"
        if warning_count
        else "passed_with_information"
        if informational_count
        else "passed"
    )

    body: dict[str, object] = {
        "spec_version": "quantcheck/external-audit/v2",
        "policy_id": policy.policy_id,
        "policy_name": policy.policy_name,
        "policy_version": policy.policy_version,
        "policy_content_hash": policy.policy_content_hash,
        "mapping_id": normalized.mapping_id,
        "normalized_dataset_id": normalized.normalized_dataset_id,
        "normalized_dataset_hash": canonical_sha256(normalized),
        "dataset_name": normalized.dataset_name,
        "as_of_date": as_of_date,
        "source_record_count": normalized.record_count,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_hash": canonical_sha256(snapshot),
        "snapshot_record_count": len(snapshot.records),
        "audit_input_id": audit_input.audit_input_id,
        "audit_input_hash": canonical_sha256(audit_input),
        "selected_detectors": tuple(run.detector for run in detector_runs),
        "detector_configs": policy_detector_configs(policy),
        "detector_runs": detector_runs,
        "finding_count": sum(len(run.report.findings) for run in detector_runs),
        "rule_evaluations": evaluation.rule_evaluations,
        "policy_results": evaluation.results,
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "informational_count": informational_count,
        "waived_count": waived_count,
        "exception_applied_count": exception_applied_count,
        "disposition": disposition,
        "manifest_used": False,
        "fault_injection_used": False,
        "benchmark_claim": False,
        "network_used": False,
    }
    report = ExternalDatasetAuditReportV2.model_validate(
        {
            "external_audit_report_id": stable_id(
                prefix="xaudit2",
                namespace=EXTERNAL_AUDIT_V2_NAMESPACE,
                payload=body,
            ),
            **body,
        }
    )
    return snapshot, audit_input, report


def audit_normalized_dataset(
    normalized: NormalizedDatasetV1,
    *,
    mapping: DatasetMappingV1,
    validation_profile: ExternalDatasetValidationProfileV1,
    as_of_date: date,
    policy: AuditPolicyV1,
) -> ExternalAuditArtifactsV2:
    """Run point-in-time selection, sanitization, and selected detectors.

    ``policy`` is required and identity-bearing, so detector selection,
    actions, expectations, thresholds, and exceptions are explicit.  The
    function accepts no manifest, seed, severity, fault profile, injector, or
    benchmark input.
    """
    if not validation_profile.valid:
        raise ExternalDatasetAuditError("validation profile is not valid")
    if validation_profile.mapping_id != normalized.mapping_id:
        raise ExternalDatasetAuditError("validation profile mapping identity mismatch")
    snapshot, audit_input, report = _public_report(
        mapping=mapping,
        normalized=normalized,
        as_of_date=as_of_date,
        policy=policy,
    )
    return ExternalAuditArtifactsV2(
        policy=policy,
        validation_profile=validation_profile,
        normalized_dataset=normalized,
        snapshot=snapshot,
        audit_input=audit_input,
        public_report=report,
    )


def audit_external_file(
    path: Path,
    *,
    mapping: DatasetMappingV1,
    file_input: ExternalDatasetFileInputV1,
    as_of_date: date,
    policy: AuditPolicyV1,
    max_diagnostics: int = 100,
) -> ExternalAuditArtifactsV2:
    """Audit an integrity-pinned, read-only CSV/Parquet/Arrow file."""
    profile, normalized = load_external_file(
        path,
        mapping,
        file_input,
        max_diagnostics=max_diagnostics,
    )
    return audit_normalized_dataset(
        normalized,
        mapping=mapping,
        validation_profile=profile,
        as_of_date=as_of_date,
        policy=policy,
    )


def audit_external_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    mapping: DatasetMappingV1,
    as_of_date: date,
    policy: AuditPolicyV1,
    max_diagnostics: int = 100,
) -> ExternalAuditArtifactsV2:
    """Audit caller-owned Python mappings without modifying them."""
    profile, normalized = load_external_rows(
        rows,
        mapping,
        max_diagnostics=max_diagnostics,
    )
    return audit_normalized_dataset(
        normalized,
        mapping=mapping,
        validation_profile=profile,
        as_of_date=as_of_date,
        policy=policy,
    )


def external_audit_report_identity_matches(report: ExternalDatasetAuditReportV2) -> bool:
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
