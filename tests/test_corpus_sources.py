"""The three v0.2 corpus source classes and what each actually contributes.

The point of the v0.2 substrate is external validity, and external validity is
a claim about *diversity*. These tests check the diversity is real — measured
off the generated records, not asserted in prose — and that the hard negatives
are the legitimate-but-unusual observations they are declared to be.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from quantcheck.corpus_public import (
    CURATED_PUBLIC_CONCEPTS,
    CURATED_PUBLIC_IS_PLACEHOLDER,
    CuratedPublicSpec,
    companyfacts_json_bytes,
    curated_public_config,
    curated_public_envelope,
    curated_public_records,
)
from quantcheck.corpus_registry import (
    CORPUS_UNIT_ROLES,
    CorpusRegistryError,
    corpus_unit_ids,
    corpus_unit_records,
    corpus_unit_spec,
)
from quantcheck.corpus_synthetic import (
    CONCEPT_CATALOG,
    HARD_NEGATIVE_KINDS,
    CohortSpec,
    ExtraRow,
    IssuerSpec,
    ValueOverride,
    build_cohort_records,
    cohort_code,
    cohort_entity_id,
)
from quantcheck.fixtures import EXPECTED_FIXTURE_RECORD_COUNT
from quantcheck.point_in_time import parse_declared_revision_lineage
from quantcheck.sec_adapter import SEC_SOURCE_NAME, normalize_companyfacts
from tests.corpus_support import ORDINARY_PARTITIONS, ordinary_unit_ids, unit_bundle, unit_by_role


class TestTheCorpusIsSubstantiallyLargerThanV01:
    def test_every_ordinary_partition_dwarfs_the_v01_reviewed_fixture(self) -> None:
        for partition in ORDINARY_PARTITIONS:
            total = 0
            for unit_id in ordinary_unit_ids():
                spec = unit_bundle(unit_id)[0]
                assert spec.diversity is not None
                if spec.partition == partition:
                    total += spec.diversity.record_count
            # v0.1 measured on 26 reviewed records plus a five-observation
            # series. Two orders of magnitude is the point of the exercise.
            assert total > 40 * EXPECTED_FIXTURE_RECORD_COUNT

    def test_the_corpus_declares_four_units_in_each_of_three_partitions(self) -> None:
        assert len(corpus_unit_ids()) == 3 * len(CORPUS_UNIT_ROLES)

    def test_an_unknown_unit_is_refused_rather_than_guessed(self) -> None:
        with pytest.raises(CorpusRegistryError, match="unsupported corpus unit"):
            corpus_unit_records("cunit_ffffffffffffffff")


class TestDiversityIsMeasuredNotAsserted:
    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_the_declared_record_count_matches_the_generated_records(self, unit_id: str) -> None:
        spec, records, _snapshot = unit_bundle(unit_id)
        assert spec.diversity is not None
        assert spec.diversity.record_count == len(records)

    def test_the_broad_unit_spans_issuers_calendars_lags_and_units(self) -> None:
        spec, _records, _snapshot = unit_bundle(unit_by_role("development", "broad"))
        diversity = spec.diversity
        assert diversity is not None
        assert diversity.issuer_count == 7
        assert diversity.concept_count >= 8
        assert diversity.measurement_unit_count >= 3
        assert diversity.distinct_period_end_count >= 24
        # More than one fiscal-calendar shape is what lets a single research
        # cutoff straddle several issuers, which is what makes Look-Ahead
        # eligible at more than one filing-lag band.
        assert diversity.period_end_signature_count > 1
        assert diversity.minimum_filing_lag_days < 14
        assert diversity.maximum_filing_lag_days >= 90
        assert diversity.distinct_filing_lag_count >= 5
        assert diversity.dimensioned_record_count > 0

    def test_the_revisions_unit_spans_all_three_frozen_revision_bands(self) -> None:
        spec, records, _snapshot = unit_bundle(unit_by_role("development", "revisions"))
        assert spec.diversity is not None
        assert spec.diversity.declared_revision_lineage_count >= 40
        # The frozen high band needs a 20% relative revision, which the v0.1
        # fixture's largest (2%) could never reach.
        assert spec.diversity.maximum_relative_revision_size > Decimal("0.20")
        lineages = {
            parse_declared_revision_lineage(record.source.source_row_key)
            for record in records
            if parse_declared_revision_lineage(record.source.source_row_key) is not None
        }
        assert {lineage.sequence for lineage in lineages if lineage is not None} == {1, 2}

    def test_the_stress_unit_carries_the_declared_hard_negatives(self) -> None:
        spec, _records, _snapshot = unit_bundle(unit_by_role("development", "stress"))
        assert spec.diversity is not None
        assert spec.diversity.hard_negative_count >= 10
        assert spec.diversity.negative_value_count > 0
        assert spec.diversity.zero_value_count > 0
        assert spec.diversity.delayed_availability_count > 0

    def test_no_unit_is_generated_with_a_duplicate_record_id(self) -> None:
        for unit_id in ordinary_unit_ids():
            _spec, records, _snapshot = unit_bundle(unit_id)
            identifiers = [record.record_id for record in records]
            assert len(set(identifiers)) == len(identifiers)


class TestTheCorpusInjectsNothing:
    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_no_record_carries_availability_before_filing(self, unit_id: str) -> None:
        # available_on < filed_on is precisely the Look-Ahead defect. It must be
        # injected by the benchmark, never baked into a clean source.
        _spec, records, _snapshot = unit_bundle(unit_id)
        for record in records:
            assert record.available_on >= record.filed_on

    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_period_shapes_are_internally_consistent(self, unit_id: str) -> None:
        _spec, records, _snapshot = unit_bundle(unit_id)
        for record in records:
            if record.period_type == "instant":
                assert record.period_start is None
            else:
                assert record.period_start is not None
                assert record.period_start <= record.period_end


class TestSyntheticCohortConstruction:
    def test_the_cohort_code_is_hash_derived_and_stable(self) -> None:
        assert cohort_code("aurora-broad") == cohort_code("aurora-broad")
        assert cohort_code("aurora-broad") != cohort_code("borealis-broad")
        assert cohort_code("aurora-broad").startswith("ccoh_")

    def test_entity_ids_are_ten_digit_and_hash_derived(self) -> None:
        entity_id = cohort_entity_id("aurora-broad-q1")
        assert entity_id.startswith("CIK")
        assert len(entity_id) == 13
        assert entity_id[3:].isdigit()
        assert entity_id != cohort_entity_id("aurora-broad-q2")

    def test_an_issuer_reporting_an_unknown_concept_is_refused(self) -> None:
        with pytest.raises(ValueError, match="unknown concepts"):
            IssuerSpec(
                issuer_key="x",
                entity_name="X",
                fiscal_calendar="calendar_quarter",
                fiscal_year_end_month=12,
                fiscal_year_end_year=2024,
                filing_lag_days=30,
                currency_unit="USD",
                volatility_bp=100,
                concepts=("NotARealConcept",),
            )

    def test_a_retail_issuer_without_an_anchor_is_refused(self) -> None:
        with pytest.raises(ValueError, match="explicit retail anchor"):
            IssuerSpec(
                issuer_key="x",
                entity_name="X",
                fiscal_calendar="retail_454",
                fiscal_year_end_month=11,
                fiscal_year_end_year=2024,
                filing_lag_days=12,
                currency_unit="USD",
                volatility_bp=100,
                concepts=("Revenues",),
            )

    def test_an_undocumented_hard_negative_kind_is_refused(self) -> None:
        with pytest.raises(ValueError, match="undocumented hard-negative kind"):
            ValueOverride(
                issuer_key="x",
                concept="Revenues",
                period_index=0,
                value="1.00",
                kind="because_i_said_so",
                reason="no",
            )

    def test_every_documented_hard_negative_kind_is_distinct(self) -> None:
        assert len(set(HARD_NEGATIVE_KINDS)) == len(HARD_NEGATIVE_KINDS)

    def test_a_cohort_needs_enough_periods_to_form_a_series(self) -> None:
        issuer = IssuerSpec(
            issuer_key="x",
            entity_name="X",
            fiscal_calendar="calendar_quarter",
            fiscal_year_end_month=12,
            fiscal_year_end_year=2024,
            filing_lag_days=30,
            currency_unit="USD",
            volatility_bp=100,
            concepts=("Revenues",),
        )
        with pytest.raises(ValueError, match="at least three periods"):
            CohortSpec(cohort_key="tiny", period_count=2, issuers=(issuer,))

    def test_a_skipped_observation_is_omitted(self) -> None:
        issuer = IssuerSpec(
            issuer_key="skip-me",
            entity_name="Skip Me Incorporated",
            fiscal_calendar="calendar_quarter",
            fiscal_year_end_month=12,
            fiscal_year_end_year=2024,
            filing_lag_days=30,
            currency_unit="USD",
            volatility_bp=0,
            concepts=("Revenues",),
        )
        full = build_cohort_records(CohortSpec(cohort_key="k1", period_count=4, issuers=(issuer,)))
        pruned = build_cohort_records(
            CohortSpec(
                cohort_key="k1",
                period_count=4,
                issuers=(issuer,),
                skipped=frozenset({("skip-me", "Revenues", 1)}),
            )
        )
        assert len(full) - len(pruned) == 1

    def test_an_extra_row_derives_its_accession_from_its_own_issuer(self) -> None:
        from datetime import date

        issuer = IssuerSpec(
            issuer_key="extra-issuer",
            entity_name="Extra Issuer Incorporated",
            fiscal_calendar="calendar_quarter",
            fiscal_year_end_month=12,
            fiscal_year_end_year=2024,
            filing_lag_days=30,
            currency_unit="USD",
            volatility_bp=0,
            concepts=("Revenues",),
        )
        extra = ExtraRow(
            row_key="extra-issuer-Revenues-HN-ONE",
            issuer_key="extra-issuer",
            concept="Revenues",
            period_type="duration",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 2, 14),
            filed_on=date(2024, 4, 3),
            available_on=date(2024, 4, 3),
            value="1000.00",
            form="10-Q",
            accession_ordinal=801,
            kind="fiscal_year_change_stub_period",
            reason="stub",
        )
        records = build_cohort_records(
            CohortSpec(cohort_key="k2", period_count=4, issuers=(issuer,), extra_rows=(extra,))
        )
        row = next(r for r in records if r.source.source_row_key == extra.row_key)
        assert row.accession_number is not None
        assert row.accession_number.startswith(cohort_entity_id("extra-issuer").removeprefix("CIK"))

    def test_the_concept_catalogue_covers_both_period_shapes_and_three_unit_kinds(self) -> None:
        assert {spec.period_type for spec in CONCEPT_CATALOG} == {"instant", "duration"}
        assert len({spec.unit_kind for spec in CONCEPT_CATALOG}) == 3


class TestCuratedPublicSource:
    def test_the_placeholder_status_is_machine_readable(self) -> None:
        # The provenance must never claim a live retrieval that did not happen.
        assert CURATED_PUBLIC_IS_PLACEHOLDER is True
        spec, _records, _snapshot = unit_bundle(unit_by_role("development", "public"))
        assert spec.provenance.source_class == "curated_public"
        assert spec.provenance.license_tier == "public_government"
        assert spec.provenance.verbatim_source is False
        assert "no live retrieval" in spec.provenance.notes

    def test_records_come_through_the_frozen_sec_adapter(self) -> None:
        _spec, records, _snapshot = unit_bundle(unit_by_role("development", "public"))
        assert records
        for record in records:
            assert record.source.source_name == SEC_SOURCE_NAME
            assert record.source.source_locator.startswith("https://data.sec.gov/")
            assert record.available_on == record.filed_on
            assert record.dimensions == ()

    def test_the_envelope_exercises_the_adapters_exclusion_path(self) -> None:
        spec = CuratedPublicSpec(
            registrant_key="aurora-public",
            entity_name="Aurora Public Registrant Placeholder",
            filing_lag_days=55,
            scale="1.00",
        )
        result = normalize_companyfacts(
            companyfacts_json_bytes(curated_public_envelope(spec)),
            curated_public_config(spec),
        )
        reasons = {exclusion.reason for exclusion in result.exclusions}
        assert "taxonomy_not_allowlisted" in reasons
        assert "concept_not_allowlisted" in reasons

    def test_the_document_covers_every_allowlisted_concept(self) -> None:
        spec = CuratedPublicSpec(
            registrant_key="aurora-public",
            entity_name="Aurora Public Registrant Placeholder",
            filing_lag_days=55,
            scale="1.00",
        )
        records = curated_public_records(spec)
        assert {record.concept for record in records} == {
            concept for concept, _unit, _shape in CURATED_PUBLIC_CONCEPTS
        }

    def test_the_envelope_serializer_emits_json_numbers_not_strings(self) -> None:
        # The frozen adapter correctly refuses a quoted financial value, so the
        # canonical (Decimal-as-string) encoder cannot be used here.
        payload = companyfacts_json_bytes(
            {"val": Decimal("1250000.00"), "eps": Decimal("0.91"), "n": 3, "s": "x"}
        )
        # Canonical decimal text, unquoted: trailing zeros normalise away and a
        # real fraction survives, and neither is ever a binary float.
        assert b'"val": 1250000' in payload
        assert b'"eps": 0.91' in payload
        assert b'"n": 3' in payload
        assert b'"s": "x"' in payload

    def test_the_envelope_serializer_refuses_an_unsupported_value(self) -> None:
        with pytest.raises(TypeError, match="unsupported Company Facts value"):
            companyfacts_json_bytes({"val": object()})

    def test_public_registrants_are_disjoint_from_synthetic_issuers(self) -> None:
        public_spec, public_records, _s = unit_bundle(unit_by_role("development", "public"))
        assert public_spec.diversity is not None
        public_entities = {record.entity_id for record in public_records}
        for role in ("broad", "revisions", "stress"):
            _spec, records, _snapshot = unit_bundle(unit_by_role("development", role))
            assert not public_entities & {record.entity_id for record in records}


class TestDeclaredSupportIsHonest:
    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_a_unit_only_claims_profiles_it_actually_supplies(self, unit_id: str) -> None:
        from quantcheck.corpus_eligibility import eligible_unit_count

        spec, records, snapshot = unit_bundle(unit_id)
        for profile in spec.supported_fault_profiles:
            count = eligible_unit_count(
                fault_profile=profile,
                severity="low",
                unit=spec,
                records=records,
                snapshot=snapshot,
            )
            assert count > 0, f"{spec.unit_name} claims {profile} but supplies nothing"

    def test_the_public_source_class_cannot_claim_revision_overwrite(self) -> None:
        # A Company Facts response carries no declared lineage marker, so the
        # source class structurally cannot express a revision history.
        spec = corpus_unit_spec(unit_by_role("development", "public"))
        assert "revision_overwrite" not in spec.supported_fault_profiles
