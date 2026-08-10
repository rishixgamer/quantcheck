"""Versioned contracts for externally supplied financial datasets.

This additive module maps customer-controlled tabular sources into the frozen
``FinancialFact`` contract.  It deliberately does not alter that contract or
the v0.1 benchmark surface.  Every semantic choice is represented here:
columns, constants, null handling, period shape, availability meaning,
provenance visibility, and source-declared revision lineage.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BeforeValidator, Field, model_validator

from quantcheck.benchmark_v2_contract import ALL_V2_DETECTORS, DetectorKeyV2
from quantcheck.benchmark_v2_schemas import DetectorRunV2
from quantcheck.corpus_schemas import CorpusModel
from quantcheck.external_dataset_policy_contract import (
    AUDIT_POLICY_ID_PATTERN,
    AuditPolicyV1,
    PolicyAuditResultV1,
    PolicyRuleEvaluationV1,
)
from quantcheck.json_types import parse_canonical_date
from quantcheck.schemas import (
    AUDIT_INPUT_SNAPSHOT_ID_PATTERN,
    CONTENT_HASH_PATTERN,
    DATASET_SNAPSHOT_ID_PATTERN,
    RECORD_ID_PATTERN,
    AuditInputSnapshot,
    BenchmarkDetectorConfigs,
    DatasetSnapshot,
    FinancialFact,
)

__all__ = [
    "ALL_EXTERNAL_INPUT_FORMATS",
    "DATASET_MAPPING_V1_SPEC_VERSION",
    "EXTERNAL_AUDIT_V1_SPEC_VERSION",
    "EXTERNAL_AUDIT_V2_SPEC_VERSION",
    "NORMALIZED_DATASET_V1_SPEC_VERSION",
    "VALIDATION_PROFILE_V1_SPEC_VERSION",
    "AvailabilityColumnMappingV1",
    "AvailabilityEqualsFilingMappingV1",
    "CsvInputOptionsV1",
    "DatasetMappingV1",
    "DateColumnMappingV1",
    "DateConstantMappingV1",
    "DiagnosticV1",
    "DimensionColumnMappingV1",
    "ExternalAuditArtifactsV1",
    "ExternalAuditArtifactsV2",
    "ExternalDatasetAuditReportV1",
    "ExternalDatasetAuditReportV2",
    "ExternalDatasetFileInputV1",
    "ExternalDatasetValidationProfileV1",
    "ExternalInputFormatV1",
    "IndependentRevisionMappingV1",
    "MappedTextColumnV1",
    "MappedTextConstantV1",
    "NormalizedDatasetV1",
    "NormalizedRowProvenanceV1",
    "OptionalDateAbsentMappingV1",
    "OptionalTextAbsentMappingV1",
    "PeriodTypeColumnMappingV1",
    "PeriodTypeConstantMappingV1",
    "RevisionColumnsMappingV1",
    "ValueColumnMappingV1",
]

DATASET_MAPPING_V1_SPEC_VERSION: Literal["quantcheck/dataset-mapping/v1"] = (
    "quantcheck/dataset-mapping/v1"
)
NORMALIZED_DATASET_V1_SPEC_VERSION: Literal["quantcheck/normalized-dataset/v1"] = (
    "quantcheck/normalized-dataset/v1"
)
VALIDATION_PROFILE_V1_SPEC_VERSION: Literal["quantcheck/dataset-validation-profile/v1"] = (
    "quantcheck/dataset-validation-profile/v1"
)
EXTERNAL_AUDIT_V1_SPEC_VERSION: Literal["quantcheck/external-audit/v1"] = (
    "quantcheck/external-audit/v1"
)
EXTERNAL_AUDIT_V2_SPEC_VERSION: Literal["quantcheck/external-audit/v2"] = (
    "quantcheck/external-audit/v2"
)

DATASET_MAPPING_V1_NAMESPACE = "quantcheck/dataset-mapping/v1"
NORMALIZED_DATASET_V1_NAMESPACE = "quantcheck/normalized-dataset/v1"
VALIDATION_PROFILE_V1_NAMESPACE = "quantcheck/dataset-validation-profile/v1"
EXTERNAL_AUDIT_V1_NAMESPACE = "quantcheck/external-audit/v1"
EXTERNAL_AUDIT_V2_NAMESPACE = "quantcheck/external-audit/v2"
EXTERNAL_SOURCE_ROW_V1_NAMESPACE = "quantcheck/external-source-row/v1"
EXTERNAL_REVISION_LINEAGE_V1_NAMESPACE = "quantcheck/external-revision-lineage/v1"

DATASET_MAPPING_ID_PATTERN = re.compile(r"^dmap_[0-9a-f]{16}$")
NORMALIZED_DATASET_ID_PATTERN = re.compile(r"^ndset_[0-9a-f]{16}$")
VALIDATION_PROFILE_ID_PATTERN = re.compile(r"^dprof_[0-9a-f]{16}$")
EXTERNAL_AUDIT_ID_PATTERN = re.compile(r"^xaudit_[0-9a-f]{16}$")
EXTERNAL_AUDIT_V2_ID_PATTERN = re.compile(r"^xaudit2_[0-9a-f]{16}$")

_MAX_TOKEN_LENGTH = 512

ExternalInputFormatV1 = Literal["csv", "parquet", "arrow_file", "arrow_stream", "python"]
ALL_EXTERNAL_INPUT_FORMATS: tuple[ExternalInputFormatV1, ...] = (
    "csv",
    "parquet",
    "arrow_file",
    "arrow_stream",
    "python",
)


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


def _validate_date(value: object) -> date:
    if isinstance(value, datetime):
        raise ValueError("expected a day-level date, got datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_canonical_date(value)
    raise ValueError(f"expected date or canonical date string, got {type(value).__name__}")


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
FinancialDate = Annotated[date, BeforeValidator(_validate_date)]
ContentHash = Annotated[str, _pattern_validator(CONTENT_HASH_PATTERN, "content hash")]
MappingId = Annotated[str, _pattern_validator(DATASET_MAPPING_ID_PATTERN, "mapping_id")]
NormalizedDatasetId = Annotated[
    str, _pattern_validator(NORMALIZED_DATASET_ID_PATTERN, "normalized_dataset_id")
]
ValidationProfileId = Annotated[
    str, _pattern_validator(VALIDATION_PROFILE_ID_PATTERN, "validation_profile_id")
]
ExternalAuditId = Annotated[
    str, _pattern_validator(EXTERNAL_AUDIT_ID_PATTERN, "external_audit_report_id")
]
ExternalAuditV2Id = Annotated[
    str, _pattern_validator(EXTERNAL_AUDIT_V2_ID_PATTERN, "external_audit_report_id")
]
AuditPolicyId = Annotated[str, _pattern_validator(AUDIT_POLICY_ID_PATTERN, "policy_id")]
RecordId = Annotated[str, _pattern_validator(RECORD_ID_PATTERN, "record_id")]
SnapshotId = Annotated[str, _pattern_validator(DATASET_SNAPSHOT_ID_PATTERN, "snapshot_id")]
AuditInputId = Annotated[str, _pattern_validator(AUDIT_INPUT_SNAPSHOT_ID_PATTERN, "audit_input_id")]


class MappedTextColumnV1(CorpusModel):
    """Read a required text value from one exact external column."""

    kind: Literal["column"] = "column"
    column: Token


class MappedTextConstantV1(CorpusModel):
    """Use one declared text constant for every source row."""

    kind: Literal["constant"] = "constant"
    value: Token


class OptionalTextAbsentMappingV1(CorpusModel):
    """Declare that the source does not supply one optional canonical field."""

    kind: Literal["absent"] = "absent"
    reason: Token


MappedTextV1 = Annotated[
    MappedTextColumnV1 | MappedTextConstantV1,
    Field(discriminator="kind"),
]
OptionalMappedTextV1 = Annotated[
    MappedTextColumnV1 | MappedTextConstantV1 | OptionalTextAbsentMappingV1,
    Field(discriminator="kind"),
]


class ValueColumnMappingV1(CorpusModel):
    """The exact financial-value column; binary floating point is prohibited."""

    column: Token
    exactness: Literal["decimal_integer_or_canonical_text_only"] = (
        "decimal_integer_or_canonical_text_only"
    )


class DateColumnMappingV1(CorpusModel):
    """A source-provided day-level calendar date."""

    kind: Literal["column"] = "column"
    column: Token
    encoding: Literal["iso8601_date_or_arrow_date"] = "iso8601_date_or_arrow_date"


class DateConstantMappingV1(CorpusModel):
    """One explicitly declared calendar date used for every row."""

    kind: Literal["constant"] = "constant"
    value: FinancialDate


class OptionalDateAbsentMappingV1(CorpusModel):
    """Declare that an optional day-level field is absent."""

    kind: Literal["absent"] = "absent"
    reason: Token


MappedDateV1 = Annotated[
    DateColumnMappingV1 | DateConstantMappingV1,
    Field(discriminator="kind"),
]
OptionalMappedDateV1 = Annotated[
    DateColumnMappingV1 | DateConstantMappingV1 | OptionalDateAbsentMappingV1,
    Field(discriminator="kind"),
]


class AvailabilityColumnMappingV1(CorpusModel):
    """Map a real source date with an explicit research-availability meaning."""

    kind: Literal["column"] = "column"
    column: Token
    semantics: Literal["first_available_to_researcher_end_of_day"] = (
        "first_available_to_researcher_end_of_day"
    )
    evidence_reference: Token


class AvailabilityEqualsFilingMappingV1(CorpusModel):
    """Explicitly assert source-supported equality to the filing date."""

    kind: Literal["same_as_filing"] = "same_as_filing"
    basis: Literal["source_contract_confirms_filing_date_equals_availability_date"] = (
        "source_contract_confirms_filing_date_equals_availability_date"
    )
    evidence_reference: Token


AvailabilityMappingV1 = Annotated[
    AvailabilityColumnMappingV1 | AvailabilityEqualsFilingMappingV1,
    Field(discriminator="kind"),
]


class PeriodTypeColumnMappingV1(CorpusModel):
    """Map source-specific period labels by two explicit, disjoint values."""

    kind: Literal["column"] = "column"
    column: Token
    instant_value: Token
    duration_value: Token

    @model_validator(mode="after")
    def _check_values(self) -> PeriodTypeColumnMappingV1:
        if self.instant_value == self.duration_value:
            raise ValueError("instant_value and duration_value must be distinct")
        return self


class PeriodTypeConstantMappingV1(CorpusModel):
    """Declare a single canonical period shape for the whole dataset."""

    kind: Literal["constant"] = "constant"
    value: Literal["instant", "duration"]


PeriodTypeMappingV1 = Annotated[
    PeriodTypeColumnMappingV1 | PeriodTypeConstantMappingV1,
    Field(discriminator="kind"),
]


class DimensionColumnMappingV1(CorpusModel):
    """One declared canonical axis whose member comes from one source column."""

    axis: Token
    member_column: Token


def _normalize_dimensions(
    value: tuple[DimensionColumnMappingV1, ...],
) -> tuple[DimensionColumnMappingV1, ...]:
    axes = [dimension.axis for dimension in value]
    if len(set(axes)) != len(axes):
        raise ValueError("dimension axes must be unique")
    columns = [dimension.member_column for dimension in value]
    if len(set(columns)) != len(columns):
        raise ValueError("dimension member columns must be unique")
    return tuple(sorted(value, key=lambda dimension: dimension.axis))


DimensionMappingsV1 = Annotated[
    tuple[DimensionColumnMappingV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_dimensions),
]


class IndependentRevisionMappingV1(CorpusModel):
    """State that this source supplies no usable revision-lineage semantics."""

    kind: Literal["independent"] = "independent"
    declaration: Literal["source_does_not_provide_revision_lineage"] = (
        "source_does_not_provide_revision_lineage"
    )


class RevisionColumnsMappingV1(CorpusModel):
    """Use explicit source-declared lineage and positive sequence columns."""

    kind: Literal["columns"] = "columns"
    lineage_column: Token
    sequence_column: Token
    semantics: Literal["source_declared_revision_lineage_and_sequence"] = (
        "source_declared_revision_lineage_and_sequence"
    )
    null_pair_semantics: Literal["both_null_means_independent_occurrence"] = (
        "both_null_means_independent_occurrence"
    )

    @model_validator(mode="after")
    def _check_columns(self) -> RevisionColumnsMappingV1:
        if self.lineage_column == self.sequence_column:
            raise ValueError("lineage and sequence must use distinct columns")
        return self


RevisionMappingV1 = Annotated[
    IndependentRevisionMappingV1 | RevisionColumnsMappingV1,
    Field(discriminator="kind"),
]


class DatasetMappingV1(CorpusModel):
    """Complete external-column mapping into the frozen financial-fact schema."""

    spec_version: Literal["quantcheck/dataset-mapping/v1"] = DATASET_MAPPING_V1_SPEC_VERSION
    dataset_name: Token
    unmapped_columns: Literal["reject", "allow"]
    entity_id: MappedTextV1
    entity_name: OptionalMappedTextV1
    concept_namespace: MappedTextV1
    concept: MappedTextV1
    value: ValueColumnMappingV1
    unit: MappedTextV1
    dimensions: DimensionMappingsV1
    period_type: PeriodTypeMappingV1
    period_start: OptionalMappedDateV1
    period_end: MappedDateV1
    filed_on: MappedDateV1
    available_on: AvailabilityMappingV1
    form: OptionalMappedTextV1
    accession_or_equivalent: OptionalMappedTextV1
    source_name: MappedTextV1
    source_locator: MappedTextV1
    source_row_id: MappedTextColumnV1
    source_provenance_visibility: Literal["public_audit_evidence"]
    revision_lineage: RevisionMappingV1

    @model_validator(mode="after")
    def _check_period_contract(self) -> DatasetMappingV1:
        if isinstance(self.period_type, PeriodTypeConstantMappingV1):
            start_is_absent = isinstance(self.period_start, OptionalDateAbsentMappingV1)
            if self.period_type.value == "instant" and not start_is_absent:
                raise ValueError("an instant-only mapping must declare period_start absent")
            if self.period_type.value == "duration" and start_is_absent:
                raise ValueError("a duration-only mapping must map period_start")
        return self


def _normalize_null_tokens(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("CSV null tokens must be unique")
    return tuple(sorted(value))


class CsvInputOptionsV1(CorpusModel):
    """Explicit CSV syntax and null semantics; no dialect is sniffed."""

    encoding: Literal["utf-8"] = "utf-8"
    delimiter: str = ","
    quote_character: str = '"'
    null_tokens: Annotated[
        tuple[str, ...],
        BeforeValidator(_to_tuple),
        AfterValidator(_normalize_null_tokens),
    ] = ()

    @model_validator(mode="after")
    def _check_characters(self) -> CsvInputOptionsV1:
        if len(self.delimiter) != 1 or self.delimiter in "\r\n\x00":
            raise ValueError("CSV delimiter must be one non-line-ending character")
        if len(self.quote_character) != 1 or self.quote_character in "\r\n\x00":
            raise ValueError("CSV quote_character must be one non-line-ending character")
        if self.delimiter == self.quote_character:
            raise ValueError("CSV delimiter and quote_character must differ")
        return self


class ExternalDatasetFileInputV1(CorpusModel):
    """File syntax and optional dry-run integrity expectations, never a path."""

    input_format: Literal["csv", "parquet", "arrow_file", "arrow_stream"]
    expected_sha256: ContentHash | None = None
    expected_size_bytes: NonNegativeInteger | None = None
    csv: CsvInputOptionsV1 | None = None

    @model_validator(mode="after")
    def _check_format_options(self) -> ExternalDatasetFileInputV1:
        if self.input_format == "csv" and self.csv is None:
            raise ValueError("CSV input requires explicit csv options")
        if self.input_format != "csv" and self.csv is not None:
            raise ValueError("CSV options are only valid for CSV input")
        return self


class DiagnosticV1(CorpusModel):
    """A fixed, data-free validation diagnostic suitable for machine use."""

    code: Token
    severity: Literal["error", "warning", "info"]
    stage: Literal["input", "schema", "normalization", "revision", "integrity"]
    field: Token | None = None
    row_number: PositiveInteger | None = None
    message: Token


def _normalize_diagnostics(value: tuple[DiagnosticV1, ...]) -> tuple[DiagnosticV1, ...]:
    return tuple(
        sorted(
            value,
            key=lambda item: (
                item.row_number if item.row_number is not None else 0,
                item.stage,
                item.code,
                item.field or "",
            ),
        )
    )


DiagnosticsV1 = Annotated[
    tuple[DiagnosticV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_diagnostics),
]


class ExternalDatasetValidationProfileV1(CorpusModel):
    """Dry-run result: structural validation only, never an audit claim."""

    validation_profile_id: ValidationProfileId
    spec_version: Literal["quantcheck/dataset-validation-profile/v1"] = (
        VALIDATION_PROFILE_V1_SPEC_VERSION
    )
    mapping_id: MappingId
    input_format: ExternalInputFormatV1
    source_sha256: ContentHash | None
    source_size_bytes: NonNegativeInteger | None
    row_count: NonNegativeInteger
    valid_record_count: NonNegativeInteger
    error_count: NonNegativeInteger
    warning_count: NonNegativeInteger
    diagnostics: DiagnosticsV1
    omitted_diagnostic_count: NonNegativeInteger
    valid: bool
    audit_claim: Literal[False] = False
    benchmark_claim: Literal[False] = False
    network_used: Literal[False] = False
    manifest_used: Literal[False] = False

    @model_validator(mode="after")
    def _check_counts(self) -> ExternalDatasetValidationProfileV1:
        if self.valid != (self.error_count == 0):
            raise ValueError("valid must reflect whether error_count is zero")
        if self.valid_record_count > self.row_count:
            raise ValueError("valid_record_count must not exceed row_count")
        visible_errors = sum(item.severity == "error" for item in self.diagnostics)
        visible_warnings = sum(item.severity == "warning" for item in self.diagnostics)
        if visible_errors > self.error_count or visible_warnings > self.warning_count:
            raise ValueError("visible diagnostics cannot exceed total counts")
        if len(self.diagnostics) + self.omitted_diagnostic_count != (
            self.error_count + self.warning_count
        ):
            raise ValueError("diagnostic totals are inconsistent")
        return self


class NormalizedRowProvenanceV1(CorpusModel):
    """Private exact source identity linked to one normalized canonical fact."""

    record_id: RecordId
    source_row_id: Token
    source_name: Token
    source_locator: Token
    revision_lineage: Token | None = None
    revision_sequence: PositiveInteger | None = None

    @model_validator(mode="after")
    def _check_revision_pair(self) -> NormalizedRowProvenanceV1:
        if (self.revision_lineage is None) != (self.revision_sequence is None):
            raise ValueError("revision lineage and sequence must be present together")
        return self


def _normalize_facts(value: tuple[FinancialFact, ...]) -> tuple[FinancialFact, ...]:
    ids = [item.record_id for item in value]
    if len(set(ids)) != len(ids):
        raise ValueError("normalized record identifiers must be unique")
    return tuple(sorted(value, key=lambda item: item.record_id))


def _normalize_provenance(
    value: tuple[NormalizedRowProvenanceV1, ...],
) -> tuple[NormalizedRowProvenanceV1, ...]:
    ids = [item.record_id for item in value]
    if len(set(ids)) != len(ids):
        raise ValueError("normalized provenance record identifiers must be unique")
    return tuple(sorted(value, key=lambda item: item.record_id))


NormalizedFactsV1 = Annotated[
    tuple[FinancialFact, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_facts),
]
NormalizedProvenanceV1 = Annotated[
    tuple[NormalizedRowProvenanceV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_provenance),
]


class NormalizedDatasetV1(CorpusModel):
    """Deterministic private normalized output, independent of source row order."""

    normalized_dataset_id: NormalizedDatasetId
    spec_version: Literal["quantcheck/normalized-dataset/v1"] = NORMALIZED_DATASET_V1_SPEC_VERSION
    mapping_id: MappingId
    dataset_name: Token
    record_count: NonNegativeInteger
    records: NormalizedFactsV1
    provenance: NormalizedProvenanceV1

    @model_validator(mode="after")
    def _check_links(self) -> NormalizedDatasetV1:
        if self.record_count != len(self.records) or self.record_count != len(self.provenance):
            raise ValueError("record_count must equal records and provenance")
        if tuple(item.record_id for item in self.records) != tuple(
            item.record_id for item in self.provenance
        ):
            raise ValueError("every normalized record must have exactly one provenance link")
        return self


def _normalize_detector_runs(value: tuple[DetectorRunV2, ...]) -> tuple[DetectorRunV2, ...]:
    order: dict[DetectorKeyV2, int] = {
        "duplicate_observation": 0,
        "lookahead_timestamp": 1,
        "revision_overwrite": 2,
        "unit_drift": 3,
    }
    keys = [item.detector for item in value]
    if len(set(keys)) != len(keys):
        raise ValueError("a selected detector may appear only once")
    return tuple(sorted(value, key=lambda item: order[item.detector]))


ExternalDetectorRunsV1 = Annotated[
    tuple[DetectorRunV2, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_detector_runs),
]


class ExternalDatasetAuditReportV1(CorpusModel):
    """Manifest-free public report for one externally supplied dataset audit."""

    external_audit_report_id: ExternalAuditId
    spec_version: Literal["quantcheck/external-audit/v1"] = EXTERNAL_AUDIT_V1_SPEC_VERSION
    mapping_id: MappingId
    normalized_dataset_id: NormalizedDatasetId
    normalized_dataset_hash: ContentHash
    dataset_name: Token
    as_of_date: FinancialDate
    source_record_count: NonNegativeInteger
    snapshot_id: SnapshotId
    snapshot_hash: ContentHash
    snapshot_record_count: NonNegativeInteger
    audit_input_id: AuditInputId
    audit_input_hash: ContentHash
    detector_configs: BenchmarkDetectorConfigs
    detector_runs: ExternalDetectorRunsV1
    finding_count: NonNegativeInteger
    manifest_used: Literal[False] = False
    fault_injection_used: Literal[False] = False
    benchmark_claim: Literal[False] = False
    network_used: Literal[False] = False

    @model_validator(mode="after")
    def _check_report(self) -> ExternalDatasetAuditReportV1:
        if self.snapshot_record_count > self.source_record_count:
            raise ValueError("snapshot count must not exceed normalized source count")
        if self.finding_count != sum(len(run.report.findings) for run in self.detector_runs):
            raise ValueError("finding_count must equal the selected detector reports")
        for run in self.detector_runs:
            if run.report.audit_input_id != self.audit_input_id:
                raise ValueError("every detector report must use the same audit input")
            if (
                run.report.dataset_name != self.dataset_name
                or run.report.as_of_date != self.as_of_date
            ):
                raise ValueError("every detector report must use the audit context")
        return self


class ExternalAuditArtifactsV1(CorpusModel):
    """In-memory workflow result; only ``public_report`` is the public artifact."""

    validation_profile: ExternalDatasetValidationProfileV1
    normalized_dataset: NormalizedDatasetV1
    snapshot: DatasetSnapshot
    audit_input: AuditInputSnapshot
    public_report: ExternalDatasetAuditReportV1


def _normalize_selected_detectors(
    value: tuple[DetectorKeyV2, ...],
) -> tuple[DetectorKeyV2, ...]:
    if len(set(value)) != len(value):
        raise ValueError("selected detectors must be unique")
    return tuple(detector for detector in ALL_V2_DETECTORS if detector in value)


ExternalSelectedDetectorsV2 = Annotated[
    tuple[DetectorKeyV2, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_selected_detectors),
]


def _normalize_policy_evaluations(
    value: tuple[PolicyRuleEvaluationV1, ...],
) -> tuple[PolicyRuleEvaluationV1, ...]:
    rule_ids = [item.rule_id for item in value]
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("policy rule evaluations must have unique rule identifiers")
    return tuple(sorted(value, key=lambda item: item.rule_id))


def _normalize_policy_results(
    value: tuple[PolicyAuditResultV1, ...],
) -> tuple[PolicyAuditResultV1, ...]:
    result_ids = [item.policy_result_id for item in value]
    if len(set(result_ids)) != len(result_ids):
        raise ValueError("policy results must have unique result identifiers")
    return tuple(sorted(value, key=lambda item: item.policy_result_id))


ExternalPolicyEvaluationsV2 = Annotated[
    tuple[PolicyRuleEvaluationV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_policy_evaluations),
]
ExternalPolicyResultsV2 = Annotated[
    tuple[PolicyAuditResultV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_policy_results),
]


class ExternalDatasetAuditReportV2(CorpusModel):
    """Policy-bearing public report for one external production audit."""

    external_audit_report_id: ExternalAuditV2Id
    spec_version: Literal["quantcheck/external-audit/v2"] = EXTERNAL_AUDIT_V2_SPEC_VERSION
    policy_id: AuditPolicyId
    policy_name: Token
    policy_version: Token
    policy_content_hash: ContentHash
    mapping_id: MappingId
    normalized_dataset_id: NormalizedDatasetId
    normalized_dataset_hash: ContentHash
    dataset_name: Token
    as_of_date: FinancialDate
    source_record_count: NonNegativeInteger
    snapshot_id: SnapshotId
    snapshot_hash: ContentHash
    snapshot_record_count: NonNegativeInteger
    audit_input_id: AuditInputId
    audit_input_hash: ContentHash
    selected_detectors: ExternalSelectedDetectorsV2
    detector_configs: BenchmarkDetectorConfigs
    detector_runs: ExternalDetectorRunsV1
    finding_count: NonNegativeInteger
    rule_evaluations: ExternalPolicyEvaluationsV2
    policy_results: ExternalPolicyResultsV2
    blocking_count: NonNegativeInteger
    warning_count: NonNegativeInteger
    informational_count: NonNegativeInteger
    waived_count: NonNegativeInteger
    exception_applied_count: NonNegativeInteger
    disposition: Literal[
        "blocked",
        "review_required",
        "passed_with_information",
        "passed",
    ]
    manifest_used: Literal[False] = False
    fault_injection_used: Literal[False] = False
    benchmark_claim: Literal[False] = False
    network_used: Literal[False] = False

    @model_validator(mode="after")
    def _check_report(self) -> ExternalDatasetAuditReportV2:
        if self.snapshot_record_count > self.source_record_count:
            raise ValueError("snapshot count must not exceed normalized source count")
        run_detectors = tuple(run.detector for run in self.detector_runs)
        if run_detectors != self.selected_detectors:
            raise ValueError("detector runs must exactly match policy-selected detectors")
        if self.finding_count != sum(len(run.report.findings) for run in self.detector_runs):
            raise ValueError("finding_count must equal the selected detector reports")
        for run in self.detector_runs:
            if run.report.audit_input_id != self.audit_input_id:
                raise ValueError("every detector report must use the same audit input")
            if (
                run.report.dataset_name != self.dataset_name
                or run.report.as_of_date != self.as_of_date
            ):
                raise ValueError("every detector report must use the audit context")

        evaluations_by_rule = {item.rule_id: item for item in self.rule_evaluations}
        result_counts: dict[str, int] = {}
        for result in self.policy_results:
            evaluation = evaluations_by_rule.get(result.rule_id)
            if evaluation is None:
                raise ValueError("every policy result must link to one rule evaluation")
            if (
                evaluation.rule_kind != result.rule_kind
                or evaluation.configured_action != result.base_action
            ):
                raise ValueError("policy result must match its rule evaluation contract")
            result_counts[result.rule_id] = result_counts.get(result.rule_id, 0) + 1
        if any(
            evaluation.result_count != result_counts.get(evaluation.rule_id, 0)
            for evaluation in self.rule_evaluations
        ):
            raise ValueError("rule evaluation counts must partition all policy results")

        counts = {
            "blocking": sum(item.effective_action == "blocking" for item in self.policy_results),
            "warning": sum(item.effective_action == "warning" for item in self.policy_results),
            "informational": sum(
                item.effective_action == "informational" for item in self.policy_results
            ),
        }
        if (
            self.blocking_count,
            self.warning_count,
            self.informational_count,
        ) != (counts["blocking"], counts["warning"], counts["informational"]):
            raise ValueError("action counts must equal effective policy result actions")
        if self.waived_count != sum(item.effective_action is None for item in self.policy_results):
            raise ValueError("waived_count must equal waived policy results")
        if self.exception_applied_count != sum(
            item.disposition == "exception_applied" for item in self.policy_results
        ):
            raise ValueError("exception count must equal applied policy exceptions")
        expected_disposition = (
            "blocked"
            if self.blocking_count
            else "review_required"
            if self.warning_count
            else "passed_with_information"
            if self.informational_count
            else "passed"
        )
        if self.disposition != expected_disposition:
            raise ValueError("disposition must follow blocking, warning, information precedence")
        return self


class ExternalAuditArtifactsV2(CorpusModel):
    """In-memory policy audit result; only ``public_report`` is public evidence."""

    policy: AuditPolicyV1
    validation_profile: ExternalDatasetValidationProfileV1
    normalized_dataset: NormalizedDatasetV1
    snapshot: DatasetSnapshot
    audit_input: AuditInputSnapshot
    public_report: ExternalDatasetAuditReportV2

    @model_validator(mode="after")
    def _check_links(self) -> ExternalAuditArtifactsV2:
        report = self.public_report
        if (
            report.policy_id,
            report.policy_name,
            report.policy_version,
            report.policy_content_hash,
        ) != (
            self.policy.policy_id,
            self.policy.policy_name,
            self.policy.policy_version,
            self.policy.policy_content_hash,
        ):
            raise ValueError("public report policy provenance must match the supplied policy")
        if (
            self.validation_profile.mapping_id != self.normalized_dataset.mapping_id
            or report.mapping_id != self.normalized_dataset.mapping_id
        ):
            raise ValueError("validation, normalized data, and report must share one mapping")
        if (
            report.normalized_dataset_id != self.normalized_dataset.normalized_dataset_id
            or report.snapshot_id != self.snapshot.snapshot_id
            or report.audit_input_id != self.audit_input.audit_input_id
        ):
            raise ValueError("public report artifact identities must match in-memory evidence")
        return self
