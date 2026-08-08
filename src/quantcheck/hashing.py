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
    "BENCHMARK_AGGREGATE_REPORT_NAMESPACE",
    "BENCHMARK_CLEAN_CONTROL_CASE_NAMESPACE",
    "BENCHMARK_CONFIG_NAMESPACE",
    "BENCHMARK_FAULT_CASE_NAMESPACE",
    "benchmark_aggregate_report_id",
    "benchmark_clean_control_case_id",
    "benchmark_config_id",
    "benchmark_fault_case_id",
    "CASE_CONFIG_NAMESPACE",
    "DATASET_SNAPSHOT_NAMESPACE",
    "DUPLICATE_AUDIT_REPORT_NAMESPACE",
    "DUPLICATE_CREATED_RECORD_NAMESPACE",
    "DUPLICATE_FAULT_NAMESPACE",
    "DUPLICATE_FINDING_NAMESPACE",
    "DUPLICATE_IMPACT_NAMESPACE",
    "DUPLICATE_MANIFEST_NAMESPACE",
    "DUPLICATE_RESEARCH_RESULT_NAMESPACE",
    "DUPLICATE_SCORE_REPORT_NAMESPACE",
    "duplicate_audit_report_id",
    "duplicate_created_record_id",
    "duplicate_fault_id",
    "duplicate_finding_id",
    "duplicate_impact_id",
    "duplicate_manifest_id",
    "duplicate_research_result_id",
    "duplicate_score_report_id",
    "LOOKAHEAD_AUDIT_REPORT_NAMESPACE",
    "LOOKAHEAD_FAULT_NAMESPACE",
    "LOOKAHEAD_FINDING_NAMESPACE",
    "LOOKAHEAD_IMPACT_NAMESPACE",
    "LOOKAHEAD_MANIFEST_NAMESPACE",
    "LOOKAHEAD_MODIFIED_RECORD_NAMESPACE",
    "LOOKAHEAD_RESEARCH_RESULT_NAMESPACE",
    "LOOKAHEAD_SCORE_REPORT_NAMESPACE",
    "REVISION_NAMESPACE",
    "REVISION_OVERWRITE_AUDIT_REPORT_NAMESPACE",
    "REVISION_OVERWRITE_FAULT_NAMESPACE",
    "REVISION_OVERWRITE_FINDING_NAMESPACE",
    "REVISION_OVERWRITE_HISTORY_UNIT_NAMESPACE",
    "REVISION_OVERWRITE_IMPACT_NAMESPACE",
    "REVISION_OVERWRITE_MANIFEST_NAMESPACE",
    "REVISION_OVERWRITE_MODIFIED_RECORD_NAMESPACE",
    "REVISION_OVERWRITE_RESEARCH_RESULT_NAMESPACE",
    "REVISION_OVERWRITE_SCORE_REPORT_NAMESPACE",
    "SEC_SOURCE_ROW_NAMESPACE",
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
    "fault_manifest_id",
    "lookahead_audit_report_id",
    "lookahead_fault_id",
    "lookahead_finding_id",
    "lookahead_impact_id",
    "lookahead_modified_record_id",
    "lookahead_research_result_id",
    "lookahead_score_report_id",
    "revision_id",
    "revision_history_unit_id",
    "revision_overwrite_audit_report_id",
    "revision_overwrite_fault_id",
    "revision_overwrite_finding_id",
    "revision_overwrite_impact_id",
    "revision_overwrite_manifest_id",
    "revision_overwrite_modified_record_id",
    "revision_overwrite_research_result_id",
    "revision_overwrite_score_report_id",
    "sec_source_row_id",
    "sha256_hex_of_bytes",
    "source_record_id",
    "stable_id",
    "UNIT_DRIFT_AUDIT_REPORT_NAMESPACE",
    "UNIT_DRIFT_FAULT_NAMESPACE",
    "UNIT_DRIFT_FINDING_NAMESPACE",
    "UNIT_DRIFT_IMPACT_NAMESPACE",
    "UNIT_DRIFT_MANIFEST_NAMESPACE",
    "UNIT_DRIFT_MODIFIED_RECORD_NAMESPACE",
    "UNIT_DRIFT_RESEARCH_RESULT_NAMESPACE",
    "UNIT_DRIFT_SCORE_REPORT_NAMESPACE",
    "unit_drift_audit_report_id",
    "unit_drift_fault_id",
    "unit_drift_finding_id",
    "unit_drift_impact_id",
    "unit_drift_manifest_id",
    "unit_drift_modified_record_id",
    "unit_drift_research_result_id",
    "unit_drift_score_report_id",
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
REVISION_NAMESPACE = "quantcheck/revision/v1"
SEC_SOURCE_ROW_NAMESPACE = "quantcheck/sec-companyfacts-source-row/v1"
LOOKAHEAD_MODIFIED_RECORD_NAMESPACE = "quantcheck/lookahead-modified-record/v1"
LOOKAHEAD_FAULT_NAMESPACE = "quantcheck/lookahead-fault/v1"
LOOKAHEAD_MANIFEST_NAMESPACE = "quantcheck/lookahead-manifest/v1"
LOOKAHEAD_FINDING_NAMESPACE = "quantcheck/lookahead-finding/v1"
LOOKAHEAD_AUDIT_REPORT_NAMESPACE = "quantcheck/lookahead-audit-report/v1"
LOOKAHEAD_SCORE_REPORT_NAMESPACE = "quantcheck/lookahead-score-report/v1"
LOOKAHEAD_RESEARCH_RESULT_NAMESPACE = "quantcheck/lookahead-research-result/v1"
LOOKAHEAD_IMPACT_NAMESPACE = "quantcheck/lookahead-impact/v1"
UNIT_DRIFT_MODIFIED_RECORD_NAMESPACE = "quantcheck/unit-drift-modified-record/v1"
UNIT_DRIFT_FAULT_NAMESPACE = "quantcheck/unit-drift-fault/v1"
UNIT_DRIFT_MANIFEST_NAMESPACE = "quantcheck/unit-drift-manifest/v1"
UNIT_DRIFT_FINDING_NAMESPACE = "quantcheck/unit-drift-finding/v1"
UNIT_DRIFT_AUDIT_REPORT_NAMESPACE = "quantcheck/unit-drift-audit-report/v1"
UNIT_DRIFT_SCORE_REPORT_NAMESPACE = "quantcheck/unit-drift-score-report/v1"
UNIT_DRIFT_RESEARCH_RESULT_NAMESPACE = "quantcheck/unit-drift-research-result/v1"
UNIT_DRIFT_IMPACT_NAMESPACE = "quantcheck/unit-drift-impact/v1"
DUPLICATE_CREATED_RECORD_NAMESPACE = "quantcheck/duplicate-created-record/v1"
DUPLICATE_FAULT_NAMESPACE = "quantcheck/duplicate-fault/v1"
DUPLICATE_MANIFEST_NAMESPACE = "quantcheck/duplicate-manifest/v1"
DUPLICATE_FINDING_NAMESPACE = "quantcheck/duplicate-finding/v1"
DUPLICATE_AUDIT_REPORT_NAMESPACE = "quantcheck/duplicate-audit-report/v1"
DUPLICATE_SCORE_REPORT_NAMESPACE = "quantcheck/duplicate-score-report/v1"
DUPLICATE_RESEARCH_RESULT_NAMESPACE = "quantcheck/duplicate-research-result/v1"
DUPLICATE_IMPACT_NAMESPACE = "quantcheck/duplicate-impact/v1"
REVISION_OVERWRITE_HISTORY_UNIT_NAMESPACE = "quantcheck/revision-overwrite-history-unit/v1"
REVISION_OVERWRITE_MODIFIED_RECORD_NAMESPACE = "quantcheck/revision-overwrite-modified-record/v1"
REVISION_OVERWRITE_FAULT_NAMESPACE = "quantcheck/revision-overwrite-fault/v1"
REVISION_OVERWRITE_MANIFEST_NAMESPACE = "quantcheck/revision-overwrite-manifest/v1"
REVISION_OVERWRITE_FINDING_NAMESPACE = "quantcheck/revision-overwrite-finding/v1"
REVISION_OVERWRITE_AUDIT_REPORT_NAMESPACE = "quantcheck/revision-overwrite-audit-report/v1"
REVISION_OVERWRITE_SCORE_REPORT_NAMESPACE = "quantcheck/revision-overwrite-score-report/v1"
REVISION_OVERWRITE_RESEARCH_RESULT_NAMESPACE = "quantcheck/revision-overwrite-research-result/v1"
REVISION_OVERWRITE_IMPACT_NAMESPACE = "quantcheck/revision-overwrite-impact/v1"
BENCHMARK_CONFIG_NAMESPACE = "quantcheck/benchmark-config/v1"
BENCHMARK_FAULT_CASE_NAMESPACE = "quantcheck/benchmark-fault-case/v1"
BENCHMARK_CLEAN_CONTROL_CASE_NAMESPACE = "quantcheck/benchmark-clean-control-case/v1"
BENCHMARK_AGGREGATE_REPORT_NAMESPACE = "quantcheck/benchmark-aggregate-report/v1"

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


