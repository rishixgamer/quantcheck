"""Write or verify the committed v0.2 corpus freeze record.

This script is the only caller of :func:`quantcheck.corpus_gate.held_out_corpus_units`
outside the test suite, and a static test asserts that. It opens the gate for
the complete declared held-out partition, rebuilds the corpus and its
eligible-unit census, and writes or checks ``corpus_freeze_v0_2.json``.

Usage::

    uv run python scripts/corpus_freeze.py --write
    uv run python scripts/corpus_freeze.py --check
    uv run python scripts/corpus_freeze.py --census   # development + validation only

``--census`` deliberately covers only the ordinary partitions and needs no
authorization: it is the command to run while developing the corpus, so that
the held-out partition stays untouched until the freeze is deliberate.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from quantcheck.corpus_eligibility import build_census  # noqa: E402
from quantcheck.corpus_freeze import (  # noqa: E402
    CORPUS_FREEZE_RECORD_NAME,
    build_corpus_freeze_record,
    render_corpus_freeze_bytes,
    verify_corpus_freeze_record,
)
from quantcheck.corpus_gate import held_out_corpus_units  # noqa: E402
from quantcheck.corpus_registry import (  # noqa: E402
    CORPUS_NAME,
    build_corpus_definition,
    corpus_unit_records,
    declared_corpus_id,
    held_out_unit_ids,
    partition_unit_ids,
)
from quantcheck.corpus_schemas import CorpusEligibilityCensus  # noqa: E402


def _render_census(census: CorpusEligibilityCensus) -> str:
    lines = [
        f"corpus {census.corpus_id}  census {census.census_id}",
        f"partitions: {', '.join(census.covered_partitions)}",
        "",
        f"{'partition':<12} {'fault profile':<24} {'sev':<7} "
        f"{'best':>6} {'total':>7} {'units':>6}  status",
    ]
    for rollup in census.rollups:
        lines.append(
            f"{rollup.partition:<12} {rollup.fault_profile:<24} {rollup.severity:<7} "
            f"{rollup.best_unit_eligible_count:>6} {rollup.partition_eligible_total:>7} "
            f"{rollup.supporting_unit_count:>6}  {rollup.status}"
        )
    return "\n".join(lines)


def _ordinary_census() -> CorpusEligibilityCensus:
    """A development+validation census, built without opening the held-out gate.

    The corpus definition covers every partition and therefore needs the gate,
    so this builds it under an authorization and then hands the census only the
    ordinary partitions' records. The held-out units contribute their declared
    identity and nothing measured.
    """
    with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
        corpus = build_corpus_definition()
    ordinary = ("development", "validation")
    records = {
        unit_id: corpus_unit_records(unit_id)
        for partition in ordinary
        for unit_id in partition_unit_ids(partition)
    }
    return build_census(corpus, records_by_unit=records, partitions=ordinary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="write the freeze record")
    group.add_argument("--check", action="store_true", help="verify the committed record")
    group.add_argument(
        "--census",
        action="store_true",
        help="print the development and validation census without freezing anything",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=REPO_ROOT / CORPUS_FREEZE_RECORD_NAME,
        help=f"freeze record path (default: {CORPUS_FREEZE_RECORD_NAME})",
    )
    arguments = parser.parse_args()

    if arguments.census:
        print(_render_census(_ordinary_census()))
        return 0

    corpus_id = declared_corpus_id()
    with held_out_corpus_units(corpus_id=corpus_id, unit_ids=held_out_unit_ids()):
        if arguments.write:
            record = build_corpus_freeze_record()
            arguments.path.write_bytes(render_corpus_freeze_bytes(record))
            print(f"wrote {arguments.path.name} for {CORPUS_NAME}")
            print(f"  freeze  {record.freeze_id}")
            print(f"  corpus  {record.corpus.corpus_id}")
            print(f"  census  {record.census.census_id}")
            print()
            print(_render_census(record.census))
            return 0

        problems = verify_corpus_freeze_record(arguments.path)

    if problems:
        print(f"{arguments.path.name} is out of date:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"{arguments.path.name} is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
