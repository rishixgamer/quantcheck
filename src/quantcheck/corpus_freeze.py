"""The committed v0.2 corpus freeze record.

``corpus_freeze_v0_2.json`` is what makes the held-out partition *held out*
rather than merely unexamined. It commits, before any v0.2 detector has run:

* every unit's identifier, partition, provenance, horizon, and content hash;
* every unit's measured diversity profile;
* the complete eligible-unit census — exact denominators by unit, profile, and
  severity, and the partition rollup that says whether each of the twelve
  fault/severity cells is eligible or declared unsupported.

Two properties follow from committing it.

**Cells are settled before the freeze.** The census in the record is the
evidence that every intended cell was measurable *before* anyone could look at
held-out detector performance. A cell that later disappoints cannot be quietly
re-declared, because the declaration is in the frozen bytes.

**Held-out description survives without authorization.** Reading this record
needs no authorization at all — it is committed evidence. Rebuilding it does,
because rebuilding materializes held-out records. That is the same
execution-not-representation split ADR-010 froze for reserved final seeds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from quantcheck.corpus_contract import CORPUS_SPEC_VERSION, CorpusContractError
from quantcheck.corpus_eligibility import build_census, census_identity_matches
from quantcheck.corpus_registry import (
    build_corpus_definition,
    corpus_definition_identity_matches,
    corpus_unit_records,
    held_out_unit_ids,
    partition_unit_ids,
)
from quantcheck.corpus_schemas import (
    CorpusDefinition,
    CorpusEligibilityCensus,
    CorpusModel,
    CorpusUnitIds,
    Token,
)
from quantcheck.hashing import stable_id
from quantcheck.schemas import FinancialFact
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

__all__ = [
    "CORPUS_FREEZE_NAMESPACE",
    "CORPUS_FREEZE_RECORD_NAME",
    "CorpusFreezeError",
    "CorpusFreezeRecord",
    "build_corpus_freeze_record",
    "load_corpus_freeze_record",
    "render_corpus_freeze_bytes",
    "verify_corpus_freeze_record",
]

CORPUS_FREEZE_RECORD_NAME = "corpus_freeze_v0_2.json"
CORPUS_FREEZE_NAMESPACE = "quantcheck/corpus-freeze/v2"


class CorpusFreezeError(CorpusContractError):
    """Raised when a corpus freeze record cannot be produced or trusted."""


class CorpusFreezeRecord(CorpusModel):
    """The complete frozen description of one v0.2 corpus."""

    freeze_id: Token
    spec_version: Literal["quantcheck/corpus/v2"] = CORPUS_SPEC_VERSION
    corpus: CorpusDefinition
    census: CorpusEligibilityCensus
    held_out_unit_ids: CorpusUnitIds

    def model_post_init(self, context: object, /) -> None:
        if self.census.corpus_id != self.corpus.corpus_id:
            raise ValueError("the census must describe the frozen corpus")
        declared = {
            unit.corpus_unit_id
            for partition in self.corpus.partitions
            if partition.partition == "heldout"
            for unit in partition.units
        }
        if declared != set(self.held_out_unit_ids):
            raise ValueError("held_out_unit_ids must list exactly the held-out partition")
        covered = set(self.census.covered_partitions)
        if covered != {"development", "validation", "heldout"}:
            raise ValueError("a freeze record's census must cover every partition")


def _freeze_body(
    *,
    corpus: CorpusDefinition,
    census: CorpusEligibilityCensus,
    held_out: tuple[str, ...],
) -> dict[str, object]:
    return {
        "spec_version": CORPUS_SPEC_VERSION,
        "corpus": corpus,
        "census": census,
        "held_out_unit_ids": held_out,
    }


def build_corpus_freeze_record() -> CorpusFreezeRecord:
    """Build the freeze record from the registry.

    Requires an active held-out authorization covering the complete held-out
    partition, because it materializes every unit in order to hash it and count
    its eligible units.
    """
    corpus = build_corpus_definition()
    records_by_unit: dict[str, tuple[FinancialFact, ...]] = {}
    for partition_spec in corpus.partitions:
        for unit_id in partition_unit_ids(partition_spec.partition):
            records_by_unit[unit_id] = corpus_unit_records(unit_id)
    census = build_census(corpus, records_by_unit=records_by_unit)
    body = _freeze_body(
        corpus=corpus,
        census=census,
        held_out=held_out_unit_ids(),
    )
    freeze_id = stable_id(prefix="cfrz", namespace=CORPUS_FREEZE_NAMESPACE, payload=body)
    return CorpusFreezeRecord.model_validate({"freeze_id": freeze_id, **body})


def render_corpus_freeze_bytes(record: CorpusFreezeRecord) -> bytes:
    """The canonical bytes a freeze record is committed as."""
    return canonical_json_bytes(record)


def load_corpus_freeze_record(path: Path) -> CorpusFreezeRecord:
    """Read a committed freeze record. Needs no authorization.

    A held-out unit's identity, hash, and eligibility counts are committed
    evidence; refusing to deserialize them would make the frozen corpus
    unreadable by the very tooling built to report it.
    """
    if not path.is_file():
        raise CorpusFreezeError(f"corpus freeze record does not exist: {path}")
    document = parse_canonical_json(path.read_bytes())
    return CorpusFreezeRecord.model_validate(document)


def verify_corpus_freeze_record(path: Path) -> tuple[str, ...]:
    """Compare a committed freeze record against a freshly built one.

    Returns every disagreement rather than the first, so one run reports the
    whole picture; an empty result means the record is current. Requires the
    held-out authorization, because verifying means rebuilding.
    """
    saved = load_corpus_freeze_record(path)
    rebuilt = build_corpus_freeze_record()
    problems: list[str] = []
    if not corpus_definition_identity_matches(saved.corpus):
        problems.append("the saved corpus identifier does not match its own content")
    if not census_identity_matches(saved.census):
        problems.append("the saved census identifier does not match its own content")
    if saved.corpus.corpus_id != rebuilt.corpus.corpus_id:
        problems.append(
            f"corpus identifier drifted: saved {saved.corpus.corpus_id}, "
            f"rebuilt {rebuilt.corpus.corpus_id}"
        )
    if saved.census.census_id != rebuilt.census.census_id:
        problems.append(
            f"census identifier drifted: saved {saved.census.census_id}, "
            f"rebuilt {rebuilt.census.census_id}"
        )
    if render_corpus_freeze_bytes(saved) != render_corpus_freeze_bytes(rebuilt):
        problems.append("freeze record bytes differ from a freshly built record")
    return tuple(problems)
