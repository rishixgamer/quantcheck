"""Strict additive schemas for the v0.2 execution/evaluation contract."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BeforeValidator, model_validator

from quantcheck.benchmark_v2_contract import (
    ALL_V2_DETECTORS,
    BENCHMARK_V2_SPEC_VERSION,
    DETECTOR_EXECUTION_V2_SPEC_VERSION,
    DETECTOR_IDENTITY_BY_KEY,
    EVALUATION_V2_SPEC_VERSION,
    DetectorKeyV2,
    FindingCategoryV2,
)
from quantcheck.corpus_schemas import (
    CORPUS_ID_PATTERN,
    CORPUS_UNIT_ID_PATTERN,
    CorpusHorizon,
    CorpusModel,
)
from quantcheck.json_types import parse_canonical_date
from quantcheck.schemas import (
    AUDIT_INPUT_SNAPSHOT_ID_PATTERN,
    AUDIT_REPORT_ID_PATTERN,
    CONTENT_HASH_PATTERN,
    FAULT_ID_PATTERN,
    FINDING_ID_PATTERN,
    MANIFEST_ID_PATTERN,
    AuditInputSnapshot,
    AuditReport,
    BenchmarkDetectorConfigs,
    Finding,
    ScoreReport,
)

__all__ = [
    "BENCHMARK_V2_CASE_ID_PATTERN",
    "BENCHMARK_V2_ID_PATTERN",
    "DETECTOR_EXECUTION_V2_ID_PATTERN",
    "EVALUATION_V2_ID_PATTERN",
    "FINDING_INTERPRETATION_V2_ID_PATTERN",
    "BenchmarkV2CaseConfig",
    "BenchmarkV2CaseMatrix",
    "BenchmarkV2Config",
    "BenchmarkV2Evaluation",
    "BenchmarkV2Profile",
    "DetectorExecutionConfigV2",
    "DetectorExecutionV2",
    "DetectorRunV2",
    "FaultUnitOutcomeV2",
    "FindingInterpretationV2",
    "ProductionFindingInterpretationV2",
]

BENCHMARK_V2_ID_PATTERN = re.compile(r"^bench2_[0-9a-f]{16}$")
BENCHMARK_V2_CASE_ID_PATTERN = re.compile(r"^bcase2_[0-9a-f]{16}$")
DETECTOR_EXECUTION_V2_ID_PATTERN = re.compile(r"^dexec2_[0-9a-f]{16}$")
FINDING_INTERPRETATION_V2_ID_PATTERN = re.compile(r"^fint2_[0-9a-f]{16}$")
EVALUATION_V2_ID_PATTERN = re.compile(r"^eval2_[0-9a-f]{16}$")

_MAX_TOKEN_LENGTH = 512
_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


def _validate_token(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"expected a string, got {type(value).__name__}")
    if not value or value != value.strip():
        raise ValueError("must be a non-blank string without surrounding whitespace")
    if len(value) > _MAX_TOKEN_LENGTH:
        raise ValueError(f"must be at most {_MAX_TOKEN_LENGTH} characters")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError("must not contain control characters")
    return value


def _validate_non_negative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected an integer")
    if value < 0:
        raise ValueError("must not be negative")
    return value


def _validate_positive_int(value: object) -> int:
    validated = _validate_non_negative_int(value)
    if validated == 0:
        raise ValueError("must be positive")
    return validated


def _to_tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


def _pattern_validator(pattern: re.Pattern[str], label: str) -> BeforeValidator:
    def validate(value: object) -> str:
        text = _validate_token(value)
        if pattern.fullmatch(text) is None:
            raise ValueError(f"malformed {label}: {text!r}")
        return text

    return BeforeValidator(validate)


Token = Annotated[str, BeforeValidator(_validate_token)]
NonNegativeInteger = Annotated[int, BeforeValidator(_validate_non_negative_int)]
PositiveInteger = Annotated[int, BeforeValidator(_validate_positive_int)]
ContentHash = Annotated[str, _pattern_validator(CONTENT_HASH_PATTERN, "content hash")]
CorpusId = Annotated[str, _pattern_validator(CORPUS_ID_PATTERN, "corpus_id")]
CorpusUnitId = Annotated[str, _pattern_validator(CORPUS_UNIT_ID_PATTERN, "corpus_unit_id")]
AuditInputId = Annotated[str, _pattern_validator(AUDIT_INPUT_SNAPSHOT_ID_PATTERN, "audit_input_id")]
AuditReportId = Annotated[str, _pattern_validator(AUDIT_REPORT_ID_PATTERN, "audit_report_id")]
ManifestId = Annotated[str, _pattern_validator(MANIFEST_ID_PATTERN, "manifest_id")]
FindingId = Annotated[str, _pattern_validator(FINDING_ID_PATTERN, "finding_id")]
FaultId = Annotated[str, _pattern_validator(FAULT_ID_PATTERN, "fault_id")]
BenchmarkV2Id = Annotated[str, _pattern_validator(BENCHMARK_V2_ID_PATTERN, "benchmark_v2_id")]
BenchmarkV2CaseId = Annotated[
    str, _pattern_validator(BENCHMARK_V2_CASE_ID_PATTERN, "benchmark_v2_case_id")
]
DetectorExecutionV2Id = Annotated[
    str, _pattern_validator(DETECTOR_EXECUTION_V2_ID_PATTERN, "detector_execution_id")
]
FindingInterpretationV2Id = Annotated[
    str,
    _pattern_validator(FINDING_INTERPRETATION_V2_ID_PATTERN, "finding_interpretation_id"),
]
EvaluationV2Id = Annotated[str, _pattern_validator(EVALUATION_V2_ID_PATTERN, "evaluation_id")]


def _validate_date(value: object) -> date:
    if isinstance(value, datetime):
        raise ValueError("expected a day-level date, got datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_canonical_date(value)
    raise ValueError(f"expected date or canonical date string, got {type(value).__name__}")


FinancialDate = Annotated[date, BeforeValidator(_validate_date)]


def _normalize_detectors(value: tuple[DetectorKeyV2, ...]) -> tuple[DetectorKeyV2, ...]:
    if not value:
        raise ValueError("at least one detector must be selected")
    if len(set(value)) != len(value):
        raise ValueError("selected_detectors must not contain duplicates")
    unknown = set(value) - set(ALL_V2_DETECTORS)
    if unknown:
        raise ValueError(f"unsupported detectors: {sorted(unknown)}")
    return tuple(detector for detector in ALL_V2_DETECTORS if detector in value)


SelectedDetectors = Annotated[
    tuple[DetectorKeyV2, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_detectors),
]


class DetectorExecutionConfigV2(CorpusModel):
    """One normalized selection plus the frozen public detector configs."""

    spec_version: Literal["quantcheck/detector-execution/v2"] = DETECTOR_EXECUTION_V2_SPEC_VERSION
    selected_detectors: SelectedDetectors = ALL_V2_DETECTORS
    detector_configs: BenchmarkDetectorConfigs = BenchmarkDetectorConfigs()


class DetectorRunV2(CorpusModel):
    """One frozen detector's unchanged audit report."""

    detector: DetectorKeyV2
    report: AuditReport

    @model_validator(mode="after")
    def _check_identity(self) -> DetectorRunV2:
        detector_id, detector_version = DETECTOR_IDENTITY_BY_KEY[self.detector]
        if (self.report.detector_id, self.report.detector_version) != (
            detector_id,
            detector_version,
        ):
            raise ValueError("detector run identity does not match its selected detector")
        for finding in self.report.findings:
            if (finding.detector_id, finding.detector_version) != (
                detector_id,
                detector_version,
            ):
                raise ValueError("a detector run contains another detector's finding")
        return self


