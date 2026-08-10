"""Proof that corpus partition identity cannot reach a detector.

A corpus that splits into development, validation, and held-out partitions
introduces a failure mode v0.1 did not have: the split itself becoming a
feature. These tests close every route it could take.

1. **Vocabulary.** Every detector-visible string *value* is either present in
   every partition — shared taxonomy vocabulary such as ``us-gaap``,
   ``Revenues``, ``USD``, ``10-Q``, which by construction distinguishes nothing
   — or present in exactly one and hash-opaque, such as an entity id or a
   cohort code. A value present in some partitions but not all would be the
   leak signal.

   This is deliberately not a substring search for the word "development": the
   real ``us-gaap`` concept ``ResearchAndDevelopmentExpense`` contains it, is
   present identically in all three partitions, and therefore carries no
   partition information whatsoever. Renaming a real taxonomy concept to make a
   naive test pass would be tuning the data to the test.
2. **Opacity.** The partition-specific values carry no partition token, because
   they are SHA-256 derived rather than allocated in a readable order.
3. **Structure.** The sanitized audit boundary has no field that could carry a
   partition, unit, or corpus identifier, and the detector entry point takes no
   such parameter.
4. **Identity.** Issuers, records, and source locators are disjoint across
   partitions, so a detector cannot recognise a partition by having seen a
   record from it before.
5. **Imports.** No detector module imports the corpus layer, so a detector has
   no way to ask which partition it is looking at.
6. **Construction.** The registry refuses to build a unit whose detector-visible
   naming carries a partition token, so the property cannot be lost in a rename.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

import quantcheck
from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.corpus_contract import CORPUS_PARTITIONS, PARTITION_LEAKAGE_TOKENS
from quantcheck.corpus_registry import (
    CORPUS_UNIT_ROLES,
    CorpusRegistryError,
    check_detector_visible_naming,
    partition_unit_ids,
)
from quantcheck.schemas import AuditInputRecord
from quantcheck.sec_adapter import SEC_SOURCE_NAME
from quantcheck.serialization import canonical_json_bytes
from tests.corpus_support import ORDINARY_PARTITIONS, ordinary_unit_ids, unit_bundle

#: Detector modules that must stay ignorant of the corpus layer.
_DETECTOR_MODULES = (
    "lookahead_detection",
    "unit_drift_detection",
    "duplicate_detection",
    "revision_overwrite_detection",
    "audit_boundary",
    "duplicate_fingerprint",
    "unit_drift_series",
    "revision_overwrite_series",
)


#: The string-valued fields of the sanitized audit record, by name.
_STRING_FIELDS = (
    "record_id",
    "entity_id",
    "concept_namespace",
    "concept",
    "unit",
    "form",
    "accession_number",
    "source_name",
    "source_locator",
)

#: Fields whose vocabulary is shared taxonomy and must be *identical* across
#: partitions, and fields whose values identify a source and must be *disjoint*.
_SHARED_VOCABULARY_FIELDS = ("concept_namespace", "concept", "unit", "form")
#: ``source_name`` is deliberately absent: every curated public unit carries
#: the frozen adapter's own ``sec-companyfacts`` source name, which is shared by
#: all three partitions and therefore distinguishes none of them. It is covered
#: by the per-value rule and by its own test below instead.
_DISJOINT_IDENTITY_FIELDS = (
    "record_id",
    "entity_id",
    "accession_number",
    "source_locator",
)

_OPACITY_FIELDS = (*_DISJOINT_IDENTITY_FIELDS, "source_name")


#: A value that identifies a source rather than naming taxonomy. Every such
#: value is derived from a SHA-256 digest: a record id, a hash-derived CIK, an
#: accession built on that CIK, an opaque cohort code, or a corpus locator or
#: Company Facts URL built on one of those. None of them can be decoded back
#: into a partition.
_OPAQUE_VALUE = re.compile(
    r"^(?:"
    r"rec_[0-9a-f]{16}"
    r"|CIK[0-9]{10}"
    r"|[0-9]{10}-[0-9]{2}-[0-9]{6}"
    r"|ccoh_[0-9a-f]{16}"
    r"|quantcheck/corpus/v2/ccoh_[0-9a-f]{16}"
    r"|https://data\.sec\.gov/api/xbrl/companyfacts/CIK[0-9]{10}\.json"
    r")$"
)


def _field_values(partition: str, field: str) -> set[str]:
    values: set[str] = set()
    for unit_id in partition_unit_ids(partition):
        _spec, _records, snapshot = unit_bundle(unit_id)
        for record in sanitize_for_audit(snapshot).records:
            value = getattr(record, field)
            if value is not None:
                values.add(str(value))
    return values


def _dimension_values(partition: str) -> set[str]:
    values: set[str] = set()
    for unit_id in partition_unit_ids(partition):
        _spec, _records, snapshot = unit_bundle(unit_id)
        for record in sanitize_for_audit(snapshot).records:
            values.update(f"{d.axis}={d.member}" for d in record.dimensions)
    return values


class TestVocabularyCannotDistinguishPartitions:
    @pytest.mark.parametrize("field", _SHARED_VOCABULARY_FIELDS)
    def test_shared_taxonomy_vocabulary_is_identical_across_partitions(self, field: str) -> None:
        development = _field_values("development", field)
        validation = _field_values("validation", field)
        assert development
        assert development == validation, (
            f"field {field!r} differs between partitions: {sorted(development ^ validation)}"
        )

    def test_dimension_vocabulary_is_identical_across_partitions(self) -> None:
        assert _dimension_values("development") == _dimension_values("validation")

    @pytest.mark.parametrize("field", _DISJOINT_IDENTITY_FIELDS)
    def test_identity_vocabulary_is_fully_disjoint_across_partitions(self, field: str) -> None:
        development = _field_values("development", field)
        validation = _field_values("validation", field)
        assert development
        assert not development & validation, (
            f"field {field!r} shares {len(development & validation)} values between partitions"
        )

    def test_the_only_shared_source_name_is_the_frozen_sec_adapters(self) -> None:
        shared = _field_values("development", "source_name") & _field_values(
            "validation", "source_name"
        )
        assert shared == {SEC_SOURCE_NAME}

    @pytest.mark.parametrize("field", _STRING_FIELDS)
    def test_every_value_is_either_shared_or_opaque_to_one_partition(self, field: str) -> None:
        """The precise anti-leak property, stated per value rather than per field.

        A value present in every partition distinguishes nothing. A value
        present in exactly one partition does distinguish it — unavoidably, for
        entity ids and cohort codes — and is therefore required to be
        hash-opaque, so the partition it belongs to cannot be read off it.
        """
        development = _field_values("development", field)
        validation = _field_values("validation", field)
        for value in development ^ validation:
            assert _OPAQUE_VALUE.fullmatch(value), (
                f"field {field!r} value {value!r} belongs to one partition but is not opaque"
            )


class TestPartitionSpecificValuesAreOpaque:
    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_disjoint_identity_values_carry_no_partition_token(self, unit_id: str) -> None:
        _spec, _records, snapshot = unit_bundle(unit_id)
        for record in sanitize_for_audit(snapshot).records:
            for field in _OPACITY_FIELDS:
                value = getattr(record, field)
                if value is None:
                    continue
                lowered = str(value).lower()
                for token in PARTITION_LEAKAGE_TOKENS:
                    assert token not in lowered, f"{value!r} carries partition token {token!r}"

    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_the_dataset_name_is_the_opaque_cohort_code(self, unit_id: str) -> None:
        spec, _records, snapshot = unit_bundle(unit_id)
        # The unit's own metadata name does say which partition it is in; the
        # dataset name that crosses the boundary must not.
        assert spec.partition in spec.unit_name
        assert spec.partition not in spec.audit_dataset_name
        assert sanitize_for_audit(snapshot).dataset_name == spec.audit_dataset_name

    @pytest.mark.parametrize("unit_id", ordinary_unit_ids())
    def test_the_unit_name_never_reaches_the_audit_bytes(self, unit_id: str) -> None:
        spec, _records, snapshot = unit_bundle(unit_id)
        payload = canonical_json_bytes(sanitize_for_audit(snapshot)).decode()
        assert spec.unit_name not in payload
        assert spec.corpus_unit_id not in payload


class TestTheAuditBoundaryHasNowhereToPutIt:
    def test_audit_input_record_declares_no_corpus_field(self) -> None:
        forbidden = {"partition", "corpus", "corpus_unit_id", "unit_name", "seed_class"}
        assert not forbidden & set(AuditInputRecord.model_fields)

    def test_sanitization_drops_the_source_row_key(self) -> None:
        # The row key is where a revision-lineage marker lives, and it is also
        # where a careless corpus could have stamped a partition.
        assert "source_row_key" not in AuditInputRecord.model_fields

    def test_the_detector_entry_point_has_no_corpus_channel(self) -> None:
        signature = inspect.signature(quantcheck.run_all_detectors)
        for name in signature.parameters:
            assert "corpus" not in name
            assert "partition" not in name


class TestPartitionsShareNoIdentity:
    def test_issuers_are_disjoint_across_partitions(self) -> None:
        seen: dict[str, str] = {}
        for partition in ORDINARY_PARTITIONS:
            for unit_id in partition_unit_ids(partition):
                _spec, records, _snapshot = unit_bundle(unit_id)
                for record in records:
                    previous = seen.setdefault(record.entity_id, partition)
                    assert previous == partition, (
                        f"entity {record.entity_id} appears in {previous} and {partition}"
                    )

    def test_record_ids_are_disjoint_across_partitions(self) -> None:
        seen: dict[str, str] = {}
        for partition in ORDINARY_PARTITIONS:
            for unit_id in partition_unit_ids(partition):
                _spec, records, _snapshot = unit_bundle(unit_id)
                for record in records:
                    previous = seen.setdefault(record.record_id, partition)
                    assert previous == partition

    def test_source_locators_are_disjoint_across_partitions(self) -> None:
        by_partition = {
            partition: {
                unit_bundle(unit_id)[0].source_locator for unit_id in partition_unit_ids(partition)
            }
            for partition in ORDINARY_PARTITIONS
        }
        assert not by_partition["development"] & by_partition["validation"]

    def test_every_partition_offers_the_same_roles(self) -> None:
        # Structural symmetry is what makes a held-out result comparable with a
        # development one: the partitions differ in issuers, never in shape.
        for partition in CORPUS_PARTITIONS:
            assert len(partition_unit_ids(partition)) == len(CORPUS_UNIT_ROLES)


class TestDetectorsCannotReachTheCorpusLayer:
    @pytest.mark.parametrize("module_name", _DETECTOR_MODULES)
    def test_no_detector_module_imports_the_corpus_layer(self, module_name: str) -> None:
        source = Path(quantcheck.__file__).parent / f"{module_name}.py"
        text = source.read_text()
        assert "corpus" not in text, f"{module_name} mentions the corpus layer"


class TestTheNamingRuleIsEnforcedNotReviewed:
    @pytest.mark.parametrize(
        "name",
        [
            "development-broad",
            "heldout_cohort",
            "quantcheck/corpus/v2/holdout",
            "TRAIN-cohort",
            "validation",
        ],
    )
    def test_a_partition_bearing_detector_visible_name_is_refused(self, name: str) -> None:
        with pytest.raises(CorpusRegistryError, match="partition token"):
            check_detector_visible_naming(name)

    def test_an_opaque_cohort_code_is_accepted(self) -> None:
        check_detector_visible_naming(
            "ccoh_0123456789abcdef", "quantcheck/corpus/v2/ccoh_0123456789abcdef"
        )

    def test_a_hex_cohort_code_cannot_spell_a_partition_token(self) -> None:
        # Structural, not lucky: every leakage token contains at least one
        # character outside the hexadecimal alphabet, so no derived code can
        # ever contain one.
        hexadecimal = set("0123456789abcdef")
        for token in PARTITION_LEAKAGE_TOKENS:
            assert not set(token) <= hexadecimal, f"{token!r} is spellable in hex"
