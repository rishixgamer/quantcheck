"""SHA-256 content hashes and deterministic stable identifiers.

Four things are kept strictly apart here:

* the canonical JSON-compatible *value* (``serialization.to_canonical_json``);
* the canonical UTF-8 *bytes* (``serialization.canonical_json_bytes``);
* the full 64-character SHA-256 *digest* (:func:`canonical_sha256`);
* the prefixed *stable identifier* (:func:`stable_id`).

No identifier here uses ``uuid4``, ``id()``, or Python's built-in ``hash()``,
so identifiers are stable across processes, machines, and ``PYTHONHASHSEED``
values. Runtime metadata, output directories, and filesystem paths are never
part of an identifier payload.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from quantcheck.json_types import CanonicalizationError, JsonValue
from quantcheck.schemas import (
    ArtifactIdentity,
    AuditInputRecord,
    AuditInputSnapshot,
    CaseConfig,
    DatasetSnapshot,
    FinancialFact,
)
from quantcheck.serialization import canonical_json_bytes, to_canonical_json

__all__ = [
    "AUDIT_INPUT_SNAPSHOT_NAMESPACE",
    "CASE_CONFIG_NAMESPACE",
    "DATASET_SNAPSHOT_NAMESPACE",
    "SOURCE_RECORD_NAMESPACE",
    "STABLE_ID_DIGEST_LENGTH",
    "STABLE_ID_SCHEME",
    "audit_input_snapshot_id",
    "audit_input_snapshot_identity_matches",
    "build_artifact_identity",
    "canonical_sha256",
    "case_config_id",
    "case_config_identity_matches",
    "dataset_snapshot_id",
    "dataset_snapshot_identity_matches",
    "sha256_hex_of_bytes",
    "source_record_id",
    "stable_id",
]

#: Framing constant mixed into every stable identifier payload. Changing it
#: changes every identifier, so it is versioned.
STABLE_ID_SCHEME = "quantcheck/stable-id/v1"

#: Number of leading hex characters of the digest kept in a stable identifier.
#: 16 hex characters is 64 bits.
STABLE_ID_DIGEST_LENGTH = 16

SOURCE_RECORD_NAMESPACE = "quantcheck/source-record/v1"
DATASET_SNAPSHOT_NAMESPACE = "quantcheck/dataset-snapshot/v1"
AUDIT_INPUT_SNAPSHOT_NAMESPACE = "quantcheck/audit-input-snapshot/v1"
CASE_CONFIG_NAMESPACE = "quantcheck/case-config/v1"

_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9]{0,15}$")
_MIN_DIGEST_LENGTH = 8
_MAX_DIGEST_LENGTH = 64


def sha256_hex_of_bytes(data: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of raw bytes."""
    if not isinstance(data, bytes | bytearray):
        raise CanonicalizationError(f"expected bytes, got {type(data).__name__}")
    return hashlib.sha256(bytes(data)).hexdigest()


def canonical_sha256(value: object) -> str:
    """Return the SHA-256 digest of a value's canonical UTF-8 bytes."""
    return sha256_hex_of_bytes(canonical_json_bytes(value))


def stable_id(
    *,
    prefix: str,
    namespace: str,
    payload: object,
    digest_length: int = STABLE_ID_DIGEST_LENGTH,
) -> str:
    """Build a deterministic ``<prefix>_<hex>`` identifier.

    The digest covers a versioned envelope of the scheme, the namespace, and
    the canonical form of the payload, so two different namespaces can never
    collide by carrying the same payload.

    Args:
        prefix: lowercase alphanumeric identifier prefix, starting with a letter.
        namespace: versioned namespace naming what kind of thing this is.
        payload: the logical identity of the thing, in the canonical domain.
        digest_length: how many leading hex characters to keep.

    Raises:
        CanonicalizationError: for a malformed prefix, namespace, or length,
            or for a payload outside the canonical JSON domain.
    """
    if not isinstance(prefix, str) or _PREFIX_PATTERN.fullmatch(prefix) is None:
        raise CanonicalizationError(f"malformed stable identifier prefix: {prefix!r}")
    if not isinstance(namespace, str) or not namespace:
        raise CanonicalizationError(f"malformed stable identifier namespace: {namespace!r}")
    if isinstance(digest_length, bool) or not isinstance(digest_length, int):
        raise CanonicalizationError("digest_length must be an integer")
    if not _MIN_DIGEST_LENGTH <= digest_length <= _MAX_DIGEST_LENGTH:
        raise CanonicalizationError(
            f"digest_length must be between {_MIN_DIGEST_LENGTH} and {_MAX_DIGEST_LENGTH}"
        )
    envelope = {
        "id_scheme": STABLE_ID_SCHEME,
        "namespace": namespace,
        "payload": to_canonical_json(payload),
    }
    return f"{prefix}_{canonical_sha256(envelope)[:digest_length]}"


