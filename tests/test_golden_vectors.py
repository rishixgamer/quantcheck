"""Static golden vectors for the canonical contract.

Every expected value below is a hand-checked literal. Nothing here recomputes
an expectation from the implementation it is testing.

The three SHA-256 digests were verified independently of this codebase by
piping the exact expected text through ``shasum -a 256``:

    printf '%s' '<GOLDEN_..._TEXT>' | shasum -a 256

The stable-identifier rule was verified the same way: the full digest of
GOLDEN_RECORD_ID_ENVELOPE_TEXT is
``65fda11bcd81ffa12482ed99e6b7c0d01300e85c67c97b91e5072ba9ab39e514``, whose
first 16 characters are exactly the digest part of ``rec_65fda11bcd81ffa1``.

**These are not historical values.** The lost 0.1.0 serialization contract
(``docs/SERIALIZATION_AND_HASHING.md`` in the original repository) did not
survive, so no historical digest or identifier can be reproduced or is being
claimed. These vectors freeze the *rebuilt* contract.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from quantcheck.hashing import (
    SOURCE_RECORD_NAMESPACE,
    STABLE_ID_SCHEME,
    audit_input_snapshot_id,
    canonical_sha256,
    case_config_id,
    dataset_snapshot_id,
    source_record_id,
)
from quantcheck.schemas import DatasetSnapshot, Dimension, FinancialFact, SourceReference
from quantcheck.serialization import canonical_json_bytes, canonical_json_text

# --- Vector 1: a raw nested value with a Decimal, a date, and Unicode --------

GOLDEN_RAW_VALUE = {
    "zeta": [1, 2, 3],
    "alpha": {"nested": {"deep": "value"}, "beta": None},
    "amount": Decimal("1234567.8900"),
    "day": date(2024, 3, 31),
    "flag": True,
    "unicode": "Société 日本語",
}

GOLDEN_RAW_TEXT = (
    '{"alpha":{"beta":null,"nested":{"deep":"value"}},"amount":"1234567.89",'
    '"day":"2024-03-31","flag":true,"unicode":"Société 日本語","zeta":[1,2,3]}'
)

GOLDEN_RAW_SHA256 = "586a63206a04bbe8b3033ddc643e021da70dea81e1dea32693bce2ad1f5d5592"


def test_golden_raw_value_text() -> None:
    assert canonical_json_text(GOLDEN_RAW_VALUE) == GOLDEN_RAW_TEXT


def test_golden_raw_value_bytes() -> None:
    assert canonical_json_bytes(GOLDEN_RAW_VALUE) == GOLDEN_RAW_TEXT.encode("utf-8")


def test_golden_raw_value_digest() -> None:
    assert canonical_sha256(GOLDEN_RAW_VALUE) == GOLDEN_RAW_SHA256


def test_golden_raw_text_shows_the_documented_rules() -> None:
    # keys sorted, no whitespace, Decimal as a normalized string, ISO date,
    # real Unicode characters, and sequence order preserved.
    assert GOLDEN_RAW_TEXT.index('"alpha"') < GOLDEN_RAW_TEXT.index('"zeta"')
    assert ", " not in GOLDEN_RAW_TEXT
    assert '"amount":"1234567.89"' in GOLDEN_RAW_TEXT
    assert '"day":"2024-03-31"' in GOLDEN_RAW_TEXT
    assert "Société 日本語" in GOLDEN_RAW_TEXT
    assert '"zeta":[1,2,3]' in GOLDEN_RAW_TEXT


# --- Vector 2: a representative public model ---------------------------------

GOLDEN_RECORD_ID = "rec_65fda11bcd81ffa1"

GOLDEN_RECORD_ID_ENVELOPE_TEXT = (
    '{"id_scheme":"quantcheck/stable-id/v1",'
    '"namespace":"quantcheck/source-record/v1",'
    '"payload":{"source_locator":"fixture-0001","source_name":"reviewed-fixture",'
    '"source_row_key":"row-0001"}}'
)

GOLDEN_SOURCE = SourceReference(
    source_name="reviewed-fixture",
    source_locator="fixture-0001",
    source_row_key="row-0001",
)

GOLDEN_FACT = FinancialFact(
    record_id=GOLDEN_RECORD_ID,
    entity_id="CIK0000320193",
    entity_name="Example Corporation",
    concept_namespace="us-gaap",
    concept="Revenues",
    value=Decimal("1234567.8900"),
    unit="USD",
    dimensions=(
        Dimension(axis="Segment", member="Total"),
        Dimension(axis="Region", member="US"),
    ),
    period_type="duration",
    period_start=date(2024, 1, 1),
    period_end=date(2024, 3, 31),
    filed_on=date(2024, 5, 2),
    available_on=date(2024, 5, 2),
    form="10-Q",
    accession_number="0000320193-24-000069",
    source=GOLDEN_SOURCE,
)

GOLDEN_FACT_TEXT = (
    '{"accession_number":"0000320193-24-000069","available_on":"2024-05-02",'
    '"concept":"Revenues","concept_namespace":"us-gaap",'
    '"dimensions":[{"axis":"Region","member":"US"},{"axis":"Segment","member":"Total"}],'
    '"entity_id":"CIK0000320193","entity_name":"Example Corporation",'
    '"filed_on":"2024-05-02","form":"10-Q","period_end":"2024-03-31",'
    '"period_start":"2024-01-01","period_type":"duration",'
    '"record_id":"rec_65fda11bcd81ffa1",'
    '"source":{"source_locator":"fixture-0001","source_name":"reviewed-fixture",'
    '"source_row_key":"row-0001"},"unit":"USD","value":"1234567.89"}'
)

GOLDEN_FACT_SHA256 = "49d948dd34b71d731bb56bb136f05d57bee73ebd4ec1a52c34d1ec5ed9bfde5f"


def test_golden_source_record_id() -> None:
    assert (
        source_record_id(
            source_name="reviewed-fixture",
            source_locator="fixture-0001",
            source_row_key="row-0001",
        )
        == GOLDEN_RECORD_ID
    )


def test_golden_record_id_envelope_is_exactly_what_gets_hashed() -> None:
    """Freezes the stable-ID envelope shape, not just its digest."""
    envelope = {
        "id_scheme": STABLE_ID_SCHEME,
        "namespace": SOURCE_RECORD_NAMESPACE,
        "payload": {
            "source_name": "reviewed-fixture",
            "source_locator": "fixture-0001",
            "source_row_key": "row-0001",
        },
    }
    assert canonical_json_text(envelope) == GOLDEN_RECORD_ID_ENVELOPE_TEXT


def test_golden_fact_text() -> None:
    assert canonical_json_text(GOLDEN_FACT) == GOLDEN_FACT_TEXT


def test_golden_fact_bytes() -> None:
    assert canonical_json_bytes(GOLDEN_FACT) == GOLDEN_FACT_TEXT.encode("utf-8")


def test_golden_fact_digest() -> None:
    assert canonical_sha256(GOLDEN_FACT) == GOLDEN_FACT_SHA256


def test_golden_fact_dimensions_are_sorted_in_the_output() -> None:
    assert GOLDEN_FACT_TEXT.index('"axis":"Region"') < GOLDEN_FACT_TEXT.index('"axis":"Segment"')


def test_golden_fact_declared_scale_is_normalized_in_the_output() -> None:
    assert GOLDEN_FACT.value == Decimal("1234567.8900")
    assert '"value":"1234567.89"' in GOLDEN_FACT_TEXT


# --- Vector 3: a snapshot and the remaining identifier prefixes ---------------

GOLDEN_SNAPSHOT_ID = "snap_65237a55e3708090"
GOLDEN_SNAPSHOT_SHA256 = "6b3ddccaa32b82490538fcb08eaef2d7701c2f7c19bfffabb10f4500573e4646"
GOLDEN_EMPTY_AUDIT_INPUT_ID = "audit_4dfda65d5466bd74"
GOLDEN_CASE_ID = "case_dbd6b6fc9c417064"

GOLDEN_SNAPSHOT = DatasetSnapshot(
    snapshot_id=GOLDEN_SNAPSHOT_ID,
    dataset_name="golden-demo",
    as_of_date=date(2024, 6, 30),
    records=(GOLDEN_FACT,),
)


def test_golden_dataset_snapshot_id() -> None:
    assert (
        dataset_snapshot_id(
            dataset_name="golden-demo",
            as_of_date=date(2024, 6, 30),
            records=[GOLDEN_FACT],
        )
        == GOLDEN_SNAPSHOT_ID
    )


def test_golden_dataset_snapshot_digest() -> None:
    assert canonical_sha256(GOLDEN_SNAPSHOT) == GOLDEN_SNAPSHOT_SHA256


def test_golden_empty_audit_input_snapshot_id() -> None:
    assert (
        audit_input_snapshot_id(
            dataset_name="golden-demo", as_of_date=date(2024, 6, 30), records=[]
        )
        == GOLDEN_EMPTY_AUDIT_INPUT_ID
    )


def test_golden_case_config_id() -> None:
    assert (
        case_config_id(
            case_name="golden-case",
            dataset_name="golden-demo",
            as_of_date=date(2024, 6, 30),
            seed=42,
            spec_version="v0.1",
        )
        == GOLDEN_CASE_ID
    )


def test_every_golden_identifier_matches_its_documented_shape() -> None:
    assert GOLDEN_RECORD_ID.startswith("rec_")
    assert GOLDEN_SNAPSHOT_ID.startswith("snap_")
    assert GOLDEN_EMPTY_AUDIT_INPUT_ID.startswith("audit_")
    assert GOLDEN_CASE_ID.startswith("case_")
    for identifier in (
        GOLDEN_RECORD_ID,
        GOLDEN_SNAPSHOT_ID,
        GOLDEN_EMPTY_AUDIT_INPUT_ID,
        GOLDEN_CASE_ID,
    ):
        digest_part = identifier.split("_", 1)[1]
        assert len(digest_part) == 16
        assert set(digest_part) <= set("0123456789abcdef")
