"""Strict, versioned production-audit policy contracts.

These types configure customer-facing audits only.  They are deliberately
separate from every benchmark configuration and contain no injector, manifest,
seed, scoring, or hidden-truth field.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from quantcheck.benchmark_v2_contract import ALL_V2_DETECTORS, DetectorKeyV2
from quantcheck.corpus_schemas import CorpusModel
from quantcheck.duplicate_contract import DUPLICATE_RULE_ID
from quantcheck.hashing import canonical_sha256, stable_id
from quantcheck.json_types import parse_canonical_date
from quantcheck.lookahead_contract import LOOKAHEAD_RULE_ID
from quantcheck.revision_overwrite_contract import REVISION_OVERWRITE_RULE_ID
from quantcheck.schemas import (
    CONTENT_HASH_PATTERN,
    FINDING_ID_PATTERN,
    RECORD_ID_PATTERN,
    CanonicalDecimal,
    Dimension,
)
from quantcheck.unit_drift_contract import UNIT_DRIFT_RULE_ID

__all__ = [
    "AUDIT_POLICY_ID_PATTERN",
    "AUDIT_POLICY_V1_SPEC_VERSION",
    "POLICY_RESULT_V1_SPEC_VERSION",
    "AuditPolicyContentV1",
    "AuditPolicyId",
    "AuditPolicyV1",
    "ConceptScopeV1",
    "ConceptUnitExpectationV1",
    "ConceptUnitPolicyEvidenceV1",
    "DatasetPolicyExceptionV1",
    "DatasetPolicyExceptionScopeV1",
    "DetectorFindingPolicyEvidenceV1",
    "DetectorPolicyRuleV1",
    "PolicyActionV1",
    "PolicyAuditResultV1",
    "PolicyRuleEvaluationV1",
    "PublicationLagExpectationV1",
    "PublicationLagPolicyEvidenceV1",
    "ReportingFrequencyExpectationV1",
    "ReportingFrequencyPolicyEvidenceV1",
    "UnitDriftThresholdPolicyV1",
    "audit_policy_identity_matches",
    "build_audit_policy",
]

AUDIT_POLICY_V1_SPEC_VERSION: Literal["quantcheck/audit-policy/v1"] = "quantcheck/audit-policy/v1"
POLICY_RESULT_V1_SPEC_VERSION: Literal["quantcheck/policy-result/v1"] = (
    "quantcheck/policy-result/v1"
)

AUDIT_POLICY_V1_NAMESPACE = "quantcheck/audit-policy/v1"
POLICY_RESULT_V1_NAMESPACE = "quantcheck/policy-result/v1"

AUDIT_POLICY_ID_PATTERN = re.compile(r"^apol_[0-9a-f]{16}$")
POLICY_RESULT_ID_PATTERN = re.compile(r"^pres_[0-9a-f]{16}$")

_MAX_TOKEN_LENGTH = 512
_DETECTOR_RULE_IDS: dict[DetectorKeyV2, str] = {
    "duplicate_observation": DUPLICATE_RULE_ID,
    "lookahead_timestamp": LOOKAHEAD_RULE_ID,
    "revision_overwrite": REVISION_OVERWRITE_RULE_ID,
    "unit_drift": UNIT_DRIFT_RULE_ID,
}

PolicyActionV1 = Literal["blocking", "warning", "informational"]
PolicyRuleKindV1 = Literal[
    "detector",
    "concept_unit",
    "publication_lag",
    "reporting_frequency",
]


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


def _validate_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected an integer")
    return value


def _validate_date(value: object) -> date:
    if isinstance(value, datetime):
        raise ValueError("expected a day-level date, got datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_canonical_date(value)
    raise ValueError(f"expected date or canonical date string, got {type(value).__name__}")


def _validate_non_negative_int(value: object) -> int:
    validated = _validate_integer(value)
    if validated < 0:
        raise ValueError("must not be negative")
    return validated


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
Integer = Annotated[int, BeforeValidator(_validate_integer)]
NonNegativeInteger = Annotated[int, BeforeValidator(_validate_non_negative_int)]
PositiveInteger = Annotated[int, BeforeValidator(_validate_positive_int)]
FinancialDate = Annotated[date, BeforeValidator(_validate_date)]
ContentHash = Annotated[str, _pattern_validator(CONTENT_HASH_PATTERN, "content hash")]
AuditPolicyId = Annotated[str, _pattern_validator(AUDIT_POLICY_ID_PATTERN, "policy_id")]
PolicyResultId = Annotated[str, _pattern_validator(POLICY_RESULT_ID_PATTERN, "policy_result_id")]
FindingId = Annotated[str, _pattern_validator(FINDING_ID_PATTERN, "finding_id")]
RecordId = Annotated[str, _pattern_validator(RECORD_ID_PATTERN, "record_id")]


def _normalize_tokens(value: tuple[str, ...]) -> tuple[str, ...]:
    if not value or len(set(value)) != len(value):
        raise ValueError("values must be non-empty and unique")
    return tuple(sorted(value))


UniqueTokens = Annotated[
    tuple[Token, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_tokens),
]


class UnitDriftThresholdPolicyV1(CorpusModel):
    """The only currently configurable detector threshold contract."""

    ratio_threshold: CanonicalDecimal

    @model_validator(mode="after")
    def _check_threshold(self) -> UnitDriftThresholdPolicyV1:
        if self.ratio_threshold <= Decimal(1):
            raise ValueError("ratio_threshold must be greater than one")
        return self


class DetectorPolicyRuleV1(CorpusModel):
    """Explicit enablement and action for one frozen detector rule."""

    detector: DetectorKeyV2
    rule_id: Token
    enabled: bool
    action: PolicyActionV1
    disabled_reason: Token | None
    threshold: UnitDriftThresholdPolicyV1 | None

    @model_validator(mode="after")
    def _check_rule(self) -> DetectorPolicyRuleV1:
        if self.rule_id != _DETECTOR_RULE_IDS[self.detector]:
            raise ValueError("rule_id must match the selected detector contract")
        if self.enabled == (self.disabled_reason is not None):
            raise ValueError("disabled detectors require a reason; enabled detectors forbid one")
        if self.threshold is not None and self.detector != "unit_drift":
            raise ValueError("only the Unit Drift detector permits a configurable threshold")
        if self.detector == "unit_drift" and self.threshold is None:
            raise ValueError("the Unit Drift detector requires an explicit threshold")
        return self


def _normalize_detector_rules(
    value: tuple[DetectorPolicyRuleV1, ...],
) -> tuple[DetectorPolicyRuleV1, ...]:
    detectors = [rule.detector for rule in value]
    if len(value) != len(ALL_V2_DETECTORS) or set(detectors) != set(ALL_V2_DETECTORS):
        raise ValueError("policy must explicitly configure each supported detector exactly once")
    return tuple(sorted(value, key=lambda rule: ALL_V2_DETECTORS.index(rule.detector)))


DetectorPolicyRules = Annotated[
    tuple[DetectorPolicyRuleV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_detector_rules),
]


class ConceptScopeV1(CorpusModel):
    """Exact public-record scope shared by production expectation rules."""

    concept_namespace: Token
    concept: Token
    entity_id: Token | None = None
    unit: Token | None = None


class ConceptUnitExpectationV1(CorpusModel):
    """Accepted units for one exact concept scope."""

    rule_id: Token
    scope: ConceptScopeV1
    accepted_units: UniqueTokens
    action: PolicyActionV1

    @model_validator(mode="after")
    def _check_rule_prefix(self) -> ConceptUnitExpectationV1:
        if not self.rule_id.startswith("policy.concept_unit."):
            raise ValueError("concept/unit rule_id must start with 'policy.concept_unit.'")
        if self.scope.unit is not None:
            raise ValueError("concept/unit rules must express units through accepted_units")
        return self


class PublicationLagExpectationV1(CorpusModel):
    """Allowed day-level publication lag for records in one exact scope."""

    rule_id: Token
    scope: ConceptScopeV1
    basis: Literal[
        "filing_after_period_end",
        "availability_after_filing",
        "availability_after_period_end",
    ]
    minimum_days: Integer
    maximum_days: Integer
    action: PolicyActionV1

    @model_validator(mode="after")
    def _check_lag(self) -> PublicationLagExpectationV1:
        if not self.rule_id.startswith("policy.publication_lag."):
            raise ValueError("publication-lag rule_id must start with 'policy.publication_lag.'")
        if self.minimum_days > self.maximum_days:
            raise ValueError("minimum_days must not exceed maximum_days")
        return self


class ReportingFrequencyExpectationV1(CorpusModel):
    """Maximum adjacent period-end gap for one exact reporting series."""

    rule_id: Token
    scope: ConceptScopeV1
    period_type: Literal["instant", "duration"]
    maximum_gap_days: PositiveInteger
    action: PolicyActionV1

    @model_validator(mode="after")
    def _check_rule_prefix(self) -> ReportingFrequencyExpectationV1:
        if not self.rule_id.startswith("policy.reporting_frequency."):
            raise ValueError(
                "reporting-frequency rule_id must start with 'policy.reporting_frequency.'"
            )
        return self


def _normalize_expectations[
    T: (
        ConceptUnitExpectationV1,
        PublicationLagExpectationV1,
        ReportingFrequencyExpectationV1,
    )
](value: tuple[T, ...]) -> tuple[T, ...]:
    rule_ids = [rule.rule_id for rule in value]
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("expectation rule identifiers must be unique")
    return tuple(sorted(value, key=lambda rule: rule.rule_id))


ConceptUnitExpectations = Annotated[
    tuple[ConceptUnitExpectationV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_expectations),
]
PublicationLagExpectations = Annotated[
    tuple[PublicationLagExpectationV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_expectations),
]
ReportingFrequencyExpectations = Annotated[
    tuple[ReportingFrequencyExpectationV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_expectations),
]


class DatasetPolicyExceptionScopeV1(CorpusModel):
    """Optional exact predicates that make one dataset exception narrower."""

    record_id: RecordId | None = None
    entity_id: Token | None = None
    concept_namespace: Token | None = None
    concept: Token | None = None
    unit: Token | None = None

    @model_validator(mode="after")
    def _check_concept_pair(self) -> DatasetPolicyExceptionScopeV1:
        if (self.concept_namespace is None) != (self.concept is None):
            raise ValueError("concept namespace and concept must be supplied together")
        return self


class DatasetPolicyExceptionV1(CorpusModel):
    """A reasoned, exact dataset exception that never erases its result."""

    exception_id: Token
    dataset_name: Token
    rule_id: Token
    scope: DatasetPolicyExceptionScopeV1
    effect: Literal["waive", "override_action"]
    action_override: PolicyActionV1 | None
    reason: Token

    @model_validator(mode="after")
    def _check_effect(self) -> DatasetPolicyExceptionV1:
        if self.effect == "waive" and self.action_override is not None:
            raise ValueError("a waived exception cannot also override the action")
        if self.effect == "override_action" and self.action_override is None:
            raise ValueError("an action override requires action_override")
        return self


def _normalize_exceptions(
    value: tuple[DatasetPolicyExceptionV1, ...],
) -> tuple[DatasetPolicyExceptionV1, ...]:
    ids = [exception.exception_id for exception in value]
    if len(set(ids)) != len(ids):
        raise ValueError("exception identifiers must be unique")
    targets = [(exception.dataset_name, exception.rule_id, exception.scope) for exception in value]
    if len(set(targets)) != len(targets):
        raise ValueError("duplicate exception targets are not permitted")
    return tuple(sorted(value, key=lambda exception: exception.exception_id))


DatasetPolicyExceptions = Annotated[
    tuple[DatasetPolicyExceptionV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_exceptions),
]


class AuditPolicyContentV1(CorpusModel):
    """The exact canonical content hashed into one production policy identity."""

    spec_version: Literal["quantcheck/audit-policy/v1"] = AUDIT_POLICY_V1_SPEC_VERSION
    policy_name: Token
    policy_version: Token
    detector_rules: DetectorPolicyRules
    concept_unit_expectations: ConceptUnitExpectations
    publication_lag_expectations: PublicationLagExpectations
    reporting_frequency_expectations: ReportingFrequencyExpectations
    dataset_exceptions: DatasetPolicyExceptions

    @model_validator(mode="after")
    def _check_rule_links(self) -> AuditPolicyContentV1:
        all_rule_ids = [rule.rule_id for rule in self.detector_rules]
        all_rule_ids.extend(rule.rule_id for rule in self.concept_unit_expectations)
        all_rule_ids.extend(rule.rule_id for rule in self.publication_lag_expectations)
        all_rule_ids.extend(rule.rule_id for rule in self.reporting_frequency_expectations)
        if len(set(all_rule_ids)) != len(all_rule_ids):
            raise ValueError("all policy rule identifiers must be globally unique")
        enabled = {rule.rule_id: rule.enabled for rule in self.detector_rules}
        enabled.update({rule.rule_id: True for rule in self.concept_unit_expectations})
        enabled.update({rule.rule_id: True for rule in self.publication_lag_expectations})
        enabled.update({rule.rule_id: True for rule in self.reporting_frequency_expectations})
        for exception in self.dataset_exceptions:
            if exception.rule_id not in enabled:
                raise ValueError("dataset exception targets an unknown policy rule")
            if not enabled[exception.rule_id]:
                raise ValueError("dataset exception cannot target an explicitly disabled rule")
        return self


class AuditPolicyV1(AuditPolicyContentV1):
    """An identity-bearing, immutable production policy document."""

    policy_id: AuditPolicyId
    policy_content_hash: ContentHash

    @model_validator(mode="after")
    def _check_identity(self) -> AuditPolicyV1:
        if not audit_policy_identity_matches(self):
            raise ValueError("policy identity or content hash does not match its content")
        return self


def _policy_content(policy: AuditPolicyV1) -> AuditPolicyContentV1:
    return AuditPolicyContentV1.model_validate(
        {name: getattr(policy, name) for name in AuditPolicyContentV1.model_fields}
    )


def build_audit_policy(content: AuditPolicyContentV1) -> AuditPolicyV1:
    """Attach deterministic SHA-256 content and stable identities to a policy."""
    content_hash = canonical_sha256(content)
    return AuditPolicyV1.model_validate(
        {
            **content.model_dump(mode="python"),
            "policy_id": stable_id(
                prefix="apol",
                namespace=AUDIT_POLICY_V1_NAMESPACE,
                payload=content,
            ),
            "policy_content_hash": content_hash,
        }
    )


def audit_policy_identity_matches(policy: AuditPolicyV1) -> bool:
    content = _policy_content(policy)
    return policy.policy_content_hash == canonical_sha256(
        content
    ) and policy.policy_id == stable_id(
        prefix="apol",
        namespace=AUDIT_POLICY_V1_NAMESPACE,
        payload=content,
    )


class DetectorFindingPolicyEvidenceV1(CorpusModel):
    kind: Literal["detector_finding"] = "detector_finding"
    finding_id: FindingId


class ConceptUnitPolicyEvidenceV1(CorpusModel):
    kind: Literal["concept_unit"] = "concept_unit"
    record_id: RecordId
    concept_namespace: Token
    concept: Token
    observed_unit: Token
    accepted_units: UniqueTokens


class PublicationLagPolicyEvidenceV1(CorpusModel):
    kind: Literal["publication_lag"] = "publication_lag"
    record_id: RecordId
    basis: Literal[
        "filing_after_period_end",
        "availability_after_filing",
        "availability_after_period_end",
    ]
    period_end: FinancialDate
    filed_on: FinancialDate
    available_on: FinancialDate
    observed_days: Integer
    minimum_days: Integer
    maximum_days: Integer


class ReportingFrequencyPolicyEvidenceV1(CorpusModel):
    kind: Literal["reporting_frequency"] = "reporting_frequency"
    entity_id: Token
    concept_namespace: Token
    concept: Token
    unit: Token
    dimensions: tuple[Dimension, ...]
    period_type: Literal["instant", "duration"]
    previous_period_end: FinancialDate
    current_period_end: FinancialDate
    gap_days: PositiveInteger
    maximum_gap_days: PositiveInteger


PolicyResultEvidenceV1 = Annotated[
    DetectorFindingPolicyEvidenceV1
    | ConceptUnitPolicyEvidenceV1
    | PublicationLagPolicyEvidenceV1
    | ReportingFrequencyPolicyEvidenceV1,
    Field(discriminator="kind"),
]


def _normalize_record_ids(value: tuple[str, ...]) -> tuple[str, ...]:
    if not value or len(set(value)) != len(value):
        raise ValueError("affected record identifiers must be non-empty and unique")
    return tuple(sorted(value))


AffectedRecordIds = Annotated[
    tuple[RecordId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_record_ids),
]


class PolicyAuditResultV1(CorpusModel):
    """One detector finding or policy violation after exception resolution."""

    policy_result_id: PolicyResultId
    spec_version: Literal["quantcheck/policy-result/v1"] = POLICY_RESULT_V1_SPEC_VERSION
    rule_id: Token
    rule_kind: PolicyRuleKindV1
    affected_record_ids: AffectedRecordIds
    base_action: PolicyActionV1
    effective_action: PolicyActionV1 | None
    disposition: Literal["active", "exception_applied"]
    exception_id: Token | None
    exception_effect: Literal["waive", "override_action"] | None
    exception_reason: Token | None
    evidence: PolicyResultEvidenceV1

    @model_validator(mode="after")
    def _check_exception(self) -> PolicyAuditResultV1:
        exception_fields = (
            self.exception_id,
            self.exception_effect,
            self.exception_reason,
        )
        if self.disposition == "active":
            if any(value is not None for value in exception_fields):
                raise ValueError("an active result cannot name an exception")
            if self.effective_action is None:
                raise ValueError("an active result requires an effective action")
        else:
            if any(value is None for value in exception_fields):
                raise ValueError("an applied exception requires identity, effect, and reason")
            if self.exception_effect == "waive" and self.effective_action is not None:
                raise ValueError("a waived result cannot retain an effective action")
            if self.exception_effect == "override_action" and self.effective_action is None:
                raise ValueError("an action override requires an effective action")
        expected_evidence_kind = (
            "detector_finding" if self.rule_kind == "detector" else self.rule_kind
        )
        if self.evidence.kind != expected_evidence_kind:
            raise ValueError("policy result evidence kind must match its rule kind")
        body = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "policy_result_id"
        }
        if self.policy_result_id != policy_result_id(body=body):
            raise ValueError("policy result identity does not match its content")
        return self


class PolicyRuleEvaluationV1(CorpusModel):
    """Auditable status for every configured rule, including disabled rules."""

    rule_id: Token
    rule_kind: PolicyRuleKindV1
    configured_action: PolicyActionV1
    status: Literal["disabled", "evaluated", "not_evaluated"]
    reason: Token | None
    evaluated_record_count: NonNegativeInteger
    result_count: NonNegativeInteger

    @model_validator(mode="after")
    def _check_status(self) -> PolicyRuleEvaluationV1:
        if self.status == "disabled":
            if self.reason is None or self.evaluated_record_count or self.result_count:
                raise ValueError("disabled status requires a reason and zero counts")
        elif self.status == "not_evaluated":
            if self.reason is None or self.result_count:
                raise ValueError("not_evaluated status requires a reason and zero results")
        elif self.reason is not None:
            raise ValueError("evaluated status cannot carry a disablement reason")
        return self


def policy_result_id(*, body: dict[str, object]) -> str:
    """Return the deterministic identifier for one complete policy result body."""
    return stable_id(
        prefix="pres",
        namespace=POLICY_RESULT_V1_NAMESPACE,
        payload=body,
    )
