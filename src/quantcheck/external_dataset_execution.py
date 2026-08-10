"""Bounded, resumable local execution for partitioned external audits.

The implementation deliberately uses files and local processes only.  Work is
content-addressed per complete-entity partition, so unchanged partitions can
be hash-verified and reused while changed partitions receive new identities.
Scientific execution remains the existing manifest-free
``audit_external_file`` path.
"""

from __future__ import annotations

import hashlib
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns

from pydantic import BaseModel, ValidationError

from quantcheck.benchmark_store import (
    ArtifactIntegrityError,
    ArtifactPersistenceError,
    AtomicArtifactStore,
)
from quantcheck.external_dataset_audit import (
    ExternalDatasetAuditError,
    audit_external_file,
    external_audit_report_identity_matches,
)
from quantcheck.external_dataset_contract import (
    ExternalDatasetAuditReportV2,
    ExternalDatasetValidationProfileV1,
)
from quantcheck.external_dataset_execution_contract import (
    SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS,
    ExternalAuditArtifactReferenceV1,
    ExternalAuditExecutionPlanV1,
    ExternalAuditFinalizationV1,
    ExternalAuditOperationalEventV1,
    ExternalAuditOperationalLogV1,
    ExternalAuditPartitionSpecV1,
    ExternalAuditPartitionStatusV1,
    ExternalAuditPrivatePartitionSummaryV1,
    ExternalAuditRunFailureV1,
    build_external_audit_finalization,
    external_audit_partition_identity_matches,
    external_audit_plan_identity_matches,
)
from quantcheck.external_dataset_ingestion import ExternalDatasetValidationError
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.json_types import CanonicalizationError
from quantcheck.serialization import canonical_json_bytes

__all__ = [
    "ExternalAuditExecutionError",
    "ExternalAuditExecutionResult",
    "ExternalAuditPartitionInput",
    "logical_execution_artifact_paths",
    "run_external_audit_execution",
]

_HASH_CHUNK_SIZE = 1024 * 1024


class ExternalAuditExecutionError(ValueError):
    """Raised when a logical execution plan or saved success is invalid."""


@dataclass(frozen=True, slots=True)
class ExternalAuditPartitionInput:
    """Runtime path paired with one path-free logical partition specification."""

    path: Path
    partition: ExternalAuditPartitionSpecV1


@dataclass(frozen=True, slots=True)
class _PartitionJob:
    output_root: Path
    input: ExternalAuditPartitionInput
    plan: ExternalAuditExecutionPlanV1


@dataclass(frozen=True, slots=True)
class _PartitionOutcome:
    status: ExternalAuditPartitionStatusV1
    entity_ids: tuple[str, ...]
    runtime_ns: int


@dataclass(frozen=True, slots=True)
class ExternalAuditExecutionResult:
    """One finalized attempt plus non-logical execution telemetry."""

    plan: ExternalAuditExecutionPlanV1
    finalization: ExternalAuditFinalizationV1
    reused_partition_ids: tuple[str, ...]
    executed_partition_ids: tuple[str, ...]
    failed_partition_ids: tuple[str, ...]
    partition_runtime_ns: tuple[tuple[str, int], ...]


def _public_partition_directory(partition_id: str) -> str:
    return f"partitions/{partition_id}"


def _private_partition_directory(partition_id: str) -> str:
    return f"partitions/{partition_id}"


def _partition_public_path(partition_id: str, name: str) -> str:
    return f"{_public_partition_directory(partition_id)}/{name}.json"


def _partition_private_path(partition_id: str, name: str) -> str:
    return f"{_private_partition_directory(partition_id)}/{name}.json"


def _run_public_path(run_id: str, name: str) -> str:
    return f"runs/{run_id}/{name}.json"


def _file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            while block := handle.read(_HASH_CHUNK_SIZE):
                digest.update(block)
                size += len(block)
    except OSError as exc:
        raise ExternalAuditExecutionError("partition input is unavailable") from exc
    return digest.hexdigest(), size


