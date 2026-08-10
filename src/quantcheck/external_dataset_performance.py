"""Reproducible performance corpora and measurements for local audit execution."""

from __future__ import annotations

import csv
import gc
import hashlib
import platform
import tracemalloc
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from time import perf_counter_ns
from typing import Annotated, Literal

from pydantic import AfterValidator, BeforeValidator, model_validator

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.benchmark_v2_schemas import DetectorExecutionConfigV2
from quantcheck.corpus_schemas import (
    ContentHash,
    CorpusModel,
    NonNegativeInteger,
    PositiveInteger,
    Token,
)
from quantcheck.duplicate_detection import detect_duplicate_observations
from quantcheck.external_dataset_contract import (
    AvailabilityColumnMappingV1,
    CsvInputOptionsV1,
    DatasetMappingV1,
    DateColumnMappingV1,
    ExternalDatasetFileInputV1,
    MappedTextColumnV1,
    MappedTextConstantV1,
    PeriodTypeColumnMappingV1,
    RevisionColumnsMappingV1,
    ValueColumnMappingV1,
)
from quantcheck.external_dataset_execution import (
    ExternalAuditExecutionResult,
    ExternalAuditPartitionInput,
    logical_execution_artifact_paths,
    run_external_audit_execution,
)
from quantcheck.external_dataset_execution_contract import (
    SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS,
    ExternalAuditExecutionPlanV1,
    build_external_audit_execution_plan,
    build_external_audit_partition_spec,
)
from quantcheck.external_dataset_ingestion import load_external_file
from quantcheck.external_dataset_policy_examples import monitoring_policy_v1
from quantcheck.hashing import canonical_sha256, sha256_hex_of_bytes
from quantcheck.lookahead_detection import detect_lookahead
from quantcheck.point_in_time import build_dataset_snapshot
from quantcheck.revision_overwrite_detection import detect_revision_overwrite
from quantcheck.unit_drift_detection import detect_unit_drift

__all__ = [
    "DEFAULT_PERFORMANCE_ENVELOPES",
    "DetectorPerformanceMeasurementV1",
    "ExternalAuditPerformanceCaseV1",
    "ExternalAuditPerformanceReportV1",
    "ParallelPerformanceMeasurementV1",
    "PerformanceEnvelopeV1",
    "deterministic_entity_partition_map",
    "performance_dataset_mapping",
    "prepare_performance_corpus",
    "run_performance_benchmark",
]

PERFORMANCE_SPEC_VERSION: Literal["quantcheck/external-audit-performance/v1"] = (
    "quantcheck/external-audit-performance/v1"
)
_PERIODS_PER_ENTITY = 20
_AS_OF_DATE = date(2030, 1, 1)
_COLUMNS = (
    "entity",
    "entity_name",
    "concept",
    "amount",
    "unit",
    "period_kind",
    "period_start",
    "period_end",
    "filed_date",
    "available_date",
    "form",
    "accession",
    "source_row",
    "revision_lineage",
    "revision_sequence",
)


def _to_tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


class PerformanceEnvelopeV1(CorpusModel):
    """One representative deterministic corpus size."""

    label: Literal["small", "medium", "large"]
    record_count: PositiveInteger
    partition_count: PositiveInteger
    maximum_records_per_partition: PositiveInteger

    @model_validator(mode="after")
    def _check_shape(self) -> PerformanceEnvelopeV1:
        if self.record_count % _PERIODS_PER_ENTITY:
            raise ValueError("record_count must contain complete twenty-period entities")
        entity_count = self.record_count // _PERIODS_PER_ENTITY
        if entity_count % self.partition_count:
            raise ValueError("entity count must divide evenly across partitions")
        expected = self.record_count // self.partition_count
        if self.maximum_records_per_partition != expected:
            raise ValueError("performance partitions have an exact even size")
        return self


DEFAULT_PERFORMANCE_ENVELOPES = (
    PerformanceEnvelopeV1(
        label="small",
        record_count=1_000,
        partition_count=2,
        maximum_records_per_partition=500,
    ),
    PerformanceEnvelopeV1(
        label="medium",
        record_count=10_000,
        partition_count=4,
        maximum_records_per_partition=2_500,
    ),
    PerformanceEnvelopeV1(
        label="large",
        record_count=50_000,
        partition_count=10,
        maximum_records_per_partition=5_000,
    ),
)


