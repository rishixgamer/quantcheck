"""Property-based checks over the v0.2 corpus generators and contract.

Example-based tests fix the corpus as it is today. These fix the *invariants*
that must survive any future cohort a maintainer writes.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from quantcheck.corpus_contract import CORPUS_PARTITIONS, PARTITION_LEAKAGE_TOKENS
from quantcheck.corpus_registry import CorpusRegistryError, check_detector_visible_naming
from quantcheck.corpus_synthetic import (
    CONCEPT_CATALOG,
    CohortSpec,
    IssuerSpec,
    RevisionPlan,
    build_cohort_records,
    cohort_code,
    cohort_entity_id,
    period_bounds,
)
from quantcheck.point_in_time import build_dataset_snapshot, parse_declared_revision_lineage
from quantcheck.serialization import canonical_json_bytes

_CONCEPT_NAMES = [spec.concept for spec in CONCEPT_CATALOG]

_issuer_keys = st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=3, max_size=24).filter(
    lambda value: value.strip("-") != ""
)


@st.composite
def _issuers(draw: st.DrawFn) -> IssuerSpec:
    return IssuerSpec(
        issuer_key=draw(_issuer_keys),
        entity_name=draw(st.text(alphabet="ABCDEFGHIJ ", min_size=3, max_size=20)).strip()
        or "Example Issuer",
        fiscal_calendar="calendar_quarter",
        fiscal_year_end_month=draw(st.integers(min_value=1, max_value=12)),
        fiscal_year_end_year=draw(st.integers(min_value=2022, max_value=2026)),
        filing_lag_days=draw(st.integers(min_value=0, max_value=180)),
        currency_unit=draw(st.sampled_from(["USD", "EUR", "GBP", "JPY"])),
        volatility_bp=draw(st.integers(min_value=0, max_value=3000)),
        concepts=tuple(
            draw(st.lists(st.sampled_from(_CONCEPT_NAMES), min_size=1, max_size=4, unique=True))
        ),
    )


@settings(max_examples=40, deadline=None)
@given(issuer=_issuers(), period_count=st.integers(min_value=3, max_value=10))
def test_generated_records_are_never_pre_corrupted(issuer: IssuerSpec, period_count: int) -> None:
    """A clean source never carries the defect the benchmark exists to inject."""
    records = build_cohort_records(
        CohortSpec(cohort_key="prop", period_count=period_count, issuers=(issuer,))
    )
    for record in records:
        assert record.available_on == record.filed_on
        assert record.filed_on >= record.period_end
        assert record.value != 0


@settings(max_examples=40, deadline=None)
@given(issuer=_issuers(), period_count=st.integers(min_value=3, max_value=10))
def test_generation_is_a_pure_function_of_the_specification(
    issuer: IssuerSpec, period_count: int
) -> None:
    cohort = CohortSpec(cohort_key="prop", period_count=period_count, issuers=(issuer,))
    assert canonical_json_bytes(build_cohort_records(cohort)) == canonical_json_bytes(
        build_cohort_records(cohort)
    )


@settings(max_examples=40, deadline=None)
@given(issuer=_issuers(), period_count=st.integers(min_value=3, max_value=10))
def test_record_ids_are_unique_within_a_cohort(issuer: IssuerSpec, period_count: int) -> None:
    records = build_cohort_records(
        CohortSpec(cohort_key="prop", period_count=period_count, issuers=(issuer,))
    )
    identifiers = [record.record_id for record in records]
    assert len(set(identifiers)) == len(identifiers)


@settings(max_examples=40, deadline=None)
@given(issuer=_issuers(), period_count=st.integers(min_value=3, max_value=12))
def test_periods_are_strictly_increasing_and_non_overlapping(
    issuer: IssuerSpec, period_count: int
) -> None:
    bounds = period_bounds(issuer, period_count)
    assert len(bounds) == period_count
    for (_previous_start, previous_end), (start, end) in zip(bounds, bounds[1:], strict=False):
        assert previous_end < start <= end


@settings(max_examples=30, deadline=None)
@given(
    issuer=_issuers(),
    period_count=st.integers(min_value=3, max_value=8),
    relative_size=st.decimals(
        min_value=Decimal("0.02"), max_value=Decimal("0.90"), places=3, allow_nan=False
    ),
    gap=st.integers(min_value=1, max_value=400),
)
def test_a_revision_plan_always_produces_a_two_member_lineage(
    issuer: IssuerSpec, period_count: int, relative_size: Decimal, gap: int
) -> None:
    concept = issuer.concepts[0]
    records = build_cohort_records(
        CohortSpec(
            cohort_key="prop",
            period_count=period_count,
            issuers=(issuer,),
            revision_plans=(
                RevisionPlan(
                    issuer_key=issuer.issuer_key,
                    concept=concept,
                    period_index=0,
                    relative_size=str(relative_size),
                    later_filing_gap_days=gap,
                ),
            ),
        )
    )
    lineages: dict[str, set[int]] = {}
    for record in records:
        parsed = parse_declared_revision_lineage(record.source.source_row_key)
        if parsed is not None:
            lineages.setdefault(parsed.lineage_id, set()).add(parsed.sequence)
    assert len(lineages) == 1
    assert next(iter(lineages.values())) == {1, 2}


@settings(max_examples=30, deadline=None)
@given(
    issuer=_issuers(),
    period_count=st.integers(min_value=3, max_value=8),
    offset=st.integers(min_value=-400, max_value=400),
)
def test_a_snapshot_never_contains_a_record_not_yet_available(
    issuer: IssuerSpec, period_count: int, offset: int
) -> None:
    records = build_cohort_records(
        CohortSpec(cohort_key="prop", period_count=period_count, issuers=(issuer,))
    )
    as_of = records[0].period_end + timedelta(days=offset)
    snapshot = build_dataset_snapshot(records, dataset_name="prop", as_of_date=as_of)
    for record in snapshot.records:
        assert record.available_on <= as_of


@settings(max_examples=100, deadline=None)
@given(key=st.text(min_size=1, max_size=60))
def test_derived_identifiers_are_always_well_formed(key: str) -> None:
    code = cohort_code(key)
    assert code.startswith("ccoh_")
    assert len(code) == len("ccoh_") + 16
    entity_id = cohort_entity_id(key)
    assert entity_id.startswith("CIK")
    assert len(entity_id) == 13
    assert entity_id[3:].isdigit()


@settings(max_examples=100, deadline=None)
@given(key=st.text(min_size=1, max_size=60))
def test_a_derived_cohort_code_can_never_carry_a_partition_token(key: str) -> None:
    """The opacity guarantee, over arbitrary cohort keys.

    A code is hexadecimal, and every leakage token contains a character outside
    that alphabet, so the property is structural rather than incidental.
    """
    check_detector_visible_naming(cohort_code(key))


@settings(max_examples=100, deadline=None)
@given(
    prefix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz-_/", min_size=0, max_size=12),
    token=st.sampled_from(PARTITION_LEAKAGE_TOKENS),
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz-_/", min_size=0, max_size=12),
)
def test_any_name_containing_a_partition_token_is_refused(
    prefix: str, token: str, suffix: str
) -> None:
    try:
        check_detector_visible_naming(f"{prefix}{token}{suffix}")
    except CorpusRegistryError:
        return
    raise AssertionError(f"{prefix}{token}{suffix} was accepted")


@settings(max_examples=50, deadline=None)
@given(partition=st.sampled_from(CORPUS_PARTITIONS))
def test_every_partition_name_is_itself_a_leakage_token(partition: str) -> None:
    assert partition in PARTITION_LEAKAGE_TOKENS


@settings(max_examples=30, deadline=None)
@given(issuer=_issuers(), period_count=st.integers(min_value=3, max_value=8))
def test_duration_records_always_carry_a_start_and_instants_never_do(
    issuer: IssuerSpec, period_count: int
) -> None:
    records = build_cohort_records(
        CohortSpec(cohort_key="prop", period_count=period_count, issuers=(issuer,))
    )
    for record in records:
        if record.period_type == "instant":
            assert record.period_start is None
        else:
            assert record.period_start is not None
            assert record.period_start <= record.period_end


def test_period_bounds_are_stable_for_a_fixed_specification() -> None:
    issuer = IssuerSpec(
        issuer_key="stable",
        entity_name="Stable Issuer",
        fiscal_calendar="calendar_quarter",
        fiscal_year_end_month=12,
        fiscal_year_end_year=2024,
        filing_lag_days=45,
        currency_unit="USD",
        volatility_bp=0,
        concepts=("Revenues",),
    )
    assert period_bounds(issuer, 4)[-1] == (date(2024, 10, 1), date(2024, 12, 31))
