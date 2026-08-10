"""Bounded local execution, resume, isolation, and worker determinism."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

import quantcheck.external_dataset_execution as execution
from quantcheck.external_dataset_audit import audit_external_rows
from quantcheck.external_dataset_contract import ExternalDatasetAuditReportV2
from quantcheck.external_dataset_execution import (
    ExternalAuditExecutionError,
    logical_execution_artifact_paths,
    run_external_audit_execution,
)
from quantcheck.external_dataset_execution_contract import (
    SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS,
    ExternalAuditPartitionStatusV1,
    build_external_audit_execution_plan,
    build_external_audit_partition_spec,
    external_audit_finalization_identity_matches,
    external_audit_plan_identity_matches,
)
from quantcheck.external_dataset_performance import (
    PerformanceEnvelopeV1,
    deterministic_entity_partition_map,
    prepare_performance_corpus,
)
from quantcheck.external_dataset_policy_examples import monitoring_policy_v1
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.schemas import Finding
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json


def _envelope(*, records: int = 40, partitions: int = 2) -> PerformanceEnvelopeV1:
    return PerformanceEnvelopeV1(
        label="small",
        record_count=records,
        partition_count=partitions,
        maximum_records_per_partition=records // partitions,
    )


def _logical_bytes(root: Path, result: object) -> tuple[tuple[str, str, bytes], ...]:
    return tuple(
        (visibility, path, (root / visibility / path).read_bytes())
        for visibility, path in logical_execution_artifact_paths(result)  # type: ignore[arg-type]
    )


def test_entity_partitioning_is_hash_stable_balanced_and_order_independent() -> None:
    entities = tuple(f"ENTITY-{index:04d}" for index in range(12))
    forward = deterministic_entity_partition_map(entities, 3)
    reverse = deterministic_entity_partition_map(tuple(reversed(entities)), 3)
    assert forward == reverse
    assert sorted(forward.values()).count(0) == 4
    assert sorted(forward.values()).count(1) == 4
    assert sorted(forward.values()).count(2) == 4


def test_plan_identity_excludes_paths_worker_counts_and_input_order(tmp_path: Path) -> None:
    first = prepare_performance_corpus(tmp_path / "private-a", _envelope())
    second = prepare_performance_corpus(tmp_path / "PRIVATE-B", _envelope())
    assert canonical_json_bytes(first.plan) == canonical_json_bytes(second.plan)
    assert first.plan.run_id == second.plan.run_id
    assert external_audit_plan_identity_matches(first.plan)
    assert tuple(item.partition_id for item in first.plan.partitions) == tuple(
        sorted(item.partition_id for item in first.plan.partitions)
    )
    assert "worker" not in type(first.plan).model_fields


def test_sequential_and_parallel_workers_write_identical_logical_trees(tmp_path: Path) -> None:
    prepared = prepare_performance_corpus(tmp_path / "source", _envelope(records=80))
    sequential_root = tmp_path / "sequential"
    parallel_root = tmp_path / "parallel"
    sequential = run_external_audit_execution(
        prepared.plan,
        prepared.inputs,
        output_root=sequential_root,
        worker_count=1,
    )
    parallel = run_external_audit_execution(
        prepared.plan,
        tuple(reversed(prepared.inputs)),
        output_root=parallel_root,
        worker_count=2,
    )
    assert sequential.finalization.status == parallel.finalization.status == "succeeded"
    assert canonical_json_bytes(sequential.finalization) == canonical_json_bytes(
        parallel.finalization
    )
    assert _logical_bytes(sequential_root, sequential) == _logical_bytes(parallel_root, parallel)
    assert external_audit_finalization_identity_matches(sequential.finalization)


def test_unsupported_worker_count_is_rejected_before_execution(tmp_path: Path) -> None:
    prepared = prepare_performance_corpus(tmp_path / "source", _envelope())
    with pytest.raises(ExternalAuditExecutionError, match="unsupported worker"):
        run_external_audit_execution(
            prepared.plan,
            prepared.inputs,
            output_root=tmp_path / "artifacts",
            worker_count=max(SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS) + 1,
        )


def test_unchanged_rerun_is_idempotent_and_reuses_every_partition(tmp_path: Path) -> None:
    prepared = prepare_performance_corpus(tmp_path / "source", _envelope())
    root = tmp_path / "artifacts"
    first = run_external_audit_execution(
        prepared.plan, prepared.inputs, output_root=root, worker_count=1
    )
    before = _logical_bytes(root, first)
    second = run_external_audit_execution(
        prepared.plan, prepared.inputs, output_root=root, worker_count=4
    )
    assert second.executed_partition_ids == ()
    assert second.reused_partition_ids == tuple(
        partition.partition_id for partition in prepared.plan.partitions
    )
    assert canonical_json_bytes(first.finalization) == canonical_json_bytes(second.finalization)
    assert before == _logical_bytes(root, second)


def test_one_changed_partition_reruns_only_that_content_identity(tmp_path: Path) -> None:
    envelope = _envelope(records=60, partitions=3)
    original = prepare_performance_corpus(tmp_path / "original", envelope)
    root = tmp_path / "artifacts"
    run_external_audit_execution(original.plan, original.inputs, output_root=root)
    changed = prepare_performance_corpus(tmp_path / "changed", envelope, changed_partition_index=0)
    result = run_external_audit_execution(changed.plan, changed.inputs, output_root=root)
    assert len(result.executed_partition_ids) == 1
    assert len(result.reused_partition_ids) == 2
    original_ids = {item.partition_id for item in original.plan.partitions}
    changed_ids = {item.partition_id for item in changed.plan.partitions}
    assert len(original_ids ^ changed_ids) == 2


def test_failed_partition_is_isolated_and_retry_is_idempotent(tmp_path: Path) -> None:
    prepared = prepare_performance_corpus(tmp_path / "source", _envelope())
    damaged = prepared.inputs[0]
    original_bytes = damaged.path.read_bytes()
    damaged.path.write_bytes(b"not,the,pinned,source\n")
    root = tmp_path / "artifacts"
    first = run_external_audit_execution(prepared.plan, prepared.inputs, output_root=root)
    assert first.finalization.status == "completed_with_failures"
    assert len(first.failed_partition_ids) == 1
    assert first.finalization.succeeded_partition_count == 1
    assert all(
        (root / visibility / path).is_file()
        for visibility, path in logical_execution_artifact_paths(first)
    )

    damaged.path.write_bytes(original_bytes)
    second = run_external_audit_execution(prepared.plan, prepared.inputs, output_root=root)
    assert second.finalization.status == "succeeded"
    assert second.failed_partition_ids == ()
    assert second.executed_partition_ids == (damaged.partition.partition_id,)
    assert len(second.reused_partition_ids) == 1


def test_interruption_leaves_no_finalization_and_completed_case_is_reused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = prepare_performance_corpus(tmp_path / "source", _envelope())
    root = tmp_path / "artifacts"
    original = execution._execute_partition_job
    call_count = 0

    def interrupt_second(job: object) -> object:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise KeyboardInterrupt
        return original(job)  # type: ignore[arg-type]

    monkeypatch.setattr(execution, "_execute_partition_job", interrupt_second)
    with pytest.raises(KeyboardInterrupt):
        run_external_audit_execution(prepared.plan, prepared.inputs, output_root=root)
    finalization = root / "public" / "runs" / prepared.plan.run_id / "finalization.json"
    assert not finalization.exists()

    monkeypatch.setattr(execution, "_execute_partition_job", original)
    resumed = run_external_audit_execution(prepared.plan, prepared.inputs, output_root=root)
    assert resumed.finalization.status == "succeeded"
    assert len(resumed.reused_partition_ids) == 1
    assert len(resumed.executed_partition_ids) == 1


def test_public_tree_is_redacted_and_private_data_is_not_duplicated(tmp_path: Path) -> None:
    prepared = prepare_performance_corpus(tmp_path / "PRIVATE-SOURCE", _envelope())
    root = tmp_path / "artifacts"
    result = run_external_audit_execution(prepared.plan, prepared.inputs, output_root=root)
    public_bytes = b"".join(path.read_bytes() for path in (root / "public").rglob("*.json"))
    operations_bytes = b"".join(path.read_bytes() for path in (root / "operations").rglob("*.json"))
    private_bytes = b"".join(path.read_bytes() for path in (root / "private").rglob("*.json"))
    assert b"perf-row-" not in public_bytes
    assert b"perf-row-" not in operations_bytes
    assert b"PRIVATE-SOURCE" not in public_bytes + operations_bytes
    assert b"perf-row-" in private_bytes
    assert b"source_row_key" not in public_bytes
    finalization_bytes = canonical_json_bytes(result.finalization)
    assert b'"visibility":"private"' not in finalization_bytes
    assert b"private/" not in finalization_bytes
    assert not tuple(root.rglob("*.tmp"))
    normalized = tuple((root / "private").rglob("normalized_dataset.json"))
    assert len(normalized) == len(prepared.plan.partitions)
    assert not tuple((root / "private").rglob("snapshot.json"))
    assert not tuple((root / "private").rglob("audit_input.json"))


def test_operational_log_is_structured_redacted_and_schedule_free(tmp_path: Path) -> None:
    prepared = prepare_performance_corpus(tmp_path / "source", _envelope())
    root = tmp_path / "artifacts"
    run_external_audit_execution(
        prepared.plan,
        prepared.inputs,
        output_root=root,
        worker_count=2,
    )
    path = root / "operations" / "runs" / prepared.plan.run_id / "latest.json"
    payload = parse_canonical_json(path.read_bytes())
    assert isinstance(payload, dict)
    assert payload["redacted"] is True
    assert payload["worker_count"] == 2
    assert all("runtime" not in event and "path" not in event for event in payload["events"])


def test_prior_success_tampering_is_not_overwritten(tmp_path: Path) -> None:
    prepared = prepare_performance_corpus(tmp_path / "source", _envelope())
    root = tmp_path / "artifacts"
    first = run_external_audit_execution(prepared.plan, prepared.inputs, output_root=root)
    partition_id = first.finalization.partitions[0].partition_id
    report = root / "public" / "partitions" / partition_id / "audit_report.json"
    report.write_bytes(report.read_bytes() + b" ")
    with pytest.raises(ExternalAuditExecutionError, match="prior success"):
        run_external_audit_execution(prepared.plan, prepared.inputs, output_root=root)
    status_path = root / "public" / "partitions" / partition_id / "status.json"
    status = ExternalAuditPartitionStatusV1.model_validate(
        parse_canonical_json(status_path.read_bytes())
    )
    assert status.status == "succeeded"


def test_entity_overlap_prevents_finalization(tmp_path: Path) -> None:
    prepared = prepare_performance_corpus(tmp_path / "source", _envelope())
    first, second = prepared.inputs
    with first.path.open(encoding="utf-8", newline="") as handle:
        first_entity = next(csv.DictReader(handle))["entity"]
    with second.path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert first_entity is not None
    for row in rows:
        row["entity"] = first_entity
        row["entity_name"] = "Overlapping Entity"
    with second.path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    mapping = prepared.plan.mapping
    policy = monitoring_policy_v1()
    raw = second.path.read_bytes()
    source_document = second.partition.source.model_dump(mode="python")
    source_document["expected_sha256"] = sha256_hex_of_bytes(raw)
    source_document["expected_size_bytes"] = len(raw)
    source = type(second.partition.source).model_validate(source_document)
    changed_second = build_external_audit_partition_spec(
        partition_key=second.partition.partition_key,
        source=source,
        expected_record_count=second.partition.expected_record_count,
        mapping=mapping,
        policy=policy,
        as_of_date=prepared.plan.as_of_date,
    )
    plan = build_external_audit_execution_plan(
        mapping=mapping,
        policy=policy,
        as_of_date=prepared.plan.as_of_date,
        maximum_records_per_partition=prepared.plan.maximum_records_per_partition,
        partitions=(first.partition, changed_second),
    )
    inputs = (
        first,
        type(second)(path=second.path, partition=changed_second),
    )
    root = tmp_path / "overlap-artifacts"
    with pytest.raises(ExternalAuditExecutionError, match="entity overlap"):
        run_external_audit_execution(plan, inputs, output_root=root)
    assert not (root / "public" / "runs" / plan.run_id / "finalization.json").exists()
    assert (root / "public" / "runs" / plan.run_id / "failure.json").is_file()


def test_complete_entity_partitions_preserve_monolithic_logical_findings(
    tmp_path: Path,
) -> None:
    prepared = prepare_performance_corpus(tmp_path / "source", _envelope())
    changed_input = prepared.inputs[0]
    with changed_input.path.open(encoding="utf-8", newline="") as handle:
        changed_rows = list(csv.DictReader(handle))
    changed_rows[0]["available_date"] = changed_rows[0]["period_end"]
    with changed_input.path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(changed_rows[0]))
        writer.writeheader()
        writer.writerows(changed_rows)

    raw = changed_input.path.read_bytes()
    source_document = changed_input.partition.source.model_dump(mode="python")
    source_document["expected_sha256"] = sha256_hex_of_bytes(raw)
    source_document["expected_size_bytes"] = len(raw)
    source = type(changed_input.partition.source).model_validate(source_document)
    changed_spec = build_external_audit_partition_spec(
        partition_key=changed_input.partition.partition_key,
        source=source,
        expected_record_count=changed_input.partition.expected_record_count,
        mapping=prepared.plan.mapping,
        policy=prepared.plan.policy,
        as_of_date=prepared.plan.as_of_date,
    )
    inputs = (
        type(changed_input)(path=changed_input.path, partition=changed_spec),
        *prepared.inputs[1:],
    )
    plan = build_external_audit_execution_plan(
        mapping=prepared.plan.mapping,
        policy=prepared.plan.policy,
        as_of_date=prepared.plan.as_of_date,
        maximum_records_per_partition=prepared.plan.maximum_records_per_partition,
        partitions=tuple(item.partition for item in inputs),
    )
    root = tmp_path / "artifacts"
    result = run_external_audit_execution(plan, inputs, output_root=root)

    partition_findings: list[Finding] = []
    for status in result.finalization.partitions:
        report_path = (
            root
            / "public"
            / next(
                reference.relative_path
                for reference in status.public_artifacts
                if reference.role == "audit_report"
            )
        )
        report = ExternalDatasetAuditReportV2.model_validate(
            parse_canonical_json(report_path.read_bytes())
        )
        partition_findings.extend(
            finding for run in report.detector_runs for finding in run.report.findings
        )

    all_rows: list[dict[str, object]] = []
    for item in inputs:
        with item.path.open(encoding="utf-8", newline="") as handle:
            all_rows.extend(
                {key: (None if value == "" else value) for key, value in supplied.items()}
                for supplied in csv.DictReader(handle)
            )
    monolithic = audit_external_rows(
        all_rows,
        mapping=plan.mapping,
        as_of_date=plan.as_of_date,
        policy=plan.policy,
    ).public_report
    monolithic_findings = [
        finding for run in monolithic.detector_runs for finding in run.report.findings
    ]
    assert partition_findings
    assert tuple(
        canonical_json_bytes(item)
        for item in sorted(partition_findings, key=lambda finding: finding.finding_id)
    ) == tuple(
        canonical_json_bytes(item)
        for item in sorted(monolithic_findings, key=lambda finding: finding.finding_id)
    )