class DetectorPerformanceMeasurementV1(CorpusModel):
    detector: Literal[
        "duplicate_observation",
        "lookahead_timestamp",
        "revision_overwrite",
        "unit_drift",
    ]
    runtime_ns: NonNegativeInteger


def _normalize_detector_measurements(
    value: tuple[DetectorPerformanceMeasurementV1, ...],
) -> tuple[DetectorPerformanceMeasurementV1, ...]:
    detectors = [item.detector for item in value]
    if len(set(detectors)) != 4:
        raise ValueError("performance cases require exactly four detector measurements")
    return tuple(sorted(value, key=lambda item: item.detector))


DetectorMeasurementsV1 = Annotated[
    tuple[DetectorPerformanceMeasurementV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_detector_measurements),
]


class ExternalAuditPerformanceCaseV1(CorpusModel):
    """Required measurements for one corpus envelope on one local worker."""

    label: Literal["small", "medium", "large"]
    input_record_count: PositiveInteger
    partition_count: PositiveInteger
    maximum_records_per_partition: PositiveInteger
    worker_count: Literal[1] = 1
    detector_runtimes: DetectorMeasurementsV1
    total_runtime_ns: PositiveInteger
    peak_memory_bytes: PositiveInteger
    peak_memory_method: Literal["tracemalloc_largest_partition_python_allocations"] = (
        "tracemalloc_largest_partition_python_allocations"
    )
    normalized_input_size_bytes: PositiveInteger
    public_artifact_size_bytes: PositiveInteger
    private_artifact_size_bytes: PositiveInteger
    unchanged_rerun_runtime_ns: PositiveInteger
    changed_partition_rerun_runtime_ns: PositiveInteger
    changed_partition_reused_count: NonNegativeInteger
    changed_partition_executed_count: PositiveInteger
    logical_artifact_hash: ContentHash


class ParallelPerformanceMeasurementV1(CorpusModel):
    """Large-envelope scaling plus deterministic logical-tree proof."""

    worker_count: PositiveInteger
    total_runtime_ns: PositiveInteger
    estimated_peak_memory_upper_bound_bytes: PositiveInteger
    logical_artifact_hash: ContentHash


def _normalize_parallel_measurements(
    value: tuple[ParallelPerformanceMeasurementV1, ...],
) -> tuple[ParallelPerformanceMeasurementV1, ...]:
    counts = [item.worker_count for item in value]
    if tuple(sorted(counts)) != SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS:
        raise ValueError("parallel measurements must cover every supported worker count")
    hashes = {item.logical_artifact_hash for item in value}
    if len(hashes) != 1:
        raise ValueError("parallel executions did not produce identical logical artifacts")
    return tuple(sorted(value, key=lambda item: item.worker_count))


ParallelMeasurementsV1 = Annotated[
    tuple[ParallelPerformanceMeasurementV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_parallel_measurements),
]


class ExternalAuditPerformanceReportV1(CorpusModel):
    """Machine-specific operational evidence, never benchmark truth."""

    spec_version: Literal["quantcheck/external-audit-performance/v1"] = PERFORMANCE_SPEC_VERSION
    python_version: Token
    platform: Token
    processor: Token
    cases: Annotated[tuple[ExternalAuditPerformanceCaseV1, ...], BeforeValidator(_to_tuple)]
    large_parallel_measurements: ParallelMeasurementsV1
    deterministic_corpus: Literal[True] = True
    scientific_metrics_claim: Literal[False] = False


@dataclass(frozen=True, slots=True)
class PreparedPerformanceCorpus:
    plan: ExternalAuditExecutionPlanV1
    inputs: tuple[ExternalAuditPartitionInput, ...]


def deterministic_entity_partition_map(
    entity_ids: tuple[str, ...],
    partition_count: int,
) -> dict[str, int]:
    """Assign whole entities by SHA-256 rank, never Python hash or input order."""
    if isinstance(partition_count, bool) or not isinstance(partition_count, int):
        raise ValueError("partition_count must be an integer")
    if partition_count < 1:
        raise ValueError("partition_count must be positive")
    unique = set(entity_ids)
    if len(unique) != len(entity_ids):
        raise ValueError("entity_ids must be unique")
    ordered = sorted(
        entity_ids,
        key=lambda item: (hashlib.sha256(item.encode("utf-8")).hexdigest(), item),
    )
    return {entity_id: index % partition_count for index, entity_id in enumerate(ordered)}


