"""CSV, Parquet, Arrow IPC, and Python interoperability without float coercion."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import cast

import pyarrow as pa
import pyarrow.parquet as parquet
import pytest

from quantcheck.external_dataset_contract import DatasetMappingV1, ExternalDatasetFileInputV1
from quantcheck.external_dataset_ingestion import (
    ExternalDatasetValidationError,
    load_external_file,
    normalize_external_file,
    normalize_external_rows,
    normalized_dataset_identity_matches,
    profile_external_file,
)
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import (
    COLUMNS,
    explicit_revision_rows,
    independent_mapping,
    mapping,
    pinned_file_input,
    reviewed_rows,
    row,
    write_arrow,
    write_csv,
)


@pytest.mark.parametrize("input_format", ["parquet", "arrow_file", "arrow_stream"])
def test_arrow_container_formats_normalize_exact_decimal_values(
    tmp_path: Path,
    input_format: str,
) -> None:
    path = tmp_path / f"facts.{input_format}"
    write_arrow(path, reviewed_rows(), input_format)
    dataset = normalize_external_file(path, mapping(), pinned_file_input(path, input_format))
    assert normalized_dataset_identity_matches(dataset)
    assert set(item.value for item in dataset.records) == {
        Decimal("100.25"),
        Decimal("120"),
        Decimal("130"),
    }


def test_csv_and_parquet_produce_byte_identical_normalized_output(tmp_path: Path) -> None:
    rows = reviewed_rows() + explicit_revision_rows()
    csv_path = tmp_path / "facts.csv"
    parquet_path = tmp_path / "facts.parquet"
    write_csv(csv_path, rows)
    write_arrow(parquet_path, rows, "parquet")
    csv_dataset = normalize_external_file(
        csv_path,
        mapping(),
        pinned_file_input(csv_path, "csv"),
    )
    parquet_dataset = normalize_external_file(
        parquet_path,
        mapping(),
        pinned_file_input(parquet_path, "parquet"),
    )
    assert canonical_json_bytes(csv_dataset) == canonical_json_bytes(parquet_dataset)


def test_python_rows_produce_the_same_output_and_are_not_mutated(tmp_path: Path) -> None:
    rows = reviewed_rows()
    before = deepcopy(rows)
    python_dataset = normalize_external_rows(rows, mapping())
    csv_path = tmp_path / "facts.csv"
    write_csv(csv_path, rows)
    csv_dataset = normalize_external_file(
        csv_path,
        mapping(),
        pinned_file_input(csv_path, "csv"),
    )
    assert rows == before
    assert canonical_json_bytes(python_dataset) == canonical_json_bytes(csv_dataset)


def test_python_float_is_rejected_without_round_trip() -> None:
    rows = [row("private-row-secret", amount=0.1)]
    with pytest.raises(ExternalDatasetValidationError) as caught:
        normalize_external_rows(rows, mapping())
    diagnostic = caught.value.profile.diagnostics[0]
    assert diagnostic.code == "normalization.invalid_decimal"
    assert "0.1" not in canonical_json_bytes(caught.value.profile).decode()


def test_canonical_decimal_text_is_accepted_but_exponent_text_is_rejected() -> None:
    accepted = normalize_external_rows([row("row-fixed", amount="100.250")], mapping())
    assert accepted.records[0].value == Decimal("100.250")
    with pytest.raises(ExternalDatasetValidationError) as caught:
        normalize_external_rows([row("row-exponent", amount="1e3")], mapping())
    assert caught.value.profile.diagnostics[0].code == "normalization.invalid_decimal"


def test_arrow_float_value_schema_is_rejected_before_row_normalization(tmp_path: Path) -> None:
    supplied = reviewed_rows()
    schema = pa.schema(
        [
            pa.field(column, pa.float64() if column == "amount" else pa.string())
            for column in COLUMNS
        ]
    )
    converted = [
        {
            key: (
                float(cast(Decimal, value))
                if key == "amount"
                else None
                if value is None
                else str(value)
            )
            for key, value in item.items()
        }
        for item in supplied
    ]
    table = pa.Table.from_pylist(converted, schema=schema)
    path = tmp_path / "float.parquet"
    parquet.write_table(table, path)  # type: ignore[no-untyped-call]
    profile = profile_external_file(
        path,
        mapping(),
        pinned_file_input(path, "parquet"),
    )
    assert profile.valid is False
    assert profile.diagnostics[0].code == "schema.float_value_column"


def test_independent_mapping_uses_source_identity_without_accidental_revision_inference() -> None:
    supplied = row("upstream-key#r9")
    supplied.pop("entity_name")
    supplied.pop("revision_lineage")
    supplied.pop("revision_sequence")
    dataset = normalize_external_rows([supplied], independent_mapping())
    fact = dataset.records[0]
    assert "#r" not in fact.source.source_row_key
    assert dataset.provenance[0].source_row_id == "upstream-key#r9"


def test_raw_source_row_id_is_preserved_privately_but_hashed_in_canonical_source_key() -> None:
    dataset = normalize_external_rows(explicit_revision_rows(), mapping())
    private_ids = {item.source_row_id for item in dataset.provenance}
    assert private_ids == {"revision-source-a", "revision-source-b"}
    assert all(item.source.source_row_key.startswith("xline_") for item in dataset.records)
    assert all("revision-source" not in item.source.source_row_key for item in dataset.records)


def test_source_row_order_never_changes_normalized_bytes() -> None:
    rows = reviewed_rows() + explicit_revision_rows()
    forward = normalize_external_rows(rows, mapping())
    reverse = normalize_external_rows(list(reversed(rows)), mapping())
    assert canonical_json_bytes(forward) == canonical_json_bytes(reverse)


def test_explicit_dimension_axis_and_member_column_are_preserved() -> None:
    document = mapping().model_dump(mode="python")
    document["dimensions"] = [{"axis": "ProductAxis", "member_column": "product_member"}]
    dimension_mapping = DatasetMappingV1.model_validate(document)
    supplied = row("dimension-row")
    supplied["product_member"] = "CloudMember"
    dataset = normalize_external_rows([supplied], dimension_mapping)
    assert tuple(
        (dimension.axis, dimension.member) for dimension in dataset.records[0].dimensions
    ) == (("ProductAxis", "CloudMember"),)


def test_missing_mapped_dimension_member_is_rejected() -> None:
    document = mapping().model_dump(mode="python")
    document["dimensions"] = [{"axis": "ProductAxis", "member_column": "product_member"}]
    dimension_mapping = DatasetMappingV1.model_validate(document)
    with pytest.raises(ExternalDatasetValidationError) as caught:
        normalize_external_rows([row("dimension-row")], dimension_mapping)
    assert caught.value.profile.diagnostics[0].code == "schema.missing_column"


def test_evidenced_same_as_filing_rule_is_applied_without_source_date_guessing() -> None:
    document = mapping().model_dump(mode="python")
    document["available_on"] = {
        "kind": "same_as_filing",
        "basis": "source_contract_confirms_filing_date_equals_availability_date",
        "evidence_reference": "vendor-contract-page-12",
    }
    equality_mapping = DatasetMappingV1.model_validate(document)
    supplied = row("same-as-filing", filed_date="2024-04-30")
    supplied.pop("available_date")
    dataset = normalize_external_rows([supplied], equality_mapping)
    assert dataset.records[0].available_on == dataset.records[0].filed_on


def test_file_profile_reports_integrity_metadata_without_audit_claim(tmp_path: Path) -> None:
    path = tmp_path / "facts.csv"
    write_csv(path, reviewed_rows())
    profile, dataset = load_external_file(path, mapping(), pinned_file_input(path, "csv"))
    assert profile.valid is True
    assert profile.source_sha256 is not None
    assert profile.source_size_bytes == path.stat().st_size
    assert profile.audit_claim is profile.benchmark_claim is False
    assert dataset.record_count == 3


def test_file_format_is_explicit_and_never_inferred_from_extension(tmp_path: Path) -> None:
    path = tmp_path / "looks-like-parquet.parquet"
    write_csv(path, reviewed_rows())
    declared = ExternalDatasetFileInputV1(
        input_format="parquet",
        expected_sha256=pinned_file_input(path, "csv").expected_sha256,
    )
    profile = profile_external_file(path, mapping(), declared)
    assert profile.valid is False
    assert profile.diagnostics[0].code == "input.malformed"
