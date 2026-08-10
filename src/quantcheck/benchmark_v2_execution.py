"""Manifest-blind execution of an explicit v0.2 detector selection."""

from __future__ import annotations

from collections.abc import Callable

from quantcheck.benchmark_v2_contract import DETECTOR_EXECUTION_V2_NAMESPACE, DetectorKeyV2
from quantcheck.benchmark_v2_schemas import (
    DetectorExecutionConfigV2,
    DetectorExecutionV2,
    DetectorRunV2,
)
from quantcheck.duplicate_detection import (
    detect_duplicate_observations,
    duplicate_audit_report_identity_matches,
    duplicate_finding_identity_matches,
)
from quantcheck.hashing import (
    audit_input_snapshot_identity_matches,
    canonical_sha256,
    stable_id,
)
from quantcheck.lookahead_detection import (
    audit_report_identity_matches,
    detect_lookahead,
    finding_identity_matches,
)
from quantcheck.revision_overwrite_detection import (
    detect_revision_overwrite,
    revision_overwrite_audit_report_identity_matches,
    revision_overwrite_finding_identity_matches,
)
from quantcheck.schemas import AuditInputSnapshot, AuditReport, Finding
from quantcheck.unit_drift_detection import (
    detect_unit_drift,
    unit_drift_audit_report_identity_matches,
    unit_drift_finding_identity_matches,
)

__all__ = [
    "DetectorExecutionV2Error",
    "detector_execution_findings",
    "detector_execution_v2_identity_matches",
    "run_selected_detectors_v2",
]


class DetectorExecutionV2Error(ValueError):
    """Raised when selected detector output fails its frozen identity contract."""


_REPORT_IDENTITY_CHECKS: dict[DetectorKeyV2, Callable[[AuditReport], bool]] = {
    "duplicate_observation": duplicate_audit_report_identity_matches,
    "lookahead_timestamp": audit_report_identity_matches,
    "revision_overwrite": revision_overwrite_audit_report_identity_matches,
    "unit_drift": unit_drift_audit_report_identity_matches,
}
_FINDING_IDENTITY_CHECKS: dict[DetectorKeyV2, Callable[[Finding], bool]] = {
    "duplicate_observation": duplicate_finding_identity_matches,
    "lookahead_timestamp": finding_identity_matches,
    "revision_overwrite": revision_overwrite_finding_identity_matches,
    "unit_drift": unit_drift_finding_identity_matches,
}


def _execution_body(
    *,
    audit_input: AuditInputSnapshot,
    config: DetectorExecutionConfigV2,
    runs: tuple[DetectorRunV2, ...],
) -> dict[str, object]:
    return {
        "spec_version": "quantcheck/detector-execution/v2",
        "audit_input_id": audit_input.audit_input_id,
        "audit_input_hash": canonical_sha256(audit_input),
        "audit_input": audit_input,
        "dataset_name": audit_input.dataset_name,
        "as_of_date": audit_input.as_of_date,
        "config": config,
        "runs": runs,
        "finding_count": sum(len(run.report.findings) for run in runs),
    }


def _run_detector(
    detector: DetectorKeyV2,
    audit_input: AuditInputSnapshot,
    config: DetectorExecutionConfigV2,
) -> AuditReport:
    detector_configs = config.detector_configs
    if detector == "lookahead_timestamp":
        return detect_lookahead(audit_input)
    if detector == "unit_drift":
        return detect_unit_drift(audit_input, detector_configs.unit_drift_detector)
    if detector == "duplicate_observation":
        return detect_duplicate_observations(audit_input)
    if detector == "revision_overwrite":
        return detect_revision_overwrite(
            audit_input,
            detector_configs.revision_overwrite_detector,
        )
    raise DetectorExecutionV2Error(f"unsupported detector: {detector!r}")


def _validate_run(run: DetectorRunV2) -> None:
    if not _REPORT_IDENTITY_CHECKS[run.detector](run.report):
        raise DetectorExecutionV2Error(
            f"{run.detector} audit report identity does not match its content"
        )
    if any(not _FINDING_IDENTITY_CHECKS[run.detector](finding) for finding in run.report.findings):
        raise DetectorExecutionV2Error(
            f"{run.detector} emitted a finding with invalid deterministic identity"
        )


def run_selected_detectors_v2(
    audit_input: AuditInputSnapshot,
    config: DetectorExecutionConfigV2 | None = None,
) -> DetectorExecutionV2:
    """Run one, several, or all frozen detectors over one sanitized snapshot.

    There is deliberately no manifest, clean snapshot, seed, severity, target,
    or injector parameter.  The detector trust boundary is the function's
    ``AuditInputSnapshot`` argument, exactly as it is in v0.1.
    """
    if not audit_input_snapshot_identity_matches(audit_input):
        raise DetectorExecutionV2Error("audit input identity does not match its content")
    resolved = config or DetectorExecutionConfigV2()
    runs = tuple(
        DetectorRunV2(
            detector=detector,
            report=_run_detector(detector, audit_input, resolved),
        )
        for detector in resolved.selected_detectors
    )
    for run in runs:
        _validate_run(run)
    body = _execution_body(audit_input=audit_input, config=resolved, runs=runs)
    return DetectorExecutionV2.model_validate(
        {
            "detector_execution_id": stable_id(
                prefix="dexec2",
                namespace=DETECTOR_EXECUTION_V2_NAMESPACE,
                payload=body,
            ),
            **body,
        }
    )


def detector_execution_v2_identity_matches(execution: DetectorExecutionV2) -> bool:
    """Verify the v0.2 container and every unchanged v0.1 report/finding ID."""
    if canonical_sha256(execution.audit_input) != execution.audit_input_hash:
        return False
    for run in execution.runs:
        try:
            _validate_run(run)
        except DetectorExecutionV2Error:
            return False
    body = {
        name: getattr(execution, name)
        for name in DetectorExecutionV2.model_fields
        if name != "detector_execution_id"
    }
    expected = stable_id(
        prefix="dexec2",
        namespace=DETECTOR_EXECUTION_V2_NAMESPACE,
        payload=body,
    )
    return execution.detector_execution_id == expected


def detector_execution_findings(execution: DetectorExecutionV2) -> tuple[Finding, ...]:
    """Return every selected finding once in deterministic finding-id order."""
    return tuple(
        sorted(
            (finding for run in execution.runs for finding in run.report.findings),
            key=lambda finding: finding.finding_id,
        )
    )