def performance_dataset_mapping() -> DatasetMappingV1:
    """Explicit mapping for the deterministic performance corpus."""
    return DatasetMappingV1(
        dataset_name="quantcheck-deterministic-performance-corpus-v1",
        unmapped_columns="reject",
        entity_id=MappedTextColumnV1(column="entity"),
        entity_name=MappedTextColumnV1(column="entity_name"),
        concept_namespace=MappedTextConstantV1(value="example-taxonomy"),
        concept=MappedTextColumnV1(column="concept"),
        value=ValueColumnMappingV1(column="amount"),
        unit=MappedTextColumnV1(column="unit"),
        dimensions=(),
        period_type=PeriodTypeColumnMappingV1(
            column="period_kind",
            instant_value="I",
            duration_value="D",
        ),
        period_start=DateColumnMappingV1(column="period_start"),
        period_end=DateColumnMappingV1(column="period_end"),
        filed_on=DateColumnMappingV1(column="filed_date"),
        available_on=AvailabilityColumnMappingV1(
            column="available_date",
            evidence_reference="deterministic-performance-corpus-contract-v1",
        ),
        form=MappedTextColumnV1(column="form"),
        accession_or_equivalent=MappedTextColumnV1(column="accession"),
        source_name=MappedTextConstantV1(value="quantcheck-performance-generator"),
        source_locator=MappedTextConstantV1(value="quantcheck://performance-corpus/v1"),
        source_row_id=MappedTextColumnV1(column="source_row"),
        source_provenance_visibility="public_audit_evidence",
        revision_lineage=RevisionColumnsMappingV1(
            lineage_column="revision_lineage",
            sequence_column="revision_sequence",
        ),
    )


def _performance_row(entity_index: int, period_index: int, *, changed: bool) -> dict[str, str]:
    start = date(2018, 1, 1) + timedelta(days=91 * period_index)
    end = start + timedelta(days=89)
    filed = end + timedelta(days=30)
    available = filed + timedelta(days=2)
    record_index = entity_index * _PERIODS_PER_ENTITY + period_index
    amount = Decimal(1_000 + entity_index * 17 + period_index)
    if changed:
        amount += Decimal(1)
    return {
        "entity": f"PERF-{entity_index:06d}",
        "entity_name": f"Deterministic Issuer {entity_index:06d}",
        "concept": "IllustrativeQuarterlyRevenue",
        "amount": str(amount),
        "unit": "USD",
        "period_kind": "D",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "filed_date": filed.isoformat(),
        "available_date": available.isoformat(),
        "form": "10-Q",
        "accession": f"perf-accession-{record_index:08d}",
        "source_row": f"perf-row-{record_index:08d}",
        "revision_lineage": "",
        "revision_sequence": "",
    }


def prepare_performance_corpus(
    directory: Path,
    envelope: PerformanceEnvelopeV1,
    *,
    changed_partition_index: int | None = None,
) -> PreparedPerformanceCorpus:
    """Write deterministic CSV partitions and build their path-free plan."""
    if changed_partition_index is not None and not (
        0 <= changed_partition_index < envelope.partition_count
    ):
        raise ValueError("changed_partition_index is outside the corpus")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    entity_count = envelope.record_count // _PERIODS_PER_ENTITY
    entity_ids = tuple(f"PERF-{index:06d}" for index in range(entity_count))
    assignments = deterministic_entity_partition_map(entity_ids, envelope.partition_count)
    paths = tuple(root / f"partition-{index:04d}.csv" for index in range(envelope.partition_count))
    counts = [0 for _ in paths]
    with ExitStack() as stack:
        writers: list[csv.DictWriter[str]] = []
        for path in paths:
            handle = stack.enter_context(path.open("w", encoding="utf-8", newline=""))
            writer = csv.DictWriter(handle, fieldnames=_COLUMNS)
            writer.writeheader()
            writers.append(writer)
        for entity_index, entity_id in enumerate(entity_ids):
            partition_index = assignments[entity_id]
            for period_index in range(_PERIODS_PER_ENTITY):
                writers[partition_index].writerow(
                    _performance_row(
                        entity_index,
                        period_index,
                        changed=partition_index == changed_partition_index,
                    )
                )
                counts[partition_index] += 1

    mapping = performance_dataset_mapping()
    policy = monitoring_policy_v1()
    specifications = []
    inputs = []
    for partition_index, (path, record_count) in enumerate(zip(paths, counts, strict=True)):
        raw = path.read_bytes()
        source = ExternalDatasetFileInputV1(
            input_format="csv",
            expected_sha256=sha256_hex_of_bytes(raw),
            expected_size_bytes=len(raw),
            csv=CsvInputOptionsV1(null_tokens=("",)),
        )
        specification = build_external_audit_partition_spec(
            partition_key=f"partition-{partition_index:04d}",
            source=source,
            expected_record_count=record_count,
            mapping=mapping,
            policy=policy,
            as_of_date=_AS_OF_DATE,
        )
        specifications.append(specification)
        inputs.append(ExternalAuditPartitionInput(path=path, partition=specification))
    plan = build_external_audit_execution_plan(
        mapping=mapping,
        policy=policy,
        as_of_date=_AS_OF_DATE,
        maximum_records_per_partition=envelope.maximum_records_per_partition,
        partitions=tuple(reversed(specifications)),  # normalization must remove enumeration order
    )
    by_id = {item.partition.partition_id: item for item in inputs}
    return PreparedPerformanceCorpus(
        plan=plan,
        inputs=tuple(by_id[item.partition_id] for item in plan.partitions),
    )


