"""The v0.2 corpus contract and its schema layer.

These tests are about the *rules*: what a source class may claim, what a
licence tier permits, which cells must be accounted for, and which of those
claims the schema layer refuses rather than records.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from quantcheck.corpus_contract import (
    CORPUS_ELIGIBILITY_UNIT_KINDS,
    CORPUS_FAULT_PROFILES,
    CORPUS_INCLUSION_RULES,
    CORPUS_LICENSE_TIERS,
    CORPUS_PARTITIONS,
    CORPUS_SEVERITIES,
    CORPUS_SOURCE_CLASSES,
    CORPUS_SPEC_VERSION,
    CORPUS_UNSUPPORTED_REASON_CODES,
    IN_REPOSITORY_SOURCE_CLASSES,
    MINIMUM_CELL_ELIGIBLE_UNITS,
    MINIMUM_PARTITION_ELIGIBLE_UNITS,
    CorpusContractError,
    corpus_cells,
    inclusion_rule_description,
)
from quantcheck.corpus_schemas import (
    CorpusDiversityProfile,
    CorpusEligibilityCell,
    CorpusEligibilityRollup,
    CorpusHorizon,
    CorpusProvenance,
    CorpusUnitSpec,
)
from quantcheck.serialization import canonical_json_bytes


def _diversity(**overrides: object) -> CorpusDiversityProfile:
    fields: dict[str, object] = {
        "record_count": 100,
        "issuer_count": 5,
        "concept_count": 6,
        "measurement_unit_count": 3,
        "distinct_period_end_count": 12,
        "period_end_signature_count": 4,
        "minimum_filing_lag_days": 7,
        "maximum_filing_lag_days": 90,
        "distinct_filing_lag_count": 5,
        "declared_revision_lineage_count": 4,
        "maximum_relative_revision_size": Decimal("0.25"),
        "delayed_availability_count": 1,
        "dimensioned_record_count": 2,
        "negative_value_count": 1,
        "zero_value_count": 1,
        "hard_negative_count": 3,
    }
    fields.update(overrides)
    return CorpusDiversityProfile.model_validate(fields)


def _provenance(**overrides: object) -> CorpusProvenance:
    fields: dict[str, object] = {
        "source_class": "synthetic_adversarial",
        "license_tier": "synthetic_repository",
        "publisher": "quantcheck",
        "retrieval_method": "in_package_pure_factory",
        "in_repository": True,
        "redistributable": True,
        "verbatim_source": False,
        "notes": "invented",
    }
    fields.update(overrides)
    return CorpusProvenance.model_validate(fields)


def _unit(**overrides: object) -> CorpusUnitSpec:
    fields: dict[str, object] = {
        "corpus_unit_id": "cunit_0123456789abcdef",
        "unit_name": "development-broad",
        "partition": "development",
        "audit_dataset_name": "ccoh_00112233445566aa",
        "source_name": "ccoh_00112233445566aa",
        "source_locator": "quantcheck/corpus/v2/ccoh_00112233445566aa",
        "provenance": _provenance(),
        "horizon": CorpusHorizon(
            snapshot_as_of_date=date(2024, 8, 31),
            research_as_of_date=date(2024, 5, 15),
        ),
        "inclusion_rule_ids": ("IR-01", "IR-02"),
        "supported_fault_profiles": ("duplicate_observation", "unit_drift"),
        "diversity": _diversity(),
        "content_hash": "a" * 64,
    }
    fields.update(overrides)
    return CorpusUnitSpec.model_validate(fields)


class TestContractShape:
    def test_spec_version_is_the_v2_corpus_contract(self) -> None:
        assert CORPUS_SPEC_VERSION == "quantcheck/corpus/v2"

    def test_source_classes_and_license_tiers_are_closed_lists(self) -> None:
        assert CORPUS_SOURCE_CLASSES == (
            "synthetic_adversarial",
            "curated_public",
            "external_private",
        )
        assert CORPUS_LICENSE_TIERS == (
            "synthetic_repository",
            "public_government",
            "external_restricted",
        )

    def test_external_data_may_never_be_committed(self) -> None:
        assert "external_private" not in IN_REPOSITORY_SOURCE_CLASSES

    def test_every_fault_profile_declares_what_one_eligible_unit_is(self) -> None:
        assert set(CORPUS_ELIGIBILITY_UNIT_KINDS) == set(CORPUS_FAULT_PROFILES)

    def test_the_cell_grid_is_every_profile_by_every_severity(self) -> None:
        assert len(corpus_cells()) == len(CORPUS_FAULT_PROFILES) * len(CORPUS_SEVERITIES)
        assert len(corpus_cells()) == 12

    def test_three_partitions_with_a_separate_held_out_one(self) -> None:
        assert CORPUS_PARTITIONS == ("development", "validation", "heldout")

    def test_adequacy_floors_are_declared_numbers_not_derived_ones(self) -> None:
        # Declared in the contract, ahead of any evidence, precisely so they
        # cannot be chosen afterwards to make a cell pass.
        assert MINIMUM_CELL_ELIGIBLE_UNITS == 8
        assert MINIMUM_PARTITION_ELIGIBLE_UNITS == 24

    def test_unsupported_reason_codes_are_a_closed_list(self) -> None:
        assert len(CORPUS_UNSUPPORTED_REASON_CODES) == 3

    def test_every_inclusion_rule_has_documented_text(self) -> None:
        for rule_id in CORPUS_INCLUSION_RULES:
            assert inclusion_rule_description(rule_id).strip()

    def test_an_unknown_inclusion_rule_is_refused(self) -> None:
        with pytest.raises(CorpusContractError, match="IR-99"):
            inclusion_rule_description("IR-99")


class TestProvenanceRules:
    def test_a_curated_public_unit_may_be_committed(self) -> None:
        provenance = _provenance(
            source_class="curated_public",
            license_tier="public_government",
            publisher="sec-edgar-companyfacts",
            verbatim_source=False,
        )
        assert provenance.in_repository is True

    def test_an_external_unit_cannot_claim_to_be_in_the_repository(self) -> None:
        with pytest.raises(ValidationError, match="must not be committed"):
            _provenance(
                source_class="external_private",
                license_tier="external_restricted",
                in_repository=True,
                redistributable=False,
            )

    def test_redistributable_must_follow_the_licence_tier(self) -> None:
        with pytest.raises(ValidationError, match="redistributable must follow"):
            _provenance(license_tier="external_restricted", redistributable=True)

    def test_synthetic_data_cannot_claim_a_verbatim_upstream_source(self) -> None:
        with pytest.raises(ValidationError, match="no verbatim upstream source"):
            _provenance(verbatim_source=True)

    def test_an_external_unit_must_use_the_restricted_tier(self) -> None:
        with pytest.raises(ValidationError, match="must be external_restricted"):
            _provenance(
                source_class="external_private",
                license_tier="synthetic_repository",
                in_repository=False,
                redistributable=True,
            )


class TestUnitSpecRules:
    def test_a_committed_unit_must_publish_its_hash_and_diversity(self) -> None:
        with pytest.raises(ValidationError, match="must publish its content hash"):
            _unit(content_hash=None)

    def test_an_external_unit_must_not_publish_record_derived_content(self) -> None:
        external = _provenance(
            source_class="external_private",
            license_tier="external_restricted",
            in_repository=False,
            redistributable=False,
            verbatim_source=True,
        )
        with pytest.raises(ValidationError, match="must not publish record-derived content"):
            _unit(provenance=external, diversity=_diversity(), content_hash="b" * 64)

    def test_an_external_unit_without_content_validates(self) -> None:
        external = _provenance(
            source_class="external_private",
            license_tier="external_restricted",
            in_repository=False,
            redistributable=False,
            verbatim_source=True,
        )
        unit = _unit(provenance=external, diversity=None, content_hash=None)
        assert unit.diversity is None
        assert unit.content_hash is None

    def test_an_unknown_inclusion_rule_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="unknown corpus inclusion rules"):
            _unit(inclusion_rule_ids=("IR-01", "IR-42"))

    def test_inclusion_rules_and_profiles_are_normalized(self) -> None:
        unit = _unit(
            inclusion_rule_ids=("IR-03", "IR-01"),
            supported_fault_profiles=("unit_drift", "duplicate_observation"),
        )
        assert unit.inclusion_rule_ids == ("IR-01", "IR-03")
        assert unit.supported_fault_profiles == ("duplicate_observation", "unit_drift")

    def test_a_research_cutoff_after_the_snapshot_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="must not follow snapshot"):
            CorpusHorizon(
                snapshot_as_of_date=date(2024, 5, 15),
                research_as_of_date=date(2024, 8, 31),
            )

    def test_a_unit_is_canonically_serializable(self) -> None:
        # The corpus layer must hash and serialize through exactly the same
        # machinery every v0.1 artifact does.
        assert canonical_json_bytes(_unit()).startswith(b"{")


class TestDiversityRules:
    def test_an_inverted_filing_lag_range_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="minimum filing lag"):
            _diversity(minimum_filing_lag_days=90, maximum_filing_lag_days=7)

    def test_a_lineage_free_unit_cannot_report_a_revision_size(self) -> None:
        with pytest.raises(ValidationError, match="cannot report a revision size"):
            _diversity(
                declared_revision_lineage_count=0,
                maximum_relative_revision_size=Decimal("0.25"),
            )


class TestEligibilityCellRules:
    def test_a_cell_must_name_its_own_families_unit_kind(self) -> None:
        with pytest.raises(ValidationError, match="counts"):
            CorpusEligibilityCell(
                partition="development",
                corpus_unit_id="cunit_0123456789abcdef",
                fault_profile="unit_drift",
                severity="low",
                eligibility_unit_kind="revision_history_unit",
                eligible_unit_count=10,
                snapshot_record_count=100,
            )

    def test_a_rollup_cannot_claim_eligibility_below_the_declared_floors(self) -> None:
        with pytest.raises(ValidationError, match="must clear both declared floors"):
            CorpusEligibilityRollup(
                partition="development",
                fault_profile="unit_drift",
                severity="low",
                eligibility_unit_kind="comparable_observation",
                best_unit_id="cunit_0123456789abcdef",
                best_unit_eligible_count=2,
                partition_eligible_total=2,
                supporting_unit_count=1,
                minimum_cell_eligible_units=MINIMUM_CELL_ELIGIBLE_UNITS,
                minimum_partition_eligible_units=MINIMUM_PARTITION_ELIGIBLE_UNITS,
                status="eligible",
            )

    def test_a_rollup_cannot_call_a_qualifying_cell_insufficient(self) -> None:
        with pytest.raises(ValidationError, match="is not insufficient"):
            CorpusEligibilityRollup(
                partition="development",
                fault_profile="unit_drift",
                severity="low",
                eligibility_unit_kind="comparable_observation",
                best_unit_id="cunit_0123456789abcdef",
                best_unit_eligible_count=50,
                partition_eligible_total=90,
                supporting_unit_count=2,
                minimum_cell_eligible_units=MINIMUM_CELL_ELIGIBLE_UNITS,
                minimum_partition_eligible_units=MINIMUM_PARTITION_ELIGIBLE_UNITS,
                status="insufficient",
            )

    def test_the_contract_floors_cannot_be_locally_overridden(self) -> None:
        with pytest.raises(ValidationError, match="declared contract floor"):
            CorpusEligibilityRollup(
                partition="development",
                fault_profile="unit_drift",
                severity="low",
                eligibility_unit_kind="comparable_observation",
                best_unit_id="cunit_0123456789abcdef",
                best_unit_eligible_count=2,
                partition_eligible_total=2,
                supporting_unit_count=1,
                minimum_cell_eligible_units=1,
                minimum_partition_eligible_units=1,
                status="eligible",
            )

    def test_a_nonzero_best_count_requires_the_unit_that_produced_it(self) -> None:
        with pytest.raises(ValidationError, match="requires the unit that produced it"):
            CorpusEligibilityRollup(
                partition="development",
                fault_profile="unit_drift",
                severity="low",
                eligibility_unit_kind="comparable_observation",
                best_unit_id=None,
                best_unit_eligible_count=12,
                partition_eligible_total=12,
                supporting_unit_count=1,
                minimum_cell_eligible_units=MINIMUM_CELL_ELIGIBLE_UNITS,
                minimum_partition_eligible_units=MINIMUM_PARTITION_ELIGIBLE_UNITS,
                status="eligible",
            )