def revision_id(*, lineage_id: str, sequence: int) -> str:
    """Return the ``rev_`` identifier for one entry of a declared revision lineage.

    The payload is the source-declared lineage key and its sequence number —
    never a list position, never a value comparison. Two records only belong
    to the same revision history when a source explicitly says so; this
    helper never infers that from matching business-key fields.

    This identifier is not stored on any schema field: :class:`FinancialFact`
    is frozen by the Milestone 1 golden vectors, so adding a field would
    change every fact's canonical bytes. Point-in-time revision ordering
    instead reads the lineage and sequence directly from the declared
    ``source_row_key`` (see ``quantcheck.point_in_time``); this helper exists
    so that lineage/sequence pairs have their own stable, testable identity.
    """
    if isinstance(sequence, bool) or not isinstance(sequence, int):
        raise CanonicalizationError(f"sequence must be an integer, got {type(sequence).__name__}")
    if sequence < 1:
        raise CanonicalizationError("sequence must be a positive integer")
    payload = {"lineage_id": lineage_id, "sequence": sequence}
    return stable_id(prefix="rev", namespace=REVISION_NAMESPACE, payload=payload)


def sec_source_row_id(
    *,
    canonical_cik: str,
    taxonomy: str,
    concept: str,
    unit: str,
    source_entry: object,
    duplicate_ordinal: int,
) -> str:
    """Return the stable identity of one SEC Company Facts source occurrence.

    The complete parsed source entry participates in identity, including SEC
    fiscal/frame metadata that has no dedicated field in ``FinancialFact``.
    ``duplicate_ordinal`` preserves the multiplicity of byte-equivalent source
    entries without depending on their position in the SEC list.  It is an
    ordinal within an equivalence class after canonical sorting, not a source
    list index.
    """
    if isinstance(duplicate_ordinal, bool) or not isinstance(duplicate_ordinal, int):
        raise CanonicalizationError(
            f"duplicate_ordinal must be an integer, got {type(duplicate_ordinal).__name__}"
        )
    if duplicate_ordinal < 1:
        raise CanonicalizationError("duplicate_ordinal must be a positive integer")
    payload = {
        "cik": canonical_cik,
        "taxonomy": taxonomy,
        "concept": concept,
        "unit": unit,
        "source_entry": source_entry,
        "duplicate_ordinal": duplicate_ordinal,
    }
    return stable_id(prefix="srow", namespace=SEC_SOURCE_ROW_NAMESPACE, payload=payload)


