"""Immutable public domain schemas for QuantCheck.

Every model here is a frozen, strictly validated Pydantic v2 model that
forbids unknown fields. The models depend only on the standard library and
Pydantic; they never reference pandas, HTTPX, Streamlit, file handles, or
network clients.

Milestone 3 extends the contract layer with the narrow artifacts required by
the Look-Ahead vertical slice. Milestone 5 adds the corresponding Unit Drift
configuration, evidence, manifest, scoring, and aggregate-value contracts.
Recovery Phase 7 adds the narrow Revision Overwrite contracts. These models
still do not attempt to describe the benchmark framework.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, model_validator

from quantcheck.json_types import (
    canonical_decimal_string,
    parse_canonical_date,
    parse_canonical_datetime,
    parse_canonical_decimal,
)
from quantcheck.unit_drift_math import decimal_divide, symmetric_absolute_ratio

__all__ = [
    "AUDIT_INPUT_SNAPSHOT_ID_PATTERN",
    "AUDIT_REPORT_ID_PATTERN",
    "CASE_CONFIG_ID_PATTERN",
    "CONTENT_HASH_PATTERN",
    "DATASET_SNAPSHOT_ID_PATTERN",
    "FAULT_ID_PATTERN",
    "FINDING_ID_PATTERN",
    "IMPACT_ID_PATTERN",
    "MANIFEST_ID_PATTERN",
    "MODIFIED_RECORD_ID_PATTERN",
    "RECORD_ID_PATTERN",
    "RESEARCH_RESULT_ID_PATTERN",
    "REVISION_ID_PATTERN",
    "REVISION_UNIT_ID_PATTERN",
    "SCORE_REPORT_ID_PATTERN",
    "ArtifactIdentity",
    "AuditReport",
    "AuditInputRecord",
    "AuditInputSnapshot",
    "AvailabilityCountResult",
    "AggregateValueImpact",
    "AggregateValueResult",
    "CanonicalModel",
    "CaseConfig",
    "DatasetSnapshot",
    "DetectionMetrics",
    "Dimension",
    "DuplicateEvidence",
    "DuplicateFingerprint",
    "DuplicateInjectionConfig",
    "DuplicateManifest",
    "DuplicateManifestEntry",
    "DuplicateMutation",
    "DuplicateSeverity",
    "EconomicFactKey",
    "ExactFindingMatch",
    "FaultManifest",
    "FaultManifestEntry",
    "FinancialFact",
    "Finding",
    "FindingConfidence",
    "FindingSeverity",
    "LookAheadEvidence",
    "LookAheadInjectionConfig",
    "LookAheadMutation",
    "LookAheadSeverity",
    "PeriodType",
    "RecordCountImpact",
    "RecordCountResult",
    "ResearchImpact",
    "RevisionHistoryUnit",
    "RevisionOverwriteDetectorConfig",
    "RevisionOverwriteEvidence",
    "RevisionOverwriteInjectionConfig",
    "RevisionOverwriteManifest",
    "RevisionOverwriteManifestEntry",
    "RevisionOverwriteMutation",
    "RevisionOverwriteSeverity",
    "RuntimeMetadata",
    "ScoreReport",
    "SourceReference",
    "ComparableSeriesKey",
    "UnitDriftDetectorConfig",
    "UnitDriftEvidence",
    "UnitDriftInjectionConfig",
    "UnitDriftManifest",
    "UnitDriftManifestEntry",
    "UnitDriftMutation",
    "UnitDriftNeighborEvidence",
    "UnitDriftResearchConfig",
    "UnitDriftSeverity",
    "GrowthRankingConfig",
    "GrowthRankingEntry",
    "GrowthRankingImpact",
    "GrowthRankingResult",
]

_MAX_TOKEN_LENGTH = 512

RECORD_ID_PATTERN = re.compile(r"^rec_[0-9a-f]{16}$")
MODIFIED_RECORD_ID_PATTERN = RECORD_ID_PATTERN
DATASET_SNAPSHOT_ID_PATTERN = re.compile(r"^snap_[0-9a-f]{16}$")
AUDIT_INPUT_SNAPSHOT_ID_PATTERN = re.compile(r"^audit_[0-9a-f]{16}$")
CASE_CONFIG_ID_PATTERN = re.compile(r"^case_[0-9a-f]{16}$")
CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FAULT_ID_PATTERN = re.compile(r"^fault_[0-9a-f]{16}$")
MANIFEST_ID_PATTERN = re.compile(r"^man_[0-9a-f]{16}$")
FINDING_ID_PATTERN = re.compile(r"^find_[0-9a-f]{16}$")
AUDIT_REPORT_ID_PATTERN = re.compile(r"^arep_[0-9a-f]{16}$")
SCORE_REPORT_ID_PATTERN = re.compile(r"^score_[0-9a-f]{16}$")
RESEARCH_RESULT_ID_PATTERN = re.compile(r"^rsch_[0-9a-f]{16}$")
IMPACT_ID_PATTERN = re.compile(r"^impact_[0-9a-f]{16}$")
REVISION_ID_PATTERN = re.compile(r"^rev_[0-9a-f]{16}$")
REVISION_UNIT_ID_PATTERN = re.compile(r"^runit_[0-9a-f]{16}$")

PeriodType = Literal["instant", "duration"]
LookAheadSeverity = Literal["low", "medium", "high"]
UnitDriftSeverity = Literal["low", "medium", "high"]
DuplicateSeverity = Literal["low", "medium", "high"]
RevisionOverwriteSeverity = Literal["low", "medium", "high"]
FindingSeverity = Literal["low", "medium", "high"]
FindingConfidence = Literal["proven_by_contract", "suspicious", "strong"]


class CanonicalModel(BaseModel):
    """Base class for every public QuantCheck schema.

    ``frozen`` gives immutability and hashability, ``extra="forbid"`` rejects
    unknown fields, and ``strict`` disables Pydantic's implicit coercions so
    that every accepted input form is one this module states explicitly.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        validate_default=True,
        revalidate_instances="never",
    )


def _validate_token(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"expected a string, got {type(value).__name__}")
    if not value:
        raise ValueError("must not be empty")
    if value != value.strip():
        raise ValueError("must not have leading or trailing whitespace")
    if len(value) > _MAX_TOKEN_LENGTH:
        raise ValueError(f"must be at most {_MAX_TOKEN_LENGTH} characters")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ValueError("must not contain control characters")
    return value


def _validate_decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid financial value")
    if isinstance(value, Decimal):
        canonical_decimal_string(value)
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        return parse_canonical_decimal(value)
    raise ValueError(
        f"expected Decimal, int, or a canonical decimal string, got {type(value).__name__}"
    )


