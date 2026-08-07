"""Rules of the single canonical serialization path."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from quantcheck.json_types import CanonicalizationError
from quantcheck.serialization import (
    MAX_CANONICAL_DEPTH,
    canonical_json_bytes,
    canonical_json_text,
    parse_canonical_json,
    to_canonical_json,
)
from tests.support import financial_fact


def test_mapping_keys_are_sorted_regardless_of_insertion_order() -> None:
    forward = {"alpha": 1, "beta": 2, "gamma": 3}
    backward = {"gamma": 3, "beta": 2, "alpha": 1}
    assert canonical_json_bytes(forward) == canonical_json_bytes(backward)
    assert canonical_json_text(forward) == '{"alpha":1,"beta":2,"gamma":3}'


def test_nested_mapping_order_is_also_normalized() -> None:
    forward = {"outer": {"b": {"z": 1, "a": 2}, "a": 3}}
    backward = {"outer": {"a": 3, "b": {"a": 2, "z": 1}}}
    assert canonical_json_bytes(forward) == canonical_json_bytes(backward)


def test_sequence_order_is_preserved() -> None:
    assert canonical_json_text([3, 1, 2]) == "[3,1,2]"
    assert canonical_json_bytes([1, 2]) != canonical_json_bytes([2, 1])


def test_tuples_and_lists_serialize_identically() -> None:
    assert canonical_json_bytes((1, 2, 3)) == canonical_json_bytes([1, 2, 3])


def test_output_is_compact_with_no_whitespace_or_trailing_newline() -> None:
    text = canonical_json_text({"a": [1, 2], "b": {"c": "d"}})
    assert text == '{"a":[1,2],"b":{"c":"d"}}'
    assert not text.endswith("\n")


def test_unicode_is_written_as_itself_not_escaped() -> None:
    text = canonical_json_text({"name": "Nestlé Ünïcode 日本語"})
    assert "Nestlé Ünïcode 日本語" in text
    assert "\\u" not in text
    assert canonical_json_bytes({"k": "é"}) == '{"k":"é"}'.encode()


def test_unicode_normalization_is_not_applied() -> None:
    composed = "é"
    decomposed = "é"
    assert canonical_json_bytes({"k": composed}) != canonical_json_bytes({"k": decomposed})


def test_control_characters_in_strings_are_escaped_by_json() -> None:
    assert canonical_json_text({"k": "a\nb"}) == '{"k":"a\\nb"}'


def test_dates_use_exact_iso_calendar_strings() -> None:
    assert canonical_json_text({"d": date(2024, 3, 31)}) == '{"d":"2024-03-31"}'


def test_timestamps_use_exact_utc_strings() -> None:
    moment = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)
    assert canonical_json_text({"t": moment}) == '{"t":"2026-08-06T12:00:00.000000Z"}'


def test_decimals_become_canonical_strings_never_json_numbers() -> None:
    assert canonical_json_text({"v": Decimal("1234567.8900")}) == '{"v":"1234567.89"}'
    assert canonical_json_text({"v": Decimal("-12.5")}) == '{"v":"-12.5"}'


def test_very_large_and_very_small_decimals_stay_exact() -> None:
    assert canonical_json_text({"v": Decimal("1E+40")}) == ('{"v":"' + "1" + "0" * 40 + '"}')
    assert canonical_json_text({"v": Decimal("-1E-40")}) == ('{"v":"-0.' + "0" * 39 + '1"}')


def test_booleans_stay_booleans_and_are_not_confused_with_integers() -> None:
    assert canonical_json_text({"a": True, "b": 1}) == '{"a":true,"b":1}'


def test_none_becomes_null() -> None:
    assert canonical_json_text({"a": None}) == '{"a":null}'


def test_large_integers_keep_full_precision() -> None:
    big = 2**80
    assert canonical_json_text({"n": big}) == f'{{"n":{big}}}'


@pytest.mark.parametrize(
    "value",
    [
        1.5,
        float("nan"),
        float("inf"),
        b"bytes",
        bytearray(b"bytes"),
        {1, 2},
        frozenset({1}),
        complex(1, 2),
        object(),
        Decimal("NaN"),
        Decimal("Infinity"),
        datetime(2024, 1, 1),  # noqa: DTZ001
    ],
)
def test_unsupported_values_are_rejected(value: Any) -> None:
    with pytest.raises(CanonicalizationError):
        to_canonical_json(value)


def test_float_is_rejected_even_when_nested() -> None:
    with pytest.raises(CanonicalizationError, match="float"):
        to_canonical_json({"outer": {"inner": [1, 2.5]}})


def test_non_string_mapping_keys_are_rejected() -> None:
    with pytest.raises(CanonicalizationError, match="mapping keys must be strings"):
        to_canonical_json({1: "a"})


def test_there_is_no_str_fallback_for_unknown_objects() -> None:
    class Opaque:
        def __str__(self) -> str:
            return "0x7fdeadbeef"

    with pytest.raises(CanonicalizationError, match="unsupported value of type Opaque"):
        to_canonical_json({"o": Opaque()})


def test_excessive_nesting_is_rejected() -> None:
    deep: Any = "leaf"
    for _ in range(MAX_CANONICAL_DEPTH + 2):
        deep = [deep]
    with pytest.raises(CanonicalizationError, match="nests deeper"):
        to_canonical_json(deep)


def test_repeated_calls_return_identical_bytes() -> None:
    fact = financial_fact()
    results = {canonical_json_bytes(fact) for _ in range(20)}
    assert len(results) == 1


def test_model_serialization_sorts_fields_and_covers_them_all() -> None:
    fact = financial_fact()
    value = to_canonical_json(fact)
    assert isinstance(value, dict)
    assert list(value) == sorted(value)
    assert set(value) == set(type(fact).model_fields)


def test_model_serialization_does_not_use_pydantic_json() -> None:
    """Pydantic would emit a JSON number for Decimal; the contract needs a string."""
    fact = financial_fact(value=Decimal("1.5"))
    assert '"value":"1.5"' in canonical_json_text(fact)


def test_optional_fields_appear_explicitly_as_null() -> None:
    text = canonical_json_text(financial_fact(entity_name=None))
    assert '"entity_name":null' in text


def test_canonical_bytes_are_utf8_encoded_text() -> None:
    fact = financial_fact(entity_name="Société Générale")
    assert canonical_json_bytes(fact) == canonical_json_text(fact).encode("utf-8")


def test_parse_canonical_json_round_trips_the_text() -> None:
    fact = financial_fact()
    parsed = parse_canonical_json(canonical_json_bytes(fact))
    assert isinstance(parsed, dict)
    assert parsed["record_id"] == fact.record_id
    assert parsed["value"] == "1234567.89"


def test_parse_canonical_json_rejects_float_literals() -> None:
    with pytest.raises(CanonicalizationError, match="floating-point"):
        parse_canonical_json(b'{"v":1.5}')


@pytest.mark.parametrize("payload", [b'{"v":NaN}', b'{"v":Infinity}', b'{"v":-Infinity}'])
def test_parse_canonical_json_rejects_json_constants(payload: bytes) -> None:
    with pytest.raises(CanonicalizationError, match="JSON constant"):
        parse_canonical_json(payload)


def test_parse_canonical_json_rejects_malformed_bytes() -> None:
    with pytest.raises(CanonicalizationError, match="malformed canonical JSON"):
        parse_canonical_json(b'{"v":}')


def test_parse_canonical_json_rejects_invalid_utf8() -> None:
    with pytest.raises(CanonicalizationError, match="valid UTF-8"):
        parse_canonical_json(b'{"v":"\xff\xfe"}')
