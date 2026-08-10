"""Ambiguity rejection, dry-run diagnostics, and privacy behavior."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from quantcheck.external_dataset_contract import DatasetMappingV1
from quantcheck.external_dataset_ingestion import (
    ExternalDatasetValidationError,
    normalize_external_rows,
    profile_external_rows,
    validation_profile_identity_matches,
)
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import explicit_revision_rows, mapping, row


def _diagnostic_codes(profile: object) -> set[str]:
    return {item.code for item in profile.diagnostics}  # type: ignore[attr-defined]


def test_dry_run_validates_without_making_audit_or_benchmark_claims() -> None:
    profile = profile_external_rows([row("source-row-1")], mapping())
    assert profile.valid is True
    assert profile.audit_claim is False
    assert profile.benchmark_claim is False
    assert profile.network_used is False
    assert profile.manifest_used is False
    assert validation_profile_identity_matches(profile)


def test_dry_run_returns_machine_readable_errors_instead_of_raising() -> None:
    supplied = row("source-row-1")
    supplied.pop("available_date")
    profile = profile_external_rows([supplied], mapping())
    assert profile.valid is False
    assert profile.error_count == 1
    assert profile.diagnostics[0].code == "schema.missing_column"
    assert profile.diagnostics[0].field == "available_date"


def test_normalization_raises_only_a_fixed_data_free_message() -> None:
    secret = "CUSTOMER_SECRET_VALUE_918273"
    with pytest.raises(ExternalDatasetValidationError) as caught:
        normalize_external_rows([row(secret, amount=secret)], mapping())
    assert str(caught.value) == "external dataset validation failed"
    serialized = canonical_json_bytes(caught.value.profile).decode()
    assert secret not in serialized
    assert "amount" not in caught.value.profile.diagnostics[0].message


def test_diagnostic_cap_is_deterministic_and_counts_omitted_errors() -> None:
    supplied = [row(f"row-{index}", amount="not-a-decimal") for index in range(10)]
    profile = profile_external_rows(supplied, mapping(), max_diagnostics=3)
    assert profile.error_count == 10
    assert len(profile.diagnostics) == 3
    assert profile.omitted_diagnostic_count == 7


def test_missing_and_unmapped_columns_are_rejected_under_strict_policy() -> None:
    supplied = row("row-1")
    supplied.pop("unit")
    supplied["vendor_internal_score"] = "secret"
    profile = profile_external_rows([supplied], mapping())
    assert _diagnostic_codes(profile) == {
        "schema.missing_column",
        "schema.unmapped_column",
    }


def test_unmapped_columns_may_be_allowed_only_by_explicit_mapping_policy() -> None:
    document = mapping().model_dump(mode="python")
    document["unmapped_columns"] = "allow"
    permissive = DatasetMappingV1.model_validate(document)
    supplied = row("row-1")
    supplied["ignored_by_explicit_policy"] = "not-normalized"
    dataset = normalize_external_rows([supplied], permissive)
    assert dataset.record_count == 1
    assert "not-normalized" not in canonical_json_bytes(dataset).decode()


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("amount", 12.5, "normalization.invalid_decimal"),
        ("amount", True, "normalization.invalid_decimal"),
        ("period_end", "2024-02-30", "normalization.invalid_date"),
        ("period_end", datetime(2024, 3, 31, tzinfo=UTC), "normalization.invalid_date"),
        ("period_kind", "quarterly", "normalization.invalid_period_type"),
        ("available_date", None, "normalization.missing_value"),
    ],
)
def test_malformed_financial_semantics_are_rejected(
    field: str,
    value: object,
    code: str,
) -> None:
    supplied = row("row-1")
    supplied[field] = value
    profile = profile_external_rows([supplied], mapping())
    assert code in _diagnostic_codes(profile)


def test_source_locator_cannot_be_a_local_path() -> None:
    document = mapping().model_dump(mode="python")
    document["source_locator"] = {"kind": "constant", "value": "/private/customer.csv"}
    local_mapping = DatasetMappingV1.model_validate(document)
    profile = profile_external_rows([row("row-1")], local_mapping)
    assert profile.diagnostics[0].code == "normalization.invalid_source_locator"
    assert "/private/customer.csv" not in canonical_json_bytes(profile).decode()


def test_duplicate_source_row_identity_is_rejected_not_ordinalized() -> None:
    profile = profile_external_rows([row("same"), row("same")], mapping())
    assert "normalization.duplicate_source_identity" in _diagnostic_codes(profile)
    assert profile.valid_record_count == 1


def test_revision_lineage_must_supply_both_lineage_and_sequence() -> None:
    supplied = row("row-1", revision_lineage="history", revision_sequence=None)
    profile = profile_external_rows([supplied], mapping())
    assert "normalization.invalid_revision" in _diagnostic_codes(profile)


def test_revision_sequence_must_be_positive_and_canonical() -> None:
    for sequence in (0, -1, "01", 1.0, True):
        supplied = row("row-1", revision_lineage="history", revision_sequence=sequence)
        profile = profile_external_rows([supplied], mapping())
        assert "normalization.invalid_revision" in _diagnostic_codes(profile)


def test_duplicate_revision_sequence_is_rejected_as_ambiguous() -> None:
    supplied = explicit_revision_rows()
    supplied[1]["revision_sequence"] = 1
    profile = profile_external_rows(supplied, mapping())
    assert "revision.ambiguous_history" in _diagnostic_codes(profile)


def test_revision_economic_identity_mismatch_is_rejected_as_ambiguous() -> None:
    supplied = explicit_revision_rows()
    supplied[1]["concept"] = "Assets"
    profile = profile_external_rows(supplied, mapping())
    assert "revision.ambiguous_history" in _diagnostic_codes(profile)


def test_nonmonotonic_revision_availability_is_rejected_as_ambiguous() -> None:
    supplied = explicit_revision_rows()
    supplied[1]["available_date"] = "2024-01-01"
    profile = profile_external_rows(supplied, mapping())
    assert "revision.ambiguous_history" in _diagnostic_codes(profile)


def test_explicit_independent_rows_are_never_grouped_by_business_key() -> None:
    document = mapping().model_dump(mode="python")
    document["revision_lineage"] = {
        "kind": "independent",
        "declaration": "source_does_not_provide_revision_lineage",
    }
    independent = DatasetMappingV1.model_validate(document)
    supplied = [row("row-a", amount=Decimal("100")), row("row-b", amount=Decimal("101"))]
    for item in supplied:
        item.pop("revision_lineage")
        item.pop("revision_sequence")
    dataset = normalize_external_rows(supplied, independent)
    assert dataset.record_count == 2


def test_python_inputs_are_never_modified_even_when_validation_fails() -> None:
    supplied = [row("row-1", amount="malformed")]
    before = deepcopy(supplied)
    profile_external_rows(supplied, mapping())
    assert supplied == before
