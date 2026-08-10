"""Deterministic contracts for bounded local external-audit execution.

This layer is additive to the frozen detector and external-audit contracts.  A
partition is an explicitly declared complete set of entity histories.  Its
identity covers source bytes and every audit-relevant contract, but never a
path, worker count, scheduler decision, timestamp, or filesystem order.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BeforeValidator, model_validator

from quantcheck.corpus_schemas import (
    ContentHash,
    CorpusDate,
    CorpusModel,
    NonNegativeInteger,
    PositiveInteger,
    Token,
)
from quantcheck.external_dataset_contract import (
    DatasetMappingV1,
    ExternalDatasetFileInputV1,
)
from quantcheck.external_dataset_ingestion import dataset_mapping_id
from quantcheck.external_dataset_policy_contract import (
    AuditPolicyV1,
    audit_policy_identity_matches,
)
from quantcheck.hashing import stable_id

__all__ = [
    "COMPLETE_ENTITY_PARTITION_SEMANTICS",
    "EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION",
    "SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS",
    "ExternalAuditArtifactReferenceV1",
    "ExternalAuditExecutionPlanV1",
    "ExternalAuditFinalizationV1",
    "ExternalAuditOperationalEventV1",
    "ExternalAuditOperationalLogV1",
    "ExternalAuditPartitionSpecV1",
    "ExternalAuditPartitionStatusV1",
    "ExternalAuditPrivatePartitionSummaryV1",
    "ExternalAuditRunFailureV1",
    "build_external_audit_execution_plan",
    "build_external_audit_partition_spec",
    "external_audit_finalization_identity_matches",
    "external_audit_partition_identity_matches",
    "external_audit_plan_identity_matches",
]

EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION: Literal["quantcheck/external-audit-execution/v1"] = (
    "quantcheck/external-audit-execution/v1"
)
COMPLETE_ENTITY_PARTITION_SEMANTICS: Literal["complete_entity_histories_disjoint"] = (
    "complete_entity_histories_disjoint"
)
SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS = (1, 2, 4)

_PARTITION_NAMESPACE = "quantcheck/external-audit-partition/v1"
_PLAN_NAMESPACE = "quantcheck/external-audit-execution-plan/v1"
_FINALIZATION_NAMESPACE = "quantcheck/external-audit-finalization/v1"
_PARTITION_ID_PATTERN = re.compile(r"^xpart_[0-9a-f]{16}$")
_RUN_ID_PATTERN = re.compile(r"^xrun_[0-9a-f]{16}$")
_FINALIZATION_ID_PATTERN = re.compile(r"^xfinal_[0-9a-f]{16}$")

ExternalAuditFailureCode = Literal[
    "artifact_conflict",
    "audit_integrity_failed",
    "input_unavailable",
    "partition_record_count_mismatch",
    "persistence_failed",
    "unexpected_internal_error",
    "validation_failed",
    "worker_failed",
]
ExternalAuditRunFailureCode = Literal[
    "partition_entity_overlap",
    "prior_success_invalid",
]


def _to_tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


def _validate_pattern(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"malformed {label}")
    return value


PartitionId = Annotated[
    str,
    BeforeValidator(lambda value: _validate_pattern(value, _PARTITION_ID_PATTERN, "partition_id")),
]
RunId = Annotated[
    str,
    BeforeValidator(lambda value: _validate_pattern(value, _RUN_ID_PATTERN, "run_id")),
]
FinalizationId = Annotated[
    str,
    BeforeValidator(
        lambda value: _validate_pattern(value, _FINALIZATION_ID_PATTERN, "finalization_id")
    ),
]


def _validate_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise ValueError("artifact path must be a nonempty relative POSIX path")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("artifact path contains an unsafe segment")
    return value


RelativeArtifactPath = Annotated[str, BeforeValidator(_validate_relative_path)]


def _normalize_partition_specs(
    value: tuple[ExternalAuditPartitionSpecV1, ...],
) -> tuple[ExternalAuditPartitionSpecV1, ...]:
    ids = [item.partition_id for item in value]
    keys = [item.partition_key for item in value]
    if not value:
        raise ValueError("an execution plan requires at least one partition")
    if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
        raise ValueError("partition identifiers and keys must be unique")
    return tuple(sorted(value, key=lambda item: item.partition_id))


class ExternalAuditPartitionSpecV1(CorpusModel):
    """One content-addressed, path-free production audit partition."""

    partition_id: PartitionId
    spec_version: Literal["quantcheck/external-audit-execution/v1"] = (
        EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION
    )
    partition_key: Token
    partition_semantics: Literal["complete_entity_histories_disjoint"] = (
        COMPLETE_ENTITY_PARTITION_SEMANTICS
    )
    source: ExternalDatasetFileInputV1
    expected_record_count: PositiveInteger
    mapping_id: Token
    policy_id: Token
    policy_content_hash: ContentHash
    as_of_date: CorpusDate

    @model_validator(mode="after")
    def _check_pinned_source(self) -> ExternalAuditPartitionSpecV1:
        if self.source.expected_sha256 is None or self.source.expected_size_bytes is None:
            raise ValueError("partition sources require exact SHA-256 and byte size")
        return self


ExternalAuditPartitionSpecsV1 = Annotated[
    tuple[ExternalAuditPartitionSpecV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_partition_specs),
]


class ExternalAuditExecutionPlanV1(CorpusModel):
    """Logical execution plan; operational worker count is deliberately absent."""

    run_id: RunId
    spec_version: Literal["quantcheck/external-audit-execution/v1"] = (
        EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION
    )
    dataset_name: Token
    mapping: DatasetMappingV1
    mapping_id: Token
    policy: AuditPolicyV1
    policy_id: Token
    policy_content_hash: ContentHash
    as_of_date: CorpusDate
    partition_semantics: Literal["complete_entity_histories_disjoint"] = (
        COMPLETE_ENTITY_PARTITION_SEMANTICS
    )
    maximum_records_per_partition: PositiveInteger
    record_count: PositiveInteger
    partitions: ExternalAuditPartitionSpecsV1

    @model_validator(mode="after")
    def _check_links(self) -> ExternalAuditExecutionPlanV1:
        if dataset_mapping_id(self.mapping) != self.mapping_id:
            raise ValueError("mapping identity does not match the plan")
        if not audit_policy_identity_matches(self.policy):
            raise ValueError("policy identity does not match its content")
        if (
            self.policy.policy_id != self.policy_id
            or self.policy.policy_content_hash != self.policy_content_hash
        ):
            raise ValueError("policy provenance does not match the plan")
        if self.mapping.dataset_name != self.dataset_name:
            raise ValueError("mapping dataset name does not match the plan")
        if self.record_count != sum(item.expected_record_count for item in self.partitions):
            raise ValueError("record_count must equal the partition total")
        for partition in self.partitions:
            if partition.expected_record_count > self.maximum_records_per_partition:
                raise ValueError("a partition exceeds maximum_records_per_partition")
            if (
                partition.mapping_id != self.mapping_id
                or partition.policy_id != self.policy_id
                or partition.policy_content_hash != self.policy_content_hash
                or partition.as_of_date != self.as_of_date
                or partition.partition_semantics != self.partition_semantics
            ):
                raise ValueError("partition audit context does not match the plan")
        return self


class ExternalAuditArtifactReferenceV1(CorpusModel):
    """Hash and size of one saved artifact, with explicit visibility."""

    role: Literal[
        "audit_report",
        "normalized_dataset",
        "partition_spec",
        "private_summary",
        "validation_profile",
    ]
    visibility: Literal["public", "private"]
    relative_path: RelativeArtifactPath
    content_hash: ContentHash
    size_bytes: NonNegativeInteger

    @model_validator(mode="after")
    def _check_visibility(self) -> ExternalAuditArtifactReferenceV1:
        if self.visibility == "public" and "private" in self.relative_path.split("/"):
            raise ValueError("a public reference cannot address private storage")
        return self


def _normalize_references(
    value: tuple[ExternalAuditArtifactReferenceV1, ...],
) -> tuple[ExternalAuditArtifactReferenceV1, ...]:
    roles = [item.role for item in value]
    if len(set(roles)) != len(roles):
        raise ValueError("artifact roles must be unique")
    return tuple(sorted(value, key=lambda item: item.role))


ArtifactReferencesV1 = Annotated[
    tuple[ExternalAuditArtifactReferenceV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_references),
]


class ExternalAuditPartitionStatusV1(CorpusModel):
    """Terminal per-partition status, written only after its evidence."""

    spec_version: Literal["quantcheck/external-audit-execution/v1"] = (
        EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION
    )
    partition_id: PartitionId
    partition_key: Token
    status: Literal["succeeded", "failed"]
    failure_code: ExternalAuditFailureCode | None
    source_record_count: NonNegativeInteger
    snapshot_record_count: NonNegativeInteger
    finding_count: NonNegativeInteger
    disposition: Literal[
        "blocked",
        "review_required",
        "passed_with_information",
        "passed",
        "not_available",
    ]
    public_artifacts: ArtifactReferencesV1
    private_artifact_hash: ContentHash | None

    @model_validator(mode="after")
    def _check_status(self) -> ExternalAuditPartitionStatusV1:
        roles = {item.role for item in self.public_artifacts}
        if self.status == "succeeded":
            if self.failure_code is not None or self.private_artifact_hash is None:
                raise ValueError("successful status cannot carry a failure")
            if roles != {"partition_spec", "validation_profile", "audit_report"}:
                raise ValueError("successful status requires all public evidence")
            if self.disposition == "not_available":
                raise ValueError("successful status requires an audit disposition")
        else:
            if self.failure_code is None or self.private_artifact_hash is not None:
                raise ValueError("failed status requires only a redacted failure code")
            if self.source_record_count or self.snapshot_record_count or self.finding_count:
                raise ValueError("failed status cannot claim scientific counts")
            if self.disposition != "not_available":
                raise ValueError("failed status has no audit disposition")
        return self


def _normalize_entity_ids(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("entity identifiers must be unique within a partition")
    return tuple(sorted(value))


class ExternalAuditPrivatePartitionSummaryV1(CorpusModel):
    """Private proof used to validate disjoint complete-entity partitions."""

    spec_version: Literal["quantcheck/external-audit-execution/v1"] = (
        EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION
    )
    partition_id: PartitionId
    normalized_dataset_id: Token
    normalized_dataset_hash: ContentHash
    entity_ids: Annotated[
        tuple[str, ...], BeforeValidator(_to_tuple), AfterValidator(_normalize_entity_ids)
    ]


def _normalize_statuses(
    value: tuple[ExternalAuditPartitionStatusV1, ...],
) -> tuple[ExternalAuditPartitionStatusV1, ...]:
    ids = [item.partition_id for item in value]
    if len(set(ids)) != len(ids):
        raise ValueError("finalization contains duplicate partition statuses")
    return tuple(sorted(value, key=lambda item: item.partition_id))


FinalizedStatusesV1 = Annotated[
    tuple[ExternalAuditPartitionStatusV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_statuses),
]


class ExternalAuditFinalizationV1(CorpusModel):
    """Atomic logical completion record, independent of execution scheduling."""

    finalization_id: FinalizationId
    spec_version: Literal["quantcheck/external-audit-execution/v1"] = (
        EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION
    )
    run_id: RunId
    status: Literal["succeeded", "completed_with_failures"]
    partition_count: PositiveInteger
    succeeded_partition_count: NonNegativeInteger
    failed_partition_count: NonNegativeInteger
    source_record_count: NonNegativeInteger
    snapshot_record_count: NonNegativeInteger
    finding_count: NonNegativeInteger
    partitions: FinalizedStatusesV1
    manifest_used: Literal[False] = False
    benchmark_claim: Literal[False] = False

    @model_validator(mode="after")
    def _check_totals(self) -> ExternalAuditFinalizationV1:
        if self.partition_count != len(self.partitions):
            raise ValueError("partition_count must equal finalized statuses")
        succeeded = tuple(item for item in self.partitions if item.status == "succeeded")
        failed = tuple(item for item in self.partitions if item.status == "failed")
        if (self.succeeded_partition_count, self.failed_partition_count) != (
            len(succeeded),
            len(failed),
        ):
            raise ValueError("partition status totals are inconsistent")
        if self.source_record_count != sum(item.source_record_count for item in succeeded):
            raise ValueError("source record total is inconsistent")
        if self.snapshot_record_count != sum(item.snapshot_record_count for item in succeeded):
            raise ValueError("snapshot record total is inconsistent")
        if self.finding_count != sum(item.finding_count for item in succeeded):
            raise ValueError("finding total is inconsistent")
        expected = "completed_with_failures" if failed else "succeeded"
        if self.status != expected:
            raise ValueError("finalization status must reflect partition failures")
        return self


class ExternalAuditOperationalEventV1(CorpusModel):
    """One data-free operational event; event order is canonical, not scheduled."""

    partition_id: PartitionId | None
    event: Literal[
        "partition_executed",
        "partition_failed",
        "partition_reused",
        "run_completed",
        "run_failed",
    ]
    failure_code: ExternalAuditFailureCode | ExternalAuditRunFailureCode | None = None


class ExternalAuditOperationalLogV1(CorpusModel):
    """Latest non-logical attempt log; durations live only in benchmark output."""

    spec_version: Literal["quantcheck/external-audit-execution/v1"] = (
        EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION
    )
    run_id: RunId
    worker_count: PositiveInteger
    events: Annotated[tuple[ExternalAuditOperationalEventV1, ...], BeforeValidator(_to_tuple)]
    redacted: Literal[True] = True


class ExternalAuditRunFailureV1(CorpusModel):
    """Atomic redacted plan-level failure; no finalization is written."""

    spec_version: Literal["quantcheck/external-audit-execution/v1"] = (
        EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION
    )
    run_id: RunId
    failure_code: ExternalAuditRunFailureCode
    redacted: Literal[True] = True


def _partition_body(
    *,
    partition_key: str,
    source: ExternalDatasetFileInputV1,
    expected_record_count: int,
    mapping_id: str,
    policy_id: str,
    policy_content_hash: str,
    as_of_date: object,
) -> dict[str, object]:
    return {
        "spec_version": EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION,
        "partition_key": partition_key,
        "partition_semantics": COMPLETE_ENTITY_PARTITION_SEMANTICS,
        "source": source,
        "expected_record_count": expected_record_count,
        "mapping_id": mapping_id,
        "policy_id": policy_id,
        "policy_content_hash": policy_content_hash,
        "as_of_date": as_of_date,
    }


def build_external_audit_partition_spec(
    *,
    partition_key: str,
    source: ExternalDatasetFileInputV1,
    expected_record_count: int,
    mapping: DatasetMappingV1,
    policy: AuditPolicyV1,
    as_of_date: object,
) -> ExternalAuditPartitionSpecV1:
    """Build one content identity without consulting its runtime file path."""
    body = _partition_body(
        partition_key=partition_key,
        source=source,
        expected_record_count=expected_record_count,
        mapping_id=dataset_mapping_id(mapping),
        policy_id=policy.policy_id,
        policy_content_hash=policy.policy_content_hash,
        as_of_date=as_of_date,
    )
    return ExternalAuditPartitionSpecV1.model_validate(
        {
            "partition_id": stable_id(
                prefix="xpart",
                namespace=_PARTITION_NAMESPACE,
                payload=body,
            ),
            **body,
        }
    )


def external_audit_partition_identity_matches(partition: ExternalAuditPartitionSpecV1) -> bool:
    body = {
        name: getattr(partition, name)
        for name in type(partition).model_fields
        if name != "partition_id"
    }
    return partition.partition_id == stable_id(
        prefix="xpart", namespace=_PARTITION_NAMESPACE, payload=body
    )


def _plan_body(
    *,
    mapping: DatasetMappingV1,
    policy: AuditPolicyV1,
    as_of_date: object,
    maximum_records_per_partition: int,
    partitions: tuple[ExternalAuditPartitionSpecV1, ...],
) -> dict[str, object]:
    ordered = tuple(sorted(partitions, key=lambda item: item.partition_id))
    return {
        "spec_version": EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION,
        "dataset_name": mapping.dataset_name,
        "mapping": mapping,
        "mapping_id": dataset_mapping_id(mapping),
        "policy": policy,
        "policy_id": policy.policy_id,
        "policy_content_hash": policy.policy_content_hash,
        "as_of_date": as_of_date,
        "partition_semantics": COMPLETE_ENTITY_PARTITION_SEMANTICS,
        "maximum_records_per_partition": maximum_records_per_partition,
        "record_count": sum(item.expected_record_count for item in ordered),
        "partitions": ordered,
    }


def build_external_audit_execution_plan(
    *,
    mapping: DatasetMappingV1,
    policy: AuditPolicyV1,
    as_of_date: object,
    maximum_records_per_partition: int,
    partitions: tuple[ExternalAuditPartitionSpecV1, ...],
) -> ExternalAuditExecutionPlanV1:
    """Build a normalized logical plan independent of input enumeration."""
    body = _plan_body(
        mapping=mapping,
        policy=policy,
        as_of_date=as_of_date,
        maximum_records_per_partition=maximum_records_per_partition,
        partitions=partitions,
    )
    return ExternalAuditExecutionPlanV1.model_validate(
        {
            "run_id": stable_id(prefix="xrun", namespace=_PLAN_NAMESPACE, payload=body),
            **body,
        }
    )


def external_audit_plan_identity_matches(plan: ExternalAuditExecutionPlanV1) -> bool:
    body = {name: getattr(plan, name) for name in type(plan).model_fields if name != "run_id"}
    return plan.run_id == stable_id(prefix="xrun", namespace=_PLAN_NAMESPACE, payload=body)


def external_audit_finalization_identity_matches(
    finalization: ExternalAuditFinalizationV1,
) -> bool:
    body = {
        name: getattr(finalization, name)
        for name in type(finalization).model_fields
        if name != "finalization_id"
    }
    return finalization.finalization_id == stable_id(
        prefix="xfinal", namespace=_FINALIZATION_NAMESPACE, payload=body
    )


def build_external_audit_finalization(
    *,
    run_id: str,
    partitions: tuple[ExternalAuditPartitionStatusV1, ...],
) -> ExternalAuditFinalizationV1:
    """Build the schedule-independent atomic terminal record."""
    ordered = tuple(sorted(partitions, key=lambda item: item.partition_id))
    succeeded = tuple(item for item in ordered if item.status == "succeeded")
    failed_count = len(ordered) - len(succeeded)
    body: dict[str, object] = {
        "spec_version": EXTERNAL_AUDIT_EXECUTION_SPEC_VERSION,
        "run_id": run_id,
        "status": "completed_with_failures" if failed_count else "succeeded",
        "partition_count": len(ordered),
        "succeeded_partition_count": len(succeeded),
        "failed_partition_count": failed_count,
        "source_record_count": sum(item.source_record_count for item in succeeded),
        "snapshot_record_count": sum(item.snapshot_record_count for item in succeeded),
        "finding_count": sum(item.finding_count for item in succeeded),
        "partitions": ordered,
        "manifest_used": False,
        "benchmark_claim": False,
    }
    return ExternalAuditFinalizationV1.model_validate(
        {
            "finalization_id": stable_id(
                prefix="xfinal",
                namespace=_FINALIZATION_NAMESPACE,
                payload=body,
            ),
            **body,
        }
    )
