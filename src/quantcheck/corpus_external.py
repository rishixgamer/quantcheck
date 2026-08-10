"""The externally supplied private/vendor source class.

An ``external_private`` corpus unit is data QuantCheck does not own and may not
redistribute: a customer extract, a vendor point-in-time file, a licensed
fundamentals feed. The whole design goal of this module is that such a unit is
**never required**. Every ordinary test, every quality gate, the committed
corpus definition, and the eligibility census all run to completion with zero
external units present, offline, on a machine that has never seen one.

Three rules make that a structural property rather than a promise:

1. **Nothing is committed.** External data is addressed by a caller-supplied
   directory or by ``QUANTCHECK_EXTERNAL_CORPUS_ROOT``. This repository holds
   no external bytes, no path to any, and no credential for any.
2. **Nothing is quoted.** An external unit's
   :class:`~quantcheck.corpus_schemas.CorpusUnitSpec` is required by schema
   validation to carry no ``content_hash`` and no diversity profile, because
   both are derived from record content. What a repository artifact may state
   about an external unit is its declared identifier, partition, provenance,
   and — from :func:`redacted_external_summary` — a record count. Nothing else.
3. **Nothing is guessed.** A declared manifest that disagrees with the bytes
   beside it is an error. An absent root is not an error; it is the default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from quantcheck.corpus_contract import CorpusContractError
from quantcheck.corpus_schemas import (
    CORPUS_UNIT_ID_PATTERN,
    CorpusHorizon,
    CorpusProvenance,
    CorpusUnitSpec,
)
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.json_types import parse_canonical_date
from quantcheck.schemas import FinancialFact
from quantcheck.serialization import parse_canonical_json

__all__ = [
    "EXTERNAL_CORPUS_MANIFEST_NAME",
    "EXTERNAL_CORPUS_ROOT_ENV",
    "ExternalCorpusError",
    "ExternalUnitDeclaration",
    "external_corpus_root",
    "external_unit_records",
    "external_unit_spec",
    "read_external_declarations",
    "redacted_external_summary",
]

#: The environment variable an operator may point at an out-of-repository
#: dataset. Unset is the supported default and never an error.
EXTERNAL_CORPUS_ROOT_ENV = "QUANTCHECK_EXTERNAL_CORPUS_ROOT"

#: The one file name this module will read from an external root.
EXTERNAL_CORPUS_MANIFEST_NAME = "quantcheck_external_corpus.json"

_REQUIRED_DECLARATION_FIELDS = frozenset(
    {
        "corpus_unit_id",
        "unit_name",
        "partition",
        "audit_dataset_name",
        "source_name",
        "source_locator",
        "snapshot_as_of_date",
        "research_as_of_date",
        "records_file",
        "records_sha256",
        "record_count",
        "supported_fault_profiles",
        "inclusion_rule_ids",
        "publisher",
        "notes",
    }
)


class ExternalCorpusError(CorpusContractError):
    """Raised when an external corpus declaration cannot be trusted."""


@dataclass(frozen=True, slots=True)
class ExternalUnitDeclaration:
    """One external unit as its owner declared it, before any bytes are read."""

    corpus_unit_id: str
    unit_name: str
    partition: str
    audit_dataset_name: str
    source_name: str
    source_locator: str
    snapshot_as_of_date: str
    research_as_of_date: str
    records_file: str
    records_sha256: str
    record_count: int
    supported_fault_profiles: tuple[str, ...]
    inclusion_rule_ids: tuple[str, ...]
    publisher: str
    notes: str


def external_corpus_root(explicit: Path | None = None) -> Path | None:
    """Return the configured external corpus root, or ``None``.

    ``None`` is the ordinary answer and is never an error: the corpus is
    complete without any external unit.
    """
    if explicit is not None:
        return explicit
    configured = os.environ.get(EXTERNAL_CORPUS_ROOT_ENV)
    if not configured:
        return None
    return Path(configured)


def _require(mapping: dict[str, object], field: str) -> object:
    if field not in mapping:
        raise ExternalCorpusError(f"external declaration is missing {field!r}")
    return mapping[field]


def _string(mapping: dict[str, object], field: str) -> str:
    value = _require(mapping, field)
    if not isinstance(value, str) or not value:
        raise ExternalCorpusError(f"external declaration field {field!r} must be a nonempty string")
    return value


def _string_tuple(mapping: dict[str, object], field: str) -> tuple[str, ...]:
    value = _require(mapping, field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ExternalCorpusError(f"external declaration field {field!r} must be a string list")
    return tuple(str(item) for item in value)


def read_external_declarations(root: Path) -> tuple[ExternalUnitDeclaration, ...]:
    """Read and validate the declarations in one external corpus root.

    Only the manifest is read here. Record bytes stay untouched until
    :func:`external_unit_records` is called for a specific unit, so merely
    listing what an operator has available never loads licensed content.
    """
    manifest_path = root / EXTERNAL_CORPUS_MANIFEST_NAME
    if not manifest_path.is_file():
        raise ExternalCorpusError(f"no {EXTERNAL_CORPUS_MANIFEST_NAME} in {root}")
    document = parse_canonical_json(manifest_path.read_bytes())
    if not isinstance(document, dict):
        raise ExternalCorpusError("an external corpus manifest must be a JSON object")
    units = document.get("units")
    if not isinstance(units, list):
        raise ExternalCorpusError("an external corpus manifest must declare a 'units' list")

    declarations: list[ExternalUnitDeclaration] = []
    for entry in units:
        if not isinstance(entry, dict):
            raise ExternalCorpusError("each external unit declaration must be a JSON object")
        unknown = sorted(set(entry) - _REQUIRED_DECLARATION_FIELDS)
        if unknown:
            raise ExternalCorpusError(f"external declaration has unsupported fields: {unknown}")
        unit_id = _string(entry, "corpus_unit_id")
        if CORPUS_UNIT_ID_PATTERN.fullmatch(unit_id) is None:
            raise ExternalCorpusError(f"malformed external corpus unit id: {unit_id!r}")
        count = _require(entry, "record_count")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ExternalCorpusError("external record_count must be a positive integer")
        digest = _string(entry, "records_sha256")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ExternalCorpusError("external records_sha256 must be a lowercase SHA-256 digest")
        records_file = _string(entry, "records_file")
        if "/" in records_file or "\\" in records_file or records_file.startswith("."):
            raise ExternalCorpusError("external records_file must be a plain file name")
        declarations.append(
            ExternalUnitDeclaration(
                corpus_unit_id=unit_id,
                unit_name=_string(entry, "unit_name"),
                partition=_string(entry, "partition"),
                audit_dataset_name=_string(entry, "audit_dataset_name"),
                source_name=_string(entry, "source_name"),
                source_locator=_string(entry, "source_locator"),
                snapshot_as_of_date=_string(entry, "snapshot_as_of_date"),
                research_as_of_date=_string(entry, "research_as_of_date"),
                records_file=records_file,
                records_sha256=digest,
                record_count=count,
                supported_fault_profiles=_string_tuple(entry, "supported_fault_profiles"),
                inclusion_rule_ids=_string_tuple(entry, "inclusion_rule_ids"),
                publisher=_string(entry, "publisher"),
                notes=_string(entry, "notes"),
            )
        )

    identifiers = [declaration.corpus_unit_id for declaration in declarations]
    if len(set(identifiers)) != len(identifiers):
        raise ExternalCorpusError("external corpus unit identifiers must be unique")
    return tuple(sorted(declarations, key=lambda item: item.corpus_unit_id))


def external_unit_spec(declaration: ExternalUnitDeclaration) -> CorpusUnitSpec:
    """Build the repository-safe unit specification for an external unit.

    ``diversity`` and ``content_hash`` are deliberately absent, and
    :class:`~quantcheck.corpus_schemas.CorpusUnitSpec` rejects an external unit
    that supplies either — that validator is the mechanism that stops licensed
    record content from reaching a committed artifact.
    """
    return CorpusUnitSpec(
        corpus_unit_id=declaration.corpus_unit_id,
        unit_name=declaration.unit_name,
        partition=declaration.partition,  # type: ignore[arg-type]
        audit_dataset_name=declaration.audit_dataset_name,
        source_name=declaration.source_name,
        source_locator=declaration.source_locator,
        provenance=CorpusProvenance(
            source_class="external_private",
            license_tier="external_restricted",
            publisher=declaration.publisher,
            retrieval_method="operator_supplied_directory",
            in_repository=False,
            redistributable=False,
            verbatim_source=True,
            notes=declaration.notes,
        ),
        horizon=CorpusHorizon(
            snapshot_as_of_date=parse_canonical_date(declaration.snapshot_as_of_date),
            research_as_of_date=parse_canonical_date(declaration.research_as_of_date),
        ),
        inclusion_rule_ids=declaration.inclusion_rule_ids,
        supported_fault_profiles=declaration.supported_fault_profiles,  # type: ignore[arg-type]
        diversity=None,
        content_hash=None,
    )


def external_unit_records(
    root: Path,
    declaration: ExternalUnitDeclaration,
) -> tuple[FinancialFact, ...]:
    """Load one external unit's records, verifying the declared digest first.

    The digest is checked against the raw bytes before anything is parsed, so a
    file that has drifted from its declaration is refused rather than silently
    admitted under the wrong identity.
    """
    path = root / declaration.records_file
    if not path.is_file():
        raise ExternalCorpusError(f"declared external records file is missing: {path.name}")
    raw_bytes = path.read_bytes()
    actual = sha256_hex_of_bytes(raw_bytes)
    if actual != declaration.records_sha256:
        raise ExternalCorpusError(
            f"external unit {declaration.corpus_unit_id} does not match its declared digest"
        )
    document = parse_canonical_json(raw_bytes)
    if not isinstance(document, list):
        raise ExternalCorpusError("an external records file must be a JSON list of records")
    records = tuple(FinancialFact.model_validate(entry) for entry in document)
    if len(records) != declaration.record_count:
        raise ExternalCorpusError(
            f"external unit {declaration.corpus_unit_id} declared "
            f"{declaration.record_count} records but supplied {len(records)}"
        )
    return records


def redacted_external_summary(declaration: ExternalUnitDeclaration) -> dict[str, object]:
    """The complete set of facts about an external unit a repository may state.

    Everything derived from record *content* is absent by construction: this
    returns identity, partition, and a count, and nothing a licence could
    reasonably cover.
    """
    return {
        "corpus_unit_id": declaration.corpus_unit_id,
        "partition": declaration.partition,
        "source_class": "external_private",
        "license_tier": "external_restricted",
        "in_repository": False,
        "record_count": declaration.record_count,
    }
