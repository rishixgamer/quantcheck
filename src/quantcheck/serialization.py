"""The single authoritative canonical serialization path for QuantCheck.

Everything that needs deterministic bytes — hashing, stable identifiers,
golden vectors, and (in later milestones) artifact persistence — goes through
:func:`canonical_json_bytes`. There is deliberately no second serializer, and
Pydantic's own JSON output is never used, because its defaults do not match
this contract.

The rules are stated in ``docs/SERIALIZATION_AND_HASHING.md``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal

from quantcheck.json_types import (
    CanonicalizationError,
    JsonValue,
    canonical_date_string,
    canonical_datetime_string,
    canonical_decimal_string,
)
from quantcheck.schemas import CanonicalModel

__all__ = [
    "MAX_CANONICAL_DEPTH",
    "canonical_json_bytes",
    "canonical_json_text",
    "parse_canonical_json",
    "to_canonical_json",
]

#: Guards against pathological or cyclic structures. Real QuantCheck
#: artifacts nest far below this.
MAX_CANONICAL_DEPTH = 64


def to_canonical_json(value: object) -> JsonValue:
    """Convert a supported value into the canonical JSON-compatible domain.

    Supported inputs are ``None``, ``bool``, ``int``, ``str``, ``Decimal``,
    ``date``, timezone-aware ``datetime``, :class:`CanonicalModel` instances,
    string-keyed mappings, and non-string sequences. Everything else — most
    importantly ``float`` and ``bytes`` — is rejected rather than coerced.

    Mapping keys are sorted by Unicode code point. Sequence order is
    preserved, because sequence order is meaningful in QuantCheck artifacts.

    Raises:
        CanonicalizationError: for any unsupported value or excessive nesting.
    """
    return _convert(value, 0)


def _convert(value: object, depth: int) -> JsonValue:
    if depth > MAX_CANONICAL_DEPTH:
        raise CanonicalizationError(f"value nests deeper than {MAX_CANONICAL_DEPTH} levels")

    # bool before int: bool is a subclass of int.
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, Decimal):
        return canonical_decimal_string(value)
    # datetime before date: datetime is a subclass of date.
    if isinstance(value, datetime):
        return canonical_datetime_string(value)
    if isinstance(value, date):
        return canonical_date_string(value)
    if isinstance(value, CanonicalModel):
        return _convert_model(value, depth)
    if isinstance(value, Mapping):
        return _convert_mapping(value, depth)
    if isinstance(value, bytes | bytearray):
        raise CanonicalizationError("bytes are not serializable in the canonical JSON domain")
    if isinstance(value, Sequence):
        return [_convert(item, depth + 1) for item in value]
    raise CanonicalizationError(
        f"unsupported value of type {type(value).__name__} in the canonical JSON domain"
    )


def _convert_model(model: CanonicalModel, depth: int) -> dict[str, JsonValue]:
    converted: dict[str, JsonValue] = {}
    for field_name in type(model).model_fields:
        converted[field_name] = _convert(getattr(model, field_name), depth + 1)
    return {key: converted[key] for key in sorted(converted)}


def _convert_mapping(mapping: Mapping[object, object], depth: int) -> dict[str, JsonValue]:
    converted: dict[str, JsonValue] = {}
    for key, item in mapping.items():
        if not isinstance(key, str):
            raise CanonicalizationError(f"mapping keys must be strings, got {type(key).__name__}")
        converted[key] = _convert(item, depth + 1)
    return {key: converted[key] for key in sorted(converted)}


def canonical_json_text(value: object) -> str:
    """Return the canonical JSON text for a supported value.

    The text is compact (no whitespace between tokens), keeps non-ASCII
    characters as themselves, sorts object keys, and has no trailing newline.
    """
    return json.dumps(
        to_canonical_json(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
        check_circular=True,
    )


def canonical_json_bytes(value: object) -> bytes:
    """Return the canonical UTF-8 bytes for a supported value."""
    return canonical_json_text(value).encode("utf-8")


def _reject_float(text: str) -> JsonValue:
    raise CanonicalizationError(f"floating-point literal {text!r} is not in the canonical domain")


def _reject_constant(text: str) -> JsonValue:
    raise CanonicalizationError(f"JSON constant {text!r} is not in the canonical domain")


def parse_canonical_json(data: bytes) -> JsonValue:
    """Parse canonical UTF-8 bytes back into the JSON output domain.

    Decimals and dates come back as their canonical strings; the owning model
    turns them back into ``Decimal`` and ``date`` during validation.

    Raises:
        CanonicalizationError: if the bytes are not valid canonical JSON.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CanonicalizationError("canonical JSON must be valid UTF-8") from exc
    try:
        parsed: JsonValue = json.loads(
            text,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise CanonicalizationError(f"malformed canonical JSON: {exc.msg}") from exc
    return parsed
