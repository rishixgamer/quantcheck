"""One corpus-backed v0.2 case with mandatory paired clean-control audit."""

from __future__ import annotations

from dataclasses import dataclass

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.benchmark_v2_config import benchmark_v2_case_identity_matches
from quantcheck.benchmark_v2_contract import BenchmarkV2ContractError
from quantcheck.benchmark_v2_evaluation import ManifestV1, evaluate_detector_execution_v2
from quantcheck.benchmark_v2_execution import run_selected_detectors_v2
from quantcheck.benchmark_v2_schemas import (
    BenchmarkV2CaseConfig,
    BenchmarkV2Evaluation,
    DetectorExecutionV2,
)
from quantcheck.corpus_eligibility import eligible_unit_count, unit_snapshot
from quantcheck.corpus_registry import corpus_unit_records, corpus_unit_spec
from quantcheck.corpus_schemas import CorpusUnitSpec
from quantcheck.duplicate_injection import inject_duplicate_observations
from quantcheck.hashing import canonical_sha256
from quantcheck.lookahead_injection import inject_lookahead
from quantcheck.revision_overwrite_injection import inject_revision_overwrite
from quantcheck.schemas import (
    DatasetSnapshot,
    DuplicateInjectionConfig,
    FinancialFact,
    LookAheadInjectionConfig,
    RevisionOverwriteInjectionConfig,
    UnitDriftInjectionConfig,
)
from quantcheck.unit_drift_injection import inject_unit_drift

__all__ = ["BenchmarkV2CaseArtifacts", "run_benchmark_v2_case"]


@dataclass(frozen=True, slots=True)
class BenchmarkV2CaseArtifacts:
    """In-memory v0.2 evidence, with private truth kept in explicit fields."""

    case: BenchmarkV2CaseConfig

    # Public, manifest-blind evidence.
    clean_control_execution: DetectorExecutionV2
    corrupted_execution: DetectorExecutionV2
    evaluation: BenchmarkV2Evaluation

    # Private answer-key evidence.
    clean_snapshot: DatasetSnapshot
    corrupted_snapshot: DatasetSnapshot
    manifest: ManifestV1


def _validate_unit(case: BenchmarkV2CaseConfig) -> CorpusUnitSpec:
    unit = corpus_unit_spec(case.corpus_unit_id)
    if unit.partition != case.partition:
        raise BenchmarkV2ContractError("case partition disagrees with the corpus unit")
    if unit.audit_dataset_name != case.audit_dataset_name or unit.horizon != case.horizon:
        raise BenchmarkV2ContractError("case horizon/naming disagrees with the corpus unit")
    if unit.content_hash != case.corpus_unit_content_hash:
        raise BenchmarkV2ContractError("case content hash disagrees with the corpus unit")
    if case.fault_profile not in unit.supported_fault_profiles:
        raise BenchmarkV2ContractError("case profile is unsupported by the corpus unit")
    return unit


def _inject(
    case: BenchmarkV2CaseConfig,
    clean: DatasetSnapshot,
    source_records: tuple[FinancialFact, ...],
) -> tuple[DatasetSnapshot, ManifestV1]:
    profile = case.fault_profile
    if profile == "lookahead_timestamp":
        return inject_lookahead(
            clean,
            LookAheadInjectionConfig(
                severity=case.severity,
                seed=case.seed,
                research_as_of_date=case.horizon.research_as_of_date,
                max_targets=case.max_targets,
            ),
        )
    if profile == "unit_drift":
        return inject_unit_drift(
            clean,
            UnitDriftInjectionConfig(
                severity=case.severity,
                seed=case.seed,
                max_targets=case.max_targets,
            ),
        )
    if profile == "duplicate_observation":
        return inject_duplicate_observations(
            clean,
            DuplicateInjectionConfig(
                severity=case.severity,
                seed=case.seed,
                max_targets=case.max_targets,
            ),
        )
    if profile == "revision_overwrite":
        return inject_revision_overwrite(
            clean,
            source_records,
            RevisionOverwriteInjectionConfig(
                severity=case.severity,
                seed=case.seed,
                max_targets=case.max_targets,
            ),
        )
    raise BenchmarkV2ContractError(f"unsupported fault profile: {profile!r}")


def run_benchmark_v2_case(case: BenchmarkV2CaseConfig) -> BenchmarkV2CaseArtifacts:
    """Run one fault case and its clean control through one detector selection."""
    if not benchmark_v2_case_identity_matches(case):
        raise BenchmarkV2ContractError("v0.2 case identity does not match its content")
    unit = _validate_unit(case)
    source_records = corpus_unit_records(case.corpus_unit_id)
    if canonical_sha256(source_records) != case.corpus_unit_content_hash:
        raise BenchmarkV2ContractError("materialized corpus unit bytes do not match the case")
    clean = unit_snapshot(unit, source_records)
    observed_eligible = eligible_unit_count(
        fault_profile=case.fault_profile,
        severity=case.severity,
        unit=unit,
        records=source_records,
        snapshot=clean,
    )
    if observed_eligible != case.eligible_unit_count:
        raise BenchmarkV2ContractError("case eligible-unit count drifted from the frozen census")
    corrupted, manifest = _inject(case, clean, source_records)

    # Both detector calls cross the unchanged AuditInputSnapshot boundary.
    # This module holds the manifest only because injection has already
    # happened; the execution API has no manifest channel and cannot receive it.
    clean_audit_input = sanitize_for_audit(clean)
    corrupted_audit_input = sanitize_for_audit(corrupted)
    clean_execution = run_selected_detectors_v2(
        clean_audit_input,
        case.detector_execution,
    )
    corrupted_execution = run_selected_detectors_v2(
        corrupted_audit_input,
        case.detector_execution,
    )

    # Only after both immutable audit executions exist may private truth enter.
    evaluation = evaluate_detector_execution_v2(
        primary_fault_profile=case.fault_profile,
        corrupted_execution=corrupted_execution,
        clean_control_execution=clean_execution,
        manifest=manifest,
    )
    return BenchmarkV2CaseArtifacts(
        case=case,
        clean_control_execution=clean_execution,
        corrupted_execution=corrupted_execution,
        evaluation=evaluation,
        clean_snapshot=clean,
        corrupted_snapshot=corrupted,
        manifest=manifest,
    )
