"""Strictness, immutability, and financial semantics of the public schemas."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

import quantcheck
from quantcheck.schemas import (
    ArtifactIdentity,
    AuditInputRecord,
    AuditInputSnapshot,
    CaseConfig,
    DatasetSnapshot,
    Dimension,
    FinancialFact,
    RuntimeMetadata,
    SourceReference,
)
from tests.support import audit_input_record, financial_fact, source_reference


def test_a_valid_fact_keeps_every_supplied_value() -> None:
    fact = financial_fact()
    assert fact.record_id == "rec_0123456789abcdef"
    assert fact.value == Decimal("1234567.8900")
    assert fact.period_start == date(2024, 1, 1)
    assert fact.source.source_row_key == "row-1"


def test_missing_required_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="value"):
        FinancialFact(  # type: ignore[call-arg]
            record_id="rec_0123456789abcdef",
            entity_id="E",
            concept_namespace="us-gaap",
            concept="Revenues",
            unit="USD",
            period_type="instant",
            period_end=date(2024, 3, 31),
            filed_on=date(2024, 5, 2),
            available_on=date(2024, 5, 2),
            source=source_reference(),
        )


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        financial_fact(is_injected=True)


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "original_value",
        "injected",
        "fault_role",
        "manifest_entry_id",
        "expected_finding_count",
        "output_path",
    ],
)
def test_audit_input_record_refuses_answer_key_fields(forbidden_field: str) -> None:
    """The sanitized boundary must not accept injector-only metadata."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        audit_input_record(**{forbidden_field: "anything"})


def test_audit_input_record_declares_no_answer_key_fields() -> None:
    leaky = {
        "original_value",
        "pre_corruption_value",
        "injected",
        "is_injected",
        "fault_role",
        "role",
        "manifest",
        "manifest_entry_id",
        "target_selected",
        "expected_finding_count",
        "output_path",
        "output_dir",
        "secret",
        "credential",
    }
    assert leaky.isdisjoint(AuditInputRecord.model_fields)
    assert leaky.isdisjoint(AuditInputSnapshot.model_fields)


@pytest.mark.parametrize(
    "record_id",
    ["", "rec_", "rec_0123", "rec_0123456789ABCDEF", "REC_0123456789abcdef", "0123456789abcdef"],
)
def test_malformed_record_id_is_rejected(record_id: str) -> None:
    with pytest.raises(ValidationError):
        financial_fact(record_id=record_id)


@pytest.mark.parametrize(
    "snapshot_id",
    ["snap_0123", "audit_0123456789abcdef", "snap_0123456789ABCDEF", "0123456789abcdef", ""],
)
def test_malformed_snapshot_id_is_rejected(snapshot_id: str) -> None:
    with pytest.raises(ValidationError):
        DatasetSnapshot(
            snapshot_id=snapshot_id,
            dataset_name="demo",
            as_of_date=date(2024, 6, 30),
            records=(),
        )


def test_datetime_is_not_accepted_as_a_financial_date() -> None:
    with pytest.raises(ValidationError, match="day-level date"):
        financial_fact(filed_on=datetime(2024, 5, 2, tzinfo=UTC))


@pytest.mark.parametrize("value", ["2024-13-01", "2024-02-30", "2024-5-2", "not-a-date"])
def test_invalid_date_strings_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        financial_fact(filed_on=value)


def test_duration_period_requires_a_period_start() -> None:
    with pytest.raises(ValidationError, match="requires a period_start"):
        financial_fact(period_type="duration", period_start=None)


def test_instant_period_forbids_a_period_start() -> None:
    with pytest.raises(ValidationError, match="must not have a period_start"):
        financial_fact(period_type="instant", period_start=date(2024, 1, 1))


def test_period_start_after_period_end_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be after period_end"):
        financial_fact(period_start=date(2024, 4, 1), period_end=date(2024, 3, 31))


def test_instant_period_with_no_start_is_valid() -> None:
    fact = financial_fact(period_type="instant", period_start=None)
    assert fact.period_start is None


def test_availability_before_filing_stays_representable() -> None:
    """Look-Ahead injection depends on this; the schema must not forbid it."""
    fact = financial_fact(filed_on=date(2024, 5, 2), available_on=date(2024, 4, 1))
    assert fact.available_on < fact.filed_on


