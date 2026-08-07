"""Canonical scalar encodings: Decimal, date, and UTC timestamp."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from quantcheck.json_types import (
    CanonicalizationError,
    canonical_date_string,
    canonical_datetime_string,
    canonical_decimal_string,
    parse_canonical_date,
    parse_canonical_datetime,
    parse_canonical_decimal,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("0"), "0"),
        (Decimal("1"), "1"),
        (Decimal("1.50"), "1.5"),
        (Decimal("-1.50"), "-1.5"),
        (Decimal("1234567.8900"), "1234567.89"),
        (Decimal("-0.000001"), "-0.000001"),
        (Decimal("100"), "100"),
        (Decimal("1E+30"), "1000000000000000000000000000000"),
        (Decimal("1E-30"), "0.000000000000000000000000000001"),
        (Decimal("-1E+18"), "-1000000000000000000"),
    ],
)
def test_canonical_decimal_string_uses_plain_notation(value: Decimal, expected: str) -> None:
    assert canonical_decimal_string(value) == expected


@pytest.mark.parametrize("value", [Decimal("-0"), Decimal("-0.0"), Decimal("-0.00")])
def test_negative_zero_loses_its_sign(value: Decimal) -> None:
    assert canonical_decimal_string(value) == "0"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (Decimal("1.5"), Decimal("1.50")),
        (Decimal("150E-2"), Decimal("1.5")),
        (Decimal("100"), Decimal("1E+2")),
        (Decimal("0"), Decimal("0.000")),
    ],
)
def test_numerically_equal_decimals_encode_identically(left: Decimal, right: Decimal) -> None:
    """Declared scale is not identity; equal values must produce equal bytes."""
    assert left == right
    assert canonical_decimal_string(left) == canonical_decimal_string(right)


@pytest.mark.parametrize("text", ["NaN", "-NaN", "sNaN", "Infinity", "-Infinity"])
def test_non_finite_decimals_are_rejected(text: str) -> None:
    with pytest.raises(CanonicalizationError, match="non-finite"):
        canonical_decimal_string(Decimal(text))


def test_canonical_decimal_string_rejects_non_decimal() -> None:
    with pytest.raises(CanonicalizationError, match="expected Decimal"):
        canonical_decimal_string("1.5")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "text",
    ["0", "-0", "1", "1.50", "-1234567.8900", "10000000000000000000000000000000"],
)
def test_parse_canonical_decimal_accepts_canonical_forms(text: str) -> None:
    assert parse_canonical_decimal(text) == Decimal(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        " 1",
        "1 ",
        "+1",
        "01",
        "-01",
        "1.",
        ".5",
        "1.2.3",
        "1e5",
        "1E+5",
        "1_000",
        "NaN",
        "Infinity",
        "one",
        "0x10",
    ],
)
def test_parse_canonical_decimal_rejects_malformed_text(text: str) -> None:
    with pytest.raises(CanonicalizationError, match="malformed decimal string"):
        parse_canonical_decimal(text)


def test_decimal_encoding_round_trips_through_its_own_output() -> None:
    for value in (Decimal("0.00"), Decimal("-1.50"), Decimal("1E+30"), Decimal("-0.00")):
        text = canonical_decimal_string(value)
        parsed = parse_canonical_decimal(text)
        assert parsed == value
        assert canonical_decimal_string(parsed) == text


def test_canonical_date_string_is_an_iso_calendar_date() -> None:
    assert canonical_date_string(date(2024, 3, 31)) == "2024-03-31"
    assert canonical_date_string(date(999, 1, 2)) == "0999-01-02"


def test_canonical_date_string_rejects_datetime() -> None:
    with pytest.raises(CanonicalizationError, match="not datetime"):
        canonical_date_string(datetime(2024, 3, 31, tzinfo=UTC))


@pytest.mark.parametrize("text", ["2024-3-31", "20240331", "2024-02-30", "2024-13-01", ""])
def test_parse_canonical_date_rejects_bad_input(text: str) -> None:
    with pytest.raises(CanonicalizationError):
        parse_canonical_date(text)


def test_parse_canonical_date_round_trip() -> None:
    assert parse_canonical_date("2024-03-31") == date(2024, 3, 31)


def test_canonical_datetime_string_normalizes_to_utc() -> None:
    eastern = timezone(timedelta(hours=-5))
    moment = datetime(2024, 3, 31, 7, 8, 9, 123456, tzinfo=eastern)
    assert canonical_datetime_string(moment) == "2024-03-31T12:08:09.123456Z"


def test_canonical_datetime_string_always_has_six_fractional_digits() -> None:
    assert canonical_datetime_string(datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)) == (
        "2024-01-02T03:04:05.000000Z"
    )


def test_canonical_datetime_string_rejects_naive_datetime() -> None:
    with pytest.raises(CanonicalizationError, match="naive datetime"):
        canonical_datetime_string(datetime(2024, 3, 31, 12, 0, 0))  # noqa: DTZ001


def test_parse_canonical_datetime_round_trip() -> None:
    text = "2024-03-31T12:08:09.123456Z"
    assert canonical_datetime_string(parse_canonical_datetime(text)) == text


@pytest.mark.parametrize(
    "text",
    ["2024-03-31T12:08:09Z", "2024-03-31T12:08:09.123456+00:00", "2024-03-31 12:08:09.123456Z"],
)
def test_parse_canonical_datetime_rejects_non_canonical_text(text: str) -> None:
    with pytest.raises(CanonicalizationError, match="malformed timestamp"):
        parse_canonical_datetime(text)
