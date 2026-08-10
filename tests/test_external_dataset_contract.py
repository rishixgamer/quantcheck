"""Strict versioned dataset-mapping and output contracts."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from quantcheck.external_dataset_contract import (
    AvailabilityEqualsFilingMappingV1,
    CsvInputOptionsV1,
    DatasetMappingV1,
    ExternalDatasetFileInputV1,
    MappedTextConstantV1,
    OptionalDateAbsentMappingV1,
    PeriodTypeConstantMappingV1,
)
from quantcheck.external_dataset_ingestion import dataset_mapping_id
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import mapping, policy


def test_mapping_contract_is_strict_frozen_and_versioned() -> None:
    contract = mapping()
    assert contract.spec_version == "quantcheck/dataset-mapping/v1"
    assert contract.model_config["frozen"] is True
    assert contract.model_config["extra"] == "forbid"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DatasetMappingV1.model_validate({**contract.model_dump(), "guess_units": True})


def test_mapping_requires_every_semantic_field() -> None:
    document = mapping().model_dump(mode="python")
    document.pop("available_on")
    with pytest.raises(ValidationError, match="available_on"):
        DatasetMappingV1.model_validate(document)


def test_mapping_identity_covers_availability_evidence() -> None:
    first = mapping()
    document = first.model_dump(mode="python")
    document["available_on"]["evidence_reference"] = "different-source-contract"
    second = DatasetMappingV1.model_validate(document)
    assert dataset_mapping_id(first) != dataset_mapping_id(second)


def test_same_as_filing_requires_an_explicit_source_contract_basis() -> None:
    availability = AvailabilityEqualsFilingMappingV1(evidence_reference="vendor-contract-page-12")
    assert availability.basis == ("source_contract_confirms_filing_date_equals_availability_date")
    with pytest.raises(ValidationError):
        AvailabilityEqualsFilingMappingV1.model_validate(
            {
                "kind": "same_as_filing",
                "basis": "we-assume-it",
                "evidence_reference": "none",
            }
        )


def test_instant_only_mapping_must_explicitly_omit_period_start() -> None:
    document = mapping().model_dump(mode="python")
    document["period_type"] = {"kind": "constant", "value": "instant"}
    with pytest.raises(ValidationError, match="period_start absent"):
        DatasetMappingV1.model_validate(document)
    document["period_start"] = {
        "kind": "absent",
        "reason": "instant facts have no start date",
    }
    contract = DatasetMappingV1.model_validate(document)
    assert isinstance(contract.period_type, PeriodTypeConstantMappingV1)
    assert isinstance(contract.period_start, OptionalDateAbsentMappingV1)


def test_duration_only_mapping_cannot_omit_period_start() -> None:
    document = mapping().model_dump(mode="python")
    document["period_type"] = {"kind": "constant", "value": "duration"}
    document["period_start"] = {
        "kind": "absent",
        "reason": "upstream omitted it",
    }
    with pytest.raises(ValidationError, match="must map period_start"):
        DatasetMappingV1.model_validate(document)


def test_period_type_labels_must_be_distinct() -> None:
    document = mapping().model_dump(mode="python")
    document["period_type"]["duration_value"] = "I"
    with pytest.raises(ValidationError, match="must be distinct"):
        DatasetMappingV1.model_validate(document)


def test_revision_columns_must_be_distinct() -> None:
    document = mapping().model_dump(mode="python")
    document["revision_lineage"]["sequence_column"] = "revision_lineage"
    with pytest.raises(ValidationError, match="distinct columns"):
        DatasetMappingV1.model_validate(document)


def test_empty_dimensions_is_an_explicit_dimension_free_contract() -> None:
    assert mapping().dimensions == ()


def test_public_provenance_visibility_cannot_be_weakened() -> None:
    document = mapping().model_dump(mode="python")
    document["source_provenance_visibility"] = "private"
    with pytest.raises(ValidationError):
        DatasetMappingV1.model_validate(document)


def test_csv_syntax_and_nulls_are_explicit() -> None:
    options = CsvInputOptionsV1(null_tokens=("NULL", ""))
    assert options.null_tokens == ("", "NULL")
    with pytest.raises(ValidationError, match="must differ"):
        CsvInputOptionsV1(delimiter="|", quote_character="|")


def test_csv_file_input_requires_csv_options() -> None:
    with pytest.raises(ValidationError, match="requires explicit csv options"):
        ExternalDatasetFileInputV1(input_format="csv")
    with pytest.raises(ValidationError, match="only valid for CSV"):
        ExternalDatasetFileInputV1(input_format="parquet", csv=CsvInputOptionsV1())


def test_policy_selection_is_a_required_explicit_audit_input() -> None:
    selected = policy(enabled_detectors=("lookahead_timestamp",))
    enabled = tuple(rule.detector for rule in selected.detector_rules if rule.enabled)
    assert enabled == ("lookahead_timestamp",)


def test_mapping_canonical_bytes_do_not_depend_on_constructor_mapping_order() -> None:
    first = mapping()
    reversed_document = dict(reversed(list(first.model_dump(mode="python").items())))
    second = DatasetMappingV1.model_validate(reversed_document)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert dataset_mapping_id(first) == dataset_mapping_id(second)


def test_constants_still_require_canonical_tokens() -> None:
    with pytest.raises(ValidationError, match="surrounding whitespace"):
        MappedTextConstantV1(value=" USD ")


def test_mapping_dates_are_day_level_only() -> None:
    assert date(2024, 1, 1).isoformat() == "2024-01-01"
