"""Sequential, resumable, failure-isolating benchmark orchestration.

The runner owns four things and nothing else: the public/private artifact tree,
the structured failure taxonomy, safe resume, and the order cases execute in.
All science lives in the four completed fault families, reached only through
:mod:`quantcheck.benchmark_dispatch`.

Two rules shape everything here:

* the terminal success status is written **last**, after every required
  artifact is durably persisted; and
* one case's failure never prevents another case from finishing, and never
  removes the failed case from the matrix or the status totals.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from quantcheck.benchmark_aggregate import aggregate_from_public_artifacts
from quantcheck.benchmark_contract import (
    BENCHMARK_SPEC_VERSION,
    PRIVATE_CASE_ARTIFACT_NAMES,
    PRIVATE_ROOT_NAME,
    PUBLIC_CASE_ARTIFACT_NAMES,
    PUBLIC_ROOT_NAME,
    REQUIRED_PUBLIC_CASE_ARTIFACTS,
    BenchmarkSeedClassError,
    public_case_directory,
    redacted_failure_message,
)
from quantcheck.benchmark_dispatch import (
    BenchmarkCaseArtifacts,
    BenchmarkDispatchError,
    dispatch_benchmark_case,
)
from quantcheck.benchmark_expansion import (
    BenchmarkConfigurationError,
    expand_benchmark_cases,
)
from quantcheck.benchmark_fixtures import UnknownBenchmarkFixtureError
from quantcheck.benchmark_store import (
    ArtifactIntegrityError,
    ArtifactPersistenceError,
    AtomicArtifactStore,
)
from quantcheck.duplicate_detection import DuplicateDetectionError
from quantcheck.duplicate_injection import (
    DuplicateInjectionError,
    NoEligibleDuplicateTargetsError,
)
from quantcheck.duplicate_manifest import DuplicateManifestIntegrityError
from quantcheck.duplicate_replay import DuplicateReplayError
from quantcheck.duplicate_research import DuplicateResearchError
from quantcheck.duplicate_scoring import DuplicateScoringError
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.json_types import CanonicalizationError
from quantcheck.lookahead_detection import LookAheadDetectionError
from quantcheck.lookahead_injection import (
    LookAheadInjectionError,
    NoEligibleLookAheadTargetsError,
)
from quantcheck.lookahead_manifest import LookAheadManifestIntegrityError
from quantcheck.lookahead_replay import LookAheadReplayError
from quantcheck.lookahead_research import LookAheadResearchError
from quantcheck.lookahead_scoring import LookAheadScoringError
from quantcheck.point_in_time import AmbiguousRevisionHistoryError
from quantcheck.revision_overwrite_detection import RevisionOverwriteDetectionError
from quantcheck.revision_overwrite_injection import (
    NoEligibleRevisionOverwriteTargetsError,
    RevisionOverwriteInjectionError,
)
from quantcheck.revision_overwrite_manifest import RevisionOverwriteManifestIntegrityError
from quantcheck.revision_overwrite_replay import RevisionOverwriteReplayError
from quantcheck.revision_overwrite_research import RevisionOverwriteResearchError
from quantcheck.revision_overwrite_scoring import RevisionOverwriteScoringError
from quantcheck.schemas import (
    BenchmarkAggregateReport,
    BenchmarkArtifactReference,
    BenchmarkCaseConfig,
    BenchmarkCaseMatrix,
    BenchmarkCaseStatus,
    BenchmarkConfig,
    BenchmarkFailureCategory,
    BenchmarkFailureStage,
    BenchmarkPrivateDiagnostics,
    BenchmarkPublicFailure,
    BenchmarkPublicIndex,
    BenchmarkRuntimeMetadata,
    RuntimeMetadata,
)
from quantcheck.serialization import canonical_json_bytes
from quantcheck.unit_drift_detection import UnitDriftDetectionError
from quantcheck.unit_drift_injection import (
    NoEligibleUnitDriftTargetsError,
    UnitDriftInjectionError,
)
from quantcheck.unit_drift_manifest import UnitDriftManifestIntegrityError
from quantcheck.unit_drift_replay import UnitDriftReplayError
from quantcheck.unit_drift_research import UnitDriftResearchError
from quantcheck.unit_drift_scoring import UnitDriftScoringError

__all__ = [
    "BENCHMARK_AGGREGATE_PATH",
    "BENCHMARK_CONFIG_PATH",
    "BENCHMARK_INDEX_PATH",
    "BENCHMARK_MATRIX_PATH",
    "BENCHMARK_RUNTIME_PATH",
    "BenchmarkRunResult",
    "classify_case_exception",
    "run_benchmark",
]

BENCHMARK_CONFIG_PATH = "benchmark_config.json"
BENCHMARK_MATRIX_PATH = "case_matrix.json"
BENCHMARK_RUNTIME_PATH = "runtime_metadata.json"
BENCHMARK_AGGREGATE_PATH = "aggregate_report.json"
BENCHMARK_INDEX_PATH = "index.json"

#: Ordered exception classification. The first matching entry wins, so the
#: narrow "no eligible target" subclasses must precede their injection bases.
#: Each entry fixes a stage, a category, and a stable normalized code; the
#: public message is a constant per category, so no exception text, financial
#: value, or local path can reach a public artifact through formatting.
_FailureRule = tuple[type[BaseException], BenchmarkFailureStage, BenchmarkFailureCategory, str]

_FAILURE_TABLE: tuple[_FailureRule, ...] = (
    (UnknownBenchmarkFixtureError, "fixture_load", "configuration", "unknown_fixture"),
    (BenchmarkConfigurationError, "expansion", "configuration", "invalid_configuration"),
    (BenchmarkSeedClassError, "expansion", "configuration", "unauthorized_seed"),
    (BenchmarkDispatchError, "dispatch", "configuration", "unsupported_fault_profile"),
    (NoEligibleLookAheadTargetsError, "injection", "no_eligible_targets", "no_eligible_targets"),
    (NoEligibleUnitDriftTargetsError, "injection", "no_eligible_targets", "no_eligible_targets"),
    (NoEligibleDuplicateTargetsError, "injection", "no_eligible_targets", "no_eligible_targets"),
    (
        NoEligibleRevisionOverwriteTargetsError,
        "injection",
        "no_eligible_targets",
        "no_eligible_targets",
    ),
    (LookAheadInjectionError, "injection", "integrity", "injection_rejected"),
    (UnitDriftInjectionError, "injection", "integrity", "injection_rejected"),
    (DuplicateInjectionError, "injection", "integrity", "injection_rejected"),
    (RevisionOverwriteInjectionError, "injection", "integrity", "injection_rejected"),
    (AmbiguousRevisionHistoryError, "audit_sanitization", "integrity", "ambiguous_revision"),
    (LookAheadDetectionError, "detection", "integrity", "detection_rejected"),
    (UnitDriftDetectionError, "detection", "integrity", "detection_rejected"),
    (DuplicateDetectionError, "detection", "integrity", "detection_rejected"),
    (RevisionOverwriteDetectionError, "detection", "integrity", "detection_rejected"),
    (LookAheadManifestIntegrityError, "scoring", "integrity", "manifest_integrity"),
    (UnitDriftManifestIntegrityError, "scoring", "integrity", "manifest_integrity"),
    (DuplicateManifestIntegrityError, "scoring", "integrity", "manifest_integrity"),
    (RevisionOverwriteManifestIntegrityError, "scoring", "integrity", "manifest_integrity"),
    (LookAheadScoringError, "scoring", "integrity", "scoring_rejected"),
    (UnitDriftScoringError, "scoring", "integrity", "scoring_rejected"),
    (DuplicateScoringError, "scoring", "integrity", "scoring_rejected"),
    (RevisionOverwriteScoringError, "scoring", "integrity", "scoring_rejected"),
    (LookAheadReplayError, "repair", "integrity", "replay_rejected"),
    (UnitDriftReplayError, "repair", "integrity", "replay_rejected"),
    (DuplicateReplayError, "repair", "integrity", "replay_rejected"),
    (RevisionOverwriteReplayError, "repair", "integrity", "replay_rejected"),
    (LookAheadResearchError, "research", "integrity", "research_rejected"),
    (UnitDriftResearchError, "research", "integrity", "research_rejected"),
    (DuplicateResearchError, "research", "integrity", "research_rejected"),
    (RevisionOverwriteResearchError, "research", "integrity", "research_rejected"),
    (ArtifactIntegrityError, "persistence", "integrity", "artifact_conflict"),
    (ArtifactPersistenceError, "persistence", "persistence", "persistence_failed"),
    (CanonicalizationError, "serialization", "integrity", "canonicalization_rejected"),
    (ValidationError, "serialization", "integrity", "schema_rejected"),
    (OSError, "persistence", "persistence", "persistence_failed"),
)


def classify_case_exception(
    exc: BaseException,
) -> tuple[BenchmarkFailureStage, BenchmarkFailureCategory, str]:
    """Map one exception onto its stable public stage, category, and code.

    Anything unrecognized becomes an explicit ``internal`` failure rather than
    a silent one: it is still recorded, still surfaced as a failed case, and
    still counted, but it never claims to be a known condition.
    """
    for exception_type, stage, category, code in _FAILURE_TABLE:
        if isinstance(exc, exception_type):
            return stage, category, code
    return "dispatch", "internal", "unexpected_internal_error"


@dataclass(frozen=True, slots=True)
class BenchmarkRunResult:
    """What one benchmark run produced, in memory."""

    config: BenchmarkConfig
    matrix: BenchmarkCaseMatrix
    statuses: tuple[BenchmarkCaseStatus, ...]
    aggregate: BenchmarkAggregateReport
    reused_case_ids: tuple[str, ...]
    dispatched_case_ids: tuple[str, ...]


def _public_case_path(case_id: str, artifact: str) -> str:
    return f"{public_case_directory(case_id)}/{PUBLIC_CASE_ARTIFACT_NAMES[artifact]}"


def _private_case_path(case_id: str, artifact: str) -> str:
    return f"cases/{case_id}/{PRIVATE_CASE_ARTIFACT_NAMES[artifact]}"


def _reference(kind: str, relative_path: str, payload: bytes) -> BenchmarkArtifactReference:
    return BenchmarkArtifactReference(
        kind=kind,
        relative_path=relative_path,
        content_hash=sha256_hex_of_bytes(payload),
    )


def _persist_private(
    private: AtomicArtifactStore,
    artifacts: BenchmarkCaseArtifacts,
) -> None:
    """Persist hidden truth, then a private index that can verify it later.

    The private index is written into the private tree only. No public
    artifact, and in particular no public index entry, ever names it.
    """
    case_id = artifacts.case.benchmark_case_id
    entries: list[dict[str, str]] = []
    private_payloads: list[tuple[str, object]] = [
        ("clean_snapshot", artifacts.clean_snapshot),
        ("corrupted_snapshot", artifacts.corrupted_snapshot),
        ("manifest", artifacts.manifest),
        ("repaired_snapshot", artifacts.repaired_snapshot),
        ("research_impact", artifacts.research_impact),
    ]
    for kind, artifact in private_payloads:
        if artifact is None:
            continue
        relative = _private_case_path(case_id, kind)
        payload = private.write_immutable(relative, artifact)
        entries.append(
            {"kind": kind, "relative_path": relative, "content_hash": sha256_hex_of_bytes(payload)}
        )
    private.write_immutable(
        _private_case_path(case_id, "private_index"),
        {
            "benchmark_case_id": case_id,
            "spec_version": BENCHMARK_SPEC_VERSION,
            "entries": tuple(entries),
        },
    )


def _persist_public_case(
    public: AtomicArtifactStore,
    artifacts: BenchmarkCaseArtifacts,
) -> tuple[BenchmarkArtifactReference, ...]:
    case = artifacts.case
    case_id = case.benchmark_case_id
    written: list[BenchmarkArtifactReference] = []
    approved: list[tuple[str, object]] = [
        ("case_config", case),
        ("audit_input", artifacts.audit_input),
        ("audit_report", artifacts.audit_report),
        ("score", artifacts.score),
    ]
    if artifacts.research_summary is not None:
        approved.append(("research_summary", artifacts.research_summary))
    for kind, artifact in approved:
        relative = _public_case_path(case_id, kind)
        payload = public.write_immutable(relative, artifact)
        written.append(_reference(kind, relative, payload))
    return tuple(written)


def _existing_status(public: AtomicArtifactStore, case_id: str) -> BenchmarkCaseStatus | None:
    relative = _public_case_path(case_id, "status")
    if not public.exists(relative):
        return None
    try:
        return BenchmarkCaseStatus.model_validate(public.read_canonical(relative))
    except (ValidationError, CanonicalizationError, ArtifactPersistenceError):
        return None


def _write_status(public: AtomicArtifactStore, status: BenchmarkCaseStatus) -> None:
    """Write the terminal status last, never over a prior *successful* one."""
    relative = _public_case_path(status.benchmark_case_id, "status")
    prior = _existing_status(public, status.benchmark_case_id)
    if prior is not None and prior.status == "succeeded":
        if canonical_json_bytes(prior) == canonical_json_bytes(status):
            return
        raise ArtifactIntegrityError(
            f"case {status.benchmark_case_id} already has a conflicting successful status"
        )
    public.write_run_artifact(relative, status)


def _validated_prior_success(
    public: AtomicArtifactStore,
    private: AtomicArtifactStore,
    case: BenchmarkCaseConfig,
) -> BenchmarkCaseStatus | None:
    """Return a reusable prior success, or ``None`` if there is nothing to reuse.

    A file that merely exists proves nothing. Everything the status claims is
    revalidated: the status schema, the case identity, each referenced path,
    each content hash, the score's schema and linkage, the research summary,
    and the approved private artifacts.

    Raises:
        ArtifactIntegrityError: when the status claims success but the evidence
            does not support it. The conflicting artifacts are left untouched.
    """
    status = _existing_status(public, case.benchmark_case_id)
    if status is None or status.status != "succeeded":
        return None

    if (
        status.benchmark_id != case.benchmark_id
        or status.spec_version != case.spec_version
        or status.case_kind != case.case_kind
        or status.fault_profile != case.fault_profile
        or status.severity != case.severity
        or status.seed != case.seed
        or status.seed_class != case.seed_class
    ):
        raise ArtifactIntegrityError(
            f"stored status for {case.benchmark_case_id} describes a different case"
        )

    referenced = {reference.kind: reference for reference in status.artifacts}
    required = list(REQUIRED_PUBLIC_CASE_ARTIFACTS)
    if case.case_kind == "fault":
        required.append("research_summary")
    missing = [kind for kind in required if kind not in referenced]
    if missing:
        raise ArtifactIntegrityError(
            f"successful status for {case.benchmark_case_id} is missing {sorted(missing)}"
        )

    for reference in status.artifacts:
        expected_path = _public_case_path(case.benchmark_case_id, reference.kind)
        if reference.relative_path != expected_path:
            raise ArtifactIntegrityError(
                f"artifact reference {reference.relative_path} is not this case's own path"
            )
        if not public.exists(reference.relative_path):
            raise ArtifactIntegrityError(f"referenced artifact {reference.relative_path} is absent")
        payload = public.read_bytes(reference.relative_path)
        if sha256_hex_of_bytes(payload) != reference.content_hash:
            raise ArtifactIntegrityError(
                f"referenced artifact {reference.relative_path} does not match its content hash"
            )

    # Cross-artifact identity: the stored case configuration must be byte-for-
    # byte the case we are about to run, not merely a case with the same id.
    stored_case = public.read_bytes(referenced["case_config"].relative_path)
    if stored_case != canonical_json_bytes(case):
        raise ArtifactIntegrityError(
            f"stored case configuration for {case.benchmark_case_id} differs from the expansion"
        )

    _validate_prior_public_bodies(public, case, referenced)
    if case.case_kind == "fault":
        _validate_prior_private(private, case)
    return status


def _validate_prior_public_bodies(
    public: AtomicArtifactStore,
    case: BenchmarkCaseConfig,
    referenced: dict[str, BenchmarkArtifactReference],
) -> None:
    from quantcheck.schemas import (
        AuditInputSnapshot,
        AuditReport,
        BenchmarkCaseScore,
        BenchmarkResearchSummary,
    )

    try:
        audit_input = AuditInputSnapshot.model_validate(
            public.read_canonical(referenced["audit_input"].relative_path)
        )
        audit_report = AuditReport.model_validate(
            public.read_canonical(referenced["audit_report"].relative_path)
        )
        score = BenchmarkCaseScore.model_validate(
            public.read_canonical(referenced["score"].relative_path)
        )
    except (ValidationError, CanonicalizationError) as exc:
        raise ArtifactIntegrityError(
            f"stored public artifacts for {case.benchmark_case_id} do not validate"
        ) from exc

    if audit_report.audit_input_id != audit_input.audit_input_id:
        raise ArtifactIntegrityError("stored audit report does not describe its stored audit input")
    if score.benchmark_case_id != case.benchmark_case_id or score.benchmark_id != case.benchmark_id:
        raise ArtifactIntegrityError("stored score belongs to a different case")
    if score.case_kind != case.case_kind or score.fault_profile != case.fault_profile:
        raise ArtifactIntegrityError("stored score describes a different case shape")
    if score.score_report is not None and (
        score.score_report.audit_report_id != audit_report.audit_report_id
    ):
        raise ArtifactIntegrityError("stored score does not reference its stored audit report")

    if "research_summary" in referenced:
        try:
            summary = BenchmarkResearchSummary.model_validate(
                public.read_canonical(referenced["research_summary"].relative_path)
            )
        except (ValidationError, CanonicalizationError) as exc:
            raise ArtifactIntegrityError("stored research summary does not validate") from exc
        if summary.benchmark_case_id != case.benchmark_case_id:
            raise ArtifactIntegrityError("stored research summary belongs to a different case")


def _validate_prior_private(private: AtomicArtifactStore, case: BenchmarkCaseConfig) -> None:
    index_path = _private_case_path(case.benchmark_case_id, "private_index")
    if not private.exists(index_path):
        raise ArtifactIntegrityError(
            f"successful fault case {case.benchmark_case_id} has no private index"
        )
    try:
        index = private.read_canonical(index_path)
    except (CanonicalizationError, ArtifactPersistenceError) as exc:
        raise ArtifactIntegrityError("stored private index is not canonical") from exc
    if not isinstance(index, dict) or not isinstance(index.get("entries"), list):
        raise ArtifactIntegrityError("stored private index has an unexpected shape")
    required = {"clean_snapshot", "corrupted_snapshot", "manifest", "repaired_snapshot"}
    seen: set[str] = set()
    for entry in index["entries"]:
        if not isinstance(entry, dict):
            raise ArtifactIntegrityError("stored private index has an unexpected entry")
        relative = entry.get("relative_path")
        expected_hash = entry.get("content_hash")
        kind = entry.get("kind")
        if not isinstance(relative, str) or not isinstance(expected_hash, str):
            raise ArtifactIntegrityError("stored private index entry is malformed")
        if not private.exists(relative):
            raise ArtifactIntegrityError(f"private artifact {relative} is absent")
        if sha256_hex_of_bytes(private.read_bytes(relative)) != expected_hash:
            raise ArtifactIntegrityError(f"private artifact {relative} does not match its hash")
        if isinstance(kind, str):
            seen.add(kind)
    if not required.issubset(seen):
        raise ArtifactIntegrityError(f"private evidence for {case.benchmark_case_id} is incomplete")


def _failure_status(
    case: BenchmarkCaseConfig,
    stage: BenchmarkFailureStage,
    category: BenchmarkFailureCategory,
    code: str,
) -> BenchmarkCaseStatus:
    return BenchmarkCaseStatus(
        benchmark_case_id=case.benchmark_case_id,
        benchmark_id=case.benchmark_id,
        status="failed",
        case_kind=case.case_kind,
        fault_profile=case.fault_profile,
        severity=case.severity,
        seed=case.seed,
        seed_class=case.seed_class,
        artifacts=(),
        failure=BenchmarkPublicFailure(
            stage=stage,
            category=category,
            error_code=code,
            message=redacted_failure_message(category),
        ),
    )


def _record_failure(
    public: AtomicArtifactStore,
    private: AtomicArtifactStore,
    case: BenchmarkCaseConfig,
    exc: BaseException,
) -> BenchmarkCaseStatus:
    stage, category, code = classify_case_exception(exc)
    diagnostics = BenchmarkPrivateDiagnostics(
        benchmark_case_id=case.benchmark_case_id,
        stage=stage,
        category=category,
        error_code=code,
        exception_class=type(exc).__name__,
        # The message is kept private and stripped of newlines so a multi-line
        # exception cannot smuggle structure into a diagnostics file. No stack
        # trace is stored: it is nondeterministic and adds nothing stable.
        exception_message=" ".join(str(exc).split()) or type(exc).__name__,
    )
    status = _failure_status(case, stage, category, code)
    try:
        private.write_run_artifact(
            _private_case_path(case.benchmark_case_id, "diagnostics"), diagnostics
        )
        _write_status(public, status)
    except (ArtifactIntegrityError, ArtifactPersistenceError, OSError):
        # Recording a failure must never itself abort the run; the case still
        # ends up incomplete in aggregation, which is the honest outcome.
        return status
    return status


def _success_status(
    case: BenchmarkCaseConfig,
    references: tuple[BenchmarkArtifactReference, ...],
) -> BenchmarkCaseStatus:
    return BenchmarkCaseStatus(
        benchmark_case_id=case.benchmark_case_id,
        benchmark_id=case.benchmark_id,
        status="succeeded",
        case_kind=case.case_kind,
        fault_profile=case.fault_profile,
        severity=case.severity,
        seed=case.seed,
        seed_class=case.seed_class,
        artifacts=references,
        failure=None,
    )


def _public_index(
    benchmark_id: str,
    entries: tuple[BenchmarkArtifactReference, ...],
) -> BenchmarkPublicIndex:
    return BenchmarkPublicIndex(
        benchmark_id=benchmark_id,
        spec_version=BENCHMARK_SPEC_VERSION,
        entries=entries,
    )


def run_benchmark(
    config: BenchmarkConfig,
    *,
    output_root: Path,
    runtime: RuntimeMetadata,
    resume: bool = True,
) -> BenchmarkRunResult:
    """Execute one benchmark into an output tree and aggregate the result.

    ``output_root`` is a runtime fact: it never enters a benchmark, case, or
    aggregate identity, and two runs into different roots produce identical
    logical bytes. ``runtime`` is supplied by the caller rather than read from
    the clock here, so a determinism test can hold it fixed.
    """
    root = Path(output_root)
    public = AtomicArtifactStore(root / PUBLIC_ROOT_NAME)
    private = AtomicArtifactStore(root / PRIVATE_ROOT_NAME)

    matrix = expand_benchmark_cases(config)
    config_payload = public.write_immutable(BENCHMARK_CONFIG_PATH, config)
    matrix_payload = public.write_immutable(BENCHMARK_MATRIX_PATH, matrix)
    runtime_metadata = BenchmarkRuntimeMetadata(
        benchmark_id=config.benchmark_id,
        spec_version=BENCHMARK_SPEC_VERSION,
        runtime=runtime,
        case_count=matrix.case_count,
    )
    runtime_payload = public.write_run_artifact(BENCHMARK_RUNTIME_PATH, runtime_metadata)

    statuses: list[BenchmarkCaseStatus] = []
    reused: list[str] = []
    dispatched: list[str] = []

    for case in matrix.cases:
        if resume:
            try:
                prior = _validated_prior_success(public, private, case)
            except ArtifactIntegrityError as exc:
                # An invalid prior success is never overwritten and never
                # relabeled a fresh success. The conflicting artifacts stay on
                # disk; aggregation independently downgrades the case.
                statuses.append(
                    _failure_status(case, "persistence", "integrity", "prior_success_invalid")
                )
                _record_private_only_diagnostics(private, case, exc)
                continue
            if prior is not None:
                statuses.append(prior)
                reused.append(case.benchmark_case_id)
                continue

        try:
            artifacts = dispatch_benchmark_case(case)
            _persist_private(private, artifacts)
            references = _persist_public_case(public, artifacts)
            status = _success_status(case, references)
            _write_status(public, status)
        except Exception as exc:  # noqa: BLE001 - every case failure is recorded, never swallowed
            statuses.append(_record_failure(public, private, case, exc))
            continue
        statuses.append(status)
        dispatched.append(case.benchmark_case_id)

    aggregate = aggregate_from_public_artifacts(public)
    aggregate_payload = public.write_run_artifact(BENCHMARK_AGGREGATE_PATH, aggregate)

    entries: list[BenchmarkArtifactReference] = [
        _reference("benchmark_config", BENCHMARK_CONFIG_PATH, config_payload),
        _reference("case_matrix", BENCHMARK_MATRIX_PATH, matrix_payload),
        _reference("runtime_metadata", BENCHMARK_RUNTIME_PATH, runtime_payload),
        _reference("aggregate_report", BENCHMARK_AGGREGATE_PATH, aggregate_payload),
    ]
    for status in statuses:
        entries.extend(status.artifacts)
        status_path = _public_case_path(status.benchmark_case_id, "status")
        if public.exists(status_path):
            entries.append(_reference("status", status_path, public.read_bytes(status_path)))
    public.write_run_artifact(
        BENCHMARK_INDEX_PATH, _public_index(config.benchmark_id, tuple(entries))
    )

    return BenchmarkRunResult(
        config=config,
        matrix=matrix,
        statuses=tuple(statuses),
        aggregate=aggregate,
        reused_case_ids=tuple(reused),
        dispatched_case_ids=tuple(dispatched),
    )


def _record_private_only_diagnostics(
    private: AtomicArtifactStore,
    case: BenchmarkCaseConfig,
    exc: BaseException,
) -> None:
    stage, category, code = classify_case_exception(exc)
    diagnostics = BenchmarkPrivateDiagnostics(
        benchmark_case_id=case.benchmark_case_id,
        stage=stage,
        category=category,
        error_code=code,
        exception_class=type(exc).__name__,
        exception_message=" ".join(str(exc).split()) or type(exc).__name__,
    )
    try:
        private.write_run_artifact(
            _private_case_path(case.benchmark_case_id, "diagnostics"), diagnostics
        )
    except (ArtifactPersistenceError, OSError):  # pragma: no cover - filesystem failure
        return
