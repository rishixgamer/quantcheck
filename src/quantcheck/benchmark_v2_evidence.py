"""Persisted, resumable v0.2 development and validation benchmark evidence.

The public tree contains only detector-visible inputs, executions, evaluations,
terminal statuses, and derived aggregates. Injection manifests and canonical
snapshots remain under the explicitly separate private tree. A validation run
is refused until a development aggregate and preregistration freeze verify.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from quantcheck.benchmark_store import ArtifactIntegrityError, AtomicArtifactStore
from quantcheck.benchmark_v2_case import run_benchmark_v2_case
from quantcheck.benchmark_v2_config import (
    build_benchmark_v2_config,
    expand_benchmark_v2_cases,
)
from quantcheck.benchmark_v2_contract import ALL_V2_DETECTORS
from quantcheck.benchmark_v2_schemas import (
    BenchmarkV2CaseConfig,
    BenchmarkV2CaseMatrix,
    BenchmarkV2Config,
    BenchmarkV2Evaluation,
    BenchmarkV2Profile,
    DetectorExecutionV2,
)
from quantcheck.corpus_freeze import CorpusFreezeRecord
from quantcheck.hashing import sha256_hex_of_bytes, stable_id
from quantcheck.serialization import canonical_json_bytes

__all__ = [
    "BenchmarkV2EvidenceError",
    "aggregate_v2_from_public_root",
    "build_design_partner_beta_matrices",
    "run_v2_partition",
    "verify_v2_validation_freeze",
    "write_v2_validation_freeze",
]

EVIDENCE_SPEC_VERSION = "quantcheck/benchmark-evidence/v2"
AGGREGATE_NAMESPACE = "quantcheck/benchmark-aggregate/v2"
VALIDATION_FREEZE_NAMESPACE = "quantcheck/benchmark-validation-freeze/v2"
SEVERITIES: tuple[Literal["low", "medium", "high"], ...] = ("low", "medium", "high")
SEEDS_BY_PARTITION = {
    "development": tuple(range(0, 10)),
    "validation": tuple(range(100, 110)),
}

Partition = Literal["development", "validation"]


class BenchmarkV2EvidenceError(ValueError):
    """The persisted evidence tree or validation freeze is untrustworthy."""


def _content_reference(kind: str, relative_path: str, payload: bytes) -> dict[str, object]:
    return {
        "kind": kind,
        "relative_path": relative_path,
        "content_hash": sha256_hex_of_bytes(payload),
    }


def _case_path(case_id: str, name: str) -> str:
    return f"cases/{case_id}/{name}.json"


def _private_case_path(case_id: str, name: str) -> str:
    return f"cases/{case_id}/{name}.json"


def _root_paths(partition: Partition) -> tuple[str, str, str]:
    return (
        f"{partition}_config.json",
        f"{partition}_matrix.json",
        f"{partition}_aggregate.json",
    )


def build_design_partner_beta_matrices(
    corpus_freeze: CorpusFreezeRecord,
) -> tuple[
    tuple[BenchmarkV2Config, BenchmarkV2CaseMatrix],
    tuple[BenchmarkV2Config, BenchmarkV2CaseMatrix],
]:
    """Build the preregistered 390-case development and validation matrices."""
    pairs: list[tuple[BenchmarkV2Config, BenchmarkV2CaseMatrix]] = []
    for partition in ("development", "validation"):
        profiles: list[BenchmarkV2Profile] = []
        units = tuple(
            unit
            for partition_spec in corpus_freeze.corpus.partitions
            if partition_spec.partition == partition
            for unit in partition_spec.units
        )
        for fault_profile in ALL_V2_DETECTORS:
            unit_ids = tuple(
                unit.corpus_unit_id
                for unit in units
                if fault_profile in unit.supported_fault_profiles
            )
            profiles.append(
                BenchmarkV2Profile(
                    fault_profile=fault_profile,
                    corpus_unit_ids=unit_ids,
                    severities=SEVERITIES,
                    seeds=SEEDS_BY_PARTITION[partition],
                )
            )
        config = build_benchmark_v2_config(
            benchmark_name=f"design-partner-beta-{partition}",
            corpus_freeze=corpus_freeze,
            profiles=profiles,
        )
        matrix = expand_benchmark_v2_cases(config, corpus_freeze=corpus_freeze)
        if matrix.case_count != 390:
            raise BenchmarkV2EvidenceError(
                f"expected 390 {partition} cases, observed {matrix.case_count}"
            )
        if any(
            case.partition != partition or case.seed_class != partition for case in matrix.cases
        ):
            raise BenchmarkV2EvidenceError("partition units and seeds are not aligned")
        pairs.append((config, matrix))
    return pairs[0], pairs[1]


def _read_status(public: AtomicArtifactStore, case_id: str) -> dict[str, Any] | None:
    path = _case_path(case_id, "status")
    if not public.exists(path):
        return None
    value = public.read_canonical(path)
    if not isinstance(value, dict):
        raise ArtifactIntegrityError(f"status for {case_id} is not an object")
    return value


def _validate_prior_success(
    public: AtomicArtifactStore,
    private: AtomicArtifactStore,
    case: BenchmarkV2CaseConfig,
) -> bool:
    status = _read_status(public, case.benchmark_v2_case_id)
    if status is None or status.get("status") != "succeeded":
        return False
    if status.get("benchmark_v2_case_id") != case.benchmark_v2_case_id:
        raise ArtifactIntegrityError("stored success belongs to a different case")
    if public.read_bytes(_case_path(case.benchmark_v2_case_id, "case_config")) != (
        canonical_json_bytes(case)
    ):
        raise ArtifactIntegrityError("stored case configuration differs from the matrix")
    artifacts = status.get("artifacts")
    if not isinstance(artifacts, list):
        raise ArtifactIntegrityError("stored success has no artifact references")
    required_public = {
        "case_config",
        "clean_control_execution",
        "corrupted_execution",
        "evaluation",
    }
    seen: set[str] = set()
    for reference in artifacts:
        if not isinstance(reference, dict):
            raise ArtifactIntegrityError("stored success has a malformed artifact reference")
        kind = reference.get("kind")
        path = reference.get("relative_path")
        digest = reference.get("content_hash")
        if not isinstance(kind, str) or not isinstance(path, str) or not isinstance(digest, str):
            raise ArtifactIntegrityError("stored success has a malformed artifact reference")
        if not public.exists(path) or sha256_hex_of_bytes(public.read_bytes(path)) != digest:
            raise ArtifactIntegrityError(f"stored public artifact failed integrity: {path}")
        seen.add(kind)
    if seen != required_public:
        raise ArtifactIntegrityError("stored success does not cover the required public evidence")
    private_index_path = _private_case_path(case.benchmark_v2_case_id, "index")
    index = private.read_canonical(private_index_path)
    if not isinstance(index, dict) or not isinstance(index.get("entries"), list):
        raise ArtifactIntegrityError("stored success has no valid private index")
    private_kinds: set[str] = set()
    for reference in index["entries"]:
        if not isinstance(reference, dict):
            raise ArtifactIntegrityError("private index contains a malformed reference")
        path = reference.get("relative_path")
        digest = reference.get("content_hash")
        if not isinstance(path, str) or not isinstance(digest, str):
            raise ArtifactIntegrityError("private index contains a malformed reference")
        if not private.exists(path) or sha256_hex_of_bytes(private.read_bytes(path)) != digest:
            raise ArtifactIntegrityError(f"stored private artifact failed integrity: {path}")
        kind = reference.get("kind")
        if isinstance(kind, str):
            private_kinds.add(kind)
    if private_kinds != {"clean_snapshot", "corrupted_snapshot", "manifest"}:
        raise ArtifactIntegrityError("stored success does not cover the required private evidence")
    return True


def _persist_case(
    public: AtomicArtifactStore,
    private: AtomicArtifactStore,
    case: BenchmarkV2CaseConfig,
) -> dict[str, object]:
    result = run_benchmark_v2_case(case)
    case_id = case.benchmark_v2_case_id
    public_artifacts: tuple[tuple[str, object], ...] = (
        ("case_config", result.case),
        ("clean_control_execution", result.clean_control_execution),
        ("corrupted_execution", result.corrupted_execution),
        ("evaluation", result.evaluation),
    )
    public_references: list[dict[str, object]] = []
    for kind, artifact in public_artifacts:
        path = _case_path(case_id, kind)
        payload = public.write_immutable(path, artifact)
        public_references.append(_content_reference(kind, path, payload))

    private_references: list[dict[str, object]] = []
    private_artifacts: tuple[tuple[str, object], ...] = (
        ("clean_snapshot", result.clean_snapshot),
        ("corrupted_snapshot", result.corrupted_snapshot),
        ("manifest", result.manifest),
    )
    for kind, artifact in private_artifacts:
        path = _private_case_path(case_id, kind)
        payload = private.write_immutable(path, artifact)
        private_references.append(_content_reference(kind, path, payload))
    private.write_immutable(
        _private_case_path(case_id, "index"),
        {
            "benchmark_v2_case_id": case_id,
            "spec_version": EVIDENCE_SPEC_VERSION,
            "entries": tuple(private_references),
        },
    )

    status = {
        "benchmark_v2_case_id": case_id,
        "benchmark_v2_id": case.benchmark_v2_id,
        "spec_version": EVIDENCE_SPEC_VERSION,
        "partition": case.partition,
        "fault_profile": case.fault_profile,
        "severity": case.severity,
        "seed": case.seed,
        "status": "succeeded",
        "artifacts": tuple(public_references),
        "failure": None,
    }
    # The terminal status is deliberately the final case write.
    public.write_run_artifact(_case_path(case_id, "status"), status)
    return status


def _record_failure(
    public: AtomicArtifactStore,
    private: AtomicArtifactStore,
    case: BenchmarkV2CaseConfig,
    exc: BaseException,
) -> dict[str, object]:
    case_id = case.benchmark_v2_case_id
    error_code = f"case_{type(exc).__name__.lower()}"
    public_failure = {
        "error_code": error_code,
        "message": "the synthetic benchmark case failed; see private diagnostics",
    }
    status = {
        "benchmark_v2_case_id": case_id,
        "benchmark_v2_id": case.benchmark_v2_id,
        "spec_version": EVIDENCE_SPEC_VERSION,
        "partition": case.partition,
        "fault_profile": case.fault_profile,
        "severity": case.severity,
        "seed": case.seed,
        "status": "failed",
        "artifacts": (),
        "failure": public_failure,
    }
    attempt_id = stable_id(
        prefix="att2",
        namespace="quantcheck/benchmark-attempt/v2",
        payload={"case_id": case_id, "failure": public_failure},
    )
    public.write_immutable(f"cases/{case_id}/attempts/{attempt_id}.json", status)
    private.write_run_artifact(
        _private_case_path(case_id, "diagnostics"),
        {
            "benchmark_v2_case_id": case_id,
            "error_code": error_code,
            "exception_class": type(exc).__name__,
            "exception_message": " ".join(str(exc).split()) or type(exc).__name__,
        },
    )
    public.write_run_artifact(_case_path(case_id, "status"), status)
    return status


def _ratio(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    with localcontext() as context:
        context.prec = 50
        return Decimal(numerator) / Decimal(denominator)


def _metric_summary(rows: Sequence[dict[str, Any]]) -> dict[str, object]:
    counts = {
        "configured_case_count": len(rows),
        "successful_case_count": sum(row["status"] == "succeeded" for row in rows),
        "failed_case_count": sum(row["status"] == "failed" for row in rows),
        "incomplete_case_count": sum(row["status"] == "incomplete" for row in rows),
        "injected_faults": sum(row.get("injected_faults", 0) for row in rows),
        "findings": sum(row.get("findings", 0) for row in rows),
        "true_positive_faults": sum(row.get("true_positive_faults", 0) for row in rows),
        "false_negative_faults": sum(row.get("false_negative_faults", 0) for row in rows),
        "true_positive_findings": sum(row.get("true_positive_findings", 0) for row in rows),
        "false_positive_findings": sum(row.get("false_positive_findings", 0) for row in rows),
        "eligible_clean_denominator": sum(row.get("eligible_clean_denominator", 0) for row in rows),
        "clean_control_findings": sum(row.get("clean_control_findings", 0) for row in rows),
        "clean_control_cases_with_findings": sum(
            row.get("clean_control_findings", 0) > 0 for row in rows
        ),
        "primary_matched": sum(row.get("primary_matched", 0) for row in rows),
        "secondary_corroborating": sum(row.get("secondary_corroborating", 0) for row in rows),
        "independent_background": sum(row.get("independent_background", 0) for row in rows),
        "unmatched": sum(row.get("unmatched", 0) for row in rows),
    }
    counts["precision"] = _ratio(counts["true_positive_findings"], counts["findings"])
    counts["recall"] = _ratio(counts["true_positive_faults"], counts["injected_faults"])
    counts["false_positive_rate"] = _ratio(
        counts["false_positive_findings"],
        counts["eligible_clean_denominator"],
    )
    precision = counts["precision"]
    recall = counts["recall"]
    if precision is None or recall is None or precision + recall == 0:
        counts["f1"] = None
    else:
        with localcontext() as context:
            context.prec = 50
            counts["f1"] = (Decimal(2) * precision * recall) / (precision + recall)
    return counts


def aggregate_v2_from_public_root(output_root: Path, partition: Partition) -> dict[str, object]:
    """Rebuild one aggregate using only canonical public artifacts."""
    public = AtomicArtifactStore(Path(output_root) / "public")
    _, matrix_path, _ = _root_paths(partition)
    try:
        matrix = BenchmarkV2CaseMatrix.model_validate(public.read_canonical(matrix_path))
    except ValidationError as exc:
        raise BenchmarkV2EvidenceError("saved v0.2 matrix does not validate") from exc
    rows: list[dict[str, Any]] = []
    for case in matrix.cases:
        status = _read_status(public, case.benchmark_v2_case_id)
        base: dict[str, Any] = {
            "benchmark_v2_case_id": case.benchmark_v2_case_id,
            "partition": case.partition,
            "fault_profile": case.fault_profile,
            "severity": case.severity,
            "seed": case.seed,
            "status": "incomplete" if status is None else status.get("status"),
        }
        if base["status"] == "succeeded":
            try:
                evaluation = BenchmarkV2Evaluation.model_validate(
                    public.read_canonical(_case_path(case.benchmark_v2_case_id, "evaluation"))
                )
                clean = DetectorExecutionV2.model_validate(
                    public.read_canonical(
                        _case_path(case.benchmark_v2_case_id, "clean_control_execution")
                    )
                )
            except ValidationError as exc:
                raise BenchmarkV2EvidenceError(
                    "successful public case evidence is invalid"
                ) from exc
            metrics = evaluation.strict_primary_score.metrics
            interpretation = evaluation.production_interpretation
            base.update(
                {
                    "injected_faults": metrics.injected_faults,
                    "findings": metrics.findings,
                    "true_positive_faults": metrics.true_positive_faults,
                    "false_negative_faults": metrics.false_negative_faults,
                    "true_positive_findings": metrics.true_positive_findings,
                    "false_positive_findings": metrics.false_positive_findings,
                    "eligible_clean_denominator": metrics.eligible_clean_denominator,
                    "clean_control_findings": clean.finding_count,
                    "primary_matched": interpretation.primary_matched_count,
                    "secondary_corroborating": interpretation.secondary_corroborating_count,
                    "independent_background": interpretation.independent_background_count,
                    "unmatched": interpretation.unmatched_count,
                }
            )
        rows.append(base)

    groups: list[dict[str, object]] = []
    for dimension in ("fault_profile", "severity"):
        grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row[dimension])].append(row)
        for key in sorted(grouped):
            groups.append({"dimension": dimension, "key": key, **_metric_summary(grouped[key])})
    body = {
        "spec_version": EVIDENCE_SPEC_VERSION,
        "benchmark_v2_id": matrix.benchmark_v2_id,
        "partition": partition,
        "overall": _metric_summary(rows),
        "groups": tuple(groups),
    }
    return {
        "aggregate_v2_id": stable_id(prefix="agg2", namespace=AGGREGATE_NAMESPACE, payload=body),
        **body,
    }


def _write_index(public: AtomicArtifactStore) -> None:
    entries: list[dict[str, object]] = []
    if public.root.is_dir():
        for path in sorted(public.root.rglob("*.json")):
            relative = path.relative_to(public.root).as_posix()
            if relative == "index.json":
                continue
            entries.append(_content_reference("canonical_json", relative, path.read_bytes()))
    public.write_run_artifact(
        "index.json", {"spec_version": EVIDENCE_SPEC_VERSION, "entries": tuple(entries)}
    )


def _verify_validation_gate(
    output_root: Path,
    config: BenchmarkV2Config,
    matrix: BenchmarkV2CaseMatrix,
) -> None:
    freeze = verify_v2_validation_freeze(output_root)
    if freeze["validation_benchmark_v2_id"] != config.benchmark_v2_id:
        raise BenchmarkV2EvidenceError("validation config is outside the preregistered freeze")
    if freeze["validation_matrix_hash"] != sha256_hex_of_bytes(canonical_json_bytes(matrix)):
        raise BenchmarkV2EvidenceError("validation matrix differs from the preregistered freeze")


def run_v2_partition(
    config: BenchmarkV2Config,
    matrix: BenchmarkV2CaseMatrix,
    *,
    output_root: Path,
    partition: Partition,
    resume: bool = True,
) -> dict[str, object]:
    """Run, resume, persist, and publicly aggregate one preregistered partition."""
    if matrix.benchmark_v2_id != config.benchmark_v2_id:
        raise BenchmarkV2EvidenceError("matrix and config identities disagree")
    if any(case.partition != partition or case.seed_class != partition for case in matrix.cases):
        raise BenchmarkV2EvidenceError("matrix contains a case from another partition")
    if partition == "validation":
        _verify_validation_gate(output_root, config, matrix)

    public = AtomicArtifactStore(Path(output_root) / "public")
    private = AtomicArtifactStore(Path(output_root) / "private")
    config_path, matrix_path, aggregate_path = _root_paths(partition)
    public.write_immutable(config_path, config)
    public.write_immutable(matrix_path, matrix)

    for case in matrix.cases:
        if resume and _validate_prior_success(public, private, case):
            continue
        try:
            _persist_case(public, private, case)
        except Exception as exc:  # noqa: BLE001 - every synthetic case remains visible
            _record_failure(public, private, case, exc)

    aggregate = aggregate_v2_from_public_root(output_root, partition)
    public.write_run_artifact(aggregate_path, aggregate)
    _write_index(public)
    return aggregate


def write_v2_validation_freeze(
    output_root: Path,
    *,
    development_config: BenchmarkV2Config,
    development_matrix: BenchmarkV2CaseMatrix,
    validation_config: BenchmarkV2Config,
    validation_matrix: BenchmarkV2CaseMatrix,
    source_hashes: Mapping[str, str],
) -> dict[str, object]:
    """Freeze validation before it runs, after complete development evidence exists."""
    public = AtomicArtifactStore(Path(output_root) / "public")
    development_aggregate = aggregate_v2_from_public_root(output_root, "development")
    overall = development_aggregate["overall"]
    assert isinstance(overall, dict)
    if (
        overall["successful_case_count"] != development_matrix.case_count
        or overall["failed_case_count"] != 0
        or overall["incomplete_case_count"] != 0
    ):
        raise BenchmarkV2EvidenceError("development evidence is not complete; validation is sealed")
    body = {
        "spec_version": EVIDENCE_SPEC_VERSION,
        "development_benchmark_v2_id": development_config.benchmark_v2_id,
        "development_config_hash": sha256_hex_of_bytes(canonical_json_bytes(development_config)),
        "development_matrix_hash": sha256_hex_of_bytes(canonical_json_bytes(development_matrix)),
        "development_aggregate_id": development_aggregate["aggregate_v2_id"],
        "development_aggregate_hash": sha256_hex_of_bytes(
            canonical_json_bytes(development_aggregate)
        ),
        "validation_benchmark_v2_id": validation_config.benchmark_v2_id,
        "validation_config_hash": sha256_hex_of_bytes(canonical_json_bytes(validation_config)),
        "validation_matrix_hash": sha256_hex_of_bytes(canonical_json_bytes(validation_matrix)),
        "source_hashes": dict(sorted(source_hashes.items())),
    }
    freeze = {
        "validation_freeze_id": stable_id(
            prefix="vfrz2", namespace=VALIDATION_FREEZE_NAMESPACE, payload=body
        ),
        **body,
    }
    public.write_immutable("validation_freeze.json", freeze)
    _write_index(public)
    return freeze


def verify_v2_validation_freeze(output_root: Path) -> dict[str, Any]:
    """Verify the saved freeze and its referenced development aggregate bytes."""
    public = AtomicArtifactStore(Path(output_root) / "public")
    value = public.read_canonical("validation_freeze.json")
    if not isinstance(value, dict) or "validation_freeze_id" not in value:
        raise BenchmarkV2EvidenceError("validation freeze is malformed")
    identity = value["validation_freeze_id"]
    body = {key: item for key, item in value.items() if key != "validation_freeze_id"}
    expected = stable_id(prefix="vfrz2", namespace=VALIDATION_FREEZE_NAMESPACE, payload=body)
    if identity != expected:
        raise BenchmarkV2EvidenceError("validation freeze identity does not match its content")
    development = aggregate_v2_from_public_root(output_root, "development")
    if value.get("development_aggregate_id") != development["aggregate_v2_id"]:
        raise BenchmarkV2EvidenceError("development aggregate identity drifted after the freeze")
    if value.get("development_aggregate_hash") != sha256_hex_of_bytes(
        canonical_json_bytes(development)
    ):
        raise BenchmarkV2EvidenceError("development aggregate bytes drifted after the freeze")
    return value
