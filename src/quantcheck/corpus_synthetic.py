"""Deterministic synthetic adversarial corpus cohorts for the v0.2 substrate.

This module is a pure factory. It never touches the filesystem, the clock, or
any source of randomness: every value it produces is a function of an explicit
reviewed specification and SHA-256 of that specification, so the same cohort
key always yields byte-identical canonical records on any machine, in any
process, under any ``PYTHONHASHSEED``.

What it adds over the v0.1 reviewed fixture is deliberate breadth along the
axes that made v0.1 unmeasurable:

* **Issuers and fiscal calendars.** Cohorts mix calendar-quarter issuers with
  three different fiscal year ends and a 4-4-5 retail calendar, so more than
  one issuer's period straddles any single research cutoff. This is what makes
  a Look-Ahead cell eligible at more than one filing-lag band.
* **Periods.** Twelve or eight consecutive fiscal quarters instead of two, so a
  comparable series is long enough for Unit Drift under the frozen
  three-observation rule without a special-purpose fixture.
* **Filing lags.** Explicit per-issuer lags spanning 0 to 90 days, which is the
  axis the frozen 7/14/30-day Look-Ahead severity bands are cut on.
* **Units of measure.** Several currencies, a per-share unit, and a share
  count, so a corrupted scale is not trivially identifiable by unit alone.
* **Revision histories.** Declared ``#r<n>`` lineages with reviewed relative
  revision sizes spanning the frozen 1% / 5% / 20% Revision Overwrite bands.
* **Volatility.** Per-issuer variation amplitude, so a clean series is not a
  smooth ramp that any discontinuity stands out against.
* **Hard negatives.** Natural but unusual *legitimate* observations, declared
  one by one with the reason each is legitimate. A hard negative is never an
  injected fault, and several of them are expected to produce findings — that
  is what they are for.

Nothing here relaxes a frozen threshold. The frozen eligibility rules are
imported by the census and applied unchanged; this module only supplies data
those rules can find something in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Literal

from quantcheck.hashing import canonical_sha256, source_record_id, stable_id
from quantcheck.schemas import Dimension, FinancialFact, PeriodType, SourceReference

__all__ = [
    "COHORT_CODE_NAMESPACE",
    "CONCEPT_CATALOG",
    "CohortSpec",
    "ConceptSpec",
    "ExtraRow",
    "HARD_NEGATIVE_KINDS",
    "IssuerSpec",
    "RevisionPlan",
    "ValueOverride",
    "build_cohort_records",
    "cohort_code",
    "cohort_entity_id",
    "period_bounds",
]

#: Namespace for the opaque, detector-visible cohort code. The code is derived
#: from the cohort's own key and nothing else, so it is stable, and it is a
#: hash rather than a name so that inclusion rule IR-05 holds structurally:
#: there is no partition word to leak.
COHORT_CODE_NAMESPACE = "quantcheck/corpus-cohort-code/v2"
_ENTITY_NAMESPACE = "quantcheck/corpus-entity/v2"
_VALUE_NAMESPACE = "quantcheck/corpus-value/v2"

UnitKind = Literal["currency", "per_share", "shares"]

_CURRENCY: UnitKind = "currency"
_PER_SHARE: UnitKind = "per_share"
_SHARES: UnitKind = "shares"
FiscalCalendar = Literal["calendar_quarter", "retail_454"]

#: Every documented reason a hard negative is legitimate. A row citing a kind
#: outside this list is rejected rather than filed under the nearest one.
HARD_NEGATIVE_KINDS: tuple[str, ...] = (
    "legitimate_independent_duplicate",
    "consolidation_dimension_lookalike",
    "genuine_recovery_from_near_zero",
    "genuine_loss_quarter",
    "genuine_zero_value",
    "delayed_vendor_availability",
    "identical_value_restatement",
    "fiscal_year_change_stub_period",
    "share_split_adjusted_step",
    "same_day_filing_and_period_end",
)


@dataclass(frozen=True, slots=True)
class ConceptSpec:
    """One reported concept and the shape of the series it produces."""

    concept: str
    period_type: PeriodType
    unit_kind: UnitKind
    base_value: str
    quarterly_growth: str


#: The concept catalogue, in stable order. Instant and duration shapes, four
#: units of measure, and a spread of magnitudes from cents-per-share to
#: billions, because a scale fault is only interesting when magnitudes differ.
CONCEPT_CATALOG: tuple[ConceptSpec, ...] = (
    ConceptSpec("Revenues", "duration", _CURRENCY, "482000000.00", "0.021"),
    ConceptSpec("NetIncomeLoss", "duration", _CURRENCY, "61500000.00", "0.017"),
    ConceptSpec("OperatingIncomeLoss", "duration", _CURRENCY, "78200000.00", "0.019"),
    ConceptSpec("ResearchAndDevelopmentExpense", "duration", _CURRENCY, "34700000.00", "0.026"),
    ConceptSpec("CostOfRevenue", "duration", _CURRENCY, "268400000.00", "0.020"),
    ConceptSpec("Assets", "instant", _CURRENCY, "2140000000.00", "0.012"),
    ConceptSpec("Liabilities", "instant", _CURRENCY, "1180000000.00", "0.010"),
    ConceptSpec("StockholdersEquity", "instant", _CURRENCY, "960000000.00", "0.014"),
    ConceptSpec(
        "CashAndCashEquivalentsAtCarryingValue", "instant", _CURRENCY, "310000000.00", "0.008"
    ),
    ConceptSpec("EarningsPerShareDiluted", "duration", _PER_SHARE, "0.74", "0.016"),
    ConceptSpec("CommonStockSharesOutstanding", "instant", _SHARES, "83000000", "0.002"),
)

_CONCEPTS_BY_NAME = {spec.concept: spec for spec in CONCEPT_CATALOG}


@dataclass(frozen=True, slots=True)
class IssuerSpec:
    """One synthetic issuer: its calendar, its lag, its units, its concepts."""

    issuer_key: str
    entity_name: str
    fiscal_calendar: FiscalCalendar
    #: Month of the issuer's fiscal fourth-quarter end, 1-12. Ignored for the
    #: 4-4-5 retail calendar, which carries an explicit ``retail_anchor``.
    fiscal_year_end_month: int
    fiscal_year_end_year: int
    filing_lag_days: int
    currency_unit: str
    volatility_bp: int
    concepts: tuple[str, ...]
    dimensioned_concepts: tuple[str, ...] = ()
    #: The exact most recent 4-4-5 period end. Stated rather than derived,
    #: because a retail period end is a weekday convention no month-end rule
    #: reproduces, and guessing it would silently move every earlier period.
    retail_anchor: date | None = None

    def __post_init__(self) -> None:
        if self.fiscal_calendar == "retail_454" and self.retail_anchor is None:
            raise ValueError(f"issuer {self.issuer_key!r} needs an explicit retail anchor")
        if self.fiscal_calendar == "calendar_quarter" and self.retail_anchor is not None:
            raise ValueError(f"issuer {self.issuer_key!r} is not on a retail calendar")
        if not self.concepts:
            raise ValueError(f"issuer {self.issuer_key!r} reports no concepts")
        unknown = sorted(set(self.concepts) - set(_CONCEPTS_BY_NAME))
        if unknown:
            raise ValueError(f"issuer {self.issuer_key!r} reports unknown concepts: {unknown}")
        if not set(self.dimensioned_concepts) <= set(self.concepts):
            raise ValueError(f"issuer {self.issuer_key!r} dimensions an unreported concept")
        if self.filing_lag_days < 0:
            raise ValueError(f"issuer {self.issuer_key!r} has a negative filing lag")
        if self.volatility_bp < 0:
            raise ValueError(f"issuer {self.issuer_key!r} has a negative volatility")


@dataclass(frozen=True, slots=True)
class RevisionPlan:
    """One declared revision lineage, expressed as a reviewed relative size.

    The plan names an existing generated observation and turns it into a two
    member ``#r1``/``#r2`` lineage. ``relative_size`` is signed so downward
    restatements are represented as well as upward ones; the frozen Revision
    Overwrite rule compares its absolute value against the severity band.
    """

    issuer_key: str
    concept: str
    period_index: int
    relative_size: str
    later_filing_gap_days: int


@dataclass(frozen=True, slots=True)
class ValueOverride:
    """A reviewed replacement for one generated value.

    Used for hard negatives that must sit *inside* an otherwise ordinary
    series — a genuine recovery from near zero, a real loss quarter, a real
    zero — so the surrounding comparable series stays intact.
    """

    issuer_key: str
    concept: str
    period_index: int
    value: str
    kind: str
    reason: str

    def __post_init__(self) -> None:
        if self.kind not in HARD_NEGATIVE_KINDS:
            raise ValueError(f"undocumented hard-negative kind: {self.kind!r}")


@dataclass(frozen=True, slots=True)
class ExtraRow:
    """One reviewed record that the periodic generator cannot express.

    Every extra row is a hard negative: a legitimate independent duplicate, a
    consolidation lookalike, a vendor-delayed availability, a fiscal-year-change
    stub period, or a restatement that changed nothing.
    """

    row_key: str
    issuer_key: str
    concept: str
    period_type: PeriodType
    period_start: date | None
    period_end: date
    filed_on: date
    available_on: date
    value: str
    form: str
    #: Position within the issuer's accession sequence. The accession itself is
    #: derived from the issuer's own entity id, exactly as a generated row's is,
    #: so a hard negative is not identifiable by a literal accession shared
    #: across every cohort.
    accession_ordinal: int
    kind: str
    reason: str
    dimensions: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in HARD_NEGATIVE_KINDS:
            raise ValueError(f"undocumented hard-negative kind: {self.kind!r}")


@dataclass(frozen=True, slots=True)
class CohortSpec:
    """One complete synthetic corpus cohort.

    ``cohort_key`` is hashed into the opaque detector-visible cohort code, so
    two cohorts never collide and none of them announces its partition.
    """

    cohort_key: str
    period_count: int
    issuers: tuple[IssuerSpec, ...]
    revision_plans: tuple[RevisionPlan, ...] = ()
    value_overrides: tuple[ValueOverride, ...] = ()
    extra_rows: tuple[ExtraRow, ...] = ()
    skipped: frozenset[tuple[str, str, int]] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.period_count < 3:
            raise ValueError("a cohort needs at least three periods to form a series")
        keys = [issuer.issuer_key for issuer in self.issuers]
        if not keys:
            raise ValueError(f"cohort {self.cohort_key!r} has no issuers")
        if len(set(keys)) != len(keys):
            raise ValueError(f"cohort {self.cohort_key!r} repeats an issuer key")


def cohort_code(cohort_key: str) -> str:
    """Return the opaque, detector-visible code for one cohort."""
    return stable_id(prefix="ccoh", namespace=COHORT_CODE_NAMESPACE, payload=cohort_key)


def cohort_entity_id(issuer_key: str) -> str:
    """Return a stable ten-digit CIK-shaped entity id for one issuer key.

    Derived from a hash rather than allocated sequentially, so entity ids carry
    no ordering a reader could decode back into a partition (inclusion rules
    IR-04 and IR-05).
    """
    digest = canonical_sha256({"namespace": _ENTITY_NAMESPACE, "issuer_key": issuer_key})
    return f"CIK{int(digest[:15], 16) % 10**10:010d}"


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _shift_months(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def period_bounds(
    issuer: IssuerSpec,
    period_count: int,
) -> tuple[tuple[date, date], ...]:
    """Return ``(period_start, period_end)`` for one issuer, oldest first.

    Calendar-quarter issuers step back three months at a time from their fiscal
    year end. The 4-4-5 retail issuer steps back 91 days from its explicit
    anchor, which is what puts a real retailer's period end in the middle of a
    month — and that is exactly the property that lets a single research cutoff
    straddle more than one issuer's reporting boundary.
    """
    bounds: list[tuple[date, date]] = []
    if issuer.fiscal_calendar == "retail_454":
        assert issuer.retail_anchor is not None
        anchor = issuer.retail_anchor
        for index in range(period_count):
            end = anchor - timedelta(days=91 * (period_count - 1 - index))
            bounds.append((end - timedelta(days=90), end))
        return tuple(bounds)

    for index in range(period_count):
        delta = -3 * (period_count - 1 - index)
        year, month = _shift_months(
            issuer.fiscal_year_end_year, issuer.fiscal_year_end_month, delta
        )
        end = _month_end(year, month)
        start_year, start_month = _shift_months(year, month, -2)
        bounds.append((date(start_year, start_month, 1), end))
    return tuple(bounds)


def _unit_for(issuer: IssuerSpec, spec: ConceptSpec) -> str:
    if spec.unit_kind == _CURRENCY:
        return issuer.currency_unit
    if spec.unit_kind == _PER_SHARE:
        return f"{issuer.currency_unit}/shares"
    return "shares"


def _quantum(spec: ConceptSpec) -> Decimal:
    return Decimal("1") if spec.unit_kind == _SHARES else Decimal("0.01")


def _variation(issuer: IssuerSpec, spec: ConceptSpec, index: int) -> Decimal:
    """A deterministic value in ``[-1, 1]`` from the specification alone."""
    digest = canonical_sha256(
        {
            "namespace": _VALUE_NAMESPACE,
            "issuer_key": issuer.issuer_key,
            "concept": spec.concept,
            "period_index": index,
        }
    )
    return Decimal(int(digest[:8], 16) % 20001 - 10000) / Decimal(10000)


def _generated_value(issuer: IssuerSpec, spec: ConceptSpec, index: int) -> Decimal:
    """Grow the base value, wobble it by the issuer's volatility, and round.

    The result is forced away from zero: a zero is a meaningful hard negative
    and must be declared as one, never arrive by rounding.
    """
    quantum = _quantum(spec)
    with localcontext() as context:
        context.prec = 50
        growth = (Decimal(1) + Decimal(spec.quarterly_growth)) ** index
        wobble = Decimal(1) + _variation(issuer, spec, index) * Decimal(issuer.volatility_bp) / (
            Decimal(10000)
        )
        raw = Decimal(spec.base_value) * growth * wobble
    value = raw.quantize(quantum)
    if value == 0:
        value = quantum
    return value


def _form_for(index: int, period_count: int) -> str:
    """A fiscal fourth quarter is annual; every other quarter is quarterly."""
    quarters_from_end = period_count - 1 - index
    return "10-K" if quarters_from_end % 4 == 0 else "10-Q"


def _accession(entity_id: str, filed_on: date, ordinal: int) -> str:
    return f"{entity_id.removeprefix('CIK')}-{filed_on.year % 100:02d}-{ordinal:06d}"


def _fact(
    *,
    code: str,
    row_key: str,
    entity_id: str,
    entity_name: str,
    concept: str,
    value: Decimal,
    unit: str,
    dimensions: tuple[tuple[str, str], ...],
    period_type: PeriodType,
    period_start: date | None,
    period_end: date,
    filed_on: date,
    available_on: date,
    form: str,
    accession_number: str,
) -> FinancialFact:
    source = SourceReference(
        source_name=code,
        source_locator=f"quantcheck/corpus/v2/{code}",
        source_row_key=row_key,
    )
    return FinancialFact(
        record_id=source_record_id(
            source_name=source.source_name,
            source_locator=source.source_locator,
            source_row_key=source.source_row_key,
        ),
        entity_id=entity_id,
        entity_name=entity_name,
        concept_namespace="us-gaap",
        concept=concept,
        value=value,
        unit=unit,
        dimensions=tuple(Dimension(axis=axis, member=member) for axis, member in dimensions),
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        filed_on=filed_on,
        available_on=available_on,
        form=form,
        accession_number=accession_number,
        source=source,
    )


def _revision_index(
    plans: tuple[RevisionPlan, ...],
) -> dict[tuple[str, str, int], RevisionPlan]:
    index: dict[tuple[str, str, int], RevisionPlan] = {}
    for plan in plans:
        key = (plan.issuer_key, plan.concept, plan.period_index)
        if key in index:
            raise ValueError(f"two revision plans target the same observation: {key}")
        index[key] = plan
    return index


def _override_index(
    overrides: tuple[ValueOverride, ...],
) -> dict[tuple[str, str, int], ValueOverride]:
    index: dict[tuple[str, str, int], ValueOverride] = {}
    for override in overrides:
        key = (override.issuer_key, override.concept, override.period_index)
        if key in index:
            raise ValueError(f"two value overrides target the same observation: {key}")
        index[key] = override
    return index


def build_cohort_records(cohort: CohortSpec) -> tuple[FinancialFact, ...]:
    """Build one cohort's complete clean record set, sorted by ``record_id``.

    Sorting makes the canonical output independent of generation order, exactly
    as the v0.1 reviewed fixture does. The result contains no injected fault:
    corruption is the benchmark's job, never the corpus's.
    """
    code = cohort_code(cohort.cohort_key)
    revisions = _revision_index(cohort.revision_plans)
    overrides = _override_index(cohort.value_overrides)
    issuers_by_key = {issuer.issuer_key: issuer for issuer in cohort.issuers}
    records: list[FinancialFact] = []

    for issuer in cohort.issuers:
        entity_id = cohort_entity_id(issuer.issuer_key)
        bounds = period_bounds(issuer, cohort.period_count)
        for concept in issuer.concepts:
            spec = _CONCEPTS_BY_NAME[concept]
            unit = _unit_for(issuer, spec)
            for index, (period_start, period_end) in enumerate(bounds):
                if (issuer.issuer_key, concept, index) in cohort.skipped:
                    continue
                override = overrides.get((issuer.issuer_key, concept, index))
                value = (
                    Decimal(override.value)
                    if override is not None
                    else _generated_value(issuer, spec, index)
                )
                filed_on = period_end + timedelta(days=issuer.filing_lag_days)
                form = _form_for(index, cohort.period_count)
                base_key = f"{issuer.issuer_key}-{concept}-{period_end:%Y%m%d}"
                plan = revisions.get((issuer.issuer_key, concept, index))

                if plan is None:
                    records.append(
                        _fact(
                            code=code,
                            row_key=base_key,
                            entity_id=entity_id,
                            entity_name=issuer.entity_name,
                            concept=concept,
                            value=value,
                            unit=unit,
                            dimensions=(),
                            period_type=spec.period_type,
                            period_start=period_start if spec.period_type == "duration" else None,
                            period_end=period_end,
                            filed_on=filed_on,
                            available_on=filed_on,
                            form=form,
                            accession_number=_accession(entity_id, filed_on, index + 1),
                        )
                    )
                else:
                    later_filed = filed_on + timedelta(days=plan.later_filing_gap_days)
                    with localcontext() as context:
                        context.prec = 50
                        later_raw = value * (Decimal(1) + Decimal(plan.relative_size))
                    later_value = later_raw.quantize(_quantum(spec))
                    for sequence, (revision_value, revision_filed) in enumerate(
                        ((value, filed_on), (later_value, later_filed)), start=1
                    ):
                        records.append(
                            _fact(
                                code=code,
                                row_key=f"{base_key}#r{sequence}",
                                entity_id=entity_id,
                                entity_name=issuer.entity_name,
                                concept=concept,
                                value=revision_value,
                                unit=unit,
                                dimensions=(),
                                period_type=spec.period_type,
                                period_start=(
                                    period_start if spec.period_type == "duration" else None
                                ),
                                period_end=period_end,
                                filed_on=revision_filed,
                                available_on=revision_filed,
                                form=form if sequence == 1 else f"{form}/A",
                                accession_number=_accession(
                                    entity_id, revision_filed, index * 10 + sequence
                                ),
                            )
                        )

                if concept in issuer.dimensioned_concepts:
                    records.append(
                        _fact(
                            code=code,
                            row_key=f"{base_key}-SEG",
                            entity_id=entity_id,
                            entity_name=issuer.entity_name,
                            concept=concept,
                            value=(value / Decimal(2)).quantize(_quantum(spec)),
                            unit=unit,
                            dimensions=(("Segment", "Core"),),
                            period_type=spec.period_type,
                            period_start=period_start if spec.period_type == "duration" else None,
                            period_end=period_end,
                            filed_on=filed_on,
                            available_on=filed_on,
                            form=form,
                            accession_number=_accession(entity_id, filed_on, index + 1),
                        )
                    )

    for extra in cohort.extra_rows:
        issuer = issuers_by_key[extra.issuer_key]
        spec = _CONCEPTS_BY_NAME[extra.concept]
        records.append(
            _fact(
                code=code,
                row_key=extra.row_key,
                entity_id=cohort_entity_id(extra.issuer_key),
                entity_name=issuer.entity_name,
                concept=extra.concept,
                value=Decimal(extra.value),
                unit=_unit_for(issuer, spec),
                dimensions=extra.dimensions,
                period_type=extra.period_type,
                period_start=extra.period_start,
                period_end=extra.period_end,
                filed_on=extra.filed_on,
                available_on=extra.available_on,
                form=extra.form,
                accession_number=_accession(
                    cohort_entity_id(extra.issuer_key), extra.filed_on, extra.accession_ordinal
                ),
            )
        )

    identifiers = [record.record_id for record in records]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"cohort {cohort.cohort_key!r} generated a duplicate record id")
    return tuple(sorted(records, key=lambda record: record.record_id))
