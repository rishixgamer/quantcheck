"""model -> canonical value -> canonical bytes -> parsed JSON -> model.

Every hop must preserve the logical information the contract promises.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from quantcheck.schemas import (
    ArtifactIdentity,
    AuditInputSnapshot,
    CanonicalModel,
    CaseConfig,
    DatasetSnapshot,
    RuntimeMetadata,
)
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json
from tests.support import audit_input_record, financial_fact


def _round_trip[ModelT: CanonicalModel](model: ModelT) -> ModelT:
    parsed = parse_canonical_json(canonical_json_bytes(model))
    assert isinstance(parsed, dict)
    return type(model).model_validate(parsed)


def test_financial_fact_round_trips() -> None:
    original = financial_fact()
    assert _round_trip(original) == original


def test_instant_fact_round_trips_with_a_null_period_start() -> None:
    original = financial_fact(period_type="instant", period_start=None)
    restored = _round_trip(original)
    assert restored == original
    assert restored.period_start is None


def test_fact_with_no_dimensions_round_trips() -> None:
    original = financial_fact(dimensions=())
    assert _round_trip(original) == original


def test_fact_with_unicode_round_trips() -> None:
    original = financial_fact(entity_name="Société Générale 日本語")
    assert _round_trip(original).entity_name == "Société Générale 日本語"


def test_look_ahead_shaped_fact_round_trips() -> None:
    original = financial_fact(filed_on=date(2024, 5, 2), available_on=date(2024, 4, 1))
    restored = _round_trip(original)
    assert restored == original
    assert restored.available_on < restored.filed_on


def test_decimal_value_survives_exactly() -> None:
    for text in ("0", "-0.000001", "1234567.89", "1E+30", "-1E-30"):
        original = financial_fact(value=Decimal(text))
        assert _round_trip(original).value == Decimal(text)


def test_round_trip_is_idempotent_in_bytes() -> None:
    original = financial_fact()
    once = _round_trip(original)
    assert canonical_json_bytes(once) == canonical_json_bytes(original)
    assert canonical_json_bytes(_round_trip(once)) == canonical_json_bytes(original)


def test_dataset_snapshot_round_trips() -> None:
    original = DatasetSnapshot(
        snapshot_id="snap_0123456789abcdef",
        dataset_name="reviewed-demo",
        as_of_date=date(2024, 6, 30),
        records=(
            financial_fact(record_id="rec_bbbbbbbbbbbbbbbb"),
            financial_fact(
                record_id="rec_aaaaaaaaaaaaaaaa", period_type="instant", period_start=None
            ),
        ),
    )
    restored = _round_trip(original)
    assert restored == original
    assert [record.record_id for record in restored.records] == [
        "rec_aaaaaaaaaaaaaaaa",
        "rec_bbbbbbbbbbbbbbbb",
    ]


def test_empty_snapshot_round_trips() -> None:
    original = DatasetSnapshot(
        snapshot_id="snap_0123456789abcdef",
        dataset_name="empty",
        as_of_date=date(2024, 6, 30),
        records=(),
    )
    assert _round_trip(original) == original


def test_audit_input_snapshot_round_trips() -> None:
    original = AuditInputSnapshot(
        audit_input_id="audit_0123456789abcdef",
        dataset_name="reviewed-demo",
        as_of_date=date(2024, 6, 30),
        records=(audit_input_record(),),
    )
    assert _round_trip(original) == original


def test_case_config_round_trips() -> None:
    original = CaseConfig(
        case_id="case_0123456789abcdef",
        case_name="look-ahead-medium",
        dataset_name="reviewed-demo",
        as_of_date=date(2024, 6, 30),
        seed=42,
        spec_version="v0.1",
    )
    assert _round_trip(original) == original


def test_runtime_metadata_round_trips_including_its_timestamp() -> None:
    original = RuntimeMetadata(
        code_version="quantcheck-0.1.0.dev0",
        python_version="3.12.13",
        platform="darwin-arm64",
        generated_at=datetime(2026, 8, 6, 17, 30, 45, 123456, tzinfo=UTC),
    )
    restored = _round_trip(original)
    assert restored == original
    assert restored.generated_at.tzinfo is not None


def test_artifact_identity_round_trips() -> None:
    original = ArtifactIdentity(
        kind="dataset-snapshot",
        stable_id="snap_0123456789abcdef",
        content_hash="a" * 64,
    )
    assert _round_trip(original) == original
