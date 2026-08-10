"""Additive contracts for contextual Missing Observations.

The released v0.1 schema surface is frozen.  This module therefore defines a
new, additive contract instead of extending the v0.1 ``Finding`` evidence
union or its score-report version literal.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, localcontext
from typing import Annotated, Final, Literal, NamedTuple

from pydantic import AfterValidator, BeforeValidator, model_validator

from quantcheck.hashing import stable_id
from quantcheck.json_types import (
    canonical_decimal_string,
    parse_canonical_date,
    parse_canonical_decimal,
)
from quantcheck.schemas import (
    CONTENT_HASH_PATTERN,
    RECORD_ID_PATTERN,
    AuditInputSnapshot,
    CanonicalModel,
    DatasetSnapshot,
    DetectionMetrics,
    Dimension,
    FinancialFact,
)

__all__ = [
    "EXPECTATION_CONTEXT_TO_MECHANISM",
    "MISSING_OBSERVATION_DETECTOR_ID",
    "MISSING_OBSERVATION_DETECTOR_VERSION",
    "MISSING_OBSERVATION_FAULT_TYPE",
    "MISSING_OBSERVATION_SCORING_SPEC_VERSION",
    "MISSING_OBSERVATION_SPEC_VERSION",
    "ExpectedObservationV1",
    "MissingObservationAuditReportV1",
    "MissingObservationDetectorConfigV1",
    "MissingObservationEligibilityUnitV1",
    "MissingObservationEvidenceV1",
    "MissingObservationExactMatchV1",
    "MissingObservationFindingV1",
    "MissingObservationInjectionConfigV1",
    "MissingObservationManifestEntryV1",
    "MissingObservationManifestV1",
    "MissingObservationResearchImpactV1",
    "MissingObservationResearchResultV1",
    "MissingObservationScoreReportV1",
    "MissingObservationSeriesKeyV1",
    "MissingnessMechanism",
    "build_expected_observation",
    "build_missing_observation_detector_config",
    "detector_config_identity_matches",
    "expectation_context_for_mechanism",
    "expectation_identity_matches",
    "finding_identity_matches",
    "injection_severity_profile",
    "missing_audit_report_identity_matches",
    "missing_detector_config_id",
    "missing_expected_observation_id",
    "missing_fault_id",
    "missing_finding_id",
    "missing_impact_id",
    "missing_manifest_id",
    "missing_research_result_id",
    "missing_score_report_id",
]

MISSING_OBSERVATION_SPEC_VERSION: Final = "quantcheck/missing-observation/v1"
MISSING_OBSERVATION_FAULT_TYPE: Final = "missing_observation"
MISSING_OBSERVATION_DETECTOR_ID: Final = "quantcheck.missing_observation_detector"
MISSING_OBSERVATION_DETECTOR_VERSION: Final = "quantcheck/missing-observation-detector/v1"
MISSING_OBSERVATION_SCORING_SPEC_VERSION: Final = "quantcheck/missing-observation-scoring/v1"

MissingnessMechanism = Literal[
    "random_missingness",
    "periodic_reporting_gap",
    "entity_dependent_missingness",
    "concept_dependent_missingness",
    "survivorship_like_filtering",
    "source_feed_outage",
]
ExpectationContext = Literal[
    "explicit_required_observation",
    "declared_reporting_schedule",
    "declared_entity_coverage",
    "declared_concept_coverage",
    "declared_survivorship_cohort",
    "declared_source_feed_coverage",
]
MissingSeverity = Literal["low", "medium", "high"]
FindingSeverity = Literal["low", "medium", "high"]

EXPECTATION_CONTEXT_TO_MECHANISM: dict[ExpectationContext, MissingnessMechanism] = {
    "explicit_required_observation": "random_missingness",
    "declared_reporting_schedule": "periodic_reporting_gap",
    "declared_entity_coverage": "entity_dependent_missingness",
    "declared_concept_coverage": "concept_dependent_missingness",
    "declared_survivorship_cohort": "survivorship_like_filtering",
    "declared_source_feed_coverage": "source_feed_outage",
}
_MECHANISM_TO_CONTEXT = {value: key for key, value in EXPECTATION_CONTEXT_TO_MECHANISM.items()}

CONTEXT_TO_RULE_ID: dict[ExpectationContext, str] = {
    "explicit_required_observation": "missing.explicit_expected_observation",
    "declared_reporting_schedule": "missing.reporting_gap",
    "declared_entity_coverage": "missing.entity_coverage_gap",
    "declared_concept_coverage": "missing.concept_coverage_gap",
    "declared_survivorship_cohort": "missing.survivorship_cohort_gap",
    "declared_source_feed_coverage": "missing.source_feed_outage",
}
CONTEXT_TO_SUBTYPE: dict[ExpectationContext, str] = {
    "explicit_required_observation": "explicit_expected_observation",
    "declared_reporting_schedule": "periodic_reporting_gap",
    "declared_entity_coverage": "entity_dependent_missingness",
    "declared_concept_coverage": "concept_dependent_missingness",
    "declared_survivorship_cohort": "survivorship_like_filtering",
    "declared_source_feed_coverage": "source_feed_outage",
}
CONTEXT_TO_SEVERITY: dict[ExpectationContext, FindingSeverity] = {
    "explicit_required_observation": "low",
    "declared_reporting_schedule": "medium",
    "declared_entity_coverage": "medium",
    "declared_concept_coverage": "medium",
    "declared_survivorship_cohort": "high",
    "declared_source_feed_coverage": "high",
}

_MAX_TOKEN_LENGTH = 512
_EXPECTED_ID_PATTERN = re.compile(r"^mexp_[0-9a-f]{16}$")
_CONFIG_ID_PATTERN = re.compile(r"^mconf_[0-9a-f]{16}$")
_FAULT_ID_PATTERN = re.compile(r"^fault_[0-9a-f]{16}$")
_MANIFEST_ID_PATTERN = re.compile(r"^man_[0-9a-f]{16}$")
_FINDING_ID_PATTERN = re.compile(r"^find_[0-9a-f]{16}$")
_REPORT_ID_PATTERN = re.compile(r"^arep_[0-9a-f]{16}$")
_SCORE_ID_PATTERN = re.compile(r"^score_[0-9a-f]{16}$")
_RESEARCH_ID_PATTERN = re.compile(r"^rsch_[0-9a-f]{16}$")
_IMPACT_ID_PATTERN = re.compile(r"^impact_[0-9a-f]{16}$")


def _validate_token(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("expected a string")
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
    result = _validate_non_negative_int(value)
    if result == 0:
        raise ValueError("must be positive")
    return result


def _validate_date(value: object) -> date:
    if isinstance(value, datetime):
        raise ValueError("expected a day-level date")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_canonical_date(value)
    raise ValueError("expected a date or canonical date string")


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


def _to_tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


def _pattern_validator(pattern: re.Pattern[str], label: str) -> BeforeValidator:
    def validate(value: object) -> str:
        token = _validate_token(value)
        if pattern.fullmatch(token) is None:
            raise ValueError(f"malformed {label}: {token!r}")
        return token

    return BeforeValidator(validate)


Token = Annotated[str, BeforeValidator(_validate_token)]
FinancialDate = Annotated[date, BeforeValidator(_validate_date)]
CanonicalDecimal = Annotated[Decimal, BeforeValidator(_validate_decimal)]
NonNegativeInteger = Annotated[int, BeforeValidator(_validate_non_negative_int)]
PositiveInteger = Annotated[int, BeforeValidator(_validate_positive_int)]
ContentHash = Annotated[str, _pattern_validator(CONTENT_HASH_PATTERN, "content hash")]
RecordId = Annotated[str, _pattern_validator(RECORD_ID_PATTERN, "record_id")]
ExpectedObservationId = Annotated[
    str, _pattern_validator(_EXPECTED_ID_PATTERN, "expected_observation_id")
]
DetectorConfigId = Annotated[str, _pattern_validator(_CONFIG_ID_PATTERN, "detector_config_id")]
FaultId = Annotated[str, _pattern_validator(_FAULT_ID_PATTERN, "fault_id")]
ManifestId = Annotated[str, _pattern_validator(_MANIFEST_ID_PATTERN, "manifest_id")]
FindingId = Annotated[str, _pattern_validator(_FINDING_ID_PATTERN, "finding_id")]
ReportId = Annotated[str, _pattern_validator(_REPORT_ID_PATTERN, "audit_report_id")]
ScoreId = Annotated[str, _pattern_validator(_SCORE_ID_PATTERN, "score_report_id")]
ResearchId = Annotated[str, _pattern_validator(_RESEARCH_ID_PATTERN, "research_result_id")]
ImpactId = Annotated[str, _pattern_validator(_IMPACT_ID_PATTERN, "impact_id")]


def _normalize_dimensions(value: tuple[Dimension, ...]) -> tuple[Dimension, ...]:
    axes = [dimension.axis for dimension in value]
    if len(set(axes)) != len(axes):
        raise ValueError("dimension axes must be unique")
    return tuple(sorted(value, key=lambda dimension: dimension.axis))


Dimensions = Annotated[
    tuple[Dimension, ...], BeforeValidator(_to_tuple), AfterValidator(_normalize_dimensions)
]


def _normalize_unique_tokens(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return tuple(sorted(value))


RecordIds = Annotated[
    tuple[RecordId, ...], BeforeValidator(_to_tuple), AfterValidator(_normalize_unique_tokens)
]
ExpectedObservationIds = Annotated[
    tuple[ExpectedObservationId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_tokens),
]
EntityIds = Annotated[
    tuple[Token, ...], BeforeValidator(_to_tuple), AfterValidator(_normalize_unique_tokens)
]


def missing_expected_observation_id(*, body: object) -> str:
    return stable_id(prefix="mexp", namespace="quantcheck/missing-expectation/v1", payload=body)


def missing_detector_config_id(*, body: object) -> str:
    return stable_id(
        prefix="mconf",
        namespace="quantcheck/missing-detector-config/v1",
        payload=body,
    )


def missing_fault_id(*, body: object) -> str:
    return stable_id(prefix="fault", namespace="quantcheck/missing-fault/v1", payload=body)


def missing_manifest_id(*, body: object) -> str:
    return stable_id(prefix="man", namespace="quantcheck/missing-manifest/v1", payload=body)


def missing_finding_id(*, body: object) -> str:
    return stable_id(prefix="find", namespace="quantcheck/missing-finding/v1", payload=body)


def missing_audit_report_id(*, body: object) -> str:
    return stable_id(prefix="arep", namespace="quantcheck/missing-audit-report/v1", payload=body)


def missing_score_report_id(*, body: object) -> str:
    return stable_id(prefix="score", namespace="quantcheck/missing-score-report/v1", payload=body)


def missing_research_result_id(*, body: object) -> str:
    return stable_id(prefix="rsch", namespace="quantcheck/missing-research-result/v1", payload=body)


def missing_impact_id(*, body: object) -> str:
    return stable_id(prefix="impact", namespace="quantcheck/missing-impact/v1", payload=body)


def expectation_context_for_mechanism(mechanism: MissingnessMechanism) -> ExpectationContext:
    return _MECHANISM_TO_CONTEXT[mechanism]


class MissingObservationSeverityProfile(NamedTuple):
    target_fraction: Decimal


_SEVERITY_PROFILES: dict[MissingSeverity, MissingObservationSeverityProfile] = {
    "low": MissingObservationSeverityProfile(Decimal("0.10")),
    "medium": MissingObservationSeverityProfile(Decimal("0.25")),
    "high": MissingObservationSeverityProfile(Decimal("0.50")),
}


def injection_severity_profile(severity: MissingSeverity) -> MissingObservationSeverityProfile:
    return _SEVERITY_PROFILES[severity]


class MissingObservationSeriesKeyV1(CanonicalModel):
    """Exact public series identity used by one declared expectation."""

    entity_id: Token
    concept_namespace: Token
    concept: Token
    unit: Token
    dimensions: Dimensions = ()
    period_type: Literal["instant", "duration"]
    source_name: Token
    source_locator: Token


class ExpectedObservationV1(CanonicalModel):
    """One source/customer-supported cell that should exist by a declared day."""

    expected_observation_id: ExpectedObservationId
    spec_version: Literal["quantcheck/missing-observation/v1"] = MISSING_OBSERVATION_SPEC_VERSION
    context: ExpectationContext
    series: MissingObservationSeriesKeyV1
    period_start: FinancialDate | None = None
    period_end: FinancialDate
    expected_by: FinancialDate
    evidence_reference: Token

    @model_validator(mode="after")
    def _check_shape(self) -> ExpectedObservationV1:
        if self.series.period_type == "instant" and self.period_start is not None:
            raise ValueError("an instant expectation must not have period_start")
        if self.series.period_type == "duration":
            if self.period_start is None:
                raise ValueError("a duration expectation requires period_start")
            if self.period_start > self.period_end:
                raise ValueError("period_start must not be after period_end")
        if self.expected_by < self.period_end:
            raise ValueError("expected_by must not precede the economic period end")
        return self


def _expectation_body(expectation: ExpectedObservationV1) -> dict[str, object]:
    return {
        name: getattr(expectation, name)
        for name in ExpectedObservationV1.model_fields
        if name != "expected_observation_id"
    }


def expectation_identity_matches(expectation: ExpectedObservationV1) -> bool:
    return expectation.expected_observation_id == missing_expected_observation_id(
        body=_expectation_body(expectation)
    )


def build_expected_observation(
    *,
    context: ExpectationContext,
    series: MissingObservationSeriesKeyV1,
    period_start: date | None,
    period_end: date,
    expected_by: date,
    evidence_reference: str,
) -> ExpectedObservationV1:
    body: dict[str, object] = {
        "spec_version": MISSING_OBSERVATION_SPEC_VERSION,
        "context": context,
        "series": series,
        "period_start": period_start,
        "period_end": period_end,
        "expected_by": expected_by,
        "evidence_reference": evidence_reference,
    }
    return ExpectedObservationV1.model_validate(
        {"expected_observation_id": missing_expected_observation_id(body=body), **body}
    )


def _normalize_expectations(
    value: tuple[ExpectedObservationV1, ...],
) -> tuple[ExpectedObservationV1, ...]:
    if not value:
        raise ValueError("at least one explicit expectation is required")
    ids = [expectation.expected_observation_id for expectation in value]
    if len(set(ids)) != len(ids):
        raise ValueError("expectation identifiers must be unique")
    cells = [
        (expectation.series, expectation.period_start, expectation.period_end)
        for expectation in value
    ]
    if len(set(cells)) != len(cells):
        raise ValueError("one exact expected cell may be declared only once")
    if not all(expectation_identity_matches(expectation) for expectation in value):
        raise ValueError("expectation identity does not match its content")
    return tuple(sorted(value, key=lambda expectation: expectation.expected_observation_id))


Expectations = Annotated[
    tuple[ExpectedObservationV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_expectations),
]


class MissingObservationDetectorConfigV1(CanonicalModel):
    """The only public authority for deciding whether an absence is actionable."""

    detector_config_id: DetectorConfigId
    spec_version: Literal["quantcheck/missing-observation/v1"] = MISSING_OBSERVATION_SPEC_VERSION
    expectations: Expectations


def detector_config_identity_matches(config: MissingObservationDetectorConfigV1) -> bool:
    body = {
        name: getattr(config, name)
        for name in MissingObservationDetectorConfigV1.model_fields
        if name != "detector_config_id"
    }
    return config.detector_config_id == missing_detector_config_id(body=body)


def build_missing_observation_detector_config(
    expectations: tuple[ExpectedObservationV1, ...],
) -> MissingObservationDetectorConfigV1:
    normalized_expectations = tuple(
        sorted(expectations, key=lambda expectation: expectation.expected_observation_id)
    )
    body: dict[str, object] = {
        "spec_version": MISSING_OBSERVATION_SPEC_VERSION,
        "expectations": normalized_expectations,
    }
    return MissingObservationDetectorConfigV1.model_validate(
        {"detector_config_id": missing_detector_config_id(body=body), **body}
    )


class MissingObservationInjectionConfigV1(CanonicalModel):
    """Private deterministic injection configuration for one mechanism."""

    spec_version: Literal["quantcheck/missing-observation/v1"] = MISSING_OBSERVATION_SPEC_VERSION
    mechanism: MissingnessMechanism
    severity: MissingSeverity
    seed: NonNegativeInteger
    max_targets: PositiveInteger = 100
    survivorship_entity_ids: EntityIds = ()
    outage_period_start: FinancialDate | None = None
    outage_period_end: FinancialDate | None = None

    @model_validator(mode="after")
    def _check_mechanism_fields(self) -> MissingObservationInjectionConfigV1:
        if self.mechanism == "survivorship_like_filtering":
            if not self.survivorship_entity_ids:
                raise ValueError("survivorship-like filtering requires declared entity ids")
        elif self.survivorship_entity_ids:
            raise ValueError("survivorship entity ids apply only to survivorship-like filtering")
        if self.mechanism == "source_feed_outage":
            if self.outage_period_start is None or self.outage_period_end is None:
                raise ValueError("a source-feed outage requires an explicit period window")
            if self.outage_period_start > self.outage_period_end:
                raise ValueError("outage period start must not be after its end")
        elif self.outage_period_start is not None or self.outage_period_end is not None:
            raise ValueError("an outage period window applies only to source-feed outage")
        return self


class MissingObservationEvidenceV1(CanonicalModel):
    """Public proof that one explicitly expected cell is absent."""

    expected_observation_id: ExpectedObservationId
    context: ExpectationContext
    series: MissingObservationSeriesKeyV1
    period_start: FinancialDate | None = None
    period_end: FinancialDate
    expected_by: FinancialDate
    evidence_reference: Token
    audit_as_of_date: FinancialDate
    observed_matching_record_count: Literal[0] = 0
    supporting_record_ids: RecordIds = ()

    @model_validator(mode="after")
    def _check_due(self) -> MissingObservationEvidenceV1:
        if self.expected_by > self.audit_as_of_date:
            raise ValueError("missing evidence requires an expectation due by the audit cutoff")
        return self


class MissingObservationFindingV1(CanonicalModel):
    finding_id: FindingId
    detector_id: Literal["quantcheck.missing_observation_detector"] = (
        MISSING_OBSERVATION_DETECTOR_ID
    )
    detector_version: Literal["quantcheck/missing-observation-detector/v1"] = (
        MISSING_OBSERVATION_DETECTOR_VERSION
    )
    fault_type: Literal["missing_observation"] = MISSING_OBSERVATION_FAULT_TYPE
    fault_subtype: Token
    rule_id: Token
    expected_observation_id: ExpectedObservationId
    affected_record_ids: RecordIds = ()
    severity: FindingSeverity
    confidence: Literal["proven_by_explicit_expectation"] = "proven_by_explicit_expectation"
    evidence: MissingObservationEvidenceV1
    explanation: Token

    @model_validator(mode="after")
    def _check_finding(self) -> MissingObservationFindingV1:
        expected_subtype = CONTEXT_TO_SUBTYPE[self.evidence.context]
        expected_rule = CONTEXT_TO_RULE_ID[self.evidence.context]
        expected_severity = CONTEXT_TO_SEVERITY[self.evidence.context]
        if self.expected_observation_id != self.evidence.expected_observation_id:
            raise ValueError("finding expectation must equal its evidence expectation")
        if self.affected_record_ids != self.evidence.supporting_record_ids:
            raise ValueError("affected records must equal supporting records")
        if (
            self.fault_subtype != expected_subtype
            or self.rule_id != expected_rule
            or self.severity != expected_severity
        ):
            raise ValueError("finding classification must derive from expectation context")
        return self


def _finding_body(finding: MissingObservationFindingV1) -> dict[str, object]:
    return {
        name: getattr(finding, name)
        for name in MissingObservationFindingV1.model_fields
        if name != "finding_id"
    }


def finding_identity_matches(finding: MissingObservationFindingV1) -> bool:
    return finding.finding_id == missing_finding_id(body=_finding_body(finding))


def _normalize_findings(
    value: tuple[MissingObservationFindingV1, ...],
) -> tuple[MissingObservationFindingV1, ...]:
    return tuple(sorted(value, key=lambda finding: finding.finding_id))


Findings = Annotated[
    tuple[MissingObservationFindingV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_findings),
]


class MissingObservationAuditReportV1(CanonicalModel):
    audit_report_id: ReportId
    detector_id: Literal["quantcheck.missing_observation_detector"] = (
        MISSING_OBSERVATION_DETECTOR_ID
    )
    detector_version: Literal["quantcheck/missing-observation-detector/v1"] = (
        MISSING_OBSERVATION_DETECTOR_VERSION
    )
    audit_input_id: Token
    dataset_name: Token
    as_of_date: FinancialDate
    detector_config_id: DetectorConfigId
    detector_config_hash: ContentHash
    evaluated_expectation_ids: ExpectedObservationIds
    not_evaluated_expectation_ids: ExpectedObservationIds
    findings: Findings = ()

    @model_validator(mode="after")
    def _check_report(self) -> MissingObservationAuditReportV1:
        evaluated = set(self.evaluated_expectation_ids)
        not_evaluated = set(self.not_evaluated_expectation_ids)
        if evaluated & not_evaluated:
            raise ValueError("evaluated and not-evaluated expectations must be disjoint")
        if any(finding.expected_observation_id not in evaluated for finding in self.findings):
            raise ValueError("every finding must reference an evaluated expectation")
        if any(finding.evidence.audit_as_of_date != self.as_of_date for finding in self.findings):
            raise ValueError("finding audit cutoff must match its report")
        return self


def missing_audit_report_identity_matches(report: MissingObservationAuditReportV1) -> bool:
    body = {
        name: getattr(report, name)
        for name in MissingObservationAuditReportV1.model_fields
        if name != "audit_report_id"
    }
    return report.audit_report_id == missing_audit_report_id(body=body)


class MissingObservationEligibilityUnitV1(CanonicalModel):
    expected_observation: ExpectedObservationV1
    original_record: FinancialFact

    @model_validator(mode="after")
    def _check_identity(self) -> MissingObservationEligibilityUnitV1:
        if not expectation_identity_matches(self.expected_observation):
            raise ValueError("eligibility expectation identity is invalid")
        return self


class MissingObservationManifestEntryV1(CanonicalModel):
    fault_id: FaultId
    mechanism: MissingnessMechanism
    severity: MissingSeverity
    target_rank: NonNegativeInteger
    selection_digest: ContentHash
    expected_observation: ExpectedObservationV1
    deleted_record: FinancialFact
    expected_evidence: MissingObservationEvidenceV1

    @model_validator(mode="after")
    def _check_entry(self) -> MissingObservationManifestEntryV1:
        expectation = self.expected_observation
        evidence = self.expected_evidence
        if self.expected_evidence.expected_observation_id != (
            self.expected_observation.expected_observation_id
        ):
            raise ValueError("entry evidence must describe its expectation")
        if (
            evidence.context != expectation.context
            or evidence.series != expectation.series
            or evidence.period_start != expectation.period_start
            or evidence.period_end != expectation.period_end
            or evidence.expected_by != expectation.expected_by
            or evidence.evidence_reference != expectation.evidence_reference
        ):
            raise ValueError("entry evidence must exactly reproduce its expectation")
        return self


def _normalize_eligibility(
    value: tuple[MissingObservationEligibilityUnitV1, ...],
) -> tuple[MissingObservationEligibilityUnitV1, ...]:
    ids = [unit.expected_observation.expected_observation_id for unit in value]
    if len(set(ids)) != len(ids):
        raise ValueError("eligibility expectations must be unique")
    records = [unit.original_record.record_id for unit in value]
    if len(set(records)) != len(records):
        raise ValueError("one clean record cannot satisfy multiple eligibility units")
    return tuple(sorted(value, key=lambda unit: unit.expected_observation.expected_observation_id))


def _normalize_entries(
    value: tuple[MissingObservationManifestEntryV1, ...],
) -> tuple[MissingObservationManifestEntryV1, ...]:
    ids = [entry.fault_id for entry in value]
    expectations = [entry.expected_observation.expected_observation_id for entry in value]
    records = [entry.deleted_record.record_id for entry in value]
    for label, items in (("fault", ids), ("expectation", expectations), ("record", records)):
        if len(set(items)) != len(items):
            raise ValueError(f"manifest {label} values must be unique")
    return tuple(sorted(value, key=lambda entry: entry.fault_id))


EligibilityUnits = Annotated[
    tuple[MissingObservationEligibilityUnitV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_eligibility),
]
ManifestEntries = Annotated[
    tuple[MissingObservationManifestEntryV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_entries),
]


class MissingObservationManifestV1(CanonicalModel):
    manifest_id: ManifestId
    spec_version: Literal["quantcheck/missing-observation/v1"] = MISSING_OBSERVATION_SPEC_VERSION
    dataset_name: Token
    snapshot_as_of_date: FinancialDate
    clean_snapshot_id: Token
    clean_snapshot_hash: ContentHash
    corrupted_snapshot_id: Token
    corrupted_snapshot_hash: ContentHash
    detector_config: MissingObservationDetectorConfigV1
    detector_config_hash: ContentHash
    injection_config: MissingObservationInjectionConfigV1
    target_fraction: CanonicalDecimal
    eligible_units: EligibilityUnits
    eligible_unit_count: NonNegativeInteger
    target_count: NonNegativeInteger
    entries: ManifestEntries

    @model_validator(mode="after")
    def _check_manifest(self) -> MissingObservationManifestV1:
        if not detector_config_identity_matches(self.detector_config):
            raise ValueError("detector configuration identity is invalid")
        if self.eligible_unit_count != len(self.eligible_units):
            raise ValueError("eligible_unit_count must equal eligible_units length")
        if self.target_count != len(self.entries):
            raise ValueError("target_count must equal entries length")
        if self.target_count > self.eligible_unit_count:
            raise ValueError("target_count must not exceed eligibility")
        if self.target_count > self.injection_config.max_targets:
            raise ValueError("target_count must not exceed max_targets")
        if (
            self.target_fraction
            != injection_severity_profile(self.injection_config.severity).target_fraction
        ):
            raise ValueError("target fraction must derive from severity")
        ranks = sorted(entry.target_rank for entry in self.entries)
        if ranks != list(range(len(ranks))):
            raise ValueError("target ranks must be contiguous and zero-based")
        eligible_ids = {
            unit.expected_observation.expected_observation_id for unit in self.eligible_units
        }
        if any(
            entry.expected_observation.expected_observation_id not in eligible_ids
            for entry in self.entries
        ):
            raise ValueError("every manifest entry must reference an eligible expectation")
        if any(
            entry.mechanism != self.injection_config.mechanism
            or entry.severity != self.injection_config.severity
            for entry in self.entries
        ):
            raise ValueError("entry configuration must match the manifest")
        return self


class MissingObservationExactMatchV1(CanonicalModel):
    fault_id: FaultId
    finding_id: FindingId


def _normalize_matches(
    value: tuple[MissingObservationExactMatchV1, ...],
) -> tuple[MissingObservationExactMatchV1, ...]:
    return tuple(sorted(value, key=lambda match: (match.fault_id, match.finding_id)))


ExactMatches = Annotated[
    tuple[MissingObservationExactMatchV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_matches),
]
FindingIdTuple = Annotated[
    tuple[FindingId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_tokens),
]
FaultIdTuple = Annotated[
    tuple[FaultId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_tokens),
]


class MissingObservationScoreReportV1(CanonicalModel):
    score_report_id: ScoreId
    scoring_spec_version: Literal["quantcheck/missing-observation-scoring/v1"] = (
        MISSING_OBSERVATION_SCORING_SPEC_VERSION
    )
    audit_report_id: ReportId
    manifest_id: ManifestId
    metrics: DetectionMetrics
    f1: CanonicalDecimal | None
    matches: ExactMatches = ()
    unmatched_finding_ids: FindingIdTuple = ()
    duplicate_finding_ids: FindingIdTuple = ()
    missed_fault_ids: FaultIdTuple = ()

    @model_validator(mode="after")
    def _check_score(self) -> MissingObservationScoreReportV1:
        if len(self.matches) != self.metrics.true_positive_faults:
            raise ValueError("match count must equal true positives")
        expected_null = self.metrics.precision is None or self.metrics.recall is None
        if (self.f1 is None) != expected_null:
            raise ValueError("F1 is null exactly when precision or recall is null")
        if self.f1 is not None:
            assert self.metrics.precision is not None
            assert self.metrics.recall is not None
            with localcontext() as context:
                context.prec = 50
                denominator = self.metrics.precision + self.metrics.recall
                expected = (
                    Decimal(0)
                    if denominator == 0
                    else Decimal(2) * self.metrics.precision * self.metrics.recall / denominator
                )
            if self.f1 != expected:
                raise ValueError("F1 must be the harmonic mean")
        return self


class MissingObservationResearchResultV1(CanonicalModel):
    research_result_id: ResearchId
    method: Literal["declared_expected_cohort_mean_v1"] = "declared_expected_cohort_mean_v1"
    snapshot_id: Token
    snapshot_content_hash: ContentHash
    detector_config_id: DetectorConfigId
    as_of_date: FinancialDate
    expected_observation_count: NonNegativeInteger
    observed_expectation_ids: ExpectedObservationIds
    missing_expectation_ids: ExpectedObservationIds
    observed_record_ids: RecordIds
    observed_count: NonNegativeInteger
    aggregate_value: CanonicalDecimal
    cohort_mean: CanonicalDecimal | None

    @model_validator(mode="after")
    def _check_result(self) -> MissingObservationResearchResultV1:
        if self.expected_observation_count != (
            len(self.observed_expectation_ids) + len(self.missing_expectation_ids)
        ):
            raise ValueError("observed and missing expectations must partition the cohort")
        if self.observed_count != len(self.observed_expectation_ids):
            raise ValueError("observed_count must equal observed expectations")
        if self.observed_count != len(self.observed_record_ids):
            raise ValueError("one observed record is required per observed expectation")
        if (self.cohort_mean is None) != (self.observed_count == 0):
            raise ValueError("cohort mean is null exactly when no expectation is observed")
        return self


class MissingObservationResearchImpactV1(CanonicalModel):
    impact_id: ImpactId
    method: Literal["declared_expected_cohort_mean_v1"] = "declared_expected_cohort_mean_v1"
    clean: MissingObservationResearchResultV1
    corrupted: MissingObservationResearchResultV1
    repaired: MissingObservationResearchResultV1
    observed_count_delta: int
    aggregate_value_delta: CanonicalDecimal
    cohort_mean_delta: CanonicalDecimal | None
    changed: bool
    exact_restoration: bool

    @model_validator(mode="after")
    def _check_impact(self) -> MissingObservationResearchImpactV1:
        if self.observed_count_delta != self.corrupted.observed_count - self.clean.observed_count:
            raise ValueError("observed count delta is inconsistent")
        if self.aggregate_value_delta != (
            self.corrupted.aggregate_value - self.clean.aggregate_value
        ):
            raise ValueError("aggregate value delta is inconsistent")
        if self.clean.cohort_mean is None or self.corrupted.cohort_mean is None:
            expected_mean_delta = None
        else:
            expected_mean_delta = self.corrupted.cohort_mean - self.clean.cohort_mean
        if self.cohort_mean_delta != expected_mean_delta:
            raise ValueError("cohort mean delta is inconsistent")
        expected_changed = (
            self.observed_count_delta != 0
            or self.aggregate_value_delta != 0
            or self.cohort_mean_delta not in (None, Decimal(0))
        )
        if self.changed != expected_changed:
            raise ValueError("changed must reflect the controlled result")
        expected_restoration = self.repaired == self.clean
        if self.exact_restoration != expected_restoration:
            raise ValueError("exact restoration must compare repaired and clean results")
        return self


def due_expectations(
    config: MissingObservationDetectorConfigV1, as_of_date: date
) -> tuple[ExpectedObservationV1, ...]:
    return tuple(
        expectation for expectation in config.expectations if expectation.expected_by <= as_of_date
    )


def validate_expected_record(expectation: ExpectedObservationV1, record: FinancialFact) -> bool:
    series = expectation.series
    return (
        record.entity_id == series.entity_id
        and record.concept_namespace == series.concept_namespace
        and record.concept == series.concept
        and record.unit == series.unit
        and record.dimensions == series.dimensions
        and record.period_type == series.period_type
        and record.period_start == expectation.period_start
        and record.period_end == expectation.period_end
        and record.source.source_name == series.source_name
        and record.source.source_locator == series.source_locator
    )


def snapshot_shape(snapshot: DatasetSnapshot | AuditInputSnapshot) -> tuple[str, date]:
    return snapshot.dataset_name, snapshot.as_of_date