def _normalize_runs(value: tuple[DetectorRunV2, ...]) -> tuple[DetectorRunV2, ...]:
    keys = [run.detector for run in value]
    if len(set(keys)) != len(keys):
        raise ValueError("a detector may run at most once")
    order = {detector: index for index, detector in enumerate(ALL_V2_DETECTORS)}
    return tuple(sorted(value, key=lambda run: order[run.detector]))


DetectorRuns = Annotated[
    tuple[DetectorRunV2, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_runs),
]


class DetectorExecutionV2(CorpusModel):
    """The public result of selected detectors over one sanitized snapshot."""

    detector_execution_id: DetectorExecutionV2Id
    spec_version: Literal["quantcheck/detector-execution/v2"] = DETECTOR_EXECUTION_V2_SPEC_VERSION
    audit_input_id: AuditInputId
    audit_input_hash: ContentHash
    audit_input: AuditInputSnapshot
    dataset_name: Token
    as_of_date: FinancialDate
    config: DetectorExecutionConfigV2
    runs: DetectorRuns
    finding_count: NonNegativeInteger

    @model_validator(mode="after")
    def _check_execution(self) -> DetectorExecutionV2:
        if self.audit_input.audit_input_id != self.audit_input_id:
            raise ValueError("embedded audit input identity disagrees with the execution")
        if (
            self.audit_input.dataset_name != self.dataset_name
            or self.audit_input.as_of_date != self.as_of_date
        ):
            raise ValueError("embedded audit input context disagrees with the execution")
        if tuple(run.detector for run in self.runs) != self.config.selected_detectors:
            raise ValueError("runs must equal the normalized detector selection")
        findings: list[Finding] = []
        for run in self.runs:
            report = run.report
            if report.audit_input_id != self.audit_input_id:
                raise ValueError("every report must describe the selected audit input")
            if report.dataset_name != self.dataset_name or report.as_of_date != self.as_of_date:
                raise ValueError("every report must share the execution context")
            findings.extend(report.findings)
        if self.finding_count != len(findings):
            raise ValueError("finding_count must equal the findings across all runs")
        ids = [finding.finding_id for finding in findings]
        if len(set(ids)) != len(ids):
            raise ValueError("finding identifiers must be unique across selected detectors")
        return self