def _validate_runtime_inputs(
    plan: ExternalAuditExecutionPlanV1,
    inputs: tuple[ExternalAuditPartitionInput, ...],
) -> tuple[ExternalAuditPartitionInput, ...]:
    if not external_audit_plan_identity_matches(plan):
        raise ExternalAuditExecutionError("execution plan identity mismatch")
    by_id: dict[str, ExternalAuditPartitionInput] = {}
    for item in inputs:
        partition_id = item.partition.partition_id
        if partition_id in by_id:
            raise ExternalAuditExecutionError("runtime inputs contain a duplicate partition")
        if not external_audit_partition_identity_matches(item.partition):
            raise ExternalAuditExecutionError("partition identity mismatch")
        by_id[partition_id] = item
    expected = {item.partition_id for item in plan.partitions}
    if set(by_id) != expected:
        raise ExternalAuditExecutionError("runtime inputs do not exactly cover the plan")
    ordered: list[ExternalAuditPartitionInput] = []
    for partition in plan.partitions:
        supplied = by_id[partition.partition_id]
        if canonical_json_bytes(supplied.partition) != canonical_json_bytes(partition):
            raise ExternalAuditExecutionError("runtime partition disagrees with the plan")
        ordered.append(supplied)
    return tuple(ordered)


def _reference(
    *,
    role: str,
    visibility: str,
    relative_path: str,
    payload: bytes,
) -> ExternalAuditArtifactReferenceV1:
    return ExternalAuditArtifactReferenceV1(
        role=role,  # type: ignore[arg-type]
        visibility=visibility,  # type: ignore[arg-type]
        relative_path=relative_path,
        content_hash=sha256_hex_of_bytes(payload),
        size_bytes=len(payload),
    )


def _read_model(store: AtomicArtifactStore, path: str, model: type[BaseModel]) -> BaseModel:
    try:
        return model.model_validate(store.read_canonical(path))
    except (ValidationError, CanonicalizationError, ArtifactPersistenceError) as exc:
        raise ExternalAuditExecutionError("saved artifact failed canonical validation") from exc


def _write_status(
    public: AtomicArtifactStore,
    status: ExternalAuditPartitionStatusV1,
) -> None:
    path = _partition_public_path(status.partition_id, "status")
    if public.exists(path):
        try:
            prior = ExternalAuditPartitionStatusV1.model_validate(public.read_canonical(path))
        except (ValidationError, CanonicalizationError, ArtifactPersistenceError) as exc:
            raise ExternalAuditExecutionError("prior terminal status is invalid") from exc
        if prior.status == "succeeded" and canonical_json_bytes(prior) != canonical_json_bytes(
            status
        ):
            raise ExternalAuditExecutionError("prior successful status conflicts with this run")
    public.write_run_artifact(path, status)


def _artifact_reference_by_role(
    status: ExternalAuditPartitionStatusV1,
) -> dict[str, ExternalAuditArtifactReferenceV1]:
    return {item.role: item for item in status.public_artifacts}


