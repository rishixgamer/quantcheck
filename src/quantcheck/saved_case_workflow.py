"""The CLI's saved-stage ``inject`` / ``audit`` / ``evaluate`` workflow.

This module adds no scientific behavior of its own. Every step below is a
direct call into the exact function :mod:`quantcheck.benchmark_dispatch`
uses for a single-shot ``dispatch_benchmark_case``, called in the same order
over the same persisted evidence, so that a staged
``inject -> audit -> evaluate`` run over one :class:`BenchmarkCaseConfig`
produces byte-identical public and private artifacts to dispatching that case
directly. Two properties are load-bearing and covered by tests:

* ``audit`` never reads or constructs a manifest — it only ever reads the
  clean or corrupted snapshot ``inject`` already persisted, sanitizes it, and
  runs the manifest-blind detector tuple; and
* ``evaluate`` is the first stage that reads a manifest, and only after a
  finalized public :class:`AuditReport` already exists on disk.

A clean control has no manifest and therefore no ``evaluate`` stage: its
``audit`` stage is terminal, exactly as :func:`dispatch_benchmark_case`
computes its control score directly from the audit report without ever
touching a manifest.
"""

from __future__ import annotations

from dataclasses import dataclass

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.benchmark_contract import (
    PRIVATE_CASE_ARTIFACT_NAMES,
    PUBLIC_CASE_ARTIFACT_NAMES,
    public_case_directory,
    require_seed_execution_authorized,
)
from quantcheck.benchmark_dispatch import (
    clean_snapshot_for_case,
    combined_audit_report,
    fault_score,
    inject_for_case,
    replay_for_case,
    research_for_case,
    research_summary_for_case,
    run_all_detectors,
    score_for_case,
)
from quantcheck.benchmark_store import AtomicArtifactStore
from quantcheck.schemas import (
    AuditInputSnapshot,
    AuditReport,
    BenchmarkCaseConfig,
    BenchmarkCaseScore,
    BenchmarkDetectorConfigs,
    BenchmarkFaultProfile,
    BenchmarkResearchSummary,
    CanonicalModel,
    DatasetSnapshot,
    DuplicateManifest,
    FaultManifest,
    RevisionOverwriteManifest,
    UnitDriftManifest,
)

__all__ = [
    "AuditResult",
    "EvaluateResult",
    "InjectResult",
    "SavedStageError",
    "audit_case",
    "audit_snapshot",
    "evaluate_case",
    "inject_case",
    "private_artifact_path",
    "public_artifact_path",
]


class SavedStageError(ValueError):
    """Raised when a saved-stage command's required prior artifact is absent or invalid."""


#: The exact private manifest model for each fault family, needed only to
#: validate stored bytes back into the correct concrete type before handing
#: them to that family's own scoring/replay/research functions.
_MANIFEST_MODELS: dict[BenchmarkFaultProfile, type[CanonicalModel]] = {
    "lookahead_timestamp": FaultManifest,
    "unit_drift": UnitDriftManifest,
    "duplicate_observation": DuplicateManifest,
    "revision_overwrite": RevisionOverwriteManifest,
}


def public_artifact_path(case_id: str, artifact: str) -> str:
    """The public-store-relative path for one saved-stage case artifact.

    Uses the same ``cases/<id>/<name>`` layout as the benchmark runner, so a
    saved-stage output tree and a benchmark run's output tree are laid out
    identically.
    """
    return f"{public_case_directory(case_id)}/{PUBLIC_CASE_ARTIFACT_NAMES[artifact]}"


def private_artifact_path(case_id: str, artifact: str) -> str:
    """The private-store-relative path for one saved-stage case artifact."""
    return f"cases/{case_id}/{PRIVATE_CASE_ARTIFACT_NAMES[artifact]}"


@dataclass(frozen=True, slots=True)
class InjectResult:
    """What the ``inject`` stage persisted."""

    case: BenchmarkCaseConfig
    clean_snapshot: DatasetSnapshot
    corrupted_snapshot: DatasetSnapshot | None
    manifest: CanonicalModel | None


def inject_case(
    case: BenchmarkCaseConfig,
    *,
    public: AtomicArtifactStore,
    private: AtomicArtifactStore,
) -> InjectResult:
    """Run only the injection stage of one expanded case and persist it.

    The public case configuration and the private clean snapshot are always
    written. A ``clean_control`` case injects nothing and stops there; a
    fault case additionally writes the private corrupted snapshot and the
    private manifest. Nothing here runs detection, scoring, or replay.

    A reserved final seed is refused unless the release path authorized it.
    """
    require_seed_execution_authorized(case.seed)
    clean, source_records = clean_snapshot_for_case(case)
    public.write_immutable(public_artifact_path(case.benchmark_case_id, "case_config"), case)
    private.write_immutable(private_artifact_path(case.benchmark_case_id, "clean_snapshot"), clean)

    if case.case_kind == "clean_control":
        return InjectResult(case=case, clean_snapshot=clean, corrupted_snapshot=None, manifest=None)

    corrupted, manifest = inject_for_case(case, clean, source_records)
    private.write_immutable(
        private_artifact_path(case.benchmark_case_id, "corrupted_snapshot"), corrupted
    )
    private.write_immutable(private_artifact_path(case.benchmark_case_id, "manifest"), manifest)
    return InjectResult(
        case=case, clean_snapshot=clean, corrupted_snapshot=corrupted, manifest=manifest
    )


