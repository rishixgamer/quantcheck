"""Immutable public domain schemas for QuantCheck.

Every model here is a frozen, strictly validated Pydantic v2 model that
forbids unknown fields. The models depend only on the standard library and
Pydantic; they never reference pandas, HTTPX, Streamlit, file handles, or
network clients.

Scope note: this module contains the Milestone 1 *contract layer* only —
financial records, provenance, snapshots, the sanitized audit-input boundary,
logical case configuration, runtime metadata, and artifact identity. Fault
manifests, findings, audit reports, scoring, and damage models belong to later
milestones and are deliberately absent.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, model_validator

from quantcheck.json_types import (
    canonical_decimal_string,
    parse_canonical_date,
    parse_canonical_datetime,
    parse_canonical_decimal,
)

__all__ = [
    "AUDIT_INPUT_SNAPSHOT_ID_PATTERN",
    "CASE_CONFIG_ID_PATTERN",
    "CONTENT_HASH_PATTERN",
    "DATASET_SNAPSHOT_ID_PATTERN",
    "RECORD_ID_PATTERN",
    "ArtifactIdentity",
    "AuditInputRecord",
    "AuditInputSnapshot",
    "CanonicalModel",
    "CaseConfig",
    "DatasetSnapshot",
    "Dimension",
    "FinancialFact",
    "PeriodType",
    "RuntimeMetadata",
    "SourceReference",
]

_MAX_TOKEN_LENGTH = 512

RECORD_ID_PATTERN = re.compile(r"^rec_[0-9a-f]{16}$")
DATASET_SNAPSHOT_ID_PATTERN = re.compile(r"^snap_[0-9a-f]{16}$")
AUDIT_INPUT_SNAPSHOT_ID_PATTERN = re.compile(r"^audit_[0-9a-f]{16}$")
CASE_CONFIG_ID_PATTERN = re.compile(r"^case_[0-9a-f]{16}$")
CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

PeriodType = Literal["instant", "duration"]


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
FinancialDate = Annotated[date, BeforeValidator(_validate_date)]
UtcTimestamp = Annotated[datetime, BeforeValidator(_validate_utc_datetime)]
NonNegativeInteger = Annotated[int, BeforeValidator(_validate_non_negative_int)]

RecordId = Annotated[str, _pattern_validator(RECORD_ID_PATTERN, "record_id")]
DatasetSnapshotId = Annotated[str, _pattern_validator(DATASET_SNAPSHOT_ID_PATTERN, "snapshot_id")]
AuditInputSnapshotId = Annotated[
    str, _pattern_validator(AUDIT_INPUT_SNAPSHOT_ID_PATTERN, "audit_input_id")
]
CaseConfigId = Annotated[str, _pattern_validator(CASE_CONFIG_ID_PATTERN, "case_id")]
ContentHash = Annotated[str, _pattern_validator(CONTENT_HASH_PATTERN, "content hash")]


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