def _validated_prior_success(
    *,
    public: AtomicArtifactStore,
    private: AtomicArtifactStore,
    input: ExternalAuditPartitionInput,
) -> _PartitionOutcome | None:
    partition = input.partition
    status_path = _partition_public_path(partition.partition_id, "status")
    if not public.exists(status_path):
        return None
    try:
        status = ExternalAuditPartitionStatusV1.model_validate(public.read_canonical(status_path))
    except (ValidationError, CanonicalizationError, ArtifactPersistenceError) as exc:
        raise ExternalAuditExecutionError("prior terminal status is invalid") from exc
    if status.status == "failed":
        return None
    if (
        status.partition_id != partition.partition_id
        or status.partition_key != partition.partition_key
        or status.source_record_count != partition.expected_record_count
    ):
        raise ExternalAuditExecutionError("prior success describes a different partition")

    expected_paths = {
        "partition_spec": _partition_public_path(partition.partition_id, "partition_spec"),
        "validation_profile": _partition_public_path(partition.partition_id, "validation_profile"),
        "audit_report": _partition_public_path(partition.partition_id, "audit_report"),
    }
    references = _artifact_reference_by_role(status)
    if set(references) != set(expected_paths):
        raise ExternalAuditExecutionError("prior success is missing public evidence")
    for role, path in expected_paths.items():
        reference = references[role]
        if reference.relative_path != path or reference.visibility != "public":
            raise ExternalAuditExecutionError("prior success references an unexpected path")
        payload = public.read_bytes(path)
        if (
            len(payload) != reference.size_bytes
            or sha256_hex_of_bytes(payload) != reference.content_hash
        ):
            raise ExternalAuditExecutionError("prior public artifact hash mismatch")

    saved_partition = _read_model(
        public, expected_paths["partition_spec"], ExternalAuditPartitionSpecV1
    )
    if canonical_json_bytes(saved_partition) != canonical_json_bytes(partition):
        raise ExternalAuditExecutionError("saved partition specification drifted")
    profile = _read_model(
        public,
        expected_paths["validation_profile"],
        ExternalDatasetValidationProfileV1,
    )
    report = _read_model(
        public,
        expected_paths["audit_report"],
        ExternalDatasetAuditReportV2,
    )
    assert isinstance(profile, ExternalDatasetValidationProfileV1)
    assert isinstance(report, ExternalDatasetAuditReportV2)
    if not external_audit_report_identity_matches(report):
        raise ExternalAuditExecutionError("saved audit report identity mismatch")
    if (
        profile.mapping_id != partition.mapping_id
        or profile.row_count != partition.expected_record_count
        or report.mapping_id != partition.mapping_id
        or report.policy_id != partition.policy_id
        or report.policy_content_hash != partition.policy_content_hash
        or report.as_of_date != partition.as_of_date
        or report.source_record_count != partition.expected_record_count
    ):
        raise ExternalAuditExecutionError("saved partition evidence link mismatch")

    actual_hash, actual_size = _file_digest(input.path)
    if (
        actual_hash != partition.source.expected_sha256
        or actual_size != partition.source.expected_size_bytes
    ):
        raise ExternalAuditExecutionError("partition input no longer matches its content pin")

    normalized_path = _partition_private_path(partition.partition_id, "normalized_dataset")
    normalized_payload = private.read_bytes(normalized_path)
    normalized_hash = sha256_hex_of_bytes(normalized_payload)
    if (
        normalized_hash != status.private_artifact_hash
        or normalized_hash != report.normalized_dataset_hash
    ):
        raise ExternalAuditExecutionError("prior private artifact hash mismatch")
    summary = _read_model(
        private,
        _partition_private_path(partition.partition_id, "partition_summary"),
        ExternalAuditPrivatePartitionSummaryV1,
    )
    assert isinstance(summary, ExternalAuditPrivatePartitionSummaryV1)
    if (
        summary.partition_id != partition.partition_id
        or summary.normalized_dataset_id != report.normalized_dataset_id
        or summary.normalized_dataset_hash != normalized_hash
    ):
        raise ExternalAuditExecutionError("prior private summary link mismatch")
    return _PartitionOutcome(status=status, entity_ids=summary.entity_ids, runtime_ns=0)


def _classify_partition_exception(exc: BaseException) -> str:
    if isinstance(exc, ExternalDatasetValidationError):
        return "validation_failed"
    if isinstance(exc, ExternalDatasetAuditError):
        return "audit_integrity_failed"
    if isinstance(exc, ArtifactIntegrityError):
        return "artifact_conflict"
    if isinstance(exc, ArtifactPersistenceError | OSError):
        return "persistence_failed"
    if isinstance(exc, ExternalAuditExecutionError):
        message = str(exc)
        if "record count" in message:
            return "partition_record_count_mismatch"
        if "unavailable" in message:
            return "input_unavailable"
        return "audit_integrity_failed"
    return "unexpected_internal_error"