def lookahead_modified_record_id(
    *,
    original_record_id: str,
    spec_version: str,
    true_available_on: date,
    corrupted_available_on: date,
) -> str:
    """Return the ``rec_`` identity for one exact availability mutation.

    Source and modified occurrences intentionally share the ordinary record
    prefix so the sanitized identifier does not act as an injected-row flag.
    Their versioned namespaces still provide collision separation.
    """
    payload = {
        "original_record_id": original_record_id,
        "spec_version": spec_version,
        "mutation": {
            "field": "available_on",
            "original_date": true_available_on,
            "corrupted_date": corrupted_available_on,
        },
    }
    return stable_id(
        prefix="rec",
        namespace=LOOKAHEAD_MODIFIED_RECORD_NAMESPACE,
        payload=payload,
    )


def lookahead_fault_id(
    *,
    clean_snapshot_id: str,
    original_record_id: str,
    corrupted_record_id: str,
    seed: int,
    spec_version: str,
) -> str:
    """Return the ``fault_`` identity for a selected Look-Ahead mutation."""
    payload = {
        "clean_snapshot_id": clean_snapshot_id,
        "original_record_id": original_record_id,
        "corrupted_record_id": corrupted_record_id,
        "seed": seed,
        "spec_version": spec_version,
    }
    return stable_id(prefix="fault", namespace=LOOKAHEAD_FAULT_NAMESPACE, payload=payload)