def _measure_detector_runtimes(
    prepared: PreparedPerformanceCorpus,
) -> tuple[DetectorPerformanceMeasurementV1, ...]:
    totals = {
        "duplicate_observation": 0,
        "lookahead_timestamp": 0,
        "revision_overwrite": 0,
        "unit_drift": 0,
    }
    configs = DetectorExecutionConfigV2().detector_configs
    for item in prepared.inputs:
        _profile, normalized = load_external_file(
            item.path,
            prepared.plan.mapping,
            item.partition.source,
        )
        snapshot = build_dataset_snapshot(
            normalized.records,
            dataset_name=normalized.dataset_name,
            as_of_date=prepared.plan.as_of_date,
        )
        audit_input = sanitize_for_audit(snapshot)
        started = perf_counter_ns()
        detect_duplicate_observations(audit_input)
        totals["duplicate_observation"] += perf_counter_ns() - started
        started = perf_counter_ns()
        detect_lookahead(audit_input)
        totals["lookahead_timestamp"] += perf_counter_ns() - started
        started = perf_counter_ns()
        detect_revision_overwrite(audit_input, configs.revision_overwrite_detector)
        totals["revision_overwrite"] += perf_counter_ns() - started
        started = perf_counter_ns()
        detect_unit_drift(audit_input, configs.unit_drift_detector)
        totals["unit_drift"] += perf_counter_ns() - started
        del audit_input, snapshot, normalized
    return tuple(
        DetectorPerformanceMeasurementV1(
            detector=detector,  # type: ignore[arg-type]
            runtime_ns=runtime_ns,
        )
        for detector, runtime_ns in totals.items()
    )


def _measure_peak_partition_memory(prepared: PreparedPerformanceCorpus) -> int:
    largest = max(
        prepared.inputs,
        key=lambda item: item.partition.expected_record_count,
    )
    gc.collect()
    tracemalloc.start()
    try:
        from quantcheck.external_dataset_audit import audit_external_file

        audit_external_file(
            largest.path,
            mapping=prepared.plan.mapping,
            file_input=largest.partition.source,
            as_of_date=prepared.plan.as_of_date,
            policy=prepared.plan.policy,
        )
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


def _logical_sizes_and_hash(
    root: Path,
    result: ExternalAuditExecutionResult,
) -> tuple[int, int, int, str]:
    public_size = 0
    private_size = 0
    normalized_size = 0
    entries: list[dict[str, object]] = []
    for visibility, relative_path in logical_execution_artifact_paths(result):
        path = root / visibility / relative_path
        payload = path.read_bytes()
        size = len(payload)
        if visibility == "public":
            public_size += size
        else:
            private_size += size
            if relative_path.endswith("/normalized_dataset.json"):
                normalized_size += size
        entries.append(
            {
                "visibility": visibility,
                "relative_path": relative_path,
                "content_hash": sha256_hex_of_bytes(payload),
                "size_bytes": size,
            }
        )
    return public_size, private_size, normalized_size, canonical_sha256(tuple(entries))