def test_duplicate_dimension_axes_are_rejected() -> None:
    with pytest.raises(ValidationError, match="axes must be unique"):
        financial_fact(
            dimensions=(
                Dimension(axis="Region", member="US"),
                Dimension(axis="Region", member="EU"),
            )
        )


def test_dimensions_are_sorted_by_axis_regardless_of_input_order() -> None:
    forward = financial_fact(
        dimensions=(
            Dimension(axis="Region", member="US"),
            Dimension(axis="Segment", member="Total"),
        )
    )
    reversed_input = financial_fact(
        dimensions=(
            Dimension(axis="Segment", member="Total"),
            Dimension(axis="Region", member="US"),
        )
    )
    assert forward.dimensions == reversed_input.dimensions
    assert [dimension.axis for dimension in forward.dimensions] == ["Region", "Segment"]


def test_supplying_dimensions_as_a_list_does_not_mutate_the_caller_list() -> None:
    caller_owned = [
        Dimension(axis="Segment", member="Total"),
        Dimension(axis="Region", member="US"),
    ]
    financial_fact(dimensions=caller_owned)
    assert [dimension.axis for dimension in caller_owned] == ["Segment", "Region"]


@pytest.mark.parametrize("value", ["1e5", "+1", "01", "1.", "NaN", "Infinity", "", " 1"])
def test_malformed_decimal_strings_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        financial_fact(value=value)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_decimals_are_rejected(value: Decimal) -> None:
    with pytest.raises(ValidationError):
        financial_fact(value=value)


def test_float_is_rejected_as_a_financial_value() -> None:
    with pytest.raises(ValidationError, match="expected Decimal"):
        financial_fact(value=1234567.89)


def test_boolean_is_rejected_as_a_financial_value() -> None:
    with pytest.raises(ValidationError, match="boolean is not a valid financial value"):
        financial_fact(value=True)


def test_boolean_is_rejected_as_a_seed() -> None:
    with pytest.raises(ValidationError, match="boolean is not a valid integer"):
        CaseConfig(
            case_id="case_0123456789abcdef",
            case_name="demo",
            dataset_name="demo",
            as_of_date=date(2024, 6, 30),
            seed=True,
            spec_version="v1",
        )


def test_negative_seed_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not be negative"):
        CaseConfig(
            case_id="case_0123456789abcdef",
            case_name="demo",
            dataset_name="demo",
            as_of_date=date(2024, 6, 30),
            seed=-1,
            spec_version="v1",
        )


def test_integers_are_accepted_as_exact_decimal_values() -> None:
    assert financial_fact(value=1234567).value == Decimal("1234567")


@pytest.mark.parametrize("value", ["", "  ", " leading", "trailing ", "with\nnewline", "tab\there"])
def test_malformed_tokens_are_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        financial_fact(unit=value)


def test_models_are_frozen() -> None:
    fact = financial_fact()
    with pytest.raises(ValidationError):
        fact.value = Decimal("1")


def test_models_are_hashable() -> None:
    assert len({financial_fact(), financial_fact()}) == 1


def test_equality_is_by_logical_value() -> None:
    assert financial_fact() == financial_fact()
    assert financial_fact() != financial_fact(value=Decimal("1"))


def test_declared_decimal_scale_is_not_part_of_identity() -> None:
    """Model equality is numeric, so canonical bytes must be numeric too."""
    assert financial_fact(value=Decimal("1.50")) == financial_fact(value=Decimal("1.5"))
    assert quantcheck.canonical_sha256(financial_fact(value=Decimal("1.50"))) == (
        quantcheck.canonical_sha256(financial_fact(value=Decimal("1.5")))
    )


def test_nested_source_reference_is_validated() -> None:
    with pytest.raises(ValidationError):
        financial_fact(source={"source_name": "", "source_locator": "x", "source_row_key": "y"})


def test_nested_source_reference_accepts_a_mapping() -> None:
    fact = financial_fact(
        source={"source_name": "fx", "source_locator": "l", "source_row_key": "k"}
    )
    assert fact.source == SourceReference(source_name="fx", source_locator="l", source_row_key="k")


