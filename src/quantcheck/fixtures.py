"""Deterministic, offline, manually reviewed synthetic fixture data.

This module is a pure factory: it never touches the filesystem, the clock,
or any source of randomness. Calling :func:`generate_reviewed_fixture` with
the same ``seed`` always returns the same 26 :class:`~quantcheck.schemas.
FinancialFact` records, byte-identical in their canonical form, regardless of
process, machine, or ``PYTHONHASHSEED``.

The fixture is entirely synthetic: three fictitious entities, four financial
concepts, two quarterly periods, two units, explicit revision histories,
duplicate-candidate occurrences, dimensioned and dimension-free facts, and a
few legitimate but unusual ("hard negative") observations. It contains no
deliberately corrupted records — corruption is injected by later milestones,
never baked into the clean fixture itself.

The checked-in copy lives at ``tests/fixtures/reviewed_financial_facts.json``
and is regenerated/verified with ``scripts/generate_reviewed_fixture.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import NamedTuple

from quantcheck.hashing import source_record_id
from quantcheck.schemas import Dimension, FinancialFact, PeriodType, SourceReference
from quantcheck.serialization import canonical_json_bytes

__all__ = [
    "DEFAULT_FIXTURE_SEED",
    "EXPECTED_FIXTURE_RECORD_COUNT",
    "FIXTURE_NAME",
    "FIXTURE_SOURCE_LOCATOR",
    "FIXTURE_SPEC_VERSION",
    "RowSpec",
    "build_fixture_records",
    "canonical_reviewed_fixture_bytes",
    "default_row_specs",
    "generate_reviewed_fixture",
    "reviewed_fixture_payload",
]

#: The seed used for the checked-in reviewed fixture. Documented, not secret:
#: the fixture is public and its regeneration command is public.
DEFAULT_FIXTURE_SEED = 0

FIXTURE_NAME = "quantcheck-reviewed-fixture"
FIXTURE_SPEC_VERSION = "quantcheck/reviewed-fixture/v1"
FIXTURE_SOURCE_LOCATOR = "tests/fixtures/reviewed_financial_facts.json"
EXPECTED_FIXTURE_RECORD_COUNT = 26

_CONCEPT_NAMESPACE = "us-gaap"

_Q1_START = date(2024, 1, 1)
_Q1_END = date(2024, 3, 31)
_Q2_START = date(2024, 4, 1)
_Q2_END = date(2024, 6, 30)


class RowSpec(NamedTuple):
    """One reviewed fixture row, before it becomes a :class:`FinancialFact`.

    ``row_key`` is the source's own row coordinate: it feeds both
    ``record_id`` (via :func:`~quantcheck.hashing.source_record_id`) and, when
    it carries a ``"#r<n>"`` suffix, the declared revision-lineage marker that
    :mod:`quantcheck.point_in_time` reads.
    """

    row_key: str
    entity_id: str
    entity_name: str
    concept: str
    unit: str
    period_type: PeriodType
    period_start: date | None
    period_end: date
    filed_on: date
    available_on: date
    value: str
    form: str
    accession_number: str
    dimensions: tuple[tuple[str, str], ...] = ()


def _entity_a_name(seed: int) -> str:
    """The one documented, seed-varying field in the fixture.

    Every other row is fixed regardless of seed; this keeps "different seeds
    produce deterministic, documented variation" true without reaching for
    ``random`` merely because the factory accepts a seed.
    """
    return "Aster Analytics Corp" if seed % 2 == 0 else "Aster Analytics Corporation"


def default_row_specs(seed: int = DEFAULT_FIXTURE_SEED) -> tuple[RowSpec, ...]:
    """The 26 reviewed rows, in review order (canonical output does not depend on this order)."""
    entity_a_name = _entity_a_name(seed)

    return (
        # --- Entity A (CIK0000000001): revision history, dimensions, both units, both period types.
        RowSpec(
            "E1-REV-Q1-2024#r1",
            "CIK0000000001",
            entity_a_name,
            "Revenues",
            "USD",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 4, 15),
            date(2024, 4, 15),
            "1000000.00",
            "10-Q",
            "0000000001-24-000001",
        ),
        RowSpec(
            "E1-REV-Q1-2024#r2",
            "CIK0000000001",
            entity_a_name,
            "Revenues",
            "USD",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 5, 20),
            date(2024, 5, 20),
            "1005000.00",
            "10-Q/A",
            "0000000001-24-000002",
        ),
        RowSpec(
            "E1-REV-Q1-2024#r3",
            "CIK0000000001",
            entity_a_name,
            "Revenues",
            "USD",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 8, 10),
            date(2024, 8, 10),
            "998000.00",
            "10-K/A",
            "0000000001-24-000005",
        ),
        RowSpec(
            "E1-REV-Q2-2024",
            "CIK0000000001",
            entity_a_name,
            "Revenues",
            "USD",
            "duration",
            _Q2_START,
            _Q2_END,
            date(2024, 8, 5),
            date(2024, 8, 5),
            "1100000.00",
            "10-Q",
            "0000000001-24-000004",
        ),
        RowSpec(
            "E1-NI-Q1-2024-SEG",
            "CIK0000000001",
            entity_a_name,
            "NetIncomeLoss",
            "USD",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 4, 15),
            date(2024, 4, 15),
            "150000.00",
            "10-Q",
            "0000000001-24-000001",
            (("Segment", "Hardware"), ("Region", "US")),
        ),
        RowSpec(
            "E1-AST-2024Q1",
            "CIK0000000001",
            entity_a_name,
            "Assets",
            "USD",
            "instant",
            None,
            _Q1_END,
            date(2024, 4, 15),
            date(2024, 4, 15),
            "5000000.00",
            "10-Q",
            "0000000001-24-000001",
        ),
        RowSpec(
            "E1-AST-2024Q2",
            "CIK0000000001",
            entity_a_name,
            "Assets",
            "USD",
            "instant",
            None,
            _Q2_END,
            date(2024, 8, 5),
            date(2024, 8, 5),
            "5200000.00",
            "10-Q",
            "0000000001-24-000004",
        ),
        RowSpec(
            "E1-EPS-Q1-2024",
            "CIK0000000001",
            entity_a_name,
            "EarningsPerShareDiluted",
            "USD/shares",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 4, 15),
            date(2024, 4, 15),
            "0.42",
            "10-Q",
            "0000000001-24-000001",
        ),
        RowSpec(
            "E1-EPS-Q2-2024",
            "CIK0000000001",
            entity_a_name,
            "EarningsPerShareDiluted",
            "USD/shares",
            "duration",
            _Q2_START,
            _Q2_END,
            date(2024, 8, 5),
            date(2024, 8, 5),
            "0.46",
            "10-Q",
            "0000000001-24-000004",
        ),
        RowSpec(
            "E1-AST-2024Q1-CONSOL",
            "CIK0000000001",
            entity_a_name,
            "Assets",
            "USD",
            "instant",
            None,
            _Q1_END,
            date(2024, 4, 15),
            date(2024, 4, 15),
            "4800000.00",
            "10-Q",
            "0000000001-24-000001",
            (("ConsolidationItems", "Corporate"),),
        ),
        # --- Entity B (CIK0000000002): a shorter revision history, a loss quarter, a zero EPS.
        RowSpec(
            "E2-NI-Q1-2024#r1",
            "CIK0000000002",
            "Borealis Instruments Inc",
            "NetIncomeLoss",
            "USD",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 4, 20),
            date(2024, 4, 20),
            "250000.00",
            "10-Q",
            "0000000002-24-000001",
        ),
        RowSpec(
            "E2-NI-Q1-2024#r2",
            "CIK0000000002",
            "Borealis Instruments Inc",
            "NetIncomeLoss",
            "USD",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 6, 1),
            date(2024, 6, 1),
            "245000.00",
            "10-Q/A",
            "0000000002-24-000003",
        ),
        RowSpec(
            "E2-NI-Q2-2024",
            "CIK0000000002",
            "Borealis Instruments Inc",
            "NetIncomeLoss",
            "USD",
            "duration",
            _Q2_START,
            _Q2_END,
            date(2024, 8, 12),
            date(2024, 8, 12),
            "-125000.00",
            "10-Q",
            "0000000002-24-000004",
        ),
        RowSpec(
            "E2-REV-Q1-2024",
            "CIK0000000002",
            "Borealis Instruments Inc",
            "Revenues",
            "USD",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 4, 20),
            date(2024, 4, 20),
            "900000.00",
            "10-Q",
            "0000000002-24-000001",
        ),
        RowSpec(
            "E2-REV-Q2-2024-SEG",
            "CIK0000000002",
            "Borealis Instruments Inc",
            "Revenues",
            "USD",
            "duration",
            _Q2_START,
            _Q2_END,
            date(2024, 8, 12),
            date(2024, 8, 12),
            "950000.00",
            "10-Q",
            "0000000002-24-000004",
            (("Segment", "Total"),),
        ),
        RowSpec(
            "E2-AST-2024Q1",
            "CIK0000000002",
            "Borealis Instruments Inc",
            "Assets",
            "USD",
            "instant",
            None,
            _Q1_END,
            date(2024, 4, 20),
            date(2024, 4, 20),
            "3000000.00",
            "10-Q",
            "0000000002-24-000001",
        ),
        RowSpec(
            "E2-EPS-Q1-2024",
            "CIK0000000002",
            "Borealis Instruments Inc",
            "EarningsPerShareDiluted",
            "USD/shares",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 4, 20),
            date(2024, 4, 20),
            "0.00",
            "10-Q",
            "0000000002-24-000001",
        ),
        RowSpec(
            "E2-EPS-Q2-2024",
            "CIK0000000002",
            "Borealis Instruments Inc",
            "EarningsPerShareDiluted",
            "USD/shares",
            "duration",
            _Q2_START,
            _Q2_END,
            date(2024, 8, 12),
            date(2024, 8, 12),
            "-0.31",
            "10-Q",
            "0000000002-24-000004",
        ),
        RowSpec(
            "E2-AST-2024Q2",
            "CIK0000000002",
            "Borealis Instruments Inc",
            "Assets",
            "USD",
            "instant",
            None,
            _Q2_END,
            date(2024, 8, 12),
            date(2024, 8, 12),
            "3100000.00",
            "10-Q",
            "0000000002-24-000004",
        ),
        # --- Entity C (CIK0000000003): an independent-occurrence / duplicate-candidate pair.
        RowSpec(
            "E3-AST-2024Q1-A",
            "CIK0000000003",
            "Cascade Robotics Ltd",
            "Assets",
            "USD",
            "instant",
            None,
            _Q1_END,
            date(2024, 4, 25),
            date(2024, 4, 25),
            "2000000.00",
            "10-Q",
            "0000000003-24-000001",
        ),
        RowSpec(
            "E3-AST-2024Q1-B",
            "CIK0000000003",
            "Cascade Robotics Ltd",
            "Assets",
            "USD",
            "instant",
            None,
            _Q1_END,
            date(2024, 4, 25),
            date(2024, 4, 25),
            "2000000.00",
            "10-Q",
            "0000000003-24-000001",
        ),
        RowSpec(
            "E3-AST-2024Q2",
            "CIK0000000003",
            "Cascade Robotics Ltd",
            "Assets",
            "USD",
            "instant",
            None,
            _Q2_END,
            date(2024, 8, 15),
            date(2024, 8, 15),
            "2150000.00",
            "10-Q",
            "0000000003-24-000002",
        ),
        RowSpec(
            "E3-REV-Q1-2024",
            "CIK0000000003",
            "Cascade Robotics Ltd",
            "Revenues",
            "USD",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 4, 25),
            date(2024, 4, 25),
            "700000.00",
            "10-Q",
            "0000000003-24-000001",
        ),
        RowSpec(
            "E3-REV-Q2-2024",
            "CIK0000000003",
            "Cascade Robotics Ltd",
            "Revenues",
            "USD",
            "duration",
            _Q2_START,
            _Q2_END,
            date(2024, 8, 15),
            date(2024, 8, 15),
            "720000.00",
            "10-Q",
            "0000000003-24-000002",
        ),
        RowSpec(
            "E3-NI-Q1-2024",
            "CIK0000000003",
            "Cascade Robotics Ltd",
            "NetIncomeLoss",
            "USD",
            "duration",
            _Q1_START,
            _Q1_END,
            date(2024, 4, 25),
            date(2024, 4, 25),
            "80000.00",
            "10-Q",
            "0000000003-24-000001",
        ),
        RowSpec(
            "E3-NI-Q2-2024",
            "CIK0000000003",
            "Cascade Robotics Ltd",
            "NetIncomeLoss",
            "USD",
            "duration",
            _Q2_START,
            _Q2_END,
            date(2024, 8, 15),
            date(2024, 8, 15),
            "85000.00",
            "10-Q",
            "0000000003-24-000002",
        ),
    )


def build_fixture_records(row_specs: Sequence[RowSpec]) -> tuple[FinancialFact, ...]:
    """Build ``FinancialFact`` records from row specs, sorted by ``record_id``.

    Sorting the result makes the canonical output independent of the order
    ``row_specs`` was supplied in.
    """
    records = [
        FinancialFact(
            record_id=source_record_id(
                source_name=FIXTURE_NAME,
                source_locator=FIXTURE_SOURCE_LOCATOR,
                source_row_key=spec.row_key,
            ),
            entity_id=spec.entity_id,
            entity_name=spec.entity_name,
            concept_namespace=_CONCEPT_NAMESPACE,
            concept=spec.concept,
            value=Decimal(spec.value),
            unit=spec.unit,
            dimensions=tuple(
                Dimension(axis=axis, member=member) for axis, member in spec.dimensions
            ),
            period_type=spec.period_type,
            period_start=spec.period_start,
            period_end=spec.period_end,
            filed_on=spec.filed_on,
            available_on=spec.available_on,
            form=spec.form,
            accession_number=spec.accession_number,
            source=SourceReference(
                source_name=FIXTURE_NAME,
                source_locator=FIXTURE_SOURCE_LOCATOR,
                source_row_key=spec.row_key,
            ),
        )
        for spec in row_specs
    ]
    return tuple(sorted(records, key=lambda record: record.record_id))


def generate_reviewed_fixture(seed: int = DEFAULT_FIXTURE_SEED) -> tuple[FinancialFact, ...]:
    """Return the 26-record reviewed fixture for a given seed.

    Deterministic and pure: the same seed always returns records with
    identical canonical bytes, in any process, on any machine.
    """
    return build_fixture_records(default_row_specs(seed))


def reviewed_fixture_payload(seed: int = DEFAULT_FIXTURE_SEED) -> dict[str, object]:
    """The full canonical payload written to the checked-in fixture file."""
    records = generate_reviewed_fixture(seed)
    return {
        "fixture_name": FIXTURE_NAME,
        "spec_version": FIXTURE_SPEC_VERSION,
        "seed": seed,
        "record_count": len(records),
        "records": records,
    }


def canonical_reviewed_fixture_bytes(seed: int = DEFAULT_FIXTURE_SEED) -> bytes:
    """The canonical UTF-8 bytes of :func:`reviewed_fixture_payload`."""
    return canonical_json_bytes(reviewed_fixture_payload(seed))
