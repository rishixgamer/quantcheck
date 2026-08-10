"""Clean-control, research, and held-out evaluation for Missing Observations."""

from __future__ import annotations

import re
from decimal import Decimal, localcontext
from typing import Annotated, Final, Literal

from pydantic import BeforeValidator, model_validator

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.hashing import canonical_sha256, stable_id
from quantcheck.json_types import canonical_decimal_string, parse_canonical_decimal
from quantcheck.missing_observation_contract import (
    MissingnessMechanism,
)
from quantcheck.missing_observation_detection import detect_missing_observations
from quantcheck.missing_observation_fixture import (
    EVALUATION_MECHANISMS,
    MISSING_OBSERVATION_EVALUATION_CONFIGURATION_HASH,
    MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
    build_missing_observation_evaluation_case,
    evaluation_case_ids,
)
from quantcheck.missing_observation_gate import (
    active_missing_observation_heldout_authorization,
)
from quantcheck.missing_observation_injection import inject_missing_observations
from quantcheck.missing_observation_replay import (
    manifest_assisted_exact_missing_observation_replay,
)
from quantcheck.missing_observation_research import compare_missing_observation_research
from quantcheck.missing_observation_scoring import score_missing_observations
from quantcheck.schemas import CanonicalModel

__all__ = [
    "MISSING_OBSERVATION_EVALUATION_SPEC_VERSION",
    "MissingObservationCaseEvaluationV1",
    "MissingObservationEvaluationEvidenceV1",
    "MissingObservationMechanismEvaluationV1",
    "MissingObservationPartitionEvaluationV1",
    "evaluate_missing_observation_case",
    "evaluate_missing_observation_partition",
    "missing_observation_evaluation_identity_matches",
    "run_missing_observation_evaluation",
]

MISSING_OBSERVATION_EVALUATION_SPEC_VERSION: Final = "quantcheck/missing-observation-evaluation/v1"
EvaluationPartition = Literal["development", "validation", "heldout"]

