"""The closed registry of v0.2 corpus units and the corpus they compose.

Every unit is named by identifier and built by a pure in-package factory, never
by a path on this machine — the same rule ``quantcheck.benchmark_fixtures``
froze for v0.1, for the same reason: a source's logical identity must not be
able to pick up a directory.

The registry is also where the held-out gate bites. A unit specification,
including a held-out one, may be built and read freely: identifiers, provenance,
horizons, and declared support are committed evidence. Materializing a held-out
unit's *records* requires an authorization covering the complete held-out
partition, because that is the step that could put held-out data in front of a
detector.

Cohort composition is reviewed, not generated. Each partition holds four units:

``broad``
    Seven issuers on four different fiscal calendars with filing lags from 12
    to 90 days over twelve quarters. This is the unit that makes every
    Look-Ahead severity band eligible — including ``high``, which the v0.1
    fixture could not reach at all.
``revisions``
    Seven issuers with a declared ``#r1``/``#r2`` lineage on every reported
    concept, with reviewed relative revision sizes spanning the frozen 1% / 5%
    / 20% bands. This is the unit that makes Revision Overwrite ``medium`` and
    ``high`` eligible, which the v0.1 fixture could not reach either.
``stress``
    Four volatile issuers plus the declared hard negatives: a genuine recovery
    from near zero, a real loss quarter, a real zero, a split-adjusted step, a
    legitimate independent duplicate pair, a consolidation lookalike, a
    vendor-delayed availability, a restatement that changed nothing, a
    fiscal-year-change stub period, and a same-day filing.
``public``
    A curated public Company Facts document read through the frozen SEC
    adapter. See :mod:`quantcheck.corpus_public` for exactly what is and is not
    claimed about its bytes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from functools import cache

from quantcheck.corpus_contract import (
    CORPUS_PARTITIONS,
    HELD_OUT_PARTITION,
    PARTITION_LEAKAGE_TOKENS,
    CorpusContractError,
)
from quantcheck.corpus_gate import (
    HeldOutCorpusAuthorizationError,
    active_held_out_corpus_authorization,
    held_out_unit_authorized,
)
from quantcheck.corpus_public import (
    CURATED_PUBLIC_IS_PLACEHOLDER,
    CURATED_PUBLIC_PUBLISHER,
    CURATED_PUBLIC_RETRIEVAL_METHOD,
    CuratedPublicSpec,
    curated_public_cik,
    curated_public_records,
)
from quantcheck.corpus_schemas import (
    CorpusDefinition,
    CorpusDiversityProfile,
    CorpusHorizon,
    CorpusPartitionSpec,
    CorpusProvenance,
    CorpusUnitSpec,
    CorpusUnsupportedCell,
)
from quantcheck.corpus_synthetic import (
    CohortSpec,
    ExtraRow,
    IssuerSpec,
    RevisionPlan,
    ValueOverride,
    build_cohort_records,
    cohort_code,
    period_bounds,
)
from quantcheck.hashing import canonical_sha256, stable_id
from quantcheck.point_in_time import parse_declared_revision_lineage
from quantcheck.schemas import FinancialFact
from quantcheck.sec_adapter import SEC_SOURCE_NAME, companyfacts_url
from quantcheck.serialization import canonical_json_bytes

__all__ = [
    "CORPUS_NAME",
    "CORPUS_UNIT_ROLES",
    "CorpusRegistryError",
    "build_corpus_definition",
    "check_detector_visible_naming",
    "corpus_definition_identity_matches",
    "corpus_unit_canonical_bytes",
    "corpus_unit_ids",
    "corpus_unit_records",
    "corpus_unit_spec",
    "declared_corpus_id",
    "held_out_unit_ids",
    "partition_unit_ids",
    "require_unit_materialization_authorized",
]

CORPUS_NAME = "quantcheck-corpus-v0.2"
_UNIT_NAMESPACE = "quantcheck/corpus-unit/v2"
_CORPUS_NAMESPACE = "quantcheck/corpus-definition/v2"
_DECLARED_CORPUS_NAMESPACE = "quantcheck/corpus-declared-identity/v2"

#: The four roles every partition fills, in stable order.
CORPUS_UNIT_ROLES: tuple[str, ...] = ("broad", "public", "revisions", "stress")

#: The cohort family assigned to each partition. Deliberately neutral words:
#: the family name is hashed into the detector-visible cohort code, and a
#: family called "dev" would defeat inclusion rule IR-05 even through a hash,
#: because the code would still be *derived from* a partition word that a
#: reader with the source could confirm by recomputation.
_PARTITION_FAMILY: dict[str, str] = {
    "development": "aurora",
    "validation": "borealis",
    "heldout": "cirrus",
}


class CorpusRegistryError(CorpusContractError):
    """Raised when a corpus unit cannot be resolved or materialized safely."""


# --- reviewed cohort composition -------------------------------------------

_BROAD_CONCEPTS_A: tuple[str, ...] = (
    "Revenues",
    "NetIncomeLoss",
    "OperatingIncomeLoss",
    "CostOfRevenue",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
    "EarningsPerShareDiluted",
)
_BROAD_CONCEPTS_B: tuple[str, ...] = (
    "Revenues",
    "NetIncomeLoss",
    "ResearchAndDevelopmentExpense",
    "Assets",
    "Liabilities",
    "CashAndCashEquivalentsAtCarryingValue",
    "StockholdersEquity",
    "CommonStockSharesOutstanding",
)
_BROAD_CONCEPTS_C: tuple[str, ...] = (
    "Revenues",
    "CostOfRevenue",
    "OperatingIncomeLoss",
    "Assets",
    "CashAndCashEquivalentsAtCarryingValue",
    "StockholdersEquity",
    "EarningsPerShareDiluted",
    "CommonStockSharesOutstanding",
)
_REVISION_CONCEPTS: tuple[str, ...] = (
    "Revenues",
    "NetIncomeLoss",
    "OperatingIncomeLoss",
    "ResearchAndDevelopmentExpense",
    "CostOfRevenue",
    "Assets",
    "Liabilities",
    "StockholdersEquity",
)
_STRESS_CONCEPTS: tuple[str, ...] = (
    "Revenues",
    "NetIncomeLoss",
    "ResearchAndDevelopmentExpense",
    "Assets",
    "CommonStockSharesOutstanding",
)

#: ``(suffix, calendar, fy_end_month, lag, currency, volatility_bp, concepts,
#: dimensioned, retail_anchor)``. The lag column is the one that matters most:
#: it is the axis the frozen 7/14/30-day Look-Ahead bands are cut on, and the
#: fiscal-year-end column is what lets more than one issuer straddle a single
#: research cutoff.
_BROAD_ISSUERS: tuple[
    tuple[str, str, int, int, str, int, tuple[str, ...], tuple[str, ...], date | None], ...
] = (
    ("q1", "calendar_quarter", 12, 60, "USD", 350, _BROAD_CONCEPTS_A, ("Revenues",), None),
    ("q2", "calendar_quarter", 12, 90, "USD", 620, _BROAD_CONCEPTS_B, (), None),
    ("q3", "calendar_quarter", 10, 21, "USD", 940, _BROAD_CONCEPTS_A, (), None),
    ("q4", "calendar_quarter", 10, 45, "EUR", 470, _BROAD_CONCEPTS_B, ("Assets",), None),
    ("q5", "calendar_quarter", 11, 90, "USD", 260, _BROAD_CONCEPTS_A, (), None),
    ("q6", "calendar_quarter", 10, 16, "USD", 1180, _BROAD_CONCEPTS_C, (), None),
    ("q7", "retail_454", 11, 12, "USD", 760, _BROAD_CONCEPTS_C, (), date(2024, 11, 2)),
)

#: ``(suffix, fy_end_month, lag, currency, volatility_bp, later_filing_gap)``.
#: Every lag is small enough that the first revision is visible at the unit's
#: 2024-06-30 horizon, and every gap is large enough that the second is not —
#: which is precisely the frozen Revision Overwrite eligibility window.
_REVISION_ISSUERS: tuple[tuple[str, int, int, str, int, int], ...] = (
    ("r1", 12, 30, "USD", 300, 95),
    ("r2", 12, 45, "USD", 520, 110),
    ("r3", 12, 60, "USD", 410, 125),
    ("r4", 12, 75, "EUR", 640, 140),
    ("r5", 12, 88, "USD", 220, 100),
    ("r6", 10, 25, "USD", 780, 120),
    ("r7", 10, 40, "GBP", 350, 105),
)

#: The reviewed relative revision sizes, rotated one position per issuer so no
#: issuer is entirely inside or entirely outside a severity band. Four of the
#: eight clear 20%, six clear 5%, and all eight clear 1%.
_REVISION_SIZES: tuple[str, ...] = (
    "0.021",
    "-0.083",
    "0.255",
    "0.412",
    "0.062",
    "-0.301",
    "0.014",
    "0.225",
)

#: The date a revision lineage is anchored to. The plan targets each issuer's
#: latest period ending on or before this date, so issuers on different fiscal
#: calendars all get a lineage without the plan naming a period index.
_REVISION_TARGET_END = date(2024, 4, 30)

_STRESS_ISSUERS: tuple[tuple[str, int, int, str, int], ...] = (
    ("s1", 12, 35, "USD", 1450),
    ("s2", 12, 55, "USD", 1120),
    ("s3", 11, 40, "JPY", 1680),
    ("s4", 10, 28, "USD", 890),
)

_BROAD_PERIODS = 12
_REVISION_PERIODS = 8
_STRESS_PERIODS = 8

_BROAD_HORIZON = CorpusHorizon(
    snapshot_as_of_date=date(2024, 8, 31),
    research_as_of_date=date(2024, 5, 15),
)
_REVISION_HORIZON = CorpusHorizon(
    snapshot_as_of_date=date(2024, 6, 30),
    research_as_of_date=date(2024, 4, 15),
)
_STRESS_HORIZON = CorpusHorizon(
    snapshot_as_of_date=date(2024, 12, 31),
    research_as_of_date=date(2024, 11, 15),
)
_PUBLIC_HORIZON = CorpusHorizon(
    snapshot_as_of_date=date(2024, 8, 31),
    research_as_of_date=date(2024, 5, 15),
)


def _broad_cohort(family: str) -> CohortSpec:
    issuers = tuple(
        IssuerSpec(
            issuer_key=f"{family}-broad-{suffix}",
            entity_name=f"{family.title()} {suffix.upper()} Industries Incorporated",
            fiscal_calendar=calendar,  # type: ignore[arg-type]
            fiscal_year_end_month=fy_month,
            fiscal_year_end_year=2024,
            filing_lag_days=lag,
            currency_unit=currency,
            volatility_bp=volatility,
            concepts=concepts,
            dimensioned_concepts=dimensioned,
            retail_anchor=anchor,
        )
        for (
            suffix,
            calendar,
            fy_month,
            lag,
            currency,
            volatility,
            concepts,
            dimensioned,
            anchor,
        ) in _BROAD_ISSUERS
    )
    return CohortSpec(
        cohort_key=f"{family}-broad",
        period_count=_BROAD_PERIODS,
        issuers=issuers,
        value_overrides=(
            ValueOverride(
                issuer_key=issuers[1].issuer_key,
                concept="NetIncomeLoss",
                period_index=7,
                value="-41800000.00",
                kind="genuine_loss_quarter",
                reason="A real quarterly loss; a negative value is not a corruption.",
            ),
        ),
    )


def _revision_cohort(family: str) -> CohortSpec:
    issuers = tuple(
        IssuerSpec(
            issuer_key=f"{family}-rev-{suffix}",
            entity_name=f"{family.title()} {suffix.upper()} Holdings Public Limited",
            fiscal_calendar="calendar_quarter",
            fiscal_year_end_month=fy_month,
            fiscal_year_end_year=2024,
            filing_lag_days=lag,
            currency_unit=currency,
            volatility_bp=volatility,
            concepts=_REVISION_CONCEPTS,
        )
        for suffix, fy_month, lag, currency, volatility, _gap in _REVISION_ISSUERS
    )
    gaps = {f"{family}-rev-{suffix}": gap for suffix, _m, _l, _c, _v, gap in _REVISION_ISSUERS}

    plans: list[RevisionPlan] = []
    for issuer_index, issuer in enumerate(issuers):
        bounds = period_bounds(issuer, _REVISION_PERIODS)
        candidates = [
            index for index, (_start, end) in enumerate(bounds) if end <= _REVISION_TARGET_END
        ]
        if not candidates:
            raise CorpusRegistryError(f"issuer {issuer.issuer_key!r} has no revisable period")
        period_index = candidates[-1]
        for concept_index, concept in enumerate(_REVISION_CONCEPTS):
            size = _REVISION_SIZES[(concept_index + issuer_index) % len(_REVISION_SIZES)]
            plans.append(
                RevisionPlan(
                    issuer_key=issuer.issuer_key,
                    concept=concept,
                    period_index=period_index,
                    relative_size=size,
                    later_filing_gap_days=gaps[issuer.issuer_key],
                )
            )
    return CohortSpec(
        cohort_key=f"{family}-revisions",
        period_count=_REVISION_PERIODS,
        issuers=issuers,
        revision_plans=tuple(plans),
    )


def _stress_cohort(family: str) -> CohortSpec:
    issuers = tuple(
        IssuerSpec(
            issuer_key=f"{family}-stress-{suffix}",
            entity_name=f"{family.title()} {suffix.upper()} Ventures Company",
            fiscal_calendar="calendar_quarter",
            fiscal_year_end_month=fy_month,
            fiscal_year_end_year=2024,
            filing_lag_days=lag,
            currency_unit=currency,
            volatility_bp=volatility,
            concepts=_STRESS_CONCEPTS,
        )
        for suffix, fy_month, lag, currency, volatility in _STRESS_ISSUERS
    )
    s1, s2, s3, s4 = (issuer.issuer_key for issuer in issuers)
    overrides = (
        ValueOverride(
            issuer_key=s1,
            concept="Revenues",
            period_index=3,
            value="820000.00",
            kind="genuine_recovery_from_near_zero",
            reason=(
                "A real collapse-and-recovery quarter. The local ratio against both "
                "neighbours exceeds the frozen 50x Unit Drift threshold, so this is "
                "expected to produce a finding: it is a hard negative, not a fault."
            ),
        ),
        ValueOverride(
            issuer_key=s2,
            concept="NetIncomeLoss",
            period_index=4,
            value="-38400000.00",
            kind="genuine_loss_quarter",
            reason="A real quarterly loss; a negative value is not a corruption.",
        ),
        ValueOverride(
            issuer_key=s3,
            concept="ResearchAndDevelopmentExpense",
            period_index=2,
            value="0.00",
            kind="genuine_zero_value",
            reason="A real quarter with no capitalisable research spend.",
        ),
    ) + tuple(
        ValueOverride(
            issuer_key=s4,
            concept="CommonStockSharesOutstanding",
            period_index=index,
            value=str(830_000_000 + index * 1_100_000),
            kind="share_split_adjusted_step",
            reason=(
                "A real ten-for-one split. The step is an order of magnitude, well "
                "inside the frozen 50x threshold, so a correct detector stays silent."
            ),
        )
        for index in (5, 6, 7)
    )

    extras = (
        ExtraRow(
            row_key=f"{s1}-Assets-HN-DUPA",
            issuer_key=s1,
            concept="Assets",
            period_type="instant",
            period_start=None,
            period_end=date(2024, 11, 30),
            filed_on=date(2024, 12, 20),
            available_on=date(2024, 12, 20),
            value="2311000000.00",
            form="10-Q",
            accession_ordinal=801,
            kind="legitimate_independent_duplicate",
            reason=(
                "Two independent source occurrences of one economic fact, with no "
                "declared lineage between them; a real feed emits these. They share a "
                "chronology coordinate, so the frozen Unit Drift rule excludes this "
                "issuer's Assets series outright — which is the correct refusal to "
                "guess a local ordering."
            ),
        ),
        ExtraRow(
            row_key=f"{s1}-Assets-HN-DUPB",
            issuer_key=s1,
            concept="Assets",
            period_type="instant",
            period_start=None,
            period_end=date(2024, 11, 30),
            filed_on=date(2024, 12, 20),
            available_on=date(2024, 12, 20),
            value="2311000000.00",
            form="10-Q",
            accession_ordinal=801,
            kind="legitimate_independent_duplicate",
            reason="The second member of the legitimate independent occurrence pair.",
        ),
        ExtraRow(
            row_key=f"{s2}-Assets-HN-CONSOL",
            issuer_key=s2,
            concept="Assets",
            period_type="instant",
            period_start=None,
            period_end=date(2024, 9, 30),
            filed_on=date(2024, 12, 6),
            available_on=date(2024, 12, 6),
            value="1980000000.00",
            form="10-Q",
            accession_ordinal=701,
            kind="consolidation_dimension_lookalike",
            reason=(
                "Same business key as the consolidated total, distinguished only by a "
                "ConsolidationItems dimension. It looks like a duplicate and is not."
            ),
            dimensions=(("ConsolidationItems", "Corporate"),),
        ),
        ExtraRow(
            row_key=f"{s3}-Revenues-HN-DELAYED",
            issuer_key=s3,
            concept="Revenues",
            period_type="duration",
            period_start=date(2024, 6, 1),
            period_end=date(2024, 8, 31),
            filed_on=date(2024, 10, 5),
            available_on=date(2024, 11, 12),
            value="391500000.00",
            form="10-Q",
            accession_ordinal=702,
            kind="delayed_vendor_availability",
            reason=(
                "A vendor embargo: filed publicly before it reached the subscriber. "
                "available_on after filed_on is legitimate and is not a leak, and the "
                "frozen Look-Ahead rule correctly refuses it as a target."
            ),
        ),
        ExtraRow(
            row_key=f"{s4}-Assets-HN-SAMEDAY",
            issuer_key=s4,
            concept="Assets",
            period_type="instant",
            period_start=None,
            period_end=date(2024, 11, 30),
            filed_on=date(2024, 11, 30),
            available_on=date(2024, 11, 30),
            value="2058000000.00",
            form="10-Q",
            accession_ordinal=703,
            kind="same_day_filing_and_period_end",
            reason=(
                "A same-day disclosure. A zero filing lag is unusual but real, and it "
                "sits below every frozen Look-Ahead severity band."
            ),
        ),
        ExtraRow(
            row_key=f"{s1}-Revenues-HN-STUB",
            issuer_key=s1,
            concept="Revenues",
            period_type="duration",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 2, 14),
            filed_on=date(2024, 4, 3),
            available_on=date(2024, 4, 3),
            value="219700000.00",
            form="10-Q",
            accession_ordinal=704,
            kind="fiscal_year_change_stub_period",
            reason=(
                "A 45-day stub period from a fiscal calendar change. Its period length "
                "puts it in its own comparable series, which is correct."
            ),
        ),
        ExtraRow(
            row_key=f"{s2}-NetIncomeLoss-HN-NOCHANGE#r1",
            issuer_key=s2,
            concept="NetIncomeLoss",
            period_type="duration",
            period_start=date(2024, 7, 1),
            period_end=date(2024, 9, 30),
            filed_on=date(2024, 10, 15),
            available_on=date(2024, 10, 15),
            value="58300000.00",
            form="10-Q",
            accession_ordinal=705,
            kind="identical_value_restatement",
            reason=(
                "A refiling that corrected a footnote and left the number alone. The "
                "frozen rule finds no revision here, which is the right answer."
            ),
        ),
        ExtraRow(
            row_key=f"{s2}-NetIncomeLoss-HN-NOCHANGE#r2",
            issuer_key=s2,
            concept="NetIncomeLoss",
            period_type="duration",
            period_start=date(2024, 7, 1),
            period_end=date(2024, 9, 30),
            filed_on=date(2025, 2, 10),
            available_on=date(2025, 2, 10),
            value="58300000.00",
            form="10-Q/A",
            accession_ordinal=706,
            kind="identical_value_restatement",
            reason="The second member of the value-preserving restatement.",
        ),
    )
    return CohortSpec(
        cohort_key=f"{family}-stress",
        period_count=_STRESS_PERIODS,
        issuers=issuers,
        value_overrides=overrides,
        extra_rows=extras,
    )


def _public_spec(family: str) -> CuratedPublicSpec:
    scales = {"aurora": "1.00", "borealis": "0.63", "cirrus": "1.41"}
    return CuratedPublicSpec(
        registrant_key=f"{family}-public",
        entity_name=(
            f"{family.title()} Public Registrant Placeholder "
            "(curated field-shape document, not a real registrant)"
        ),
        filing_lag_days=55,
        scale=scales[family],
    )


# --- unit specifications ----------------------------------------------------


def _unit_identity(
    *,
    partition: str,
    role: str,
    audit_dataset_name: str,
    source_name: str,
    source_locator: str,
    horizon: CorpusHorizon,
) -> str:
    return stable_id(
        prefix="cunit",
        namespace=_UNIT_NAMESPACE,
        payload={
            "partition": partition,
            "role": role,
            "audit_dataset_name": audit_dataset_name,
            "source_name": source_name,
            "source_locator": source_locator,
            "snapshot_as_of_date": horizon.snapshot_as_of_date,
            "research_as_of_date": horizon.research_as_of_date,
        },
    )


def _synthetic_unit_inputs(partition: str, role: str) -> tuple[CohortSpec, CorpusHorizon]:
    family = _PARTITION_FAMILY[partition]
    if role == "broad":
        return _broad_cohort(family), _BROAD_HORIZON
    if role == "revisions":
        return _revision_cohort(family), _REVISION_HORIZON
    if role == "stress":
        return _stress_cohort(family), _STRESS_HORIZON
    raise CorpusRegistryError(f"unsupported synthetic corpus role: {role!r}")


def _unit_naming(partition: str, role: str) -> tuple[str, str, str, CorpusHorizon]:
    """Return the detector-visible naming and horizon for one unit."""
    if role == "public":
        spec = _public_spec(_PARTITION_FAMILY[partition])
        locator = companyfacts_url(curated_public_cik(spec.registrant_key))
        return (f"corpus-{SEC_SOURCE_NAME}", SEC_SOURCE_NAME, locator, _PUBLIC_HORIZON)
    cohort, horizon = _synthetic_unit_inputs(partition, role)
    code = cohort_code(cohort.cohort_key)
    return (code, code, f"quantcheck/corpus/v2/{code}", horizon)


def check_detector_visible_naming(*names: str) -> None:
    """Enforce inclusion rule IR-05 mechanically, not by review.

    A detector-visible string that contains a partition word — or any of the
    conventional synonyms for one — is refused at construction time, so the
    leakage property cannot be lost by someone renaming a cohort.
    """
    for name in names:
        lowered = name.lower()
        for token in PARTITION_LEAKAGE_TOKENS:
            if token in lowered:
                raise CorpusRegistryError(
                    f"detector-visible name {name!r} carries partition token {token!r}"
                )


def _diversity(
    records: tuple[FinancialFact, ...],
    *,
    hard_negative_count: int,
) -> CorpusDiversityProfile:
    lags = [(record.filed_on - record.period_end).days for record in records]
    lineages: dict[str, list[tuple[int, FinancialFact]]] = {}
    for record in records:
        lineage = parse_declared_revision_lineage(record.source.source_row_key)
        if lineage is not None:
            lineages.setdefault(lineage.lineage_id, []).append((lineage.sequence, record))

    largest = Decimal(0)
    for members in lineages.values():
        ordered = sorted(members, key=lambda item: item[0])
        for (_first_sequence, earlier), (_second_sequence, later) in zip(
            ordered, ordered[1:], strict=False
        ):
            if earlier.value == 0:
                continue
            with localcontext() as context:
                context.prec = 50
                size = abs(later.value - earlier.value) / abs(earlier.value)
            largest = max(largest, size)

    return CorpusDiversityProfile(
        record_count=len(records),
        issuer_count=len({record.entity_id for record in records}),
        concept_count=len({record.concept for record in records}),
        measurement_unit_count=len({record.unit for record in records}),
        distinct_period_end_count=len({record.period_end for record in records}),
        period_end_signature_count=len(
            {((record.period_end.month - 1) % 3, record.period_end.day) for record in records}
        ),
        minimum_filing_lag_days=max(0, min(lags)),
        maximum_filing_lag_days=max(lags),
        distinct_filing_lag_count=len(set(lags)),
        declared_revision_lineage_count=len(lineages),
        maximum_relative_revision_size=largest,
        delayed_availability_count=sum(
            1 for record in records if record.available_on != record.filed_on
        ),
        dimensioned_record_count=sum(1 for record in records if record.dimensions),
        negative_value_count=sum(1 for record in records if record.value < 0),
        zero_value_count=sum(1 for record in records if record.value == 0),
        hard_negative_count=hard_negative_count,
    )


def _declared_hard_negative_count(partition: str, role: str) -> int:
    """How many hard negatives one unit's reviewed specification declares.

    Counted from the specification rather than from the generated records, so
    a value override — which replaces a value in place and leaves no marker in
    the row key — is counted exactly like an added row.
    """
    if role == "public":
        return 0
    cohort, _horizon = _synthetic_unit_inputs(partition, role)
    return len(cohort.value_overrides) + len(cohort.extra_rows)


def _declared_support(role: str) -> tuple[str, ...]:
    if role == "revisions":
        return ("duplicate_observation", "lookahead_timestamp", "revision_overwrite", "unit_drift")
    if role == "public":
        # A Company Facts response carries no declared revision lineage marker,
        # so this source class structurally cannot support Revision Overwrite.
        return ("duplicate_observation", "lookahead_timestamp", "unit_drift")
    return ("duplicate_observation", "lookahead_timestamp", "unit_drift")


def _provenance(role: str) -> CorpusProvenance:
    if role == "public":
        return CorpusProvenance(
            source_class="curated_public",
            license_tier="public_government",
            publisher=CURATED_PUBLIC_PUBLISHER,
            retrieval_method=CURATED_PUBLIC_RETRIEVAL_METHOD,
            in_repository=True,
            redistributable=True,
            verbatim_source=not CURATED_PUBLIC_IS_PLACEHOLDER,
            notes=(
                "Curated SEC Company Facts field-shape document read through the frozen "
                "adapter. Placeholder registrants and purpose-built values; no live "
                "retrieval has been performed and no saved response is reproduced."
            ),
        )
    return CorpusProvenance(
        source_class="synthetic_adversarial",
        license_tier="synthetic_repository",
        publisher="quantcheck",
        retrieval_method="in_package_pure_factory",
        in_repository=True,
        redistributable=True,
        verbatim_source=False,
        notes="Wholly invented data generated by a pure factory; no real issuer is described.",
    )


def _materialize(partition: str, role: str) -> tuple[FinancialFact, ...]:
    if role == "public":
        return curated_public_records(_public_spec(_PARTITION_FAMILY[partition]))
    cohort, _horizon = _synthetic_unit_inputs(partition, role)
    return build_cohort_records(cohort)


@cache
def _cached_records(partition: str, role: str) -> tuple[FinancialFact, ...]:
    return _materialize(partition, role)


_SYNTHETIC_RULES = ("IR-01", "IR-02", "IR-03", "IR-04", "IR-05", "IR-06", "IR-07")
_PUBLIC_RULES = (*_SYNTHETIC_RULES, "IR-09")


@cache
def _unit_body(partition: str, role: str) -> tuple[tuple[str, object], ...]:
    """One unit's declarative fields, before its record-derived content.

    Returned as a tuple of pairs rather than a validated model because a
    committed unit is not *valid* until it carries its content hash and
    diversity — that invariant is the point of ``CorpusUnitSpec`` — and the
    registry needs the identity long before it materializes any record.
    """
    audit_dataset_name, source_name, source_locator, horizon = _unit_naming(partition, role)
    check_detector_visible_naming(audit_dataset_name, source_name, source_locator)
    return (
        (
            "corpus_unit_id",
            _unit_identity(
                partition=partition,
                role=role,
                audit_dataset_name=audit_dataset_name,
                source_name=source_name,
                source_locator=source_locator,
                horizon=horizon,
            ),
        ),
        ("unit_name", f"{partition}-{role}"),
        ("partition", partition),
        ("audit_dataset_name", audit_dataset_name),
        ("source_name", source_name),
        ("source_locator", source_locator),
        ("provenance", _provenance(role)),
        ("horizon", horizon),
        ("inclusion_rule_ids", _PUBLIC_RULES if role == "public" else _SYNTHETIC_RULES),
        ("supported_fault_profiles", _declared_support(role)),
    )


def _unit_id(partition: str, role: str) -> str:
    identifier = dict(_unit_body(partition, role))["corpus_unit_id"]
    assert isinstance(identifier, str)
    return identifier


def corpus_unit_ids() -> tuple[str, ...]:
    """Every declared corpus unit identifier, sorted."""
    return tuple(
        sorted(
            _unit_id(partition, role)
            for partition in CORPUS_PARTITIONS
            for role in CORPUS_UNIT_ROLES
        )
    )


def partition_unit_ids(partition: str) -> tuple[str, ...]:
    """Every declared unit identifier in one partition, sorted."""
    if partition not in CORPUS_PARTITIONS:
        raise CorpusRegistryError(f"unknown corpus partition: {partition!r}")
    return tuple(sorted(_unit_id(partition, role) for role in CORPUS_UNIT_ROLES))


def declared_corpus_id() -> str:
    """The corpus identity derivable *without* materializing any record.

    The full :func:`build_corpus_definition` identity covers content hashes and
    therefore needs the held-out authorization. This one covers only the
    declarative bodies, so a script can name the corpus it is about to open the
    held-out gate for without first opening it.
    """
    return stable_id(
        prefix="corp",
        namespace=_DECLARED_CORPUS_NAMESPACE,
        payload={
            "corpus_name": CORPUS_NAME,
            "spec_version": "quantcheck/corpus/v2",
            "units": tuple(
                dict(_unit_body(partition, role))
                for partition in CORPUS_PARTITIONS
                for role in CORPUS_UNIT_ROLES
            ),
        },
    )


def held_out_unit_ids() -> tuple[str, ...]:
    """The complete declared held-out partition, sorted.

    This is the exact set :func:`quantcheck.corpus_gate.held_out_corpus_units`
    must be opened for; anything narrower is refused.
    """
    return partition_unit_ids(HELD_OUT_PARTITION)


def _locate(unit_id: str) -> tuple[str, str]:
    for partition in CORPUS_PARTITIONS:
        for role in CORPUS_UNIT_ROLES:
            if _unit_id(partition, role) == unit_id:
                return partition, role
    raise CorpusRegistryError(f"unsupported corpus unit: {unit_id!r}")


def require_unit_materialization_authorized(unit_id: str) -> None:
    """Refuse to materialize a held-out unit without a complete authorization.

    This is the security boundary, and it is deliberately about materialization
    rather than description: a held-out unit's identifier, provenance, horizon,
    content hash, and eligibility counts are all committed evidence that must
    stay readable with no authorization open. What must never happen without one
    is *building its records*.
    """
    partition, _role = _locate(unit_id)
    if partition != HELD_OUT_PARTITION:
        return
    if not held_out_unit_authorized(unit_id):
        raise HeldOutCorpusAuthorizationError(
            f"corpus unit {unit_id} is held out and is not authorized for materialization"
        )
    authorization = active_held_out_corpus_authorization()
    assert authorization is not None
    declared = held_out_unit_ids()
    if authorization.unit_ids != declared:
        raise HeldOutCorpusAuthorizationError(
            "the complete held-out corpus partition must be authorized at once"
        )


def corpus_unit_records(unit_id: str) -> tuple[FinancialFact, ...]:
    """Return the clean records of one corpus unit.

    The authorization check runs *before* the memoized factory, so a cached
    held-out result can never satisfy a later unauthorized call.
    """
    partition, role = _locate(unit_id)
    require_unit_materialization_authorized(unit_id)
    return _cached_records(partition, role)


def corpus_unit_spec(unit_id: str) -> CorpusUnitSpec:
    """Return one unit's complete specification, including its content hash.

    Building the content hash requires the records, so this is subject to the
    same held-out authorization as :func:`corpus_unit_records`. Read a frozen
    held-out specification from the committed corpus freeze record instead
    (:mod:`quantcheck.corpus_freeze`) when no authorization is open.
    """
    partition, role = _locate(unit_id)
    records = corpus_unit_records(unit_id)
    return CorpusUnitSpec.model_validate(
        {
            **dict(_unit_body(partition, role)),
            "diversity": _diversity(
                records,
                hard_negative_count=_declared_hard_negative_count(partition, role),
            ),
            "content_hash": canonical_sha256(records),
        }
    )


def build_corpus_definition() -> CorpusDefinition:
    """Build the complete v0.2 corpus, materializing every unit.

    Because it covers the held-out partition, this requires an active held-out
    authorization. Ordinary readers should load the committed freeze record.
    """
    partitions = []
    for partition in CORPUS_PARTITIONS:
        units = tuple(corpus_unit_spec(unit_id) for unit_id in partition_unit_ids(partition))
        partitions.append(
            CorpusPartitionSpec(
                partition=partition,  # type: ignore[arg-type]
                units=units,
                unit_count=len(units),
                committed_record_count=sum(
                    unit.diversity.record_count for unit in units if unit.diversity is not None
                ),
            )
        )
    body = _corpus_body(partitions=tuple(partitions), unsupported=())
    # Validate once to obtain the normalized (sorted) form, then hash that
    # rather than the order the partitions happened to be built in.
    normalized = CorpusDefinition.model_validate(
        {"corpus_id": stable_id(prefix="corp", namespace=_CORPUS_NAMESPACE, payload=body), **body}
    )
    settled = _corpus_body(
        partitions=normalized.partitions,
        unsupported=normalized.declared_unsupported_cells,
    )
    return CorpusDefinition.model_validate(
        {
            "corpus_id": stable_id(prefix="corp", namespace=_CORPUS_NAMESPACE, payload=settled),
            **settled,
        }
    )


def _corpus_body(
    *,
    partitions: tuple[CorpusPartitionSpec, ...],
    unsupported: tuple[CorpusUnsupportedCell, ...],
) -> dict[str, object]:
    return {
        "spec_version": "quantcheck/corpus/v2",
        "corpus_name": CORPUS_NAME,
        "partitions": partitions,
        "declared_unsupported_cells": unsupported,
    }


def corpus_definition_identity_matches(corpus: CorpusDefinition) -> bool:
    """Report whether a corpus's stored identifier matches its content."""
    body = _corpus_body(
        partitions=corpus.partitions,
        unsupported=corpus.declared_unsupported_cells,
    )
    return corpus.corpus_id == stable_id(prefix="corp", namespace=_CORPUS_NAMESPACE, payload=body)


def corpus_unit_canonical_bytes(unit_id: str) -> bytes:
    """The canonical bytes one unit's records serialize to."""
    return canonical_json_bytes(corpus_unit_records(unit_id))