def _failed_status(
    partition: ExternalAuditPartitionSpecV1,
    *,
    failure_code: str,
    references: tuple[ExternalAuditArtifactReferenceV1, ...] = (),
) -> ExternalAuditPartitionStatusV1:
    return ExternalAuditPartitionStatusV1(
        partition_id=partition.partition_id,
        partition_key=partition.partition_key,
        status="failed",
        failure_code=failure_code,  # type: ignore[arg-type]
        source_record_count=0,
        snapshot_record_count=0,
        finding_count=0,
        disposition="not_available",
        public_artifacts=references,
        private_artifact_hash=None,
    )


def _execute_partition_job(job: _PartitionJob) -> _PartitionOutcome:
    started = perf_counter_ns()
    partition = job.input.partition
    public = AtomicArtifactStore(job.output_root / "public")
    private = AtomicArtifactStore(job.output_root / "private")
    references: list[ExternalAuditArtifactReferenceV1] = []
    try:
        spec_path = _partition_public_path(partition.partition_id, "partition_spec")
        spec_payload = public.write_immutable(spec_path, partition)
        references.append(
            _reference(
                role="partition_spec",
                visibility="public",
                relative_path=spec_path,
                payload=spec_payload,
            )
        )
        artifacts = audit_external_file(
            job.input.path,
            mapping=job.plan.mapping,
            file_input=partition.source,
            as_of_date=job.plan.as_of_date,
            policy=job.plan.policy,
        )
        if (
            artifacts.validation_profile.row_count != partition.expected_record_count
            or artifacts.normalized_dataset.record_count != partition.expected_record_count
        ):
            raise ExternalAuditExecutionError("partition record count does not match its plan")

        profile_path = _partition_public_path(partition.partition_id, "validation_profile")
        profile_payload = public.write_immutable(profile_path, artifacts.validation_profile)
        references.append(
            _reference(
                role="validation_profile",
                visibility="public",
                relative_path=profile_path,
                payload=profile_payload,
            )
        )
        report_path = _partition_public_path(partition.partition_id, "audit_report")
        report_payload = public.write_immutable(report_path, artifacts.public_report)
        references.append(
            _reference(
                role="audit_report",
                visibility="public",
                relative_path=report_path,
                payload=report_payload,
            )
        )

        normalized_path = _partition_private_path(partition.partition_id, "normalized_dataset")
        normalized_payload = private.write_immutable(normalized_path, artifacts.normalized_dataset)
        normalized_hash = sha256_hex_of_bytes(normalized_payload)
        summary = ExternalAuditPrivatePartitionSummaryV1(
            partition_id=partition.partition_id,
            normalized_dataset_id=artifacts.normalized_dataset.normalized_dataset_id,
            normalized_dataset_hash=normalized_hash,
            entity_ids=tuple(
                sorted({record.entity_id for record in artifacts.normalized_dataset.records})
            ),
        )
        private.write_immutable(
            _partition_private_path(partition.partition_id, "partition_summary"),
            summary,
        )
        status = ExternalAuditPartitionStatusV1(
            partition_id=partition.partition_id,
            partition_key=partition.partition_key,
            status="succeeded",
            failure_code=None,
            source_record_count=artifacts.public_report.source_record_count,
            snapshot_record_count=artifacts.public_report.snapshot_record_count,
            finding_count=artifacts.public_report.finding_count,
            disposition=artifacts.public_report.disposition,
            public_artifacts=tuple(references),
            private_artifact_hash=normalized_hash,
        )
        _write_status(public, status)
        return _PartitionOutcome(
            status=status,
            entity_ids=summary.entity_ids,
            runtime_ns=perf_counter_ns() - started,
        )
    except Exception as exc:
        status = _failed_status(
            partition,
            failure_code=_classify_partition_exception(exc),
            references=tuple(references),
        )
        _write_status(public, status)
        return _PartitionOutcome(
            status=status,
            entity_ids=(),
            runtime_ns=perf_counter_ns() - started,
        )