@dataclass(frozen=True, slots=True)
class AuditResult:
    """What the ``audit`` stage persisted."""

    audit_input: AuditInputSnapshot
    audit_report: AuditReport


def audit_snapshot(
    snapshot: DatasetSnapshot,
    *,
    detector_configs: BenchmarkDetectorConfigs,
    fault_profile: BenchmarkFaultProfile,
) -> tuple[AuditInputSnapshot, AuditReport]:
    """The manifest-blind core shared by every audit entry point.

    Sanitizes the snapshot exactly once, runs every detector over the result,
    and finalizes one combined report. There is no parameter through which a
    manifest, a clean value, a seed, or a target could reach this function.
    """
    audit_input = sanitize_for_audit(snapshot)
    findings = run_all_detectors(audit_input, detector_configs)
    report = combined_audit_report(audit_input, findings, fault_profile=fault_profile)
    return audit_input, report


def audit_case(
    case: BenchmarkCaseConfig,
    *,
    public: AtomicArtifactStore,
    private: AtomicArtifactStore,
) -> AuditResult:
    """Continue a saved ``inject`` stage: sanitize, detect, and finalize.

    Reads only the clean snapshot (for a clean control) or the corrupted
    snapshot (for a fault case) that ``inject_case`` already persisted. Never
    reads the manifest, even though it may already be sitting on disk.

    A reserved final seed is refused unless the release path authorized it.
    """
    require_seed_execution_authorized(case.seed)
    source_kind = "clean_snapshot" if case.case_kind == "clean_control" else "corrupted_snapshot"
    source_path = private_artifact_path(case.benchmark_case_id, source_kind)
    if not private.exists(source_path):
        raise SavedStageError(f"missing injected input for audit: {source_path}")
    snapshot = DatasetSnapshot.model_validate(private.read_canonical(source_path))

    audit_input, report = audit_snapshot(
        snapshot,
        detector_configs=case.detector_configs,
        fault_profile=case.fault_profile,
    )
    public.write_immutable(public_artifact_path(case.benchmark_case_id, "audit_input"), audit_input)
    public.write_immutable(public_artifact_path(case.benchmark_case_id, "audit_report"), report)
    return AuditResult(audit_input=audit_input, audit_report=report)


@dataclass(frozen=True, slots=True)
class EvaluateResult:
    """What the ``evaluate`` stage persisted."""

    score: BenchmarkCaseScore
    repaired_snapshot: DatasetSnapshot
    research_impact: CanonicalModel
    research_summary: BenchmarkResearchSummary


def evaluate_case(
    case: BenchmarkCaseConfig,
    *,
    public: AtomicArtifactStore,
    private: AtomicArtifactStore,
) -> EvaluateResult:
    """Score, replay, and compare research impact for one saved fault case.

    Requires a finalized public audit report and the private manifest,
    clean snapshot, and corrupted snapshot that ``inject_case``/``audit_case``
    already persisted. A clean control has no manifest and is rejected here
    by design: its terminal artifact is the audit stage's own score.

    A reserved final seed is refused unless the release path authorized it.
    """
    require_seed_execution_authorized(case.seed)
    if case.case_kind == "clean_control":
        raise SavedStageError(
            "evaluate does not apply to a clean control; it has no manifest to score against"
        )

    report_path = public_artifact_path(case.benchmark_case_id, "audit_report")
    if not public.exists(report_path):
        raise SavedStageError(f"missing finalized audit report for evaluate: {report_path}")
    report = AuditReport.model_validate(public.read_canonical(report_path))

    manifest_path = private_artifact_path(case.benchmark_case_id, "manifest")
    clean_path = private_artifact_path(case.benchmark_case_id, "clean_snapshot")
    corrupted_path = private_artifact_path(case.benchmark_case_id, "corrupted_snapshot")
    for path in (manifest_path, clean_path, corrupted_path):
        if not private.exists(path):
            raise SavedStageError(f"missing private evidence for evaluate: {path}")

    manifest_model = _MANIFEST_MODELS[case.fault_profile]
    manifest = manifest_model.model_validate(private.read_canonical(manifest_path))
    clean = DatasetSnapshot.model_validate(private.read_canonical(clean_path))
    corrupted = DatasetSnapshot.model_validate(private.read_canonical(corrupted_path))
    _, source_records = clean_snapshot_for_case(case)

    score_report = score_for_case(case, report, manifest)
    repaired = replay_for_case(case, corrupted, manifest)
    impact = research_for_case(case, clean, corrupted, repaired, manifest, source_records)
    score = fault_score(case, score_report)
    summary = research_summary_for_case(case, impact)

    private.write_immutable(
        private_artifact_path(case.benchmark_case_id, "repaired_snapshot"), repaired
    )
    private.write_immutable(
        private_artifact_path(case.benchmark_case_id, "research_impact"), impact
    )
    public.write_immutable(public_artifact_path(case.benchmark_case_id, "score"), score)
    public.write_immutable(
        public_artifact_path(case.benchmark_case_id, "research_summary"), summary
    )

    return EvaluateResult(
        score=score,
        repaired_snapshot=repaired,
        research_impact=impact,
        research_summary=summary,
    )