def fault_manifest_id(*, manifest_body: object) -> str:
    """Return the ``man_`` identity for a manifest body excluding its id."""
    return stable_id(prefix="man", namespace=LOOKAHEAD_MANIFEST_NAMESPACE, payload=manifest_body)


def lookahead_finding_id(*, finding_body: object) -> str:
    """Return the ``find_`` identity for a finding body excluding its id."""
    return stable_id(prefix="find", namespace=LOOKAHEAD_FINDING_NAMESPACE, payload=finding_body)


def lookahead_audit_report_id(*, report_body: object) -> str:
    """Return the ``arep_`` identity for an audit-report body excluding its id."""
    return stable_id(prefix="arep", namespace=LOOKAHEAD_AUDIT_REPORT_NAMESPACE, payload=report_body)


def lookahead_score_report_id(*, score_body: object) -> str:
    """Return the ``score_`` identity for a score-report body excluding its id."""
    return stable_id(prefix="score", namespace=LOOKAHEAD_SCORE_REPORT_NAMESPACE, payload=score_body)


def lookahead_research_result_id(*, result_body: object) -> str:
    """Return the ``rsch_`` identity for a research-result body excluding its id."""
    return stable_id(
        prefix="rsch", namespace=LOOKAHEAD_RESEARCH_RESULT_NAMESPACE, payload=result_body
    )


def lookahead_impact_id(*, impact_body: object) -> str:
    """Return the ``impact_`` identity for an impact body excluding its id."""
    return stable_id(prefix="impact", namespace=LOOKAHEAD_IMPACT_NAMESPACE, payload=impact_body)


def unit_drift_modified_record_id(
    *,
    original_record_id: str,
    spec_version: str,
    original_value: object,
    corrupted_value: object,
    scale_factor: object,
) -> str:
    """Return the ordinary ``rec_`` identity for one exact value scaling."""
    payload = {
        "original_record_id": original_record_id,
        "spec_version": spec_version,
        "mutation": {
            "field": "value",
            "original_value": original_value,
            "corrupted_value": corrupted_value,
            "scale_factor": scale_factor,
        },
    }
    return stable_id(prefix="rec", namespace=UNIT_DRIFT_MODIFIED_RECORD_NAMESPACE, payload=payload)


def unit_drift_fault_id(
    *,
    clean_snapshot_id: str,
    original_record_id: str,
    corrupted_record_id: str,
    seed: int,
    spec_version: str,
) -> str:
    """Return the ``fault_`` identity for a selected Unit Drift mutation."""
    payload = {
        "clean_snapshot_id": clean_snapshot_id,
        "original_record_id": original_record_id,
        "corrupted_record_id": corrupted_record_id,
        "seed": seed,
        "spec_version": spec_version,
    }
    return stable_id(prefix="fault", namespace=UNIT_DRIFT_FAULT_NAMESPACE, payload=payload)


def unit_drift_manifest_id(*, manifest_body: object) -> str:
    """Return the ``man_`` identity for a Unit Drift manifest body."""
    return stable_id(prefix="man", namespace=UNIT_DRIFT_MANIFEST_NAMESPACE, payload=manifest_body)


def unit_drift_finding_id(*, finding_body: object) -> str:
    """Return the ``find_`` identity for a Unit Drift finding body."""
    return stable_id(prefix="find", namespace=UNIT_DRIFT_FINDING_NAMESPACE, payload=finding_body)


def unit_drift_audit_report_id(*, report_body: object) -> str:
    """Return the ``arep_`` identity for a Unit Drift audit-report body."""
    return stable_id(
        prefix="arep", namespace=UNIT_DRIFT_AUDIT_REPORT_NAMESPACE, payload=report_body
    )


def unit_drift_score_report_id(*, score_body: object) -> str:
    """Return the ``score_`` identity for a Unit Drift score-report body."""
    return stable_id(
        prefix="score", namespace=UNIT_DRIFT_SCORE_REPORT_NAMESPACE, payload=score_body
    )


