"""Bounded property-based tests for the canonical contract.

Strategies are deliberately small and understandable so a failure is easy to
read and reproduce. Nothing here draws unbounded text, unbounded recursion, or
unbounded numeric magnitudes.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from quantcheck.hashing import canonical_sha256, source_record_id, stable_id
from quantcheck.json_types import (
    CanonicalizationError,
    canonical_decimal_string,
    parse_canonical_decimal,
)
from quantcheck.serialization import (
    canonical_json_bytes,
    canonical_json_text,
    parse_canonical_json,
    to_canonical_json,
)

_SETTINGS = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# Bounded, reviewable strategies.
tokens = st.text(
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
    min_size=1,
    max_size=24,
)
unicode_tokens = st.text(min_size=0, max_size=24).filter(
    lambda text: text == text.strip() and "\x00" not in text
)
decimals = st.decimals(
    min_value=Decimal("-1E12"),
    max_value=Decimal("1E12"),
    allow_nan=False,
    allow_infinity=False,
    places=4,
)
dates = st.dates(min_value=date(1990, 1, 1), max_value=date(2050, 12, 31))
json_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(10**9), max_value=10**9),
    unicode_tokens,
    decimals,
    dates,
)
json_values = st.recursive(
    json_scalars,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(tokens, children, max_size=4),
    ),
    max_leaves=12,
)


@given(decimals)
@_SETTINGS
def test_decimal_encoding_is_parseable_and_value_preserving(value: Decimal) -> None:
    text = canonical_decimal_string(value)
    parsed = parse_canonical_decimal(text)
    assert parsed == value
    assert canonical_decimal_string(parsed) == text


@given(decimals)
@_SETTINGS
def test_decimal_encoding_never_uses_exponent_notation_or_signed_zero(value: Decimal) -> None:
    text = canonical_decimal_string(value)
    assert "e" not in text.lower()
    assert not text.startswith("+")
    if value == 0:
        assert text == "0"


@given(decimals, decimals)
@_SETTINGS
def test_equal_decimals_always_encode_identically(left: Decimal, right: Decimal) -> None:
    if left == right:
        assert canonical_decimal_string(left) == canonical_decimal_string(right)


@given(dates)
@_SETTINGS
def test_dates_encode_to_a_ten_character_iso_string(value: date) -> None:
    text = canonical_json_text(value)
    assert text == f'"{value.isoformat()}"'
    assert len(text) == 12


@given(json_values)
@_SETTINGS
def test_canonicalization_is_deterministic_across_repeated_calls(value: Any) -> None:
    first = canonical_json_bytes(value)
    for _ in range(3):
        assert canonical_json_bytes(value) == first


@given(json_values)
@_SETTINGS
def test_hashing_is_deterministic_across_repeated_calls(value: Any) -> None:
    first = canonical_sha256(value)
    assert canonical_sha256(value) == first
    assert len(first) == 64


@given(json_values)
@_SETTINGS
def test_canonical_bytes_always_reparse(value: Any) -> None:
    assert parse_canonical_json(canonical_json_bytes(value)) == to_canonical_json(value)


@given(st.dictionaries(tokens, json_scalars, min_size=1, max_size=6))
@_SETTINGS
def test_mapping_order_never_affects_bytes_or_hashes(mapping: dict[str, Any]) -> None:
    shuffled = dict(reversed(list(mapping.items())))
    assert canonical_json_bytes(mapping) == canonical_json_bytes(shuffled)
    assert canonical_sha256(mapping) == canonical_sha256(shuffled)


@given(st.dictionaries(tokens, json_scalars, min_size=1, max_size=6))
@_SETTINGS
def test_canonical_output_keys_are_sorted(mapping: dict[str, Any]) -> None:
    converted = to_canonical_json(mapping)
    assert isinstance(converted, dict)
    assert list(converted) == sorted(converted)


@given(st.lists(json_scalars, min_size=2, max_size=5))
@_SETTINGS
def test_sequence_order_is_significant(items: list[Any]) -> None:
    reversed_items = list(reversed(items))
    if to_canonical_json(items) != to_canonical_json(reversed_items):
        assert canonical_json_bytes(items) != canonical_json_bytes(reversed_items)


@given(tokens, tokens, tokens)
@_SETTINGS
def test_source_record_ids_are_deterministic_and_well_formed(
    name: str, locator: str, row_key: str
) -> None:
    identifier = source_record_id(source_name=name, source_locator=locator, source_row_key=row_key)
    assert identifier == source_record_id(
        source_name=name, source_locator=locator, source_row_key=row_key
    )
    assert identifier.startswith("rec_")
    digest = identifier.removeprefix("rec_")
    assert len(digest) == 16
    assert set(digest) <= set("0123456789abcdef")


@given(tokens, tokens, json_values)
@_SETTINGS
def test_stable_ids_are_deterministic_for_a_fixed_namespace(
    namespace: str, other_namespace: str, payload: Any
) -> None:
    first = stable_id(prefix="x", namespace=namespace, payload=payload)
    assert first == stable_id(prefix="x", namespace=namespace, payload=payload)
    if namespace != other_namespace:
        assert first != stable_id(prefix="x", namespace=other_namespace, payload=payload)


@given(st.floats(allow_nan=True, allow_infinity=True))
@_SETTINGS
def test_floats_are_always_rejected(value: float) -> None:
    try:
        to_canonical_json(value)
    except CanonicalizationError:
        return
    raise AssertionError("a float reached the canonical domain")


@given(
    st.one_of(
        st.binary(max_size=8),
        st.sets(st.integers(min_value=0, max_value=8), max_size=3),
        st.frozensets(st.integers(min_value=0, max_value=8), max_size=3),
        st.complex_numbers(allow_nan=False, allow_infinity=False),
    )
)
@_SETTINGS
def test_values_outside_the_json_domain_are_rejected(value: Any) -> None:
    try:
        to_canonical_json(value)
    except CanonicalizationError:
        return
    raise AssertionError(f"{type(value).__name__} reached the canonical domain")