def _validate_date(value: object) -> date:
    if isinstance(value, datetime):
        raise ValueError("expected a day-level date, got datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_canonical_date(value)
    raise ValueError(f"expected date or a canonical ISO date string, got {type(value).__name__}")


def _validate_utc_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expected a timezone-aware datetime")
        return value.astimezone(UTC)
    if isinstance(value, str):
        return parse_canonical_datetime(value)
    raise ValueError(
        f"expected an aware datetime or canonical timestamp string, got {type(value).__name__}"
    )


def _validate_non_negative_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid integer")
    if not isinstance(value, int):
        raise ValueError(f"expected an integer, got {type(value).__name__}")
    if value < 0:
        raise ValueError("must not be negative")
    return value


def _validate_positive_int(value: object) -> int:
    validated = _validate_non_negative_int(value)
    if validated == 0:
        raise ValueError("must be a positive integer")
    return validated


def _to_tuple(value: object) -> object:
    if isinstance(value, list):
        return tuple(value)
    return value


def _pattern_validator(pattern: re.Pattern[str], label: str) -> BeforeValidator:
    def _validate(value: object) -> str:
        text = _validate_token(value)
        if pattern.fullmatch(text) is None:
            raise ValueError(f"malformed {label}: {text!r}")
        return text

    return BeforeValidator(_validate)


Token = Annotated[str, BeforeValidator(_validate_token)]
CanonicalDecimal = Annotated[Decimal, BeforeValidator(_validate_decimal)]


def _validate_unit_interval(value: Decimal) -> Decimal:
    if value < 0 or value > 1:
        raise ValueError("must be between zero and one inclusive")
    return value


UnitIntervalDecimal = Annotated[
    Decimal,
    BeforeValidator(_validate_decimal),
    AfterValidator(_validate_unit_interval),
]
FinancialDate = Annotated[date, BeforeValidator(_validate_date)]
UtcTimestamp = Annotated[datetime, BeforeValidator(_validate_utc_datetime)]
NonNegativeInteger = Annotated[int, BeforeValidator(_validate_non_negative_int)]
PositiveInteger = Annotated[int, BeforeValidator(_validate_positive_int)]

RecordId = Annotated[str, _pattern_validator(RECORD_ID_PATTERN, "record_id")]
ModifiedRecordId = RecordId
DatasetSnapshotId = Annotated[str, _pattern_validator(DATASET_SNAPSHOT_ID_PATTERN, "snapshot_id")]
AuditInputSnapshotId = Annotated[
    str, _pattern_validator(AUDIT_INPUT_SNAPSHOT_ID_PATTERN, "audit_input_id")
]
CaseConfigId = Annotated[str, _pattern_validator(CASE_CONFIG_ID_PATTERN, "case_id")]
ContentHash = Annotated[str, _pattern_validator(CONTENT_HASH_PATTERN, "content hash")]
FaultId = Annotated[str, _pattern_validator(FAULT_ID_PATTERN, "fault_id")]
ManifestId = Annotated[str, _pattern_validator(MANIFEST_ID_PATTERN, "manifest_id")]
FindingId = Annotated[str, _pattern_validator(FINDING_ID_PATTERN, "finding_id")]
AuditReportId = Annotated[str, _pattern_validator(AUDIT_REPORT_ID_PATTERN, "audit_report_id")]
ScoreReportId = Annotated[str, _pattern_validator(SCORE_REPORT_ID_PATTERN, "score_report_id")]
ResearchResultId = Annotated[
    str, _pattern_validator(RESEARCH_RESULT_ID_PATTERN, "research_result_id")
]
ImpactId = Annotated[str, _pattern_validator(IMPACT_ID_PATTERN, "impact_id")]
RevisionId = Annotated[str, _pattern_validator(REVISION_ID_PATTERN, "revision_id")]
RevisionUnitId = Annotated[str, _pattern_validator(REVISION_UNIT_ID_PATTERN, "eligibility_unit_id")]


class Dimension(CanonicalModel):
    """One qualifying axis/member pair attached to a financial observation."""

    axis: Token
    member: Token


def _normalize_dimensions(value: tuple[Dimension, ...]) -> tuple[Dimension, ...]:
    axes = [dimension.axis for dimension in value]
    if len(set(axes)) != len(axes):
        raise ValueError("dimension axes must be unique")
    return tuple(sorted(value, key=lambda dimension: dimension.axis))


Dimensions = Annotated[
    tuple[Dimension, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_dimensions),
]


def _normalize_records[RecordT: (FinancialFact, AuditInputRecord)](
    value: tuple[RecordT, ...],
) -> tuple[RecordT, ...]:
    record_ids = [record.record_id for record in value]
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("record_id values must be unique within a snapshot")
    return tuple(sorted(value, key=lambda record: record.record_id))


class SourceReference(CanonicalModel):
    """Where a record came from, in terms stable across runs and machines.

    ``source_row_key`` must be a key that the source itself defines (an
    accession/fact coordinate, a fixture row key). It must never be a
    DataFrame row position, because row position is not stable under
    reordering.
    """

    source_name: Token
    source_locator: Token
    source_row_key: Token


class FinancialFact(CanonicalModel):
    """One point-in-time financial observation.

    Temporal fields are distinct concepts and are validated independently:

    * ``period_start`` / ``period_end`` describe the economic period;
    * ``filed_on`` is when the source published the value;
    * ``available_on`` is when a researcher could act on it.

    The schema deliberately does **not** require ``available_on >= filed_on``.
    A record that is available before it was filed is exactly the Look-Ahead
    Timestamp defect QuantCheck exists to inject and detect, so the contract
    layer must be able to represent it.
    """

    record_id: RecordId
    entity_id: Token
    entity_name: Token | None = None
    concept_namespace: Token
    concept: Token
    value: CanonicalDecimal
    unit: Token
    dimensions: Dimensions = ()
    period_type: PeriodType
    period_start: FinancialDate | None = None
    period_end: FinancialDate
    filed_on: FinancialDate
    available_on: FinancialDate
    form: Token | None = None
    accession_number: Token | None = None
    source: SourceReference

    @model_validator(mode="after")
    def _check_period_shape(self) -> FinancialFact:
        if self.period_type == "instant":
            if self.period_start is not None:
                raise ValueError("an instant observation must not have a period_start")
        elif self.period_start is None:
            raise ValueError("a duration observation requires a period_start")
        elif self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


class AuditInputRecord(CanonicalModel):
    """A single record as a manifest-blind detector is allowed to see it.

    This is the sanitized side of the audit boundary. It carries no
    pre-corruption value, no injected-row flag, no answer-key role, no target
    selection, and no filesystem path. Adding any such field here would breach
    hard invariants 1 and 2 in ``AGENTS.md``.
    """

    record_id: RecordId
    entity_id: Token
    concept_namespace: Token
    concept: Token
    value: CanonicalDecimal
    unit: Token
    dimensions: Dimensions = ()
    period_type: PeriodType
    period_start: FinancialDate | None = None
    period_end: FinancialDate
    filed_on: FinancialDate
    available_on: FinancialDate
    form: Token | None = None
    accession_number: Token | None = None
    source_name: Token
    source_locator: Token

    @model_validator(mode="after")
    def _check_period_shape(self) -> AuditInputRecord:
        if self.period_type == "instant":
            if self.period_start is not None:
                raise ValueError("an instant observation must not have a period_start")
        elif self.period_start is None:
            raise ValueError("a duration observation requires a period_start")
        elif self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


FinancialFacts = Annotated[
    tuple[FinancialFact, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_records),
]

AuditInputRecords = Annotated[
    tuple[AuditInputRecord, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_records),
]


class DatasetSnapshot(CanonicalModel):
    """An immutable set of facts considered as of one research date.

    Records are sorted by ``record_id`` during validation, so the snapshot's
    logical content — and therefore its hash and identifier — does not depend
    on the order in which rows were supplied.
    """

    snapshot_id: DatasetSnapshotId
    dataset_name: Token
    as_of_date: FinancialDate
    records: FinancialFacts = ()


class AuditInputSnapshot(CanonicalModel):
    """The sanitized snapshot handed to manifest-blind detectors."""

    audit_input_id: AuditInputSnapshotId
    dataset_name: Token
    as_of_date: FinancialDate
    records: AuditInputRecords = ()


class CaseConfig(CanonicalModel):
    """The logical identity of a benchmark case.

    It contains only values that change what the case *means*. Runtime facts
    (when it ran, on which machine, under which interpreter) live in
    :class:`RuntimeMetadata` and must never appear here, or the same logical
    case would get a different identity on every run.
    """

    case_id: CaseConfigId
    case_name: Token
    dataset_name: Token
    as_of_date: FinancialDate
    seed: NonNegativeInteger
    spec_version: Token


class RuntimeMetadata(CanonicalModel):
    """Facts about one execution. Never part of any logical identity.

    Deliberately excludes output directories, temporary directories, working
    directories, absolute paths, and usernames.
    """

    code_version: Token
    python_version: Token
    platform: Token
    generated_at: UtcTimestamp


class ArtifactIdentity(CanonicalModel):
    """The pairing of an artifact's stable identifier with its content hash."""

    kind: Token
    stable_id: Token
    content_hash: ContentHash


# --- Recovery Phase 5: narrow Unit Drift contracts --------------------------


class ComparableSeriesKey(CanonicalModel):
    """Exact economic context within which local values may be compared."""

    entity_id: Token
    concept_namespace: Token
    concept: Token
    unit: Token
    dimensions: Dimensions = ()
    period_type: PeriodType
    period_length_days: PositiveInteger | None = None

    @model_validator(mode="after")
    def _check_period_shape(self) -> ComparableSeriesKey:
        if self.period_type == "instant" and self.period_length_days is not None:
            raise ValueError("instant comparable series must not have period_length_days")
        if self.period_type == "duration" and self.period_length_days is None:
            raise ValueError("duration comparable series require period_length_days")
        return self


class UnitDriftInjectionConfig(CanonicalModel):
    """Deterministic configuration for scaled-value, unchanged-unit injection."""

    fault_type: Literal["unit_drift"] = "unit_drift"
    fault_subtype: Literal["value_scaled_unit_unchanged"] = "value_scaled_unit_unchanged"
    spec_version: Literal["quantcheck/unit-drift-value-scale/v1"] = (
        "quantcheck/unit-drift-value-scale/v1"
    )
    severity: UnitDriftSeverity
    seed: NonNegativeInteger
    max_targets: PositiveInteger = 100


_APPROVED_UNIT_DRIFT_SCALE_FACTORS = frozenset(
    {Decimal("100"), Decimal("1000"), Decimal("1000000")}
)


def _normalize_supported_scale_factors(
    value: tuple[Decimal, ...],
) -> tuple[Decimal, ...]:
    if not value:
        raise ValueError("supported_scale_factors must not be empty")
    if len(set(value)) != len(value):
        raise ValueError("supported_scale_factors must not contain duplicates")
    for factor in value:
        if factor not in _APPROVED_UNIT_DRIFT_SCALE_FACTORS:
            raise ValueError(f"unsupported Unit Drift scale factor: {factor}")
    return tuple(sorted(value))


SupportedUnitDriftScaleFactors = Annotated[
    tuple[CanonicalDecimal, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_supported_scale_factors),
]


class UnitDriftDetectorConfig(CanonicalModel):
    """Public, manifest-independent local-ratio detector configuration."""

    ratio_threshold: CanonicalDecimal = Decimal("50")
    supported_scale_factors: SupportedUnitDriftScaleFactors = (
        Decimal("100"),
        Decimal("1000"),
        Decimal("1000000"),
    )

    @model_validator(mode="after")
    def _check_threshold(self) -> UnitDriftDetectorConfig:
        if self.ratio_threshold <= 1:
            raise ValueError("ratio_threshold must be greater than one")
        return self


class UnitDriftMutation(CanonicalModel):
    """The exact private reversible value scaling for one injected fault."""

    field: Literal["value"] = "value"
    original_value: CanonicalDecimal
    corrupted_value: CanonicalDecimal
    scale_factor: CanonicalDecimal

    @model_validator(mode="after")
    def _check_scale_relationship(self) -> UnitDriftMutation:
        if self.scale_factor <= 1 or self.scale_factor != self.scale_factor.to_integral_value():
            raise ValueError("scale_factor must be an integer greater than one")
        if self.original_value == 0:
            raise ValueError("Unit Drift cannot scale a zero original value")
        if self.corrupted_value != self.original_value * self.scale_factor:
            raise ValueError("corrupted_value must equal original_value times scale_factor")
        return self


# --- Recovery Phase 3: narrow Look-Ahead artifact contracts -----------------


class LookAheadInjectionConfig(CanonicalModel):
    """Deterministic configuration for period-end availability substitution."""

    spec_version: Literal["quantcheck/lookahead-period-end/v1"] = (
        "quantcheck/lookahead-period-end/v1"
    )
    severity: LookAheadSeverity
    seed: NonNegativeInteger
    research_as_of_date: FinancialDate
    max_targets: PositiveInteger = 100


class LookAheadMutation(CanonicalModel):
    """The exact private reversible date mutation for one injected fault."""

    field: Literal["available_on"] = "available_on"
    original_date: FinancialDate
    corrupted_date: FinancialDate

    @model_validator(mode="after")
    def _check_direction(self) -> LookAheadMutation:
        if self.corrupted_date >= self.original_date:
            raise ValueError("Look-Ahead corruption must move available_on backward")
        return self


class FaultManifestEntry(CanonicalModel):
    """Private answer-key evidence for one period-end substitution."""

    fault_id: FaultId
    fault_type: Literal["lookahead_timestamp"] = "lookahead_timestamp"
    fault_subtype: Literal["period_end_substitution"] = "period_end_substitution"
    spec_version: Literal["quantcheck/lookahead-period-end/v1"] = (
        "quantcheck/lookahead-period-end/v1"
    )
    severity: LookAheadSeverity
    target_rank: NonNegativeInteger
    selection_digest: ContentHash
    eligibility_unit_id: RecordId
    research_as_of_date: FinancialDate
    original_record: FinancialFact
    corrupted_record: FinancialFact
    mutation: LookAheadMutation

    @model_validator(mode="after")
    def _check_exact_relationship(self) -> FaultManifestEntry:
        if not self.original_record.record_id.startswith("rec_"):
            raise ValueError("original_record must carry a source rec_ identifier")
        if self.corrupted_record.record_id == self.original_record.record_id:
            raise ValueError("corrupted_record must carry a distinct derived record_id")
        if self.eligibility_unit_id != self.original_record.record_id:
            raise ValueError("eligibility_unit_id must equal original_record.record_id")
        if self.mutation.original_date != self.original_record.available_on:
            raise ValueError("mutation original_date must equal the original available_on")
        if self.mutation.corrupted_date != self.corrupted_record.available_on:
            raise ValueError("mutation corrupted_date must equal the corrupted available_on")
        if self.original_record.available_on != self.original_record.filed_on:
            raise ValueError("eligible clean Look-Ahead records require available_on == filed_on")
        if self.corrupted_record.available_on != self.corrupted_record.period_end:
            raise ValueError("period-end substitution must set available_on to period_end")
        if not (
            self.corrupted_record.available_on
            <= self.research_as_of_date
            < self.original_record.available_on
        ):
            raise ValueError("research_as_of_date must fall inside the manufactured leak window")

        unchanged_fields = set(FinancialFact.model_fields) - {"record_id", "available_on"}
        for field_name in unchanged_fields:
            if getattr(self.original_record, field_name) != getattr(
                self.corrupted_record, field_name
            ):
                raise ValueError(
                    "Look-Ahead injection may change only record_id and available_on; "
                    f"field {field_name!r} differs"
                )
        return self


def _normalize_unique_ids(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("identifier tuples must contain unique values")
    return tuple(sorted(value))


RecordIds = Annotated[
    tuple[RecordId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_ids),
]


def _record_period_length_days(record: FinancialFact) -> int | None:
    if record.period_type == "instant":
        return None
    assert record.period_start is not None
    return (record.period_end - record.period_start).days + 1


class UnitDriftManifestEntry(CanonicalModel):
    """Private answer-key evidence for one exact scaled-value mutation."""

    fault_id: FaultId
    fault_type: Literal["unit_drift"] = "unit_drift"
    fault_subtype: Literal["value_scaled_unit_unchanged"] = "value_scaled_unit_unchanged"
    spec_version: Literal["quantcheck/unit-drift-value-scale/v1"] = (
        "quantcheck/unit-drift-value-scale/v1"
    )
    severity: UnitDriftSeverity
    target_rank: NonNegativeInteger
    selection_digest: ContentHash
    eligibility_unit_id: RecordId
    snapshot_as_of_date: FinancialDate
    comparable_series_key: ComparableSeriesKey
    series_record_ids: RecordIds
    eligible_neighbor_record_ids: RecordIds
    original_record: FinancialFact
    corrupted_record: FinancialFact
    mutation: UnitDriftMutation

    @model_validator(mode="after")
    def _check_exact_relationship(self) -> UnitDriftManifestEntry:
        if self.eligibility_unit_id != self.original_record.record_id:
            raise ValueError("eligibility_unit_id must equal original_record.record_id")
        if self.corrupted_record.record_id == self.original_record.record_id:
            raise ValueError("corrupted_record must carry a distinct derived record_id")
        if self.original_record.record_id not in self.series_record_ids:
            raise ValueError("the selected original must belong to series_record_ids")
        if len(self.series_record_ids) < 3:
            raise ValueError("eligible Unit Drift series require at least three observations")
        if not 1 <= len(self.eligible_neighbor_record_ids) <= 2:
            raise ValueError("eligible Unit Drift targets require one or two usable neighbors")
        if not set(self.eligible_neighbor_record_ids) < set(self.series_record_ids):
            raise ValueError("eligible neighbors must be other records in the comparable series")
        if self.original_record.available_on > self.snapshot_as_of_date:
            raise ValueError("the selected original must be visible at the snapshot cutoff")
        if self.original_record.value == 0:
            raise ValueError("a zero-valued record is not an eligible Unit Drift target")

        expected_key = ComparableSeriesKey(
            entity_id=self.original_record.entity_id,
            concept_namespace=self.original_record.concept_namespace,
            concept=self.original_record.concept,
            unit=self.original_record.unit,
            dimensions=self.original_record.dimensions,
            period_type=self.original_record.period_type,
            period_length_days=_record_period_length_days(self.original_record),
        )
        if self.comparable_series_key != expected_key:
            raise ValueError("comparable_series_key does not match the original record")
        if self.mutation.original_value != self.original_record.value:
            raise ValueError("mutation original_value must equal the original record value")
        if self.mutation.corrupted_value != self.corrupted_record.value:
            raise ValueError("mutation corrupted_value must equal the corrupted record value")

        unchanged_fields = set(FinancialFact.model_fields) - {"record_id", "value"}
        for field_name in unchanged_fields:
            if getattr(self.original_record, field_name) != getattr(
                self.corrupted_record, field_name
            ):
                raise ValueError(
                    "Unit Drift injection may change only record_id and value; "
                    f"field {field_name!r} differs"
                )
        return self


def _normalize_unit_drift_manifest_entries(
    value: tuple[UnitDriftManifestEntry, ...],
) -> tuple[UnitDriftManifestEntry, ...]:
    return tuple(sorted(value, key=lambda entry: entry.fault_id))


UnitDriftManifestEntries = Annotated[
    tuple[UnitDriftManifestEntry, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unit_drift_manifest_entries),
]


class UnitDriftManifest(CanonicalModel):
    """Private Unit Drift truth, unavailable until audit finalization."""

    manifest_id: ManifestId
    fault_type: Literal["unit_drift"] = "unit_drift"
    fault_subtype: Literal["value_scaled_unit_unchanged"] = "value_scaled_unit_unchanged"
    spec_version: Literal["quantcheck/unit-drift-value-scale/v1"] = (
        "quantcheck/unit-drift-value-scale/v1"
    )
    dataset_name: Token
    snapshot_as_of_date: FinancialDate
    clean_snapshot_id: DatasetSnapshotId
    clean_snapshot_hash: ContentHash
    corrupted_snapshot_id: DatasetSnapshotId
    corrupted_snapshot_hash: ContentHash
    seed: NonNegativeInteger
    severity: UnitDriftSeverity
    scale_factor: CanonicalDecimal
    target_fraction: UnitIntervalDecimal
    max_targets: PositiveInteger
    eligible_record_ids: RecordIds
    eligible_record_count: NonNegativeInteger
    target_count: NonNegativeInteger
    entries: UnitDriftManifestEntries = ()

    @model_validator(mode="after")
    def _check_manifest_relationships(self) -> UnitDriftManifest:
        if self.scale_factor not in _APPROVED_UNIT_DRIFT_SCALE_FACTORS:
            raise ValueError("manifest scale_factor is not an approved Unit Drift factor")
        if self.eligible_record_count != len(self.eligible_record_ids):
            raise ValueError("eligible_record_count must equal eligible_record_ids length")
        if self.target_count != len(self.entries):
            raise ValueError("target_count must equal manifest entry count")
        if self.target_count > self.eligible_record_count:
            raise ValueError("target_count must not exceed eligible_record_count")
        if self.target_count > self.max_targets:
            raise ValueError("target_count must not exceed max_targets")

        fault_ids = [entry.fault_id for entry in self.entries]
        original_ids = [entry.original_record.record_id for entry in self.entries]
        corrupted_ids = [entry.corrupted_record.record_id for entry in self.entries]
        ranks = [entry.target_rank for entry in self.entries]
        for label, values in (
            ("fault_id", fault_ids),
            ("original record_id", original_ids),
            ("corrupted record_id", corrupted_ids),
            ("target_rank", ranks),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"manifest entries must have unique {label} values")
        if sorted(ranks) != list(range(len(ranks))):
            raise ValueError("target_rank values must be contiguous and zero-based")
        if not set(original_ids) <= set(self.eligible_record_ids):
            raise ValueError("every selected original must be an eligible record")
        for entry in self.entries:
            if (
                entry.spec_version != self.spec_version
                or entry.severity != self.severity
                or entry.snapshot_as_of_date != self.snapshot_as_of_date
                or entry.mutation.scale_factor != self.scale_factor
            ):
                raise ValueError("manifest entry configuration must match its manifest")
        return self


def _normalize_manifest_entries(
    value: tuple[FaultManifestEntry, ...],
) -> tuple[FaultManifestEntry, ...]:
    return tuple(sorted(value, key=lambda entry: entry.fault_id))


ManifestEntries = Annotated[
    tuple[FaultManifestEntry, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_manifest_entries),
]


class FaultManifest(CanonicalModel):
    """Private Look-Ahead truth, unavailable until audit finalization."""

    manifest_id: ManifestId
    fault_type: Literal["lookahead_timestamp"] = "lookahead_timestamp"
    fault_subtype: Literal["period_end_substitution"] = "period_end_substitution"
    spec_version: Literal["quantcheck/lookahead-period-end/v1"] = (
        "quantcheck/lookahead-period-end/v1"
    )
    dataset_name: Token
    snapshot_as_of_date: FinancialDate
    research_as_of_date: FinancialDate
    clean_snapshot_id: DatasetSnapshotId
    clean_snapshot_hash: ContentHash
    corrupted_snapshot_id: DatasetSnapshotId
    corrupted_snapshot_hash: ContentHash
    seed: NonNegativeInteger
    severity: LookAheadSeverity
    target_fraction: UnitIntervalDecimal
    minimum_lag_days: PositiveInteger
    max_targets: PositiveInteger
    eligible_record_ids: RecordIds
    eligible_record_count: NonNegativeInteger
    target_count: NonNegativeInteger
    entries: ManifestEntries = ()

    @model_validator(mode="after")
    def _check_manifest_relationships(self) -> FaultManifest:
        if self.research_as_of_date > self.snapshot_as_of_date:
            raise ValueError("research_as_of_date must not follow snapshot_as_of_date")
        if self.eligible_record_count != len(self.eligible_record_ids):
            raise ValueError("eligible_record_count must equal eligible_record_ids length")
        if self.target_count != len(self.entries):
            raise ValueError("target_count must equal manifest entry count")
        if self.target_count > self.eligible_record_count:
            raise ValueError("target_count must not exceed eligible_record_count")
        if self.target_count > self.max_targets:
            raise ValueError("target_count must not exceed max_targets")

        fault_ids = [entry.fault_id for entry in self.entries]
        original_ids = [entry.original_record.record_id for entry in self.entries]
        corrupted_ids = [entry.corrupted_record.record_id for entry in self.entries]
        ranks = [entry.target_rank for entry in self.entries]
        for label, values in (
            ("fault_id", fault_ids),
            ("original record_id", original_ids),
            ("corrupted record_id", corrupted_ids),
            ("target_rank", ranks),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"manifest entries must have unique {label} values")
        if sorted(ranks) != list(range(len(ranks))):
            raise ValueError("target_rank values must be contiguous and zero-based")
        if not set(original_ids) <= set(self.eligible_record_ids):
            raise ValueError("every selected original must be an eligible record")
        for entry in self.entries:
            if (
                entry.spec_version != self.spec_version
                or entry.severity != self.severity
                or entry.research_as_of_date != self.research_as_of_date
            ):
                raise ValueError("manifest entry configuration must match its manifest")
        return self


class LookAheadEvidence(CanonicalModel):
    """Detector-visible proof for one temporal contract violation."""

    record_id: ModifiedRecordId
    period_end: FinancialDate
    available_on: FinancialDate
    filed_on: FinancialDate
    audit_as_of_date: FinancialDate
    leaked_days: PositiveInteger
    source_name: Token
    source_locator: Token

    @model_validator(mode="after")
    def _check_public_evidence(self) -> LookAheadEvidence:
        if self.available_on != self.period_end:
            raise ValueError("period-end substitution evidence requires available_on == period_end")
        if self.available_on >= self.filed_on:
            raise ValueError("Look-Ahead evidence requires available_on < filed_on")
        if self.available_on > self.audit_as_of_date:
            raise ValueError("the affected record must be visible by the audit as-of date")
        if self.leaked_days != (self.filed_on - self.available_on).days:
            raise ValueError("leaked_days must equal filed_on minus available_on")
        return self


class UnitDriftNeighborEvidence(CanonicalModel):
    """One detector-visible chronological neighbor and exact ratio pair."""

    position: Literal["previous", "next"]
    record_id: RecordId
    period_start: FinancialDate | None
    period_end: FinancialDate
    value: CanonicalDecimal
    before_ratio: CanonicalDecimal
    after_ratio: CanonicalDecimal

    @model_validator(mode="after")
    def _check_ratios(self) -> UnitDriftNeighborEvidence:
        if self.value == 0:
            raise ValueError("a usable Unit Drift neighbor must be nonzero")
        if self.before_ratio < 1 or self.after_ratio < 1:
            raise ValueError("symmetric ratios must be at least one")
        return self


def _normalize_unit_drift_neighbors(
    value: tuple[UnitDriftNeighborEvidence, ...],
) -> tuple[UnitDriftNeighborEvidence, ...]:
    positions = [neighbor.position for neighbor in value]
    record_ids = [neighbor.record_id for neighbor in value]
    if len(set(positions)) != len(positions):
        raise ValueError("Unit Drift neighbor positions must be unique")
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("Unit Drift neighbor record IDs must be unique")
    order = {"previous": 0, "next": 1}
    return tuple(sorted(value, key=lambda neighbor: order[neighbor.position]))


UnitDriftNeighbors = Annotated[
    tuple[UnitDriftNeighborEvidence, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unit_drift_neighbors),
]


class UnitDriftEvidence(CanonicalModel):
    """Detector-visible local-series evidence for one scale discontinuity."""

    record_id: ModifiedRecordId
    comparable_series_key: ComparableSeriesKey
    period_start: FinancialDate | None
    period_end: FinancialDate
    available_on: FinancialDate
    audit_as_of_date: FinancialDate
    observed_value: CanonicalDecimal
    candidate_scale_factor: CanonicalDecimal
    correction_operation: Literal["divide", "multiply"]
    candidate_correction_factor: CanonicalDecimal
    corrected_value: CanonicalDecimal
    ratio_threshold: CanonicalDecimal
    neighbors: UnitDriftNeighbors
    usable_neighbor_count: PositiveInteger
    source_name: Token
    source_locator: Token

    @model_validator(mode="after")
    def _check_public_evidence(self) -> UnitDriftEvidence:
        if self.observed_value == 0 or self.corrected_value == 0:
            raise ValueError("Unit Drift evidence requires nonzero observed and corrected values")
        if self.candidate_scale_factor not in _APPROVED_UNIT_DRIFT_SCALE_FACTORS:
            raise ValueError("candidate_scale_factor is not an approved Unit Drift factor")
        expected_correction = (
            decimal_divide(Decimal(1), self.candidate_scale_factor)
            if self.correction_operation == "divide"
            else self.candidate_scale_factor
        )
        if self.candidate_correction_factor != expected_correction:
            raise ValueError("candidate_correction_factor disagrees with the operation")
        if self.corrected_value != self.observed_value * self.candidate_correction_factor:
            raise ValueError("corrected_value must apply candidate_correction_factor exactly")
        if self.ratio_threshold <= 1:
            raise ValueError("ratio_threshold must be greater than one")
        if self.usable_neighbor_count != len(self.neighbors) or not 1 <= len(self.neighbors) <= 2:
            raise ValueError("usable_neighbor_count must describe one or two neighbors")
        if self.available_on > self.audit_as_of_date:
            raise ValueError("the affected record must be visible by the audit as-of date")

        period_length = None
        if self.comparable_series_key.period_type == "duration":
            if self.period_start is None:
                raise ValueError("duration evidence requires period_start")
            period_length = (self.period_end - self.period_start).days + 1
        elif self.period_start is not None:
            raise ValueError("instant evidence must not have period_start")
        if period_length != self.comparable_series_key.period_length_days:
            raise ValueError("evidence period shape disagrees with comparable_series_key")

        for neighbor in self.neighbors:
            expected_before = symmetric_absolute_ratio(self.observed_value, neighbor.value)
            expected_after = symmetric_absolute_ratio(self.corrected_value, neighbor.value)
            if neighbor.before_ratio != expected_before or neighbor.after_ratio != expected_after:
                raise ValueError("neighbor ratios do not match the public values")
            if neighbor.before_ratio < self.ratio_threshold:
                raise ValueError("every before-correction ratio must meet the threshold")
            if neighbor.after_ratio >= self.ratio_threshold:
                raise ValueError("every after-correction ratio must be below the threshold")
            if neighbor.position == "previous" and neighbor.period_end >= self.period_end:
                raise ValueError("previous neighbor must precede the affected period")
            if neighbor.position == "next" and neighbor.period_end <= self.period_end:
                raise ValueError("next neighbor must follow the affected period")
        return self


# --- Recovery Phase 6: narrow Duplicate Observations contracts -------------


class DuplicateFingerprint(CanonicalModel):
    """The exact semantic identity of one source occurrence.

    Deliberately excludes ``record_id`` (a generated copy must still group
    with its source occurrence), ``form`` (a non-semantic label per the
    authoritative contract), ``entity_name`` (already outside
    ``AuditInputRecord``), and any private revision/source-row marker (also
    already outside ``AuditInputRecord``). ``source_name``/``source_locator``
    stand in for "source row" identity at the sanitized audit boundary.
    """

    entity_id: Token
    concept_namespace: Token
    concept: Token
    value: CanonicalDecimal
    unit: Token
    dimensions: Dimensions = ()
    period_type: PeriodType
    period_start: FinancialDate | None = None
    period_end: FinancialDate
    filed_on: FinancialDate
    available_on: FinancialDate
    accession_number: Token | None = None
    source_name: Token
    source_locator: Token

    @model_validator(mode="after")
    def _check_period_shape(self) -> DuplicateFingerprint:
        if self.period_type == "instant":
            if self.period_start is not None:
                raise ValueError("an instant fingerprint must not have a period_start")
        elif self.period_start is None:
            raise ValueError("a duration fingerprint requires a period_start")
        return self


class DuplicateInjectionConfig(CanonicalModel):
    """Deterministic configuration for exact-occurrence-copy injection."""

    fault_type: Literal["duplicate_observation"] = "duplicate_observation"
    fault_subtype: Literal["exact_occurrence_copy"] = "exact_occurrence_copy"
    spec_version: Literal["quantcheck/duplicate-exact-occurrence-copy/v1"] = (
        "quantcheck/duplicate-exact-occurrence-copy/v1"
    )
    severity: DuplicateSeverity
    seed: NonNegativeInteger
    max_targets: PositiveInteger = 100


class DuplicateMutation(CanonicalModel):
    """The exact private reversible copy relationship for one injected fault."""

    field: Literal["record_id"] = "record_id"
    original_record_id: RecordId
    created_record_id: RecordId
    copy_ordinal: PositiveInteger

    @model_validator(mode="after")
    def _check_copy_relationship(self) -> DuplicateMutation:
        if self.created_record_id == self.original_record_id:
            raise ValueError("created_record_id must be distinct from original_record_id")
        if self.copy_ordinal != 1:
            raise ValueError("Duplicate Observations v0.1 supports exactly one copy per fault")
        return self


class DuplicateManifestEntry(CanonicalModel):
    """Private answer-key evidence for one exact occurrence copy."""

    fault_id: FaultId
    fault_type: Literal["duplicate_observation"] = "duplicate_observation"
    fault_subtype: Literal["exact_occurrence_copy"] = "exact_occurrence_copy"
    spec_version: Literal["quantcheck/duplicate-exact-occurrence-copy/v1"] = (
        "quantcheck/duplicate-exact-occurrence-copy/v1"
    )
    severity: DuplicateSeverity
    target_rank: NonNegativeInteger
    selection_digest: ContentHash
    eligibility_unit_id: RecordId
    snapshot_as_of_date: FinancialDate
    fingerprint_hash: ContentHash
    original_record: FinancialFact
    created_record: FinancialFact
    mutation: DuplicateMutation

    @model_validator(mode="after")
    def _check_exact_relationship(self) -> DuplicateManifestEntry:
        if self.eligibility_unit_id != self.original_record.record_id:
            raise ValueError("eligibility_unit_id must equal original_record.record_id")
        if self.created_record.record_id == self.original_record.record_id:
            raise ValueError("created_record must carry a distinct derived record_id")
        if self.mutation.original_record_id != self.original_record.record_id:
            raise ValueError("mutation original_record_id must equal original_record.record_id")
        if self.mutation.created_record_id != self.created_record.record_id:
            raise ValueError("mutation created_record_id must equal created_record.record_id")
        if self.original_record.available_on > self.snapshot_as_of_date:
            raise ValueError("the selected original must be visible at the snapshot cutoff")

        unchanged_fields = set(FinancialFact.model_fields) - {"record_id"}
        for field_name in unchanged_fields:
            if getattr(self.original_record, field_name) != getattr(
                self.created_record, field_name
            ):
                raise ValueError(
                    f"Duplicate injection may change only record_id; field {field_name!r} differs"
                )
        return self


def _normalize_duplicate_manifest_entries(
    value: tuple[DuplicateManifestEntry, ...],
) -> tuple[DuplicateManifestEntry, ...]:
    return tuple(sorted(value, key=lambda entry: entry.fault_id))


DuplicateManifestEntries = Annotated[
    tuple[DuplicateManifestEntry, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_duplicate_manifest_entries),
]


class DuplicateManifest(CanonicalModel):
    """Private Duplicate Observations truth, unavailable until audit finalization."""

    manifest_id: ManifestId
    fault_type: Literal["duplicate_observation"] = "duplicate_observation"
    fault_subtype: Literal["exact_occurrence_copy"] = "exact_occurrence_copy"
    spec_version: Literal["quantcheck/duplicate-exact-occurrence-copy/v1"] = (
        "quantcheck/duplicate-exact-occurrence-copy/v1"
    )
    dataset_name: Token
    snapshot_as_of_date: FinancialDate
    clean_snapshot_id: DatasetSnapshotId
    clean_snapshot_hash: ContentHash
    corrupted_snapshot_id: DatasetSnapshotId
    corrupted_snapshot_hash: ContentHash
    seed: NonNegativeInteger
    severity: DuplicateSeverity
    target_fraction: UnitIntervalDecimal
    max_targets: PositiveInteger
    eligible_record_ids: RecordIds
    eligible_record_count: NonNegativeInteger
    target_count: NonNegativeInteger
    entries: DuplicateManifestEntries = ()

    @model_validator(mode="after")
    def _check_manifest_relationships(self) -> DuplicateManifest:
        if self.eligible_record_count != len(self.eligible_record_ids):
            raise ValueError("eligible_record_count must equal eligible_record_ids length")
        if self.target_count != len(self.entries):
            raise ValueError("target_count must equal manifest entry count")
        if self.target_count > self.eligible_record_count:
            raise ValueError("target_count must not exceed eligible_record_count")
        if self.target_count > self.max_targets:
            raise ValueError("target_count must not exceed max_targets")

        fault_ids = [entry.fault_id for entry in self.entries]
        original_ids = [entry.original_record.record_id for entry in self.entries]
        created_ids = [entry.created_record.record_id for entry in self.entries]
        ranks = [entry.target_rank for entry in self.entries]
        for label, values in (
            ("fault_id", fault_ids),
            ("original record_id", original_ids),
            ("created record_id", created_ids),
            ("target_rank", ranks),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"manifest entries must have unique {label} values")
        if sorted(ranks) != list(range(len(ranks))):
            raise ValueError("target_rank values must be contiguous and zero-based")
        if not set(original_ids) <= set(self.eligible_record_ids):
            raise ValueError("every selected original must be an eligible record")
        for entry in self.entries:
            if (
                entry.spec_version != self.spec_version
                or entry.severity != self.severity
                or entry.snapshot_as_of_date != self.snapshot_as_of_date
            ):
                raise ValueError("manifest entry configuration must match its manifest")
        return self


class DuplicateEvidence(CanonicalModel):
    """Detector-visible proof for one exact duplicate fingerprint group.

    Every field here is drawn from :class:`AuditInputRecord`; nothing here
    identifies which member of the group is the injected copy.
    """

    record_ids: RecordIds
    fingerprint_hash: ContentHash
    group_size: PositiveInteger
    entity_id: Token
    concept_namespace: Token
    concept: Token
    value: CanonicalDecimal
    unit: Token
    dimensions: Dimensions = ()
    period_type: PeriodType
    period_start: FinancialDate | None = None
    period_end: FinancialDate
    filed_on: FinancialDate
    available_on: FinancialDate
    accession_number: Token | None = None
    audit_as_of_date: FinancialDate
    source_name: Token
    source_locator: Token

    @model_validator(mode="after")
    def _check_public_evidence(self) -> DuplicateEvidence:
        if self.group_size != len(self.record_ids):
            raise ValueError("group_size must equal the number of affected record IDs")
        if self.group_size < 2:
            raise ValueError("a duplicate finding requires at least two affected records")
        if self.available_on > self.audit_as_of_date:
            raise ValueError("the affected records must be visible by the audit as-of date")
        if self.period_type == "instant":
            if self.period_start is not None:
                raise ValueError("an instant duplicate group must not have a period_start")
        elif self.period_start is None:
            raise ValueError("a duration duplicate group requires a period_start")
        return self


# --- Recovery Phase 7: narrow Revision Overwrite contracts -----------------


class EconomicFactKey(CanonicalModel):
    """Exact economic occurrence context shared by one revision history."""

    entity_id: Token
    concept_namespace: Token
    concept: Token
    unit: Token
    dimensions: Dimensions = ()
    period_type: PeriodType
    period_start: FinancialDate | None = None
    period_end: FinancialDate

    @model_validator(mode="after")
    def _check_period_shape(self) -> EconomicFactKey:
        if self.period_type == "instant":
            if self.period_start is not None:
                raise ValueError("an instant economic key must not have a period_start")
        elif self.period_start is None:
            raise ValueError("a duration economic key requires a period_start")
        elif self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


def _economic_fact_key_from_record(record: FinancialFact) -> EconomicFactKey:
    return EconomicFactKey(
        entity_id=record.entity_id,
        concept_namespace=record.concept_namespace,
        concept=record.concept,
        unit=record.unit,
        dimensions=record.dimensions,
        period_type=record.period_type,
        period_start=record.period_start,
        period_end=record.period_end,
    )


class RevisionOverwriteInjectionConfig(CanonicalModel):
    """Deterministic configuration for later-vintage substitution."""

    fault_type: Literal["revision_overwrite"] = "revision_overwrite"
    fault_subtype: Literal["later_vintage_in_earlier_state"] = "later_vintage_in_earlier_state"
    spec_version: Literal["quantcheck/revision-overwrite-later-vintage/v1"] = (
        "quantcheck/revision-overwrite-later-vintage/v1"
    )
    severity: RevisionOverwriteSeverity
    seed: NonNegativeInteger
    max_targets: PositiveInteger = 100


class RevisionOverwriteDetectorConfig(CanonicalModel):
    """Strict empty public configuration for the structural detector."""


class RevisionHistoryUnit(CanonicalModel):
    """One private, explicit adjacent historical/later revision pair."""

    eligibility_unit_id: RevisionUnitId
    lineage_id: Token
    economic_fact_key: EconomicFactKey
    snapshot_as_of_date: FinancialDate
    historical_sequence: PositiveInteger
    later_sequence: PositiveInteger
    historical_revision_id: RevisionId
    later_revision_id: RevisionId
    historical_record: FinancialFact
    later_record: FinancialFact
    relative_revision_size: CanonicalDecimal

    @model_validator(mode="after")
    def _check_history_relationship(self) -> RevisionHistoryUnit:
        historical = self.historical_record
        later = self.later_record
        if self.later_sequence != self.historical_sequence + 1:
            raise ValueError("Revision Overwrite requires adjacent declared sequences")
        if self.historical_revision_id == self.later_revision_id:
            raise ValueError("historical and later revision identities must be distinct")
        if historical.record_id == later.record_id:
            raise ValueError("historical and later source records must be distinct")
        if historical.source.source_row_key == later.source.source_row_key:
            raise ValueError("historical and later source rows must be distinct")
        if _economic_fact_key_from_record(historical) != self.economic_fact_key:
            raise ValueError("economic_fact_key must describe the historical record")
        if _economic_fact_key_from_record(later) != self.economic_fact_key:
            raise ValueError("later revision must preserve the exact economic context")
        if historical.entity_name != later.entity_name:
            raise ValueError("revision history must preserve entity_name")
        if historical.source.source_name != later.source.source_name:
            raise ValueError("revision history must preserve source_name")
        if historical.available_on != historical.filed_on:
            raise ValueError("historical clean availability must equal filing date")
        if later.available_on != later.filed_on:
            raise ValueError("later clean availability must equal filing date")
        if not (historical.available_on <= self.snapshot_as_of_date < later.available_on):
            raise ValueError("the cutoff must fall between historical and later availability")
        if later.available_on <= historical.available_on:
            raise ValueError("the later revision must be available strictly later")
        if later.filed_on <= historical.filed_on:
            raise ValueError("the later revision must be filed strictly later")
        if historical.accession_number is None or later.accession_number is None:
            raise ValueError("Revision Overwrite requires non-null accession provenance")
        if historical.accession_number == later.accession_number:
            raise ValueError("historical and later accessions must be distinct")
        if historical.value == 0:
            raise ValueError("a zero historical value has undefined relative revision size")
        if historical.value == later.value:
            raise ValueError("historical and later values must differ")
        with localcontext() as context:
            context.prec = 50
            expected_relative_size = abs(later.value - historical.value) / abs(historical.value)
        if self.relative_revision_size != expected_relative_size:
            raise ValueError("relative_revision_size must use the exact documented formula")
        if self.relative_revision_size <= 0:
            raise ValueError("relative_revision_size must be positive")
        return self


class RevisionOverwriteMutation(CanonicalModel):
    """Exact private reversible fields for one later-vintage substitution."""

    field: Literal["later_vintage"] = "later_vintage"
    historical_record_id: RecordId
    later_record_id: RecordId
    corrupted_record_id: RecordId
    retained_available_on: FinancialDate
    original_value: CanonicalDecimal
    corrupted_value: CanonicalDecimal
    original_filed_on: FinancialDate
    corrupted_filed_on: FinancialDate
    original_accession_number: Token
    corrupted_accession_number: Token
    original_form: Token | None = None
    corrupted_form: Token | None = None
    original_source_locator: Token
    corrupted_source_locator: Token
    original_source_row_key: Token
    corrupted_source_row_key: Token

    @model_validator(mode="after")
    def _check_mutation_direction(self) -> RevisionOverwriteMutation:
        if (
            len(
                {
                    self.historical_record_id,
                    self.later_record_id,
                    self.corrupted_record_id,
                }
            )
            != 3
        ):
            raise ValueError("historical, later, and corrupted record IDs must be distinct")
        if self.original_value == self.corrupted_value:
            raise ValueError("Revision Overwrite must substitute a changed value")
        if self.corrupted_filed_on <= self.original_filed_on:
            raise ValueError("the substituted filing date must be strictly later")
        if self.corrupted_accession_number == self.original_accession_number:
            raise ValueError("the substituted accession must be distinct")
        if self.corrupted_source_row_key == self.original_source_row_key:
            raise ValueError("the substituted source row must be distinct")
        return self


class RevisionOverwriteManifestEntry(CanonicalModel):
    """Private selected target plus its exact corrupted occurrence."""

    fault_id: FaultId
    fault_type: Literal["revision_overwrite"] = "revision_overwrite"
    fault_subtype: Literal["later_vintage_in_earlier_state"] = "later_vintage_in_earlier_state"
    spec_version: Literal["quantcheck/revision-overwrite-later-vintage/v1"] = (
        "quantcheck/revision-overwrite-later-vintage/v1"
    )
    severity: RevisionOverwriteSeverity
    target_rank: NonNegativeInteger
    selection_digest: ContentHash
    eligibility_unit_id: RevisionUnitId
    snapshot_as_of_date: FinancialDate
    corrupted_record: FinancialFact
    mutation: RevisionOverwriteMutation

    @model_validator(mode="after")
    def _check_entry_relationship(self) -> RevisionOverwriteManifestEntry:
        if self.mutation.corrupted_record_id != self.corrupted_record.record_id:
            raise ValueError("mutation corrupted_record_id must match corrupted_record")
        if self.mutation.retained_available_on != self.corrupted_record.available_on:
            raise ValueError("corrupted record must retain the historical availability")
        if self.mutation.corrupted_value != self.corrupted_record.value:
            raise ValueError("mutation corrupted_value must match corrupted_record")
        if self.mutation.corrupted_filed_on != self.corrupted_record.filed_on:
            raise ValueError("mutation corrupted_filed_on must match corrupted_record")
        if self.mutation.corrupted_accession_number != self.corrupted_record.accession_number:
            raise ValueError("mutation corrupted accession must match corrupted_record")
        if self.mutation.corrupted_form != self.corrupted_record.form:
            raise ValueError("mutation corrupted form must match corrupted_record")
        if self.mutation.corrupted_source_locator != self.corrupted_record.source.source_locator:
            raise ValueError("mutation corrupted source locator must match corrupted_record")
        if self.mutation.corrupted_source_row_key != self.corrupted_record.source.source_row_key:
            raise ValueError("mutation corrupted source row must match corrupted_record")
        return self


def _normalize_revision_history_units(
    value: tuple[RevisionHistoryUnit, ...],
) -> tuple[RevisionHistoryUnit, ...]:
    unit_ids = [unit.eligibility_unit_id for unit in value]
    if len(set(unit_ids)) != len(unit_ids):
        raise ValueError("eligible Revision Overwrite units must have unique identities")
    return tuple(sorted(value, key=lambda unit: unit.eligibility_unit_id))


RevisionHistoryUnits = Annotated[
    tuple[RevisionHistoryUnit, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_revision_history_units),
]


def _normalize_revision_manifest_entries(
    value: tuple[RevisionOverwriteManifestEntry, ...],
) -> tuple[RevisionOverwriteManifestEntry, ...]:
    return tuple(sorted(value, key=lambda entry: entry.fault_id))


RevisionOverwriteManifestEntries = Annotated[
    tuple[RevisionOverwriteManifestEntry, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_revision_manifest_entries),
]


class RevisionOverwriteManifest(CanonicalModel):
    """Private Revision Overwrite truth, unavailable until audit finalization."""

    manifest_id: ManifestId
    fault_type: Literal["revision_overwrite"] = "revision_overwrite"
    fault_subtype: Literal["later_vintage_in_earlier_state"] = "later_vintage_in_earlier_state"
    spec_version: Literal["quantcheck/revision-overwrite-later-vintage/v1"] = (
        "quantcheck/revision-overwrite-later-vintage/v1"
    )
    dataset_name: Token
    snapshot_as_of_date: FinancialDate
    clean_snapshot_id: DatasetSnapshotId
    clean_snapshot_hash: ContentHash
    corrupted_snapshot_id: DatasetSnapshotId
    corrupted_snapshot_hash: ContentHash
    seed: NonNegativeInteger
    severity: RevisionOverwriteSeverity
    minimum_relative_revision_size: CanonicalDecimal
    target_fraction: UnitIntervalDecimal
    max_targets: PositiveInteger
    eligible_units: RevisionHistoryUnits
    eligible_unit_count: NonNegativeInteger
    target_count: NonNegativeInteger
    entries: RevisionOverwriteManifestEntries = ()

    @model_validator(mode="after")
    def _check_manifest_relationships(self) -> RevisionOverwriteManifest:
        if self.minimum_relative_revision_size <= 0:
            raise ValueError("minimum_relative_revision_size must be positive")
        if self.eligible_unit_count != len(self.eligible_units):
            raise ValueError("eligible_unit_count must equal eligible_units length")
        if self.target_count != len(self.entries):
            raise ValueError("target_count must equal manifest entry count")
        if self.target_count > self.eligible_unit_count:
            raise ValueError("target_count must not exceed eligible_unit_count")
        if self.target_count > self.max_targets:
            raise ValueError("target_count must not exceed max_targets")

        fault_ids = [entry.fault_id for entry in self.entries]
        corrupted_ids = [entry.corrupted_record.record_id for entry in self.entries]
        selected_unit_ids = [entry.eligibility_unit_id for entry in self.entries]
        ranks = [entry.target_rank for entry in self.entries]
        for label, values in (
            ("fault_id", fault_ids),
            ("corrupted record_id", corrupted_ids),
            ("eligibility unit", selected_unit_ids),
            ("target_rank", ranks),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"manifest entries must have unique {label} values")
        if sorted(ranks) != list(range(len(ranks))):
            raise ValueError("target_rank values must be contiguous and zero-based")
        eligible_ids = {unit.eligibility_unit_id for unit in self.eligible_units}
        if not set(selected_unit_ids) <= eligible_ids:
            raise ValueError("every selected entry must reference an eligible history unit")
        for unit in self.eligible_units:
            if unit.snapshot_as_of_date != self.snapshot_as_of_date:
                raise ValueError("eligible unit cutoff must match its manifest")
            if unit.relative_revision_size < self.minimum_relative_revision_size:
                raise ValueError("eligible unit does not meet the severity threshold")
        for entry in self.entries:
            if (
                entry.spec_version != self.spec_version
                or entry.severity != self.severity
                or entry.snapshot_as_of_date != self.snapshot_as_of_date
            ):
                raise ValueError("manifest entry configuration must match its manifest")
        return self


class RevisionOverwriteEvidence(CanonicalModel):
    """Detector-visible proof of later provenance in an earlier state."""

    record_id: ModifiedRecordId
    economic_fact_key: EconomicFactKey
    observed_value: CanonicalDecimal
    available_on: FinancialDate
    filed_on: FinancialDate
    audit_as_of_date: FinancialDate
    accession_number: Token
    form: Token | None = None
    source_name: Token
    source_locator: Token
    public_provenance_hash: ContentHash

    @model_validator(mode="after")
    def _check_public_evidence(self) -> RevisionOverwriteEvidence:
        if not self.available_on <= self.audit_as_of_date < self.filed_on:
            raise ValueError("later-vintage evidence requires cutoff before filing")
        if self.available_on >= self.filed_on:
            raise ValueError("later-vintage evidence requires availability before filing")
        return self


class Finding(CanonicalModel):
    """One canonical public detector finding.

    ``fault_type``, ``fault_subtype``, and ``rule_id`` remain validated tokens
    rather than Literals so strict scoring can preserve wrong-class/rule near
    matches as explicit false positives.
    """

    finding_id: FindingId
    detector_id: Token
    detector_version: Token
    fault_type: Token
    fault_subtype: Token
    rule_id: Token
    affected_record_ids: RecordIds
    severity: FindingSeverity
    confidence: FindingConfidence
    evidence: LookAheadEvidence | UnitDriftEvidence | DuplicateEvidence | RevisionOverwriteEvidence
    explanation: Token

    @model_validator(mode="after")
    def _check_affected_record(self) -> Finding:
        if isinstance(self.evidence, DuplicateEvidence):
            if self.affected_record_ids != self.evidence.record_ids:
                raise ValueError("affected_record_ids must equal the evidence record_ids")
        elif self.affected_record_ids != (self.evidence.record_id,):
            raise ValueError("affected_record_ids must contain exactly the evidence record_id")
        return self


def _normalize_findings(value: tuple[Finding, ...]) -> tuple[Finding, ...]:
    # Exact duplicate findings are retained. Scoring, rather than schema
    # construction, is responsible for marking their additional copies false
    # positive without increasing recall.
    return tuple(sorted(value, key=lambda finding: finding.finding_id))


Findings = Annotated[
    tuple[Finding, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_findings),
]


class AuditReport(CanonicalModel):
    """A finalized immutable public report emitted before scoring starts."""

    audit_report_id: AuditReportId
    detector_id: Token
    detector_version: Token
    audit_input_id: AuditInputSnapshotId
    dataset_name: Token
    as_of_date: FinancialDate
    findings: Findings = ()

    @model_validator(mode="after")
    def _check_finding_context(self) -> AuditReport:
        for finding in self.findings:
            if finding.evidence.audit_as_of_date != self.as_of_date:
                raise ValueError("finding audit_as_of_date must match its report")
        return self


class DetectionMetrics(CanonicalModel):
    """Exact case counts and Decimal metrics; F1 lives on ScoreReport."""

    injected_faults: NonNegativeInteger
    findings: NonNegativeInteger
    true_positive_faults: NonNegativeInteger
    false_negative_faults: NonNegativeInteger
    true_positive_findings: NonNegativeInteger
    false_positive_findings: NonNegativeInteger
    eligible_clean_denominator: NonNegativeInteger
    precision: UnitIntervalDecimal | None
    recall: UnitIntervalDecimal | None
    false_positive_rate: CanonicalDecimal | None

    @model_validator(mode="after")
    def _check_count_partitions_and_nulls(self) -> DetectionMetrics:
        if self.true_positive_faults + self.false_negative_faults != self.injected_faults:
            raise ValueError("fault outcomes must partition injected_faults")
        if self.true_positive_findings + self.false_positive_findings != self.findings:
            raise ValueError("finding outcomes must partition findings")
        if self.true_positive_faults != self.true_positive_findings:
            raise ValueError("exact one-to-one matches require equal true-positive counts")
        if (self.precision is None) != (self.findings == 0):
            raise ValueError("precision is null exactly when there are no findings")
        if (self.recall is None) != (self.injected_faults == 0):
            raise ValueError("recall is null exactly when there are no injected faults")
        if (self.false_positive_rate is None) != (self.eligible_clean_denominator == 0):
            raise ValueError(
                "false_positive_rate is null exactly when the eligible clean denominator is zero"
            )
        if self.false_positive_rate is not None and self.false_positive_rate < 0:
            raise ValueError("false_positive_rate must not be negative")
        with localcontext() as context:
            context.prec = 50
            expected_precision = (
                Decimal(self.true_positive_findings) / Decimal(self.findings)
                if self.findings
                else None
            )
            expected_recall = (
                Decimal(self.true_positive_faults) / Decimal(self.injected_faults)
                if self.injected_faults
                else None
            )
            expected_false_positive_rate = (
                Decimal(self.false_positive_findings) / Decimal(self.eligible_clean_denominator)
                if self.eligible_clean_denominator
                else None
            )
        if self.precision != expected_precision:
            raise ValueError("precision must equal true_positive_findings / findings")
        if self.recall != expected_recall:
            raise ValueError("recall must equal true_positive_faults / injected_faults")
        if self.false_positive_rate != expected_false_positive_rate:
            raise ValueError(
                "false_positive_rate must equal false positives / eligible clean denominator"
            )
        return self


class ExactFindingMatch(CanonicalModel):
    """One accepted one-to-one relationship after exact scoring."""

    fault_id: FaultId
    finding_id: FindingId


def _normalize_matches(
    value: tuple[ExactFindingMatch, ...],
) -> tuple[ExactFindingMatch, ...]:
    return tuple(sorted(value, key=lambda match: (match.fault_id, match.finding_id)))


ExactMatches = Annotated[
    tuple[ExactFindingMatch, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_matches),
]
FindingIds = Annotated[
    tuple[FindingId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_ids),
]
FaultIds = Annotated[
    tuple[FaultId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unique_ids),
]


class ScoreReport(CanonicalModel):
    """Public exact-scoring result produced after audit finalization."""

    score_report_id: ScoreReportId
    scoring_spec_version: Literal[
        "quantcheck/lookahead-scoring/v1",
        "quantcheck/unit-drift-scoring/v1",
        "quantcheck/duplicate-scoring/v1",
        "quantcheck/revision-overwrite-scoring/v1",
    ] = "quantcheck/lookahead-scoring/v1"
    audit_report_id: AuditReportId
    manifest_id: ManifestId
    metrics: DetectionMetrics
    f1: UnitIntervalDecimal | None
    matches: ExactMatches = ()
    unmatched_finding_ids: FindingIds = ()
    duplicate_finding_ids: FindingIds = ()
    ambiguous_finding_ids: FindingIds = ()
    missed_fault_ids: FaultIds = ()
    ambiguous_fault_ids: FaultIds = ()

    @model_validator(mode="after")
    def _check_f1_null_convention(self) -> ScoreReport:
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
                    else (Decimal(2) * self.metrics.precision * self.metrics.recall) / denominator
                )
            if self.f1 != expected:
                raise ValueError("F1 must be the harmonic mean of precision and recall")
        return self


class AvailabilityCountResult(CanonicalModel):
    """One pure ``availability_count_v0_1`` calculation."""

    research_result_id: ResearchResultId
    method: Literal["availability_count_v0_1"] = "availability_count_v0_1"
    snapshot_id: DatasetSnapshotId
    snapshot_content_hash: ContentHash
    research_as_of_date: FinancialDate
    available_record_ids: RecordIds
    availability_count: NonNegativeInteger

    @model_validator(mode="after")
    def _check_count(self) -> AvailabilityCountResult:
        if self.availability_count != len(self.available_record_ids):
            raise ValueError("availability_count must equal available_record_ids length")
        return self


class ResearchImpact(CanonicalModel):
    """Clean/corrupted/replayed controlled availability-count comparison."""

    impact_id: ImpactId
    method: Literal["availability_count_v0_1"] = "availability_count_v0_1"
    research_as_of_date: FinancialDate
    clean: AvailabilityCountResult
    corrupted: AvailabilityCountResult
    repaired: AvailabilityCountResult
    corruption_delta: int
    changed: bool
    exact_restoration: bool

    @model_validator(mode="after")
    def _check_comparison(self) -> ResearchImpact:
        for result in (self.clean, self.corrupted, self.repaired):
            if result.research_as_of_date != self.research_as_of_date:
                raise ValueError("all research results must use the same as-of date")
        expected_delta = self.corrupted.availability_count - self.clean.availability_count
        if self.corruption_delta != expected_delta:
            raise ValueError("corruption_delta must equal corrupted minus clean count")
        if self.changed != (expected_delta != 0):
            raise ValueError("changed must reflect whether the controlled count changed")
        expected_restoration = (
            self.repaired.snapshot_id == self.clean.snapshot_id
            and self.repaired.snapshot_content_hash == self.clean.snapshot_content_hash
            and self.repaired.available_record_ids == self.clean.available_record_ids
        )
        if self.exact_restoration != expected_restoration:
            raise ValueError("exact_restoration must reflect repaired/clean identity equality")
        return self


class UnitDriftResearchConfig(CanonicalModel):
    """One exact group and end-of-day cutoff for aggregate sensitivity."""

    method: Literal["aggregate_value_v0_1"] = "aggregate_value_v0_1"
    comparable_series_key: ComparableSeriesKey
    research_as_of_date: FinancialDate


class AggregateValueResult(CanonicalModel):
    """One pure ``aggregate_value_v0_1`` calculation."""

    research_result_id: ResearchResultId
    method: Literal["aggregate_value_v0_1"] = "aggregate_value_v0_1"
    snapshot_id: DatasetSnapshotId
    snapshot_content_hash: ContentHash
    research_as_of_date: FinancialDate
    comparable_series_key: ComparableSeriesKey
    included_record_ids: RecordIds
    record_count: NonNegativeInteger
    aggregate_value: CanonicalDecimal

    @model_validator(mode="after")
    def _check_count(self) -> AggregateValueResult:
        if self.record_count != len(self.included_record_ids):
            raise ValueError("record_count must equal included_record_ids length")
        return self


class AggregateValueImpact(CanonicalModel):
    """Clean/corrupted/replayed controlled aggregate-value comparison."""

    impact_id: ImpactId
    method: Literal["aggregate_value_v0_1"] = "aggregate_value_v0_1"
    research_as_of_date: FinancialDate
    comparable_series_key: ComparableSeriesKey
    clean: AggregateValueResult
    corrupted: AggregateValueResult
    repaired: AggregateValueResult
    signed_change: CanonicalDecimal
    absolute_change: CanonicalDecimal
    relative_change: CanonicalDecimal | None
    changed: bool
    exact_restoration: bool

    @model_validator(mode="after")
    def _check_comparison(self) -> AggregateValueImpact:
        for result in (self.clean, self.corrupted, self.repaired):
            if result.research_as_of_date != self.research_as_of_date:
                raise ValueError("all aggregate results must use the same as-of date")
            if result.comparable_series_key != self.comparable_series_key:
                raise ValueError("all aggregate results must use the same comparable series")
        expected_signed = self.corrupted.aggregate_value - self.clean.aggregate_value
        if self.signed_change != expected_signed:
            raise ValueError("signed_change must equal corrupted minus clean aggregate")
        if self.absolute_change != abs(expected_signed):
            raise ValueError("absolute_change must equal the magnitude of signed_change")
        with localcontext() as context:
            context.prec = 50
            expected_relative = (
                None
                if self.clean.aggregate_value == 0
                else expected_signed / abs(self.clean.aggregate_value)
            )
        if self.relative_change != expected_relative:
            raise ValueError("relative_change must use the documented zero-baseline policy")
        if self.changed != (expected_signed != 0):
            raise ValueError("changed must reflect whether the aggregate changed")
        if self.exact_restoration != (self.repaired == self.clean):
            raise ValueError("exact_restoration must reflect exact repaired/clean result equality")
        return self


class RecordCountResult(CanonicalModel):
    """One pure ``record_count_v0_1`` calculation."""

    research_result_id: ResearchResultId
    method: Literal["record_count_v0_1"] = "record_count_v0_1"
    snapshot_id: DatasetSnapshotId
    snapshot_content_hash: ContentHash
    total_record_count: NonNegativeInteger
    duplicate_group_count: NonNegativeInteger
    duplicate_record_ids: RecordIds = ()

    @model_validator(mode="after")
    def _check_counts(self) -> RecordCountResult:
        if self.duplicate_group_count > self.total_record_count:
            raise ValueError("duplicate_group_count must not exceed total_record_count")
        if len(self.duplicate_record_ids) > self.total_record_count:
            raise ValueError("duplicate_record_ids must not exceed total_record_count")
        if self.duplicate_group_count == 0 and self.duplicate_record_ids:
            raise ValueError("duplicate_record_ids must be empty when there are no groups")
        return self


class RecordCountImpact(CanonicalModel):
    """Clean/corrupted/replayed controlled total-occurrence comparison."""

    impact_id: ImpactId
    method: Literal["record_count_v0_1"] = "record_count_v0_1"
    clean: RecordCountResult
    corrupted: RecordCountResult
    repaired: RecordCountResult
    total_count_delta: int
    duplicate_group_count_delta: int
    changed: bool
    exact_restoration: bool

    @model_validator(mode="after")
    def _check_comparison(self) -> RecordCountImpact:
        expected_total_delta = self.corrupted.total_record_count - self.clean.total_record_count
        if self.total_count_delta != expected_total_delta:
            raise ValueError("total_count_delta must equal corrupted minus clean record count")
        expected_group_delta = (
            self.corrupted.duplicate_group_count - self.clean.duplicate_group_count
        )
        if self.duplicate_group_count_delta != expected_group_delta:
            raise ValueError(
                "duplicate_group_count_delta must equal corrupted minus clean group count"
            )
        if self.changed != (expected_total_delta != 0 or expected_group_delta != 0):
            raise ValueError("changed must reflect whether the controlled counts changed")
        expected_restoration = (
            self.repaired.snapshot_id == self.clean.snapshot_id
            and self.repaired.snapshot_content_hash == self.clean.snapshot_content_hash
            and self.repaired.total_record_count == self.clean.total_record_count
            and self.repaired.duplicate_group_count == self.clean.duplicate_group_count
            and self.repaired.duplicate_record_ids == self.clean.duplicate_record_ids
        )
        if self.exact_restoration != expected_restoration:
            raise ValueError("exact_restoration must reflect repaired/clean identity equality")
        return self


class GrowthRankingConfig(CanonicalModel):
    """Exact two-period context for controlled cross-entity growth ranking."""

    method: Literal["growth_ranking_v0_1"] = "growth_ranking_v0_1"
    concept_namespace: Token
    concept: Token
    unit: Token
    dimensions: Dimensions = ()
    period_type: Literal["duration"] = "duration"
    prior_period_start: FinancialDate
    prior_period_end: FinancialDate
    current_period_start: FinancialDate
    current_period_end: FinancialDate
    research_as_of_date: FinancialDate
    top_n: PositiveInteger = 2

    @model_validator(mode="after")
    def _check_periods(self) -> GrowthRankingConfig:
        if self.prior_period_start > self.prior_period_end:
            raise ValueError("prior period start must not follow its end")
        if self.current_period_start > self.current_period_end:
            raise ValueError("current period start must not follow its end")
        if self.prior_period_end >= self.current_period_start:
            raise ValueError("growth periods must be strictly ordered and non-overlapping")
        prior_days = (self.prior_period_end - self.prior_period_start).days + 1
        current_days = (self.current_period_end - self.current_period_start).days + 1
        if prior_days != current_days:
            raise ValueError("growth periods must have the same inclusive duration")
        return self


class GrowthRankingEntry(CanonicalModel):
    """One entity's exact prior/current growth calculation and rank."""

    rank: PositiveInteger
    entity_id: Token
    prior_record_id: RecordId
    current_record_id: RecordId
    prior_value: CanonicalDecimal
    current_value: CanonicalDecimal
    growth: CanonicalDecimal

    @model_validator(mode="after")
    def _check_growth(self) -> GrowthRankingEntry:
        if self.prior_value == 0:
            raise ValueError("growth is undefined for a zero prior value")
        with localcontext() as context:
            context.prec = 50
            expected = (self.current_value - self.prior_value) / abs(self.prior_value)
        if self.growth != expected:
            raise ValueError("growth must equal (current - prior) / abs(prior)")
        return self


def _normalize_growth_entries(
    value: tuple[GrowthRankingEntry, ...],
) -> tuple[GrowthRankingEntry, ...]:
    ordered = tuple(sorted(value, key=lambda entry: entry.rank))
    if [entry.rank for entry in ordered] != list(range(1, len(ordered) + 1)):
        raise ValueError("growth ranks must be contiguous and one-based")
    entity_ids = [entry.entity_id for entry in ordered]
    if len(set(entity_ids)) != len(entity_ids):
        raise ValueError("growth ranking must contain each entity at most once")
    expected_list = sorted(ordered, key=lambda entry: entry.entity_id)
    expected_list.sort(key=lambda entry: entry.growth, reverse=True)
    expected = tuple(expected_list)
    if ordered != expected:
        raise ValueError("growth entries must rank descending with entity ID tie-breaks")
    return ordered


GrowthRankingEntries = Annotated[
    tuple[GrowthRankingEntry, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_growth_entries),
]


class GrowthRankingResult(CanonicalModel):
    """One pure ``growth_ranking_v0_1`` result."""

    research_result_id: ResearchResultId
    method: Literal["growth_ranking_v0_1"] = "growth_ranking_v0_1"
    snapshot_id: DatasetSnapshotId
    snapshot_content_hash: ContentHash
    config: GrowthRankingConfig
    rankings: GrowthRankingEntries
    eligible_entity_count: NonNegativeInteger
    top_entity_ids: Annotated[tuple[Token, ...], BeforeValidator(_to_tuple)] = ()
    excluded_zero_prior_entity_ids: Annotated[
        tuple[Token, ...], BeforeValidator(_to_tuple), AfterValidator(_normalize_unique_ids)
    ] = ()

    @model_validator(mode="after")
    def _check_result(self) -> GrowthRankingResult:
        if self.method != self.config.method:
            raise ValueError("growth result method must match its configuration")
        if self.eligible_entity_count != len(self.rankings):
            raise ValueError("eligible_entity_count must equal rankings length")
        expected_top = tuple(entry.entity_id for entry in self.rankings[: self.config.top_n])
        if self.top_entity_ids != expected_top:
            raise ValueError("top_entity_ids must be the configured ranking prefix")
        if set(self.top_entity_ids) & set(self.excluded_zero_prior_entity_ids):
            raise ValueError("zero-prior entities cannot appear in the ranking")
        return self


class GrowthRankingImpact(CanonicalModel):
    """Clean/corrupted/replayed controlled growth-ranking comparison."""

    impact_id: ImpactId
    method: Literal["growth_ranking_v0_1"] = "growth_ranking_v0_1"
    config: GrowthRankingConfig
    clean: GrowthRankingResult
    corrupted: GrowthRankingResult
    repaired: GrowthRankingResult
    changed_entity_ids: Annotated[
        tuple[Token, ...], BeforeValidator(_to_tuple), AfterValidator(_normalize_unique_ids)
    ] = ()
    maximum_absolute_growth_change: CanonicalDecimal
    ranking_changed: bool
    top_membership_changed: bool
    changed: bool
    exact_restoration: bool

    @model_validator(mode="after")
    def _check_impact(self) -> GrowthRankingImpact:
        for result in (self.clean, self.corrupted, self.repaired):
            if result.config != self.config:
                raise ValueError("all growth results must use the same configuration")
        clean_growth = {entry.entity_id: entry.growth for entry in self.clean.rankings}
        corrupted_growth = {entry.entity_id: entry.growth for entry in self.corrupted.rankings}
        all_entity_ids = set(clean_growth) | set(corrupted_growth)
        expected_changed = tuple(
            sorted(
                entity_id
                for entity_id in all_entity_ids
                if clean_growth.get(entity_id) != corrupted_growth.get(entity_id)
            )
        )
        if self.changed_entity_ids != expected_changed:
            raise ValueError("changed_entity_ids must reflect exact growth differences")
        common = set(clean_growth) & set(corrupted_growth)
        with localcontext() as context:
            context.prec = 50
            expected_maximum = max(
                (abs(corrupted_growth[entity] - clean_growth[entity]) for entity in common),
                default=Decimal(0),
            )
        if self.maximum_absolute_growth_change != expected_maximum:
            raise ValueError("maximum_absolute_growth_change is inconsistent")
        clean_order = tuple(entry.entity_id for entry in self.clean.rankings)
        corrupted_order = tuple(entry.entity_id for entry in self.corrupted.rankings)
        if self.ranking_changed != (clean_order != corrupted_order):
            raise ValueError("ranking_changed must reflect entity order")
        expected_top_change = set(self.clean.top_entity_ids) != set(self.corrupted.top_entity_ids)
        if self.top_membership_changed != expected_top_change:
            raise ValueError("top_membership_changed must reflect configured top membership")
        expected_changed_flag = bool(expected_changed) or self.ranking_changed
        if self.changed != expected_changed_flag:
            raise ValueError("changed must reflect controlled growth output changes")
        if self.exact_restoration != (self.repaired == self.clean):
            raise ValueError("exact_restoration must reflect exact repaired/clean equality")
        return self
