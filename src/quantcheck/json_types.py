"""Strict JSON-domain value types and canonical scalar encodings.

This module defines the narrow value domain QuantCheck is willing to
serialize deterministically, plus the exact string encodings used for
``Decimal``, ``date``, and timezone-aware ``datetime``.

It deliberately depends only on the standard library so that the value
domain stays independent of Pydantic, pandas, and network libraries. The
authoritative prose contract lives in ``docs/SERIALIZATION_AND_HASHING.md``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

__all__ = [
    "CANONICAL_DECIMAL_PATTERN",
    "CANONICAL_ISO_DATE_PATTERN",
    "CanonicalizationError",
    "JsonValue",
    "canonical_date_string",
    "canonical_datetime_string",
    "canonical_decimal_string",
    "parse_canonical_date",
    "parse_canonical_datetime",
    "parse_canonical_decimal",
]


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented in the canonical JSON domain."""


#: The canonical JSON output domain. ``Decimal``, ``date``, and ``datetime``
#: are *inputs*; canonicalization always replaces them with strings.
type JsonValue = None | bool | int | str | Mapping[str, "JsonValue"] | Sequence["JsonValue"]

#: Accepted textual form for a Decimal: an optional sign, an integer part with
#: no redundant leading zeros, and an optional fractional part. Exponent
#: notation, whitespace, underscores, ``+``, ``NaN``, and ``Infinity`` are
#: rejected rather than guessed at.
CANONICAL_DECIMAL_PATTERN = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")

#: Accepted textual form for a day-level financial date.
CANONICAL_ISO_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

#: Accepted textual form for a runtime timestamp: UTC, always six fractional
#: digits, always a ``Z`` suffix.
_CANONICAL_TIMESTAMP_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$"
)


def canonical_decimal_string(value: Decimal) -> str:
    """Return the canonical string encoding of a finite ``Decimal``.

    The encoding is plain fixed-point notation of the value's *numeric*
    identity: the exponent is normalized away, so ``Decimal("1.50")`` and
    ``Decimal("1.5")`` both encode as ``"1.5"``. Declared scale is deliberately
    not part of identity. Two Decimals that compare equal must produce equal
    bytes, or the same economic fact reported as ``1234567`` in one filing and
    ``1234567.00`` in the next would look like two different facts to duplicate
    and revision analysis.

    The sign of zero is also dropped: a negative zero carries no financial
    meaning and would otherwise split one value into two hashes.

    Raises:
        CanonicalizationError: if the value is NaN, sNaN, or infinite.
    """
    if not isinstance(value, Decimal):
        raise CanonicalizationError(f"expected Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise CanonicalizationError(f"non-finite Decimal is not serializable: {value!s}")
    # ``Decimal.normalize()`` applies the active arithmetic context and can
    # silently round values whose coefficient exceeds that context precision.
    # Fixed-point formatting itself is exact; remove only insignificant
    # fractional zeroes afterward so numeric equality still maps to one form.
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text.startswith("-") and set(text[1:]) <= {"0", "."}:
        text = text[1:]
    return text


def parse_canonical_decimal(text: str) -> Decimal:
    """Parse a canonical decimal string into a ``Decimal``.

    Raises:
        CanonicalizationError: if the text is not a canonical decimal string.
    """
    if not isinstance(text, str):
        raise CanonicalizationError(f"expected str, got {type(text).__name__}")
    if CANONICAL_DECIMAL_PATTERN.fullmatch(text) is None:
        raise CanonicalizationError(f"malformed decimal string: {text!r}")
    return Decimal(text)


def canonical_date_string(value: date) -> str:
    """Return the ISO calendar-date encoding of a day-level ``date``.

    ``datetime`` is rejected even though it subclasses ``date``: a financial
    day and an instant are different concepts.
    """
    if isinstance(value, datetime) or not isinstance(value, date):
        raise CanonicalizationError(f"expected date (not datetime), got {type(value).__name__}")
    return f"{value.year:04d}-{value.month:02d}-{value.day:02d}"


def parse_canonical_date(text: str) -> date:
    """Parse a canonical ISO calendar date.

    Raises:
        CanonicalizationError: if the text is not a valid canonical date.
    """
    if not isinstance(text, str):
        raise CanonicalizationError(f"expected str, got {type(text).__name__}")
    if CANONICAL_ISO_DATE_PATTERN.fullmatch(text) is None:
        raise CanonicalizationError(f"malformed date string: {text!r}")
    try:
        return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))
    except ValueError as exc:
        raise CanonicalizationError(f"invalid calendar date: {text!r}") from exc


def canonical_datetime_string(value: datetime) -> str:
    """Return the canonical UTC encoding of a timezone-aware ``datetime``.

    Runtime timestamps only. Naive datetimes are rejected because their
    instant is not determinable.
    """
    if not isinstance(value, datetime):
        raise CanonicalizationError(f"expected datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise CanonicalizationError("naive datetime is not serializable; supply a timezone")
    moment = value.astimezone(UTC)
    return (
        f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d}"
        f"T{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}"
        f".{moment.microsecond:06d}Z"
    )


def parse_canonical_datetime(text: str) -> datetime:
    """Parse a canonical UTC timestamp string into an aware ``datetime``.

    Raises:
        CanonicalizationError: if the text is not a canonical UTC timestamp.
    """
    if not isinstance(text, str):
        raise CanonicalizationError(f"expected str, got {type(text).__name__}")
    if _CANONICAL_TIMESTAMP_PATTERN.fullmatch(text) is None:
        raise CanonicalizationError(f"malformed timestamp string: {text!r}")
    try:
        return datetime(
            int(text[0:4]),
            int(text[5:7]),
            int(text[8:10]),
            int(text[11:13]),
            int(text[14:16]),
            int(text[17:19]),
            int(text[20:26]),
            tzinfo=UTC,
        )
    except ValueError as exc:
        raise CanonicalizationError(f"invalid timestamp: {text!r}") from exc