def _run_case(
    root: Path,
    envelope: PerformanceEnvelopeV1,
) -> tuple[ExternalAuditPerformanceCaseV1, PreparedPerformanceCorpus]:
    prepared = prepare_performance_corpus(root / "source", envelope)
    artifact_root = root / "artifacts"
    started = perf_counter_ns()
    first = run_external_audit_execution(
        prepared.plan,
        prepared.inputs,
        output_root=artifact_root,
        worker_count=1,
    )
    total_runtime = perf_counter_ns() - started
    detector_runtimes = _measure_detector_runtimes(prepared)
    peak_memory = _measure_peak_partition_memory(prepared)
    public_size, private_size, normalized_size, logical_hash = _logical_sizes_and_hash(
        artifact_root, first
    )

    started = perf_counter_ns()
    unchanged = run_external_audit_execution(
        prepared.plan,
        prepared.inputs,
        output_root=artifact_root,
        worker_count=1,
    )
    unchanged_runtime = perf_counter_ns() - started
    if len(unchanged.reused_partition_ids) != envelope.partition_count:
        raise RuntimeError("unchanged performance rerun failed to reuse every partition")

    changed = prepare_performance_corpus(
        root / "changed-source",
        envelope,
        changed_partition_index=0,
    )
    started = perf_counter_ns()
    changed_result = run_external_audit_execution(
        changed.plan,
        changed.inputs,
        output_root=artifact_root,
        worker_count=1,
    )
    changed_runtime = perf_counter_ns() - started
    if (
        len(changed_result.executed_partition_ids) != 1
        or len(changed_result.reused_partition_ids) != envelope.partition_count - 1
    ):
        raise RuntimeError("one-partition change did not produce the expected incremental run")

    return (
        ExternalAuditPerformanceCaseV1(
            label=envelope.label,
            input_record_count=envelope.record_count,
            partition_count=envelope.partition_count,
            maximum_records_per_partition=envelope.maximum_records_per_partition,
            detector_runtimes=detector_runtimes,
            total_runtime_ns=total_runtime,
            peak_memory_bytes=peak_memory,
            normalized_input_size_bytes=normalized_size,
            public_artifact_size_bytes=public_size,
            private_artifact_size_bytes=private_size,
            unchanged_rerun_runtime_ns=unchanged_runtime,
            changed_partition_rerun_runtime_ns=changed_runtime,
            changed_partition_reused_count=len(changed_result.reused_partition_ids),
            changed_partition_executed_count=len(changed_result.executed_partition_ids),
            logical_artifact_hash=logical_hash,
        ),
        prepared,
    )


def run_performance_benchmark(
    work_root: Path,
    *,
    envelopes: tuple[PerformanceEnvelopeV1, ...] = DEFAULT_PERFORMANCE_ENVELOPES,
) -> ExternalAuditPerformanceReportV1:
    """Run small/medium/large envelopes and prove worker-count determinism."""
    cases: list[ExternalAuditPerformanceCaseV1] = []
    prepared_by_label: dict[str, PreparedPerformanceCorpus] = {}
    for envelope in envelopes:
        case, prepared = _run_case(Path(work_root) / envelope.label, envelope)
        cases.append(case)
        prepared_by_label[envelope.label] = prepared
    large_case = next(item for item in cases if item.label == "large")
    large_prepared = prepared_by_label["large"]
    parallel: list[ParallelPerformanceMeasurementV1] = [
        ParallelPerformanceMeasurementV1(
            worker_count=1,
            total_runtime_ns=large_case.total_runtime_ns,
            estimated_peak_memory_upper_bound_bytes=large_case.peak_memory_bytes,
            logical_artifact_hash=large_case.logical_artifact_hash,
        )
    ]
    for worker_count in SUPPORTED_EXTERNAL_AUDIT_WORKER_COUNTS[1:]:
        artifact_root = Path(work_root) / f"large-workers-{worker_count}" / "artifacts"
        started = perf_counter_ns()
        result = run_external_audit_execution(
            large_prepared.plan,
            large_prepared.inputs,
            output_root=artifact_root,
            worker_count=worker_count,
        )
        runtime = perf_counter_ns() - started
        _public, _private, _normalized, logical_hash = _logical_sizes_and_hash(
            artifact_root, result
        )
        parallel.append(
            ParallelPerformanceMeasurementV1(
                worker_count=worker_count,
                total_runtime_ns=runtime,
                estimated_peak_memory_upper_bound_bytes=(
                    large_case.peak_memory_bytes * worker_count
                ),
                logical_artifact_hash=logical_hash,
            )
        )
    processor = platform.processor() or "unknown-processor"
    return ExternalAuditPerformanceReportV1(
        python_version=platform.python_version(),
        platform=platform.platform(),
        processor=processor,
        cases=tuple(cases),
        large_parallel_measurements=tuple(parallel),
    )