def source_record_id(*, source_name: str, source_locator: str, source_row_key: str) -> str:
    """Return the ``rec_`` identifier for a record's stable source coordinate.

    The payload is the source's own coordinate — never a DataFrame row
    position, never a path on this machine.
    """
    payload = {
        "source_name": source_name,
        "source_locator": source_locator,
        "source_row_key": source_row_key,
    }
    return stable_id(prefix="rec", namespace=SOURCE_RECORD_NAMESPACE, payload=payload)


class _RecordLike(Protocol):
    """Anything carrying a stable ``record_id``; used only for ordering."""

    @property
    def record_id(self) -> str: ...


def _snapshot_payload(
    dataset_name: str,
    as_of_date: date,
    records: Sequence[_RecordLike],
) -> dict[str, JsonValue]:
    ordered = sorted(records, key=lambda record: record.record_id)
    return {
        "dataset_name": to_canonical_json(dataset_name),
        "as_of_date": to_canonical_json(as_of_date),
        "records": to_canonical_json(ordered),
    }


def dataset_snapshot_id(
    *,
    dataset_name: str,
    as_of_date: date,
    records: Sequence[FinancialFact],
) -> str:
    """Return the ``snap_`` identifier for a dataset snapshot's logical content.

    Records are sorted by ``record_id`` first, so the identifier does not
    depend on the order in which rows arrived.
    """
    return stable_id(
        prefix="snap",
        namespace=DATASET_SNAPSHOT_NAMESPACE,
        payload=_snapshot_payload(dataset_name, as_of_date, records),
    )


def audit_input_snapshot_id(
    *,
    dataset_name: str,
    as_of_date: date,
    records: Sequence[AuditInputRecord],
) -> str:
    """Return the ``audit_`` identifier for a sanitized audit-input snapshot."""
    return stable_id(
        prefix="audit",
        namespace=AUDIT_INPUT_SNAPSHOT_NAMESPACE,
        payload=_snapshot_payload(dataset_name, as_of_date, records),
    )


def case_config_id(
    *,
    case_name: str,
    dataset_name: str,
    as_of_date: date,
    seed: int,
    spec_version: str,
) -> str:
    """Return the ``case_`` identifier for a case's logical configuration.

    Runtime metadata is not an argument, and must never become one.
    """
    payload = {
        "case_name": case_name,
        "dataset_name": dataset_name,
        "as_of_date": to_canonical_json(as_of_date),
        "seed": seed,
        "spec_version": spec_version,
    }
    return stable_id(prefix="case", namespace=CASE_CONFIG_NAMESPACE, payload=payload)


def dataset_snapshot_identity_matches(snapshot: DatasetSnapshot) -> bool:
    """Report whether a snapshot's stored ``snapshot_id`` matches its content."""
    expected = dataset_snapshot_id(
        dataset_name=snapshot.dataset_name,
        as_of_date=snapshot.as_of_date,
        records=snapshot.records,
    )
    return snapshot.snapshot_id == expected


def audit_input_snapshot_identity_matches(snapshot: AuditInputSnapshot) -> bool:
    """Report whether an audit-input snapshot's stored id matches its content."""
    expected = audit_input_snapshot_id(
        dataset_name=snapshot.dataset_name,
        as_of_date=snapshot.as_of_date,
        records=snapshot.records,
    )
    return snapshot.audit_input_id == expected


def case_config_identity_matches(config: CaseConfig) -> bool:
    """Report whether a case configuration's stored ``case_id`` matches it."""
    expected = case_config_id(
        case_name=config.case_name,
        dataset_name=config.dataset_name,
        as_of_date=config.as_of_date,
        seed=config.seed,
        spec_version=config.spec_version,
    )
    return config.case_id == expected


def build_artifact_identity(
    *,
    kind: str,
    stable_identifier: str,
    content: object,
) -> ArtifactIdentity:
    """Pair a stable identifier with the SHA-256 content hash of an artifact."""
    return ArtifactIdentity(
        kind=kind,
        stable_id=stable_identifier,
        content_hash=canonical_sha256(content),
    )