def _normalize_unique_tokens(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return tuple(sorted(value))


CorpusUnitIds = Annotated[
    tuple[CorpusUnitId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_tokens),
]


def _normalize_severities(value: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        raise ValueError("severities must not be empty")
    if len(set(value)) != len(value):
        raise ValueError("severities must not contain duplicates")
    if set(value) - set(_SEVERITY_ORDER):
        raise ValueError("unsupported severity")
    return tuple(sorted(value, key=_SEVERITY_ORDER.__getitem__))


Severities = Annotated[
    tuple[Literal["low", "medium", "high"], ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_severities),
]


def _normalize_seeds(value: tuple[int, ...]) -> tuple[int, ...]:
    if not value:
        raise ValueError("seeds must not be empty")
    if len(set(value)) != len(value):
        raise ValueError("seeds must not contain duplicates")
    if any(seed not in range(0, 10) and seed not in range(100, 110) for seed in value):
        raise ValueError("v0.2 development evidence permits only development/validation seeds")
    return tuple(sorted(value))


Seeds = Annotated[
    tuple[NonNegativeInteger, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_seeds),
]


class BenchmarkV2Profile(CorpusModel):
    """One fault family over explicitly named corpus units."""

    fault_profile: DetectorKeyV2
    corpus_unit_ids: CorpusUnitIds
    severities: Severities
    seeds: Seeds
    max_targets: PositiveInteger = 100

    @model_validator(mode="after")
    def _check_units(self) -> BenchmarkV2Profile:
        if not self.corpus_unit_ids:
            raise ValueError("a v0.2 profile must name at least one corpus unit")
        return self


def _normalize_profiles(value: tuple[BenchmarkV2Profile, ...]) -> tuple[BenchmarkV2Profile, ...]:
    if not value:
        raise ValueError("a v0.2 benchmark must configure at least one profile")
    keys = [profile.fault_profile for profile in value]
    if len(set(keys)) != len(keys):
        raise ValueError("a fault profile must not be configured twice")
    return tuple(sorted(value, key=lambda profile: profile.fault_profile))


Profiles = Annotated[
    tuple[BenchmarkV2Profile, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_profiles),
]


class BenchmarkV2Config(CorpusModel):
    """The normalized v0.2 development/validation experiment."""

    benchmark_v2_id: BenchmarkV2Id
    spec_version: Literal["quantcheck/benchmark/v2"] = BENCHMARK_V2_SPEC_VERSION
    benchmark_name: Token
    corpus_id: CorpusId
    corpus_freeze_id: Token
    corpus_census_id: Token
    detector_execution: DetectorExecutionConfigV2
    profiles: Profiles

    @model_validator(mode="after")
    def _check_primary_selection(self) -> BenchmarkV2Config:
        selected = set(self.detector_execution.selected_detectors)
        missing = sorted(
            profile.fault_profile
            for profile in self.profiles
            if profile.fault_profile not in selected
        )
        if missing:
            raise ValueError(f"each configured primary detector must be selected: {missing}")
        return self


class BenchmarkV2CaseConfig(CorpusModel):
    """One expanded fault case with a mandatory paired clean control."""

    benchmark_v2_case_id: BenchmarkV2CaseId
    benchmark_v2_id: BenchmarkV2Id
    spec_version: Literal["quantcheck/benchmark/v2"] = BENCHMARK_V2_SPEC_VERSION
    corpus_id: CorpusId
    corpus_freeze_id: Token
    corpus_census_id: Token
    corpus_unit_id: CorpusUnitId
    corpus_unit_content_hash: ContentHash
    partition: Literal["development", "validation"]
    audit_dataset_name: Token
    horizon: CorpusHorizon
    fault_profile: DetectorKeyV2
    injector_spec_version: Token
    severity: Literal["low", "medium", "high"]
    seed: NonNegativeInteger
    seed_class: Literal["development", "validation"]
    max_targets: PositiveInteger
    detector_execution: DetectorExecutionConfigV2
    paired_clean_control: Literal[True] = True
    eligible_unit_count: PositiveInteger

    @model_validator(mode="after")
    def _check_seed_and_primary(self) -> BenchmarkV2CaseConfig:
        expected = "development" if self.seed in range(0, 10) else "validation"
        if self.seed_class != expected:
            raise ValueError("seed_class must match the development/validation seed")
        if self.fault_profile not in self.detector_execution.selected_detectors:
            raise ValueError("the primary detector must be selected")
        return self


def _normalize_cases(value: tuple[BenchmarkV2CaseConfig, ...]) -> tuple[BenchmarkV2CaseConfig, ...]:
    ids = [case.benchmark_v2_case_id for case in value]
    if not value or len(set(ids)) != len(ids):
        raise ValueError("case matrix must be non-empty with unique case identifiers")
    return tuple(sorted(value, key=lambda case: case.benchmark_v2_case_id))


Cases = Annotated[
    tuple[BenchmarkV2CaseConfig, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_cases),
]


class BenchmarkV2CaseMatrix(CorpusModel):
    benchmark_v2_id: BenchmarkV2Id
    spec_version: Literal["quantcheck/benchmark/v2"] = BENCHMARK_V2_SPEC_VERSION
    cases: Cases
    case_count: PositiveInteger

    @model_validator(mode="after")
    def _check_matrix(self) -> BenchmarkV2CaseMatrix:
        if self.case_count != len(self.cases):
            raise ValueError("case_count must equal the expanded case count")
        if any(case.benchmark_v2_id != self.benchmark_v2_id for case in self.cases):
            raise ValueError("every case must belong to this benchmark")
        return self


FindingIds = Annotated[
    tuple[FindingId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_tokens),
]
FaultIds = Annotated[
    tuple[FaultId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_tokens),
]
RuleIds = Annotated[
    tuple[Token, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_tokens),
]


class FindingInterpretationV2(CorpusModel):
    """One unchanged detector finding assigned to exactly one v0.2 category."""

    finding: Finding
    category: FindingCategoryV2
    matched_fault_id: FaultId | None = None
    related_fault_id: FaultId | None = None
    clean_control_finding_ids: FindingIds = ()
    rationale_code: Literal[
        "exact_primary_one_to_one",
        "unique_corruption_related_rule",
        "present_in_paired_clean_control",
        "no_unique_supported_relationship",
    ]

    @model_validator(mode="after")
    def _check_category_shape(self) -> FindingInterpretationV2:
        if self.category == "primary_matched":
            if self.matched_fault_id is None or self.related_fault_id is not None:
                raise ValueError("primary matches require exactly matched_fault_id")
            if self.clean_control_finding_ids:
                raise ValueError("a primary match cannot be a clean-control finding")
        elif self.category == "secondary_corroborating":
            if self.related_fault_id is None or self.matched_fault_id is not None:
                raise ValueError("secondary findings require exactly related_fault_id")
            if self.clean_control_finding_ids:
                raise ValueError("a secondary finding cannot be a clean-control finding")
        elif self.category == "independent_background":
            if not self.clean_control_finding_ids:
                raise ValueError("background findings require clean-control evidence")
            if self.matched_fault_id is not None or self.related_fault_id is not None:
                raise ValueError("background findings do not attach to injected faults")
        elif (
            self.matched_fault_id is not None
            or self.related_fault_id is not None
            or self.clean_control_finding_ids
        ):
            raise ValueError("unmatched findings carry no accepted relationship")
        return self


def _normalize_interpretations(
    value: tuple[FindingInterpretationV2, ...],
) -> tuple[FindingInterpretationV2, ...]:
    ids = [item.finding.finding_id for item in value]
    if len(set(ids)) != len(ids):
        raise ValueError("each finding must be interpreted exactly once")
    return tuple(sorted(value, key=lambda item: item.finding.finding_id))


FindingInterpretations = Annotated[
    tuple[FindingInterpretationV2, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_interpretations),
]


class FaultUnitOutcomeV2(CorpusModel):
    """Primary recall plus corroborating rules for one injected fault unit."""

    fault_id: FaultId
    primary_finding_id: FindingId | None = None
    secondary_finding_ids: FindingIds = ()
    violated_rule_ids: RuleIds = ()


def _normalize_outcomes(value: tuple[FaultUnitOutcomeV2, ...]) -> tuple[FaultUnitOutcomeV2, ...]:
    ids = [outcome.fault_id for outcome in value]
    if len(set(ids)) != len(ids):
        raise ValueError("each injected fault unit must have one outcome")
    secondary = [finding for outcome in value for finding in outcome.secondary_finding_ids]
    if len(set(secondary)) != len(secondary):
        raise ValueError("one finding cannot corroborate multiple injected fault units")
    return tuple(sorted(value, key=lambda outcome: outcome.fault_id))


FaultUnitOutcomes = Annotated[
    tuple[FaultUnitOutcomeV2, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_outcomes),
]


class ProductionFindingInterpretationV2(CorpusModel):
    """Non-metric production interpretation over the complete finding set."""

    finding_interpretation_id: FindingInterpretationV2Id
    spec_version: Literal["quantcheck/finding-evaluation/v2"] = EVALUATION_V2_SPEC_VERSION
    corrupted_execution_id: DetectorExecutionV2Id
    clean_control_execution_id: DetectorExecutionV2Id
    findings: FindingInterpretations
    fault_units: FaultUnitOutcomes
    primary_matched_count: NonNegativeInteger
    secondary_corroborating_count: NonNegativeInteger
    independent_background_count: NonNegativeInteger
    unmatched_count: NonNegativeInteger
    genuinely_unexplained_finding_ids: FindingIds = ()

    @model_validator(mode="after")
    def _check_partition(self) -> ProductionFindingInterpretationV2:
        counts = {
            category: sum(1 for item in self.findings if item.category == category)
            for category in (
                "primary_matched",
                "secondary_corroborating",
                "independent_background",
                "unmatched",
            )
        }
        expected = (
            self.primary_matched_count,
            self.secondary_corroborating_count,
            self.independent_background_count,
            self.unmatched_count,
        )
        if expected != tuple(counts.values()):
            raise ValueError("category counts must partition the interpreted findings")
        unexplained = tuple(
            sorted(
                item.finding.finding_id for item in self.findings if item.category == "unmatched"
            )
        )
        if self.genuinely_unexplained_finding_ids != unexplained:
            raise ValueError("genuinely unexplained ids must equal the unmatched category")
        primary_ids = {
            item.finding.finding_id for item in self.findings if item.category == "primary_matched"
        }
        secondary_ids = {
            item.finding.finding_id
            for item in self.findings
            if item.category == "secondary_corroborating"
        }
        if {
            outcome.primary_finding_id
            for outcome in self.fault_units
            if outcome.primary_finding_id is not None
        } != primary_ids:
            raise ValueError("fault-unit primary outcomes must cover primary findings exactly")
        if {
            finding_id
            for outcome in self.fault_units
            for finding_id in outcome.secondary_finding_ids
        } != secondary_ids:
            raise ValueError("fault-unit secondary outcomes must cover secondary findings exactly")
        outcomes = {outcome.fault_id: outcome for outcome in self.fault_units}
        for item in self.findings:
            if item.category == "primary_matched":
                assert item.matched_fault_id is not None
                outcome = outcomes.get(item.matched_fault_id)
                if outcome is None or outcome.primary_finding_id != item.finding.finding_id:
                    raise ValueError(
                        "primary finding relationship must match its fault-unit outcome"
                    )
            elif item.category == "secondary_corroborating":
                assert item.related_fault_id is not None
                outcome = outcomes.get(item.related_fault_id)
                if outcome is None or item.finding.finding_id not in outcome.secondary_finding_ids:
                    raise ValueError(
                        "secondary finding relationship must match its fault-unit outcome"
                    )
        findings_by_id = {item.finding.finding_id: item.finding for item in self.findings}
        for outcome in self.fault_units:
            attached = (
                (outcome.primary_finding_id,) if outcome.primary_finding_id is not None else ()
            ) + outcome.secondary_finding_ids
            expected_rules = tuple(
                sorted({findings_by_id[finding_id].rule_id for finding_id in attached})
            )
            if outcome.violated_rule_ids != expected_rules:
                raise ValueError("fault-unit violated rules must equal its attached findings")
        return self


class BenchmarkV2Evaluation(CorpusModel):
    """Strict v0.1-comparable score beside the v0.2 finding interpretation."""

    evaluation_id: EvaluationV2Id
    spec_version: Literal["quantcheck/finding-evaluation/v2"] = EVALUATION_V2_SPEC_VERSION
    primary_fault_profile: DetectorKeyV2
    manifest_id: ManifestId
    detector_selection: SelectedDetectors
    corrupted_execution_id: DetectorExecutionV2Id
    clean_control_execution_id: DetectorExecutionV2Id
    strict_primary_audit_report: AuditReport
    strict_primary_score: ScoreReport
    v0_1_all_detector_comparable: bool
    injected_fault_count: PositiveInteger
    primary_matched_fault_count: NonNegativeInteger
    primary_missed_fault_count: NonNegativeInteger
    all_primary_faults_detected: bool
    production_interpretation: ProductionFindingInterpretationV2

    @model_validator(mode="after")
    def _check_evaluation(self) -> BenchmarkV2Evaluation:
        if self.strict_primary_score.manifest_id != self.manifest_id:
            raise ValueError("strict score must reference the evaluated manifest")
        if (
            self.strict_primary_score.audit_report_id
            != self.strict_primary_audit_report.audit_report_id
        ):
            raise ValueError("strict score must reference the combined strict report")
        metrics = self.strict_primary_score.metrics
        if self.injected_fault_count != metrics.injected_faults:
            raise ValueError("injected fault count must come from the strict score")
        if self.primary_matched_fault_count != metrics.true_positive_faults:
            raise ValueError("primary matched count must come from exact one-to-one scoring")
        if self.primary_missed_fault_count != metrics.false_negative_faults:
            raise ValueError("primary missed count must come from exact one-to-one scoring")
        if self.all_primary_faults_detected != (self.primary_missed_fault_count == 0):
            raise ValueError("all_primary_faults_detected must reflect the missed count")
        if self.v0_1_all_detector_comparable != (self.detector_selection == ALL_V2_DETECTORS):
            raise ValueError("v0.1 comparability requires the exact all-detector selection")
        interpretation = self.production_interpretation
        if (
            interpretation.corrupted_execution_id != self.corrupted_execution_id
            or interpretation.clean_control_execution_id != self.clean_control_execution_id
        ):
            raise ValueError("production interpretation must reference both executions")
        strict_finding_ids = {
            finding.finding_id for finding in self.strict_primary_audit_report.findings
        }
        interpreted_finding_ids = {item.finding.finding_id for item in interpretation.findings}
        if strict_finding_ids != interpreted_finding_ids:
            raise ValueError("production interpretation must preserve every strict finding once")
        strict_matches = {
            match.finding_id: match.fault_id for match in self.strict_primary_score.matches
        }
        interpreted_matches = {
            item.finding.finding_id: item.matched_fault_id
            for item in interpretation.findings
            if item.category == "primary_matched"
        }
        if strict_matches != interpreted_matches:
            raise ValueError("production primary matches must equal strict one-to-one matches")
        if interpretation.primary_matched_count != self.primary_matched_fault_count:
            raise ValueError("production primary count must equal the strict matched-fault count")
        expected_fault_ids = {match.fault_id for match in self.strict_primary_score.matches} | set(
            self.strict_primary_score.missed_fault_ids
        )
        if {outcome.fault_id for outcome in interpretation.fault_units} != expected_fault_ids:
            raise ValueError("production fault outcomes must cover every injected fault exactly")
        if len(interpretation.fault_units) != self.injected_fault_count:
            raise ValueError("production fault outcomes must equal the injected-fault count")
        return self