def test_snapshot_records_are_sorted_by_record_id() -> None:
    first = financial_fact(record_id="rec_aaaaaaaaaaaaaaaa")
    second = financial_fact(record_id="rec_bbbbbbbbbbbbbbbb")
    forward = DatasetSnapshot(
        snapshot_id="snap_0123456789abcdef",
        dataset_name="demo",
        as_of_date=date(2024, 6, 30),
        records=(first, second),
    )
    backward = DatasetSnapshot(
        snapshot_id="snap_0123456789abcdef",
        dataset_name="demo",
        as_of_date=date(2024, 6, 30),
        records=(second, first),
    )
    assert forward == backward
    assert forward.records[0].record_id == "rec_aaaaaaaaaaaaaaaa"


def test_duplicate_record_ids_in_a_snapshot_are_rejected() -> None:
    fact = financial_fact()
    with pytest.raises(ValidationError, match="must be unique"):
        DatasetSnapshot(
            snapshot_id="snap_0123456789abcdef",
            dataset_name="demo",
            as_of_date=date(2024, 6, 30),
            records=(fact, fact),
        )


def test_snapshot_records_accept_a_list_without_mutating_it() -> None:
    first = financial_fact(record_id="rec_bbbbbbbbbbbbbbbb")
    second = financial_fact(record_id="rec_aaaaaaaaaaaaaaaa")
    caller_owned = [first, second]
    snapshot = DatasetSnapshot.model_validate(
        {
            "snapshot_id": "snap_0123456789abcdef",
            "dataset_name": "demo",
            "as_of_date": date(2024, 6, 30),
            "records": caller_owned,
        }
    )
    assert isinstance(snapshot.records, tuple)
    assert caller_owned == [first, second]


def test_audit_input_snapshot_validates_its_records() -> None:
    snapshot = AuditInputSnapshot(
        audit_input_id="audit_0123456789abcdef",
        dataset_name="demo",
        as_of_date=date(2024, 6, 30),
        records=(audit_input_record(),),
    )
    assert snapshot.records[0].source_name == "reviewed-fixture"


def test_runtime_metadata_requires_an_aware_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        RuntimeMetadata(
            code_version="quantcheck-0.1.0.dev0",
            python_version="3.12.13",
            platform="darwin",
            generated_at=datetime(2026, 8, 6, 12, 0, 0),  # noqa: DTZ001
        )


def test_runtime_metadata_carries_no_path_or_user_fields() -> None:
    leaky = {"output_dir", "output_path", "cwd", "tmpdir", "username", "user", "home"}
    assert leaky.isdisjoint(RuntimeMetadata.model_fields)


def test_case_config_carries_no_runtime_fields() -> None:
    runtime_only = {"generated_at", "platform", "python_version", "code_version", "output_dir"}
    assert runtime_only.isdisjoint(CaseConfig.model_fields)


def test_artifact_identity_requires_a_full_sha256_digest() -> None:
    with pytest.raises(ValidationError, match="content hash"):
        ArtifactIdentity(kind="snapshot", stable_id="snap_0123456789abcdef", content_hash="abc")


@pytest.mark.parametrize(
    "name",
    [
        "FinancialFact",
        "SourceReference",
        "DatasetSnapshot",
        "AuditInputRecord",
        "AuditInputSnapshot",
        "CaseConfig",
        "RuntimeMetadata",
        "ArtifactIdentity",
        "Dimension",
        "CanonicalModel",
        "CanonicalizationError",
        "to_canonical_json",
        "canonical_json_text",
        "canonical_json_bytes",
        "parse_canonical_json",
        "canonical_sha256",
        "sha256_hex_of_bytes",
        "stable_id",
        "source_record_id",
        "dataset_snapshot_id",
        "audit_input_snapshot_id",
        "case_config_id",
        "build_artifact_identity",
    ],
)
def test_public_export_is_available(name: str) -> None:
    assert name in quantcheck.__all__
    assert getattr(quantcheck, name) is not None


def test_importing_quantcheck_pulls_in_no_heavy_dependency() -> None:
    import sys

    # HTTPX is the intentionally introduced Milestone 4 runtime dependency.
    forbidden = {"pandas", "numpy", "streamlit", "pyarrow", "matplotlib", "typer"}
    assert forbidden.isdisjoint(sys.modules)


def test_support_builders_accept_arbitrary_overrides() -> None:
    override: dict[str, Any] = {"unit": "EUR"}
    assert financial_fact(**override).unit == "EUR"