def _worker_failure_outcome(
    *,
    public: AtomicArtifactStore,
    partition: ExternalAuditPartitionSpecV1,
) -> _PartitionOutcome:
    status = _failed_status(partition, failure_code="worker_failed")
    _write_status(public, status)
    return _PartitionOutcome(status=status, entity_ids=(), runtime_ns=0)


def _validate_entity_disjointness(outcomes: tuple[_PartitionOutcome, ...]) -> None:
    owners: dict[str, str] = {}
    for outcome in outcomes:
        if outcome.status.status != "succeeded":
            continue
        for entity_id in outcome.entity_ids:
            prior = owners.get(entity_id)
            if prior is not None and prior != outcome.status.partition_id:
                raise ExternalAuditExecutionError("partition entity overlap")
            owners[entity_id] = outcome.status.partition_id


def _operational_events(
    *,
    outcomes: tuple[_PartitionOutcome, ...],
    reused: set[str],
    run_failure: str | None = None,
) -> tuple[ExternalAuditOperationalEventV1, ...]:
    events: list[ExternalAuditOperationalEventV1] = []
    for outcome in sorted(outcomes, key=lambda item: item.status.partition_id):
        status = outcome.status
        if status.status == "failed":
            events.append(
                ExternalAuditOperationalEventV1(
                    partition_id=status.partition_id,
                    event="partition_failed",
                    failure_code=status.failure_code,
                )
            )
        else:
            events.append(
                ExternalAuditOperationalEventV1(
                    partition_id=status.partition_id,
                    event=(
                        "partition_reused"
                        if status.partition_id in reused
                        else "partition_executed"
                    ),
                )
            )
    events.append(
        ExternalAuditOperationalEventV1(
            partition_id=None,
            event="run_failed" if run_failure else "run_completed",
            failure_code=run_failure,  # type: ignore[arg-type]
        )
    )
    return tuple(events)


def _write_operations(
    *,
    root: Path,
    run_id: str,
    worker_count: int,
    outcomes: tuple[_PartitionOutcome, ...],
    reused: set[str],
    run_failure: str | None = None,
) -> None:
    operations = AtomicArtifactStore(root / "operations")
    log = ExternalAuditOperationalLogV1(
        run_id=run_id,
        worker_count=worker_count,
        events=_operational_events(outcomes=outcomes, reused=reused, run_failure=run_failure),
    )
    operations.write_run_artifact(f"runs/{run_id}/latest.json", log)


