"""Immutable public schemas for the v0.2 benchmark corpus substrate.

Every model here is a frozen, strictly validated Pydantic v2 model that forbids
unknown fields, exactly like the v0.1 contract layer it sits beside. It
describes *sources and their eligibility*, never a record: the canonical
:class:`~quantcheck.schemas.FinancialFact` and the sanitized
:class:`~quantcheck.schemas.AuditInputRecord` are unchanged and are not
re-declared here.

The scalar validators below deliberately mirror the frozen ones in
``quantcheck.schemas`` rather than importing that module's private names. The
frozen module cannot change, so duplicating four small rules costs nothing and
keeps this layer from depending on a private surface.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BeforeValidator, model_validator

from quantcheck.corpus_contract import (
    CORPUS_ELIGIBILITY_UNIT_KINDS,
    CORPUS_INCLUSION_RULES,
    CORPUS_SPEC_VERSION,
    IN_REPOSITORY_SOURCE_CLASSES,
    MINIMUM_CELL_ELIGIBLE_UNITS,
    MINIMUM_PARTITION_ELIGIBLE_UNITS,
    REDISTRIBUTABLE_LICENSE_TIERS,
)
from quantcheck.json_types import (
    canonical_decimal_string,
    parse_canonical_date,
    parse_canonical_decimal,
)
from quantcheck.schemas import CONTENT_HASH_PATTERN, CanonicalModel

__all__ = [
    "CORPUS_ID_PATTERN",
    "CORPUS_CENSUS_ID_PATTERN",
    "CORPUS_UNIT_ID_PATTERN",
    "CorpusCensusStatus",
    "CorpusDefinition",
    "CorpusDiversityProfile",
    "CorpusEligibilityCell",
    "CorpusEligibilityCensus",
    "CorpusEligibilityRollup",
    "CorpusFaultProfile",
    "CorpusHorizon",
    "CorpusLicenseTier",
    "CorpusModel",
    "CorpusPartition",
    "CorpusPartitionSpec",
    "CorpusProvenance",
    "CorpusSeverity",
    "CorpusSourceClass",
    "CorpusUnitIds",
    "CorpusUnitSpec",
    "CorpusUnsupportedCell",
]

import re

CORPUS_UNIT_ID_PATTERN = re.compile(r"^cunit_[0-9a-f]{16}$")
CORPUS_ID_PATTERN = re.compile(r"^corp_[0-9a-f]{16}$")
CORPUS_CENSUS_ID_PATTERN = re.compile(r"^cens_[0-9a-f]{16}$")

_MAX_TOKEN_LENGTH = 512

CorpusSourceClass = Literal["synthetic_adversarial", "curated_public", "external_private"]
CorpusLicenseTier = Literal["synthetic_repository", "public_government", "external_restricted"]
CorpusPartition = Literal["development", "validation", "heldout"]
CorpusSeverity = Literal["low", "medium", "high"]
CorpusFaultProfile = Literal[
    "duplicate_observation",
    "lookahead_timestamp",
    "revision_overwrite",
    "unit_drift",
]
CorpusCensusStatus = Literal["eligible", "declared_unsupported", "insufficient"]
CorpusUnsupportedReason = Literal[
    "source_class_cannot_express",
    "frozen_threshold_unreachable",
    "deliberately_out_of_scope",
]


class CorpusModel(CanonicalModel):
    """Base class for every v0.2 corpus schema.

    Deliberately a subclass of the frozen
    :class:`~quantcheck.schemas.CanonicalModel` rather than a parallel base: the
    canonical serializer dispatches on that type, so a corpus artifact hashes,
    serializes, and round-trips through exactly the same machinery every v0.1
    artifact does. It inherits ``frozen``, ``extra="forbid"``, and ``strict``
    unchanged.
    """


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


def _validate_date(value: object) -> date:
    if isinstance(value, datetime):
        raise ValueError("expected a day-level date, got datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return parse_canonical_date(value)
    raise ValueError(f"expected date or a canonical ISO date string, got {type(value).__name__}")


def _validate_decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid decimal")
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
CorpusDate = Annotated[date, BeforeValidator(_validate_date)]
NonNegativeInteger = Annotated[int, BeforeValidator(_validate_non_negative_int)]
PositiveInteger = Annotated[int, BeforeValidator(_validate_positive_int)]
ContentHash = Annotated[str, _pattern_validator(CONTENT_HASH_PATTERN, "content hash")]
CorpusUnitId = Annotated[str, _pattern_validator(CORPUS_UNIT_ID_PATTERN, "corpus_unit_id")]
CorpusId = Annotated[str, _pattern_validator(CORPUS_ID_PATTERN, "corpus_id")]
CorpusCensusId = Annotated[str, _pattern_validator(CORPUS_CENSUS_ID_PATTERN, "census_id")]


def _normalize_inclusion_rules(value: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        raise ValueError("a corpus unit must cite at least one inclusion rule")
    if len(set(value)) != len(value):
        raise ValueError("inclusion rule identifiers must be unique")
    unknown = sorted(set(value) - set(CORPUS_INCLUSION_RULES))
    if unknown:
        raise ValueError(f"unknown corpus inclusion rules: {unknown}")
    return tuple(sorted(value))


InclusionRuleIds = Annotated[
    tuple[Token, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_inclusion_rules),
]


def _normalize_profiles(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("supported fault profiles must be unique")
    return tuple(sorted(value))


SupportedFaultProfiles = Annotated[
    tuple[CorpusFaultProfile, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_profiles),
]


class CorpusProvenance(CorpusModel):
    """Where a corpus unit came from, and what may be done with it.

    ``verbatim_source`` is the honesty field: a curated field-shape excerpt
    built to exercise a real public envelope is not a saved live response, and
    saying so here is what keeps the distinction between synthetic, curated,
    and real data explicit rather than implied.
    """

    source_class: CorpusSourceClass
    license_tier: CorpusLicenseTier
    publisher: Token
    retrieval_method: Token
    in_repository: bool
    redistributable: bool
    verbatim_source: bool
    notes: Token

    @model_validator(mode="after")
    def _check_provenance(self) -> CorpusProvenance:
        may_commit = self.source_class in IN_REPOSITORY_SOURCE_CLASSES
        if self.in_repository and not may_commit:
            raise ValueError(f"source class {self.source_class!r} must not be committed")
        if self.redistributable != (self.license_tier in REDISTRIBUTABLE_LICENSE_TIERS):
            raise ValueError("redistributable must follow the licence tier")
        if self.in_repository and not self.redistributable:
            raise ValueError("a non-redistributable unit must not be committed")
        if self.source_class == "external_private":
            if self.license_tier != "external_restricted":
                raise ValueError("an external_private unit must be external_restricted")
            if self.in_repository or self.redistributable:
                raise ValueError("an external_private unit is never committed or redistributed")
        if self.source_class == "synthetic_adversarial" and self.verbatim_source:
            raise ValueError("synthetic data has no verbatim upstream source")
        return self


class CorpusHorizon(CorpusModel):
    """The declared point-in-time context one corpus unit is designed for.

    A unit's eligibility is only meaningful relative to a cutoff, so the cutoff
    is part of the unit's pre-registered definition rather than something the
    census is free to search over.
    """

    snapshot_as_of_date: CorpusDate
    research_as_of_date: CorpusDate

    @model_validator(mode="after")
    def _check_horizon(self) -> CorpusHorizon:
        if self.research_as_of_date > self.snapshot_as_of_date:
            raise ValueError("research_as_of_date must not follow snapshot_as_of_date")
        return self


class CorpusDiversityProfile(CorpusModel):
    """The measured diversity a unit actually contributes.

    Every field is counted from the generated records, never asserted by hand,
    so a unit that fails to deliver the diversity it claims shows up as a
    number rather than as prose.
    """

    record_count: PositiveInteger
    issuer_count: PositiveInteger
    concept_count: PositiveInteger
    measurement_unit_count: PositiveInteger
    distinct_period_end_count: PositiveInteger
    #: Distinct ``(period-end month within quarter, period-end day)`` shapes.
    #: A proxy for fiscal-calendar diversity: calendar-quarter issuers all
    #: land on a month end in the third month of a quarter, so a count above
    #: one proves the corpus holds issuers whose reporting boundaries differ.
    period_end_signature_count: PositiveInteger
    minimum_filing_lag_days: NonNegativeInteger
    maximum_filing_lag_days: NonNegativeInteger
    distinct_filing_lag_count: PositiveInteger
    declared_revision_lineage_count: NonNegativeInteger
    maximum_relative_revision_size: CanonicalDecimal
    delayed_availability_count: NonNegativeInteger
    dimensioned_record_count: NonNegativeInteger
    negative_value_count: NonNegativeInteger
    zero_value_count: NonNegativeInteger
    hard_negative_count: NonNegativeInteger

    @model_validator(mode="after")
    def _check_profile(self) -> CorpusDiversityProfile:
        if self.minimum_filing_lag_days > self.maximum_filing_lag_days:
            raise ValueError("minimum filing lag must not exceed the maximum")
        if self.maximum_relative_revision_size < 0:
            raise ValueError("relative revision size must not be negative")
        if self.declared_revision_lineage_count == 0 and self.maximum_relative_revision_size != 0:
            raise ValueError("a unit with no lineage cannot report a revision size")
        return self


class CorpusUnitSpec(CorpusModel):
    """The immutable logical identity of one clean source in the corpus.

    ``unit_name`` is corpus metadata and may read however a human finds
    clearest. ``audit_dataset_name``, ``source_name``, and ``source_locator``
    are the three strings that cross the audit boundary into detector-visible
    text, and inclusion rule IR-05 requires them to carry no partition
    information; ``corpus_registry`` enforces that mechanically.
    """

    corpus_unit_id: CorpusUnitId
    spec_version: Literal["quantcheck/corpus/v2"] = CORPUS_SPEC_VERSION
    unit_name: Token
    partition: CorpusPartition
    audit_dataset_name: Token
    source_name: Token
    source_locator: Token
    provenance: CorpusProvenance
    horizon: CorpusHorizon
    inclusion_rule_ids: InclusionRuleIds
    supported_fault_profiles: SupportedFaultProfiles
    diversity: CorpusDiversityProfile | None = None
    content_hash: ContentHash | None = None

    @model_validator(mode="after")
    def _check_unit(self) -> CorpusUnitSpec:
        committed = self.provenance.in_repository
        if committed and (self.diversity is None or self.content_hash is None):
            raise ValueError("a committed unit must publish its content hash and diversity")
        if not committed and (self.diversity is not None or self.content_hash is not None):
            raise ValueError(
                "an externally supplied unit must not publish record-derived content "
                "in a repository artifact"
            )
        return self


def _normalize_unit_ids(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("corpus unit identifiers must be unique")
    return tuple(sorted(value))


CorpusUnitIds = Annotated[
    tuple[CorpusUnitId, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unit_ids),
]


def _normalize_units(value: tuple[CorpusUnitSpec, ...]) -> tuple[CorpusUnitSpec, ...]:
    if not value:
        raise ValueError("a corpus partition must contain at least one unit")
    identifiers = [unit.corpus_unit_id for unit in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("corpus unit identifiers must be unique within a partition")
    return tuple(sorted(value, key=lambda unit: unit.corpus_unit_id))


CorpusUnits = Annotated[
    tuple[CorpusUnitSpec, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_units),
]


class CorpusPartitionSpec(CorpusModel):
    """One declared partition and the units assigned to it."""

    partition: CorpusPartition
    units: CorpusUnits
    unit_count: PositiveInteger
    committed_record_count: NonNegativeInteger

    @model_validator(mode="after")
    def _check_partition(self) -> CorpusPartitionSpec:
        if self.unit_count != len(self.units):
            raise ValueError("unit_count must equal the number of units")
        for unit in self.units:
            if unit.partition != self.partition:
                raise ValueError("every unit must belong to its declared partition")
        expected = sum(
            unit.diversity.record_count for unit in self.units if unit.diversity is not None
        )
        if self.committed_record_count != expected:
            raise ValueError("committed_record_count must sum the committed units' records")
        return self


class CorpusUnsupportedCell(CorpusModel):
    """One profile/severity cell the corpus declares it does not support.

    A declaration is the only permitted alternative to eligibility, and it
    exists so that an unmeasured cell is an explicit statement in the frozen
    corpus rather than an absence the reader has to notice.
    """

    fault_profile: CorpusFaultProfile
    severity: CorpusSeverity
    partition: CorpusPartition
    reason_code: CorpusUnsupportedReason
    reason: Token


def _normalize_unsupported(
    value: tuple[CorpusUnsupportedCell, ...],
) -> tuple[CorpusUnsupportedCell, ...]:
    keys = [(cell.partition, cell.fault_profile, cell.severity) for cell in value]
    if len(set(keys)) != len(keys):
        raise ValueError("a cell must not be declared unsupported twice")
    return tuple(
        sorted(value, key=lambda cell: (cell.partition, cell.fault_profile, cell.severity))
    )


UnsupportedCells = Annotated[
    tuple[CorpusUnsupportedCell, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_unsupported),
]


def _normalize_partitions(
    value: tuple[CorpusPartitionSpec, ...],
) -> tuple[CorpusPartitionSpec, ...]:
    names = [partition.partition for partition in value]
    if len(set(names)) != len(names):
        raise ValueError("a partition must not be declared twice")
    return tuple(sorted(value, key=lambda partition: partition.partition))


CorpusPartitions = Annotated[
    tuple[CorpusPartitionSpec, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_partitions),
]


class CorpusDefinition(CorpusModel):
    """The complete normalized v0.2 corpus.

    Everything here changes what the corpus *means*. Output roots, working
    directories, clocks, hostnames, and environment variables are deliberately
    absent, exactly as they are from :class:`~quantcheck.schemas.BenchmarkConfig`.
    """

    corpus_id: CorpusId
    spec_version: Literal["quantcheck/corpus/v2"] = CORPUS_SPEC_VERSION
    corpus_name: Token
    partitions: CorpusPartitions
    declared_unsupported_cells: UnsupportedCells = ()

    @model_validator(mode="after")
    def _check_corpus(self) -> CorpusDefinition:
        declared = {partition.partition for partition in self.partitions}
        if declared != {"development", "validation", "heldout"}:
            raise ValueError("a corpus must declare development, validation, and heldout")
        unit_ids = [
            unit.corpus_unit_id for partition in self.partitions for unit in partition.units
        ]
        if len(set(unit_ids)) != len(unit_ids):
            raise ValueError("corpus unit identifiers must be unique across partitions")
        known = {partition.partition for partition in self.partitions}
        for cell in self.declared_unsupported_cells:
            if cell.partition not in known:
                raise ValueError(
                    f"unsupported cell names an undeclared partition: {cell.partition}"
                )
        return self


class CorpusEligibilityCell(CorpusModel):
    """How many units one frozen eligibility rule finds in one corpus unit.

    ``eligible_unit_count`` is a denominator, not a score. It is produced by
    calling the *same* frozen v0.1 eligibility computation the injector and the
    clean-control denominator already use, so a v0.2 number is directly
    comparable with a v0.1 one.
    """

    partition: CorpusPartition
    corpus_unit_id: CorpusUnitId
    fault_profile: CorpusFaultProfile
    severity: CorpusSeverity
    eligibility_unit_kind: Token
    eligible_unit_count: NonNegativeInteger
    snapshot_record_count: NonNegativeInteger

    @model_validator(mode="after")
    def _check_cell(self) -> CorpusEligibilityCell:
        expected = CORPUS_ELIGIBILITY_UNIT_KINDS[self.fault_profile]
        if self.eligibility_unit_kind != expected:
            raise ValueError(
                f"{self.fault_profile} counts {expected}, not {self.eligibility_unit_kind}"
            )
        return self


def _cell_key(cell: CorpusEligibilityCell) -> tuple[str, str, str, str]:
    return (cell.partition, cell.corpus_unit_id, cell.fault_profile, cell.severity)


def _normalize_cells(value: tuple[CorpusEligibilityCell, ...]) -> tuple[CorpusEligibilityCell, ...]:
    keys = [_cell_key(cell) for cell in value]
    if len(set(keys)) != len(keys):
        raise ValueError("eligibility cells must be unique")
    return tuple(sorted(value, key=_cell_key))


EligibilityCells = Annotated[
    tuple[CorpusEligibilityCell, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_cells),
]


class CorpusEligibilityRollup(CorpusModel):
    """The partition-level verdict for one profile/severity cell.

    ``status`` is derived arithmetic, never a judgement: a cell is
    ``eligible`` when the best single unit clears the declared per-cell floor
    and the partition total clears the declared partition floor,
    ``declared_unsupported`` when the corpus said so before the freeze, and
    ``insufficient`` otherwise. An ``insufficient`` cell is a corpus defect
    that must be fixed or declared before the held-out partition is frozen.
    """

    partition: CorpusPartition
    fault_profile: CorpusFaultProfile
    severity: CorpusSeverity
    eligibility_unit_kind: Token
    best_unit_id: CorpusUnitId | None
    best_unit_eligible_count: NonNegativeInteger
    partition_eligible_total: NonNegativeInteger
    supporting_unit_count: NonNegativeInteger
    minimum_cell_eligible_units: PositiveInteger
    minimum_partition_eligible_units: PositiveInteger
    status: CorpusCensusStatus

    @model_validator(mode="after")
    def _check_rollup(self) -> CorpusEligibilityRollup:
        if self.minimum_cell_eligible_units != MINIMUM_CELL_ELIGIBLE_UNITS:
            raise ValueError("the per-cell floor must be the declared contract floor")
        if self.minimum_partition_eligible_units != MINIMUM_PARTITION_ELIGIBLE_UNITS:
            raise ValueError("the partition floor must be the declared contract floor")
        if self.best_unit_eligible_count > self.partition_eligible_total:
            raise ValueError("the best unit cannot exceed the partition total")
        if (self.best_unit_id is None) != (self.best_unit_eligible_count == 0):
            raise ValueError("a nonzero best count requires the unit that produced it")
        meets_floor = (
            self.best_unit_eligible_count >= self.minimum_cell_eligible_units
            and self.partition_eligible_total >= self.minimum_partition_eligible_units
        )
        if self.status == "eligible" and not meets_floor:
            raise ValueError("an eligible cell must clear both declared floors")
        if self.status == "insufficient" and meets_floor:
            raise ValueError("a cell clearing both floors is not insufficient")
        return self


def _normalize_rollups(
    value: tuple[CorpusEligibilityRollup, ...],
) -> tuple[CorpusEligibilityRollup, ...]:
    keys = [(item.partition, item.fault_profile, item.severity) for item in value]
    if len(set(keys)) != len(keys):
        raise ValueError("eligibility rollups must be unique")
    return tuple(
        sorted(value, key=lambda item: (item.partition, item.fault_profile, item.severity))
    )


EligibilityRollups = Annotated[
    tuple[CorpusEligibilityRollup, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_rollups),
]


class CorpusEligibilityCensus(CorpusModel):
    """The exact eligible-unit denominators of one corpus, by unit and by cell.

    This is the artifact that answers, before any held-out detector run, the
    question v0.1 could only answer afterwards: is every intended
    fault/severity cell actually measurable on this data?
    """

    census_id: CorpusCensusId
    corpus_id: CorpusId
    spec_version: Literal["quantcheck/corpus/v2"] = CORPUS_SPEC_VERSION
    cells: EligibilityCells
    rollups: EligibilityRollups
    covered_partitions: Annotated[
        tuple[CorpusPartition, ...],
        BeforeValidator(_to_tuple),
    ]

    @model_validator(mode="after")
    def _check_census(self) -> CorpusEligibilityCensus:
        covered = set(self.covered_partitions)
        if not covered:
            raise ValueError("a census must cover at least one partition")
        if len(covered) != len(self.covered_partitions):
            raise ValueError("covered partitions must be unique")
        for cell in self.cells:
            if cell.partition not in covered:
                raise ValueError("a cell names a partition the census does not cover")
        for rollup in self.rollups:
            if rollup.partition not in covered:
                raise ValueError("a rollup names a partition the census does not cover")
        return self