def unit_drift_research_result_id(*, result_body: object) -> str:
    """Return the ``rsch_`` identity for an aggregate-value result body."""
    return stable_id(
        prefix="rsch", namespace=UNIT_DRIFT_RESEARCH_RESULT_NAMESPACE, payload=result_body
    )


def unit_drift_impact_id(*, impact_body: object) -> str:
    """Return the ``impact_`` identity for a Unit Drift aggregate impact body."""
    return stable_id(prefix="impact", namespace=UNIT_DRIFT_IMPACT_NAMESPACE, payload=impact_body)


def duplicate_created_record_id(
    *,
    original_record_id: str,
    spec_version: str,
    copy_ordinal: int,
) -> str:
    """Return the ordinary ``rec_`` identity for one exact occurrence copy.

    Source and created occurrences intentionally share the ordinary record
    prefix so the sanitized identifier does not act as an injected-row flag.
    """
    if isinstance(copy_ordinal, bool) or not isinstance(copy_ordinal, int):
        raise CanonicalizationError(
            f"copy_ordinal must be an integer, got {type(copy_ordinal).__name__}"
        )
    if copy_ordinal < 1:
        raise CanonicalizationError("copy_ordinal must be a positive integer")
    payload = {
        "original_record_id": original_record_id,
        "spec_version": spec_version,
        "copy_ordinal": copy_ordinal,
    }
    return stable_id(prefix="rec", namespace=DUPLICATE_CREATED_RECORD_NAMESPACE, payload=payload)


def duplicate_fault_id(
    *,
    clean_snapshot_id: str,
    original_record_id: str,
    created_record_id: str,
    seed: int,
    spec_version: str,
) -> str:
    """Return the ``fault_`` identity for a selected Duplicate mutation."""
    payload = {
        "clean_snapshot_id": clean_snapshot_id,
        "original_record_id": original_record_id,
        "created_record_id": created_record_id,
        "seed": seed,
        "spec_version": spec_version,
    }
    return stable_id(prefix="fault", namespace=DUPLICATE_FAULT_NAMESPACE, payload=payload)


def duplicate_manifest_id(*, manifest_body: object) -> str:
    """Return the ``man_`` identity for a Duplicate manifest body."""
    return stable_id(prefix="man", namespace=DUPLICATE_MANIFEST_NAMESPACE, payload=manifest_body)


def duplicate_finding_id(*, finding_body: object) -> str:
    """Return the ``find_`` identity for a Duplicate finding body."""
    return stable_id(prefix="find", namespace=DUPLICATE_FINDING_NAMESPACE, payload=finding_body)


def duplicate_audit_report_id(*, report_body: object) -> str:
    """Return the ``arep_`` identity for a Duplicate audit-report body."""
    return stable_id(prefix="arep", namespace=DUPLICATE_AUDIT_REPORT_NAMESPACE, payload=report_body)


def duplicate_score_report_id(*, score_body: object) -> str:
    """Return the ``score_`` identity for a Duplicate score-report body."""
    return stable_id(prefix="score", namespace=DUPLICATE_SCORE_REPORT_NAMESPACE, payload=score_body)


def duplicate_research_result_id(*, result_body: object) -> str:
    """Return the ``rsch_`` identity for a Duplicate research-result body."""
    return stable_id(
        prefix="rsch", namespace=DUPLICATE_RESEARCH_RESULT_NAMESPACE, payload=result_body
    )


def duplicate_impact_id(*, impact_body: object) -> str:
    """Return the ``impact_`` identity for a Duplicate impact body."""
    return stable_id(prefix="impact", namespace=DUPLICATE_IMPACT_NAMESPACE, payload=impact_body)


def revision_history_unit_id(*, unit_body: object) -> str:
    """Return the ``runit_`` identity for one complete adjacent history unit."""
    return stable_id(
        prefix="runit",
        namespace=REVISION_OVERWRITE_HISTORY_UNIT_NAMESPACE,
        payload=unit_body,
    )


