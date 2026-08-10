"""In-process determinism of the v0.2 corpus.

Cross-process determinism is proved separately in
``test_corpus_determinism_subprocess.py``; these tests cover the properties a
single interpreter can establish — purity, order independence, and the absence
of any clock, filesystem, or randomness dependency in the generators.
"""

from __future__ import annotations

import pytest

from quantcheck.corpus_eligibility import build_census, census_identity_matches
from quantcheck.corpus_public import CuratedPublicSpec, curated_public_records
from quantcheck.corpus_registry import (
    CORPUS_UNIT_ROLES,
    corpus_unit_canonical_bytes,
    corpus_unit_records,
    corpus_unit_spec,
    declared_corpus_id,
    partition_unit_ids,
)
from quantcheck.corpus_synthetic import build_cohort_records
from quantcheck.hashing import canonical_sha256
from quantcheck.serialization import canonical_json_bytes
from tests.corpus_support import ORDINARY_PARTITIONS, ordinary_unit_ids, unit_bundle


class TestGeneratorsArePure:
    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_repeated_materialization_is_byte_identical(self, unit_id: str) -> None:
        first = canonical_json_bytes(corpus_unit_records(unit_id))
        second = corpus_unit_canonical_bytes(unit_id)
        assert first == second

    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_the_declared_content_hash_covers_the_records(self, unit_id: str) -> None:
        spec, records, _snapshot = unit_bundle(unit_id)
        assert spec.content_hash == canonical_sha256(records)

    def test_a_cohort_factory_is_a_pure_function_of_its_specification(self) -> None:
        from quantcheck.corpus_registry import _synthetic_unit_inputs

        cohort, _horizon = _synthetic_unit_inputs("development", "broad")
        assert canonical_json_bytes(build_cohort_records(cohort)) == canonical_json_bytes(
            build_cohort_records(cohort)
        )

    def test_the_curated_public_factory_is_pure(self) -> None:
        spec = CuratedPublicSpec(
            registrant_key="aurora-public",
            entity_name="Aurora Public Registrant Placeholder",
            filing_lag_days=55,
            scale="1.00",
        )
        assert canonical_json_bytes(curated_public_records(spec)) == canonical_json_bytes(
            curated_public_records(spec)
        )

    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_records_are_sorted_by_record_id_regardless_of_generation_order(
        self, unit_id: str
    ) -> None:
        _spec, records, _snapshot = unit_bundle(unit_id)
        assert list(records) == sorted(records, key=lambda record: record.record_id)


class TestIdentitiesAreStable:
    def test_unit_identifiers_are_stable_across_calls(self) -> None:
        for partition in ORDINARY_PARTITIONS:
            assert partition_unit_ids(partition) == partition_unit_ids(partition)

    def test_the_declared_corpus_id_needs_no_records(self) -> None:
        # Available before any unit is materialized, which is what lets a script
        # name the corpus it is about to open the held-out gate for.
        assert declared_corpus_id() == declared_corpus_id()
        assert declared_corpus_id().startswith("corp_")

    def test_unit_identifiers_are_unique_across_the_whole_corpus(self) -> None:
        identifiers = [
            unit_id
            for partition in ("development", "validation", "heldout")
            for unit_id in partition_unit_ids(partition)
        ]
        assert len(set(identifiers)) == len(identifiers)
        assert len(identifiers) == 3 * len(CORPUS_UNIT_ROLES)

    def test_a_unit_specification_is_stable(self) -> None:
        for unit_id in ordinary_unit_ids():
            assert canonical_json_bytes(corpus_unit_spec(unit_id)) == canonical_json_bytes(
                corpus_unit_spec(unit_id)
            )


class TestCensusDeterminism:
    def test_a_census_over_the_same_inputs_is_byte_identical(self) -> None:
        from quantcheck.corpus_gate import held_out_corpus_units
        from quantcheck.corpus_registry import build_corpus_definition, held_out_unit_ids

        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            corpus = build_corpus_definition()
        records = {
            unit_id: corpus_unit_records(unit_id)
            for partition in ORDINARY_PARTITIONS
            for unit_id in partition_unit_ids(partition)
        }
        first = build_census(corpus, records_by_unit=records, partitions=ORDINARY_PARTITIONS)
        second = build_census(corpus, records_by_unit=records, partitions=ORDINARY_PARTITIONS)
        assert first.census_id == second.census_id
        assert canonical_json_bytes(first) == canonical_json_bytes(second)
        assert census_identity_matches(first)

    def test_a_census_identifier_changes_when_a_count_would(self) -> None:
        from quantcheck.corpus_gate import held_out_corpus_units
        from quantcheck.corpus_registry import build_corpus_definition, held_out_unit_ids

        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            corpus = build_corpus_definition()
        records = {
            unit_id: corpus_unit_records(unit_id)
            for partition in ORDINARY_PARTITIONS
            for unit_id in partition_unit_ids(partition)
        }
        full = build_census(corpus, records_by_unit=records, partitions=ORDINARY_PARTITIONS)
        one = build_census(corpus, records_by_unit=records, partitions=("development",))
        assert full.census_id != one.census_id