_TOKEN_MAX = 512
_EVALUATION_ID_PATTERN = re.compile(r"^meval_[0-9a-f]{16}$")
_CASE_ID_PATTERN = re.compile(r"^mcase_[0-9a-f]{16}$")
_FREEZE_ID_PATTERN = re.compile(r"^mefreeze_[0-9a-f]{16}$")
_CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _validate_token(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("must be a non-blank string without surrounding whitespace")
    if len(value) > _TOKEN_MAX:
        raise ValueError("token is too long")
    return value


def _validate_non_negative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("expected a non-negative integer")
    return value


def _validate_decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not a decimal")
    if isinstance(value, Decimal):
        canonical_decimal_string(value)
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return parse_canonical_decimal(value)
    raise ValueError("expected a Decimal, integer, or canonical decimal string")


def _validate_evaluation_id(value: object) -> str:
    token = _validate_token(value)
    if _EVALUATION_ID_PATTERN.fullmatch(token) is None:
        raise ValueError("malformed evaluation id")
    return token


def _pattern_validator(pattern: re.Pattern[str], label: str) -> BeforeValidator:
    def validate(value: object) -> str:
        token = _validate_token(value)
        if pattern.fullmatch(token) is None:
            raise ValueError(f"malformed {label}")
        return token

    return BeforeValidator(validate)


def _to_tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


Token = Annotated[str, BeforeValidator(_validate_token)]
NonNegativeInteger = Annotated[int, BeforeValidator(_validate_non_negative_int)]
CanonicalDecimal = Annotated[Decimal, BeforeValidator(_validate_decimal)]
EvaluationId = Annotated[str, BeforeValidator(_validate_evaluation_id)]
CaseId = Annotated[str, _pattern_validator(_CASE_ID_PATTERN, "case id")]
FreezeId = Annotated[str, _pattern_validator(_FREEZE_ID_PATTERN, "freeze id")]
ContentHash = Annotated[str, _pattern_validator(_CONTENT_HASH_PATTERN, "content hash")]


class MissingObservationCaseEvaluationV1(CanonicalModel):
    case_id: CaseId
    partition: EvaluationPartition
    mechanism: MissingnessMechanism
    seed: NonNegativeInteger
    detector_config_id: Token
    detector_config_hash: ContentHash
    injection_config_hash: ContentHash
    clean_control_report_id: Token
    clean_control_finding_count: NonNegativeInteger
    corrupted_report_id: Token
    manifest_id: Token
    score_report_id: Token
    injected_faults: NonNegativeInteger
    findings: NonNegativeInteger
    true_positive_faults: NonNegativeInteger
    false_positive_findings: NonNegativeInteger
    false_negative_faults: NonNegativeInteger
    precision: CanonicalDecimal | None
    recall: CanonicalDecimal | None
    f1: CanonicalDecimal | None
    research_changed: bool
    exact_restoration: bool

    @model_validator(mode="after")
    def _check_case(self) -> MissingObservationCaseEvaluationV1:
        if self.clean_control_finding_count != 0:
            raise ValueError("a held evaluation case requires a clean control with zero findings")
        if self.true_positive_faults + self.false_negative_faults != self.injected_faults:
            raise ValueError("fault counts do not partition injected faults")
        if self.true_positive_faults + self.false_positive_findings != self.findings:
            raise ValueError("finding counts do not partition findings")
        expected_precision = _ratio(self.true_positive_faults, self.findings)
        expected_recall = _ratio(self.true_positive_faults, self.injected_faults)
        if (
            self.precision != expected_precision
            or self.recall != expected_recall
            or self.f1 != _f1(expected_precision, expected_recall)
        ):
            raise ValueError("case metrics are arithmetically inconsistent")
        return self


class MissingObservationMechanismEvaluationV1(CanonicalModel):
    mechanism: MissingnessMechanism
    case_count: Literal[1] = 1
    injected_faults: NonNegativeInteger
    findings: NonNegativeInteger
    true_positive_faults: NonNegativeInteger
    false_positive_findings: NonNegativeInteger
    false_negative_faults: NonNegativeInteger
    clean_control_findings: NonNegativeInteger
    research_changed_cases: NonNegativeInteger
    exact_restoration_cases: NonNegativeInteger
    precision: CanonicalDecimal | None
    recall: CanonicalDecimal | None
    f1: CanonicalDecimal | None

    @model_validator(mode="after")
    def _check_mechanism(self) -> MissingObservationMechanismEvaluationV1:
        if self.true_positive_faults + self.false_negative_faults != self.injected_faults:
            raise ValueError("mechanism fault counts are inconsistent")
        if self.true_positive_faults + self.false_positive_findings != self.findings:
            raise ValueError("mechanism finding counts are inconsistent")
        expected_precision = _ratio(self.true_positive_faults, self.findings)
        expected_recall = _ratio(self.true_positive_faults, self.injected_faults)
        if (
            self.precision != expected_precision
            or self.recall != expected_recall
            or self.f1 != _f1(expected_precision, expected_recall)
        ):
            raise ValueError("mechanism metrics are arithmetically inconsistent")
        if self.research_changed_cases > self.case_count:
            raise ValueError("research-changed cases exceed mechanism cases")
        if self.exact_restoration_cases > self.case_count:
            raise ValueError("restoration cases exceed mechanism cases")
        return self


MechanismResults = Annotated[
    tuple[MissingObservationMechanismEvaluationV1, ...],
    BeforeValidator(_to_tuple),
]


class MissingObservationPartitionEvaluationV1(CanonicalModel):
    partition: EvaluationPartition
    case_count: NonNegativeInteger
    mechanism_results: MechanismResults
    injected_faults: NonNegativeInteger
    findings: NonNegativeInteger
    true_positive_faults: NonNegativeInteger
    false_positive_findings: NonNegativeInteger
    false_negative_faults: NonNegativeInteger
    clean_control_findings: NonNegativeInteger
    research_changed_cases: NonNegativeInteger
    exact_restoration_cases: NonNegativeInteger
    precision: CanonicalDecimal | None
    recall: CanonicalDecimal | None
    f1: CanonicalDecimal | None

    @model_validator(mode="after")
    def _check_partition(self) -> MissingObservationPartitionEvaluationV1:
        if self.case_count != len(self.mechanism_results):
            raise ValueError("case_count must equal mechanism result count")
        if tuple(result.mechanism for result in self.mechanism_results) != EVALUATION_MECHANISMS:
            raise ValueError("every mechanism must be evaluated once in contract order")
        summed_fields = (
            "injected_faults",
            "findings",
            "true_positive_faults",
            "false_positive_findings",
            "false_negative_faults",
            "clean_control_findings",
            "research_changed_cases",
            "exact_restoration_cases",
        )
        for field in summed_fields:
            if getattr(self, field) != sum(
                getattr(result, field) for result in self.mechanism_results
            ):
                raise ValueError(f"partition {field} is inconsistent")
        expected_precision = _ratio(self.true_positive_faults, self.findings)
        expected_recall = _ratio(self.true_positive_faults, self.injected_faults)
        if (
            self.precision != expected_precision
            or self.recall != expected_recall
            or self.f1 != _f1(expected_precision, expected_recall)
        ):
            raise ValueError("partition metrics are arithmetically inconsistent")
        return self


class MissingObservationEvaluationEvidenceV1(CanonicalModel):
    evaluation_id: EvaluationId
    spec_version: Literal["quantcheck/missing-observation-evaluation/v1"] = (
        MISSING_OBSERVATION_EVALUATION_SPEC_VERSION
    )
    freeze_id: FreezeId
    configuration_hash: ContentHash
    development: MissingObservationPartitionEvaluationV1
    validation: MissingObservationPartitionEvaluationV1
    heldout: MissingObservationPartitionEvaluationV1
    synthetic_contract_evidence: Literal[True] = True
    customer_evidence: Literal[False] = False

    @model_validator(mode="after")
    def _check_partitions(self) -> MissingObservationEvaluationEvidenceV1:
        if (
            self.development.partition,
            self.validation.partition,
            self.heldout.partition,
        ) != ("development", "validation", "heldout"):
            raise ValueError("evaluation partitions are mislabelled")
        if self.freeze_id != MISSING_OBSERVATION_EVALUATION_FREEZE_ID:
            raise ValueError("evaluation freeze identity is not the frozen configuration")
        if self.configuration_hash != MISSING_OBSERVATION_EVALUATION_CONFIGURATION_HASH:
            raise ValueError("evaluation configuration hash is not frozen")
        return self


def _evaluation_id(body: object) -> str:
    return stable_id(
        prefix="meval",
        namespace="quantcheck/missing-observation-evaluation-evidence/v1",
        payload=body,
    )


def missing_observation_evaluation_identity_matches(
    evidence: MissingObservationEvaluationEvidenceV1,
) -> bool:
    body = {
        name: getattr(evidence, name)
        for name in MissingObservationEvaluationEvidenceV1.model_fields
        if name != "evaluation_id"
    }
    return evidence.evaluation_id == _evaluation_id(body)


def _ratio(numerator: int, denominator: int) -> Decimal | None:
    if denominator == 0:
        return None
    with localcontext() as context:
        context.prec = 50
        return Decimal(numerator) / Decimal(denominator)


def _f1(precision: Decimal | None, recall: Decimal | None) -> Decimal | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return Decimal(0)
    with localcontext() as context:
        context.prec = 50
        return Decimal(2) * precision * recall / (precision + recall)


def evaluate_missing_observation_case(
    partition: EvaluationPartition,
    mechanism: MissingnessMechanism,
) -> MissingObservationCaseEvaluationV1:
    case = build_missing_observation_evaluation_case(partition, mechanism)
    clean_audit_input = sanitize_for_audit(case.clean_snapshot)
    clean_report = detect_missing_observations(clean_audit_input, case.detector_config)
    if clean_report.findings:
        raise ValueError("clean control produced Missing Observations findings")
    corrupted, manifest = inject_missing_observations(
        case.clean_snapshot,
        case.detector_config,
        case.injection_config,
    )
    corrupted_audit_input = sanitize_for_audit(corrupted)
    corrupted_report = detect_missing_observations(corrupted_audit_input, case.detector_config)
    score = score_missing_observations(corrupted_report, manifest)
    repaired = manifest_assisted_exact_missing_observation_replay(corrupted, manifest)
    impact = compare_missing_observation_research(
        case.clean_snapshot,
        corrupted,
        repaired,
        case.detector_config,
    )
    metrics = score.metrics
    return MissingObservationCaseEvaluationV1(
        case_id=case.case_id,
        partition=partition,
        mechanism=mechanism,
        seed=case.injection_config.seed,
        detector_config_id=case.detector_config.detector_config_id,
        detector_config_hash=canonical_sha256(case.detector_config),
        injection_config_hash=canonical_sha256(case.injection_config),
        clean_control_report_id=clean_report.audit_report_id,
        clean_control_finding_count=len(clean_report.findings),
        corrupted_report_id=corrupted_report.audit_report_id,
        manifest_id=manifest.manifest_id,
        score_report_id=score.score_report_id,
        injected_faults=metrics.injected_faults,
        findings=metrics.findings,
        true_positive_faults=metrics.true_positive_faults,
        false_positive_findings=metrics.false_positive_findings,
        false_negative_faults=metrics.false_negative_faults,
        precision=metrics.precision,
        recall=metrics.recall,
        f1=score.f1,
        research_changed=impact.changed,
        exact_restoration=impact.exact_restoration,
    )


def _mechanism_summary(
    case: MissingObservationCaseEvaluationV1,
) -> MissingObservationMechanismEvaluationV1:
    return MissingObservationMechanismEvaluationV1(
        mechanism=case.mechanism,
        case_count=1,
        injected_faults=case.injected_faults,
        findings=case.findings,
        true_positive_faults=case.true_positive_faults,
        false_positive_findings=case.false_positive_findings,
        false_negative_faults=case.false_negative_faults,
        clean_control_findings=case.clean_control_finding_count,
        research_changed_cases=int(case.research_changed),
        exact_restoration_cases=int(case.exact_restoration),
        precision=case.precision,
        recall=case.recall,
        f1=case.f1,
    )


def evaluate_missing_observation_partition(
    partition: EvaluationPartition,
) -> MissingObservationPartitionEvaluationV1:
    if partition == "heldout":
        authorization = active_missing_observation_heldout_authorization()
        if (
            authorization is None
            or authorization.freeze_id != MISSING_OBSERVATION_EVALUATION_FREEZE_ID
            or authorization.case_ids != evaluation_case_ids("heldout")
        ):
            raise PermissionError(
                "held-out evaluation requires authorization for the complete frozen case set"
            )
    cases = tuple(
        evaluate_missing_observation_case(partition, mechanism)
        for mechanism in EVALUATION_MECHANISMS
    )
    summaries = tuple(_mechanism_summary(case) for case in cases)
    injected_faults = sum(case.injected_faults for case in cases)
    findings = sum(case.findings for case in cases)
    true_positives = sum(case.true_positive_faults for case in cases)
    false_positives = sum(case.false_positive_findings for case in cases)
    false_negatives = sum(case.false_negative_faults for case in cases)
    precision = _ratio(true_positives, findings)
    recall = _ratio(true_positives, injected_faults)
    return MissingObservationPartitionEvaluationV1(
        partition=partition,
        case_count=len(cases),
        mechanism_results=summaries,
        injected_faults=injected_faults,
        findings=findings,
        true_positive_faults=true_positives,
        false_positive_findings=false_positives,
        false_negative_faults=false_negatives,
        clean_control_findings=sum(case.clean_control_finding_count for case in cases),
        research_changed_cases=sum(int(case.research_changed) for case in cases),
        exact_restoration_cases=sum(int(case.exact_restoration) for case in cases),
        precision=precision,
        recall=recall,
        f1=_f1(precision, recall),
    )


def run_missing_observation_evaluation() -> MissingObservationEvaluationEvidenceV1:
    """Run development, validation, then the separately authorized holdout."""
    development = evaluate_missing_observation_partition("development")
    validation = evaluate_missing_observation_partition("validation")
    heldout = evaluate_missing_observation_partition("heldout")
    body: dict[str, object] = {
        "spec_version": MISSING_OBSERVATION_EVALUATION_SPEC_VERSION,
        "freeze_id": MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
        "configuration_hash": MISSING_OBSERVATION_EVALUATION_CONFIGURATION_HASH,
        "development": development,
        "validation": validation,
        "heldout": heldout,
        "synthetic_contract_evidence": True,
        "customer_evidence": False,
    }
    return MissingObservationEvaluationEvidenceV1.model_validate(
        {"evaluation_id": _evaluation_id(body), **body}
    )