def revision_overwrite_modified_record_id(
    *,
    historical_record_id: str,
    later_record_id: str,
    spec_version: str,
    retained_available_on: date,
    later_value: object,
    later_filed_on: date,
    later_accession_number: str,
    later_form: str | None,
    later_source_name: str,
    later_source_locator: str,
    later_source_row_key: str,
) -> str:
    """Return the ordinary ``rec_`` identity for one later-vintage substitution."""
    payload = {
        "historical_record_id": historical_record_id,
        "later_record_id": later_record_id,
        "spec_version": spec_version,
        "substitution": {
            "retained_available_on": retained_available_on,
            "later_value": later_value,
            "later_filed_on": later_filed_on,
            "later_accession_number": later_accession_number,
            "later_form": later_form,
            "later_source_name": later_source_name,
            "later_source_locator": later_source_locator,
            "later_source_row_key": later_source_row_key,
        },
    }
    return stable_id(
        prefix="rec",
        namespace=REVISION_OVERWRITE_MODIFIED_RECORD_NAMESPACE,
        payload=payload,
    )


def revision_overwrite_fault_id(
    *,
    clean_snapshot_id: str,
    eligibility_unit_id: str,
    corrupted_record_id: str,
    seed: int,
    spec_version: str,
) -> str:
    """Return the ``fault_`` identity for a selected revision history unit."""
    payload = {
        "clean_snapshot_id": clean_snapshot_id,
        "eligibility_unit_id": eligibility_unit_id,
        "corrupted_record_id": corrupted_record_id,
        "seed": seed,
        "spec_version": spec_version,
    }
    return stable_id(prefix="fault", namespace=REVISION_OVERWRITE_FAULT_NAMESPACE, payload=payload)


def revision_overwrite_manifest_id(*, manifest_body: object) -> str:
    return stable_id(
        prefix="man", namespace=REVISION_OVERWRITE_MANIFEST_NAMESPACE, payload=manifest_body
    )


def revision_overwrite_finding_id(*, finding_body: object) -> str:
    return stable_id(
        prefix="find", namespace=REVISION_OVERWRITE_FINDING_NAMESPACE, payload=finding_body
    )


def revision_overwrite_audit_report_id(*, report_body: object) -> str:
    return stable_id(
        prefix="arep", namespace=REVISION_OVERWRITE_AUDIT_REPORT_NAMESPACE, payload=report_body
    )


def revision_overwrite_score_report_id(*, score_body: object) -> str:
    return stable_id(
        prefix="score", namespace=REVISION_OVERWRITE_SCORE_REPORT_NAMESPACE, payload=score_body
    )


def revision_overwrite_research_result_id(*, result_body: object) -> str:
    return stable_id(
        prefix="rsch",
        namespace=REVISION_OVERWRITE_RESEARCH_RESULT_NAMESPACE,
        payload=result_body,
    )


def revision_overwrite_impact_id(*, impact_body: object) -> str:
    return stable_id(
        prefix="impact", namespace=REVISION_OVERWRITE_IMPACT_NAMESPACE, payload=impact_body
    )


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


def benchmark_config_id(*, config_body: object) -> str:
    """Return the ``bench_`` identifier for a normalized logical benchmark.

    ``config_body`` is the complete normalized configuration without its own
    identifier. It must never contain an output root, a temporary directory, a
    working directory, a clock reading, a hostname, or a username.
    """
    return stable_id(
        prefix="bench",
        namespace=BENCHMARK_CONFIG_NAMESPACE,
        payload=config_body,
    )


def benchmark_fault_case_id(*, case_body: object) -> str:
    """Return the ``bcase_`` identifier for one expanded fault case."""
    return stable_id(
        prefix="bcase",
        namespace=BENCHMARK_FAULT_CASE_NAMESPACE,
        payload=case_body,
    )


def benchmark_clean_control_case_id(*, case_body: object) -> str:
    """Return the ``bcase_`` identifier for one expanded clean control.

    Controls use their own namespace so a control can never collide with a
    fault case that happens to normalize to the same body.
    """
    return stable_id(
        prefix="bcase",
        namespace=BENCHMARK_CLEAN_CONTROL_CASE_NAMESPACE,
        payload=case_body,
    )


def benchmark_aggregate_report_id(*, report_body: object) -> str:
    """Return the ``agg_`` identifier for one rebuilt aggregate report."""
    return stable_id(
        prefix="agg",
        namespace=BENCHMARK_AGGREGATE_REPORT_NAMESPACE,
        payload=report_body,
    )