def run_external_audit_execution(
    plan: ExternalAuditExecutionPlanV1,
    inputs: tuple[ExternalAuditPartitionInput, ...],
    *,
    output_root: Path,
    worker_count: int = 1,
) -> ExternalAuditExecutionResult:
    """Execute, resume, or incrementally extend one local audit artifact root.

    Supported worker counts are fixed.  They are operational inputs and do not
    enter any logical identity or final artifact.  ``KeyboardInterrupt`` and
    other ``BaseException`` interruptions propagate, leaving completed
    partition statuses reusable and no misleading finalization.
    """
    if worker_count not in SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS:
        raise ExternalAuditExecutionError("unsupported worker count")
    root = Path(output_root)
    public = AtomicArtifactStore(root / "public")
    private = AtomicArtifactStore(root / "private")
    ordered_inputs = _validate_runtime_inputs(plan, inputs)
    public.write_immutable(_run_public_path(plan.run_id, "plan"), plan)

    reused: set[str] = set()
    outcomes: dict[str, _PartitionOutcome] = {}
    jobs: list[_PartitionJob] = []
    try:
        for item in ordered_inputs:
            prior = _validated_prior_success(public=public, private=private, input=item)
            if prior is not None:
                reused.add(item.partition.partition_id)
                outcomes[item.partition.partition_id] = prior
            else:
                jobs.append(_PartitionJob(output_root=root, input=item, plan=plan))
    except ExternalAuditExecutionError as exc:
        failure = ExternalAuditRunFailureV1(
            run_id=plan.run_id,
            failure_code="prior_success_invalid",
        )
        public.write_run_artifact(_run_public_path(plan.run_id, "failure"), failure)
        ordered_outcomes = tuple(outcomes[key] for key in sorted(outcomes))
        _write_operations(
            root=root,
            run_id=plan.run_id,
            worker_count=worker_count,
            outcomes=ordered_outcomes,
            reused=reused,
            run_failure="prior_success_invalid",
        )
        raise ExternalAuditExecutionError("prior success failed integrity validation") from exc

    if worker_count == 1:
        for job in jobs:
            outcome = _execute_partition_job(job)
            outcomes[outcome.status.partition_id] = outcome
    elif jobs:
        # ``spawn`` avoids inheriting caller threads or native-library state.
        # Callers using local processes must therefore invoke the API from a
        # normal guarded Python entry point, as the repository script does.
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=min(worker_count, len(jobs)),
            mp_context=context,
        ) as executor:
            pending = {executor.submit(_execute_partition_job, job): job for job in jobs}
            for future in as_completed(pending):
                job = pending[future]
                try:
                    outcome = future.result()
                except BaseException:
                    outcome = _worker_failure_outcome(
                        public=public,
                        partition=job.input.partition,
                    )
                outcomes[outcome.status.partition_id] = outcome

    ordered_outcomes = tuple(outcomes[key] for key in sorted(outcomes))
    try:
        _validate_entity_disjointness(ordered_outcomes)
    except ExternalAuditExecutionError as exc:
        failure = ExternalAuditRunFailureV1(
            run_id=plan.run_id,
            failure_code="partition_entity_overlap",
        )
        public.write_run_artifact(_run_public_path(plan.run_id, "failure"), failure)
        _write_operations(
            root=root,
            run_id=plan.run_id,
            worker_count=worker_count,
            outcomes=ordered_outcomes,
            reused=reused,
            run_failure="partition_entity_overlap",
        )
        raise ExternalAuditExecutionError("partition entity overlap") from exc

    finalization = build_external_audit_finalization(
        run_id=plan.run_id,
        partitions=tuple(item.status for item in ordered_outcomes),
    )
    # Finalization is the last logical write. It is replaceable only because a
    # retry may legitimately turn a recorded transient failure into success.
    public.write_run_artifact(_run_public_path(plan.run_id, "finalization"), finalization)
    _write_operations(
        root=root,
        run_id=plan.run_id,
        worker_count=worker_count,
        outcomes=ordered_outcomes,
        reused=reused,
    )
    executed = tuple(
        item.status.partition_id
        for item in ordered_outcomes
        if item.status.partition_id not in reused
    )
    failed = tuple(
        item.status.partition_id for item in ordered_outcomes if item.status.status == "failed"
    )
    return ExternalAuditExecutionResult(
        plan=plan,
        finalization=finalization,
        reused_partition_ids=tuple(sorted(reused)),
        executed_partition_ids=tuple(sorted(executed)),
        failed_partition_ids=tuple(sorted(failed)),
        partition_runtime_ns=tuple(
            (item.status.partition_id, item.runtime_ns) for item in ordered_outcomes
        ),
    )


def logical_execution_artifact_paths(
    result: ExternalAuditExecutionResult,
) -> tuple[tuple[str, str], ...]:
    """Return current logical public/private paths, excluding operational logs."""
    paths: list[tuple[str, str]] = [
        ("public", _run_public_path(result.plan.run_id, "plan")),
        ("public", _run_public_path(result.plan.run_id, "finalization")),
    ]
    for status in result.finalization.partitions:
        paths.extend(("public", reference.relative_path) for reference in status.public_artifacts)
        paths.append(("public", _partition_public_path(status.partition_id, "status")))
        if status.status == "succeeded":
            for name in ("normalized_dataset", "partition_summary"):
                paths.append(("private", _partition_private_path(status.partition_id, name)))
    return tuple(sorted(paths))
