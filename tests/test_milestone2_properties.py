"""Bounded property-based tests for Milestone 2, and the static safety check
extended to the new modules.

Strategies stay small and reviewable, matching ``tests/test_properties.py``.
"""

from __future__ import annotations

import ast
import inspect
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from quantcheck import audit_boundary, fixtures, point_in_time
from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.fixtures import generate_reviewed_fixture
from quantcheck.hashing import revision_id, source_record_id
from quantcheck.point_in_time import build_dataset_snapshot
from quantcheck.schemas import FinancialFact, SourceReference
from quantcheck.serialization import canonical_json_bytes

_SETTINGS = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)

_FIXTURE = generate_reviewed_fixture()

_row_keys = st.text(
    alphabet=st.characters(min_codepoint=0x41, max_codepoint=0x5A), min_size=1, max_size=8
)
_bounded_dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))
_bounded_amounts = st.decimals(
    min_value=Decimal("-1000000"), max_value=Decimal("1000000"), allow_nan=False, places=2
)


def _independent_fact(row_key: str, available_on: date, value: Decimal) -> FinancialFact:
    return FinancialFact(
        record_id=source_record_id(source_name="p", source_locator="p", source_row_key=row_key),
        entity_id="CIK0000000009",
        concept_namespace="us-gaap",
        concept="Revenues",
        value=value,
        unit="USD",
        period_type="duration",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        filed_on=available_on,
        available_on=available_on,
        source=SourceReference(source_name="p", source_locator="p", source_row_key=row_key),
    )


# --- Availability cutoff -------------------------------------------------------


@given(_bounded_dates, _bounded_dates, _bounded_amounts)
@_SETTINGS
def test_availability_cutoff_is_exactly_available_on_le_as_of_date(
    available_on: date, as_of_date: date, value: Decimal
) -> None:
    fact = _independent_fact("row", available_on, value)
    snapshot = build_dataset_snapshot([fact], dataset_name="d", as_of_date=as_of_date)
    included = fact.record_id in [record.record_id for record in snapshot.records]
    assert included == (available_on <= as_of_date)


@given(_bounded_dates, st.integers(min_value=1, max_value=3650))
@_SETTINGS
def test_moving_the_cutoff_forward_never_removes_an_already_visible_record(
    available_on: date, forward_days: int
) -> None:
    fact = _independent_fact("row", available_on, Decimal("1"))
    early = build_dataset_snapshot([fact], dataset_name="d", as_of_date=available_on)
    later_date = available_on + timedelta(days=forward_days)
    late = build_dataset_snapshot([fact], dataset_name="d", as_of_date=later_date)
    early_ids = {r.record_id for r in early.records}
    late_ids = {r.record_id for r in late.records}
    assert early_ids <= late_ids


# --- Ordering and non-mutation -------------------------------------------------


@given(st.permutations(list(range(len(_FIXTURE)))))
@_SETTINGS
def test_snapshot_identity_is_independent_of_input_permutation(permutation: list[int]) -> None:
    permuted = [_FIXTURE[i] for i in permutation]
    baseline = build_dataset_snapshot(_FIXTURE, dataset_name="d", as_of_date=date(2024, 6, 1))
    shuffled = build_dataset_snapshot(permuted, dataset_name="d", as_of_date=date(2024, 6, 1))
    assert baseline.snapshot_id == shuffled.snapshot_id


@given(st.permutations(list(range(len(_FIXTURE)))))
@_SETTINGS
def test_build_dataset_snapshot_does_not_reorder_the_caller_list_in_place(
    permutation: list[int],
) -> None:
    records = [_FIXTURE[i] for i in permutation]
    before = list(records)
    build_dataset_snapshot(records, dataset_name="d", as_of_date=date(2024, 6, 1))
    assert records == before


@given(st.permutations(list(range(len(_FIXTURE)))))
@_SETTINGS
def test_sanitize_for_audit_is_independent_of_snapshot_record_permutation(
    permutation: list[int],
) -> None:
    snapshot = build_dataset_snapshot(_FIXTURE, dataset_name="d", as_of_date=date(2024, 6, 1))
    reordered_records = tuple(snapshot.records[i] for i in permutation if i < len(snapshot.records))
    if len(reordered_records) != len(snapshot.records):
        return
    from quantcheck.schemas import DatasetSnapshot

    reordered = DatasetSnapshot(
        snapshot_id=snapshot.snapshot_id,
        dataset_name=snapshot.dataset_name,
        as_of_date=snapshot.as_of_date,
        records=reordered_records,
    )
    assert canonical_json_bytes(sanitize_for_audit(snapshot)) == canonical_json_bytes(
        sanitize_for_audit(reordered)
    )


# --- Revision identifiers -------------------------------------------------------


@given(_row_keys, st.integers(min_value=1, max_value=1000))
@_SETTINGS
def test_revision_id_is_deterministic_and_well_formed(lineage_id: str, sequence: int) -> None:
    identifier = revision_id(lineage_id=lineage_id, sequence=sequence)
    assert identifier == revision_id(lineage_id=lineage_id, sequence=sequence)
    assert identifier.startswith("rev_")
    digest = identifier.removeprefix("rev_")
    assert len(digest) == 16
    assert set(digest) <= set("0123456789abcdef")


@given(_row_keys, _row_keys, st.integers(min_value=1, max_value=1000))
@_SETTINGS
def test_revision_id_distinguishes_lineages(lineage_a: str, lineage_b: str, sequence: int) -> None:
    if lineage_a == lineage_b:
        return
    assert revision_id(lineage_id=lineage_a, sequence=sequence) != revision_id(
        lineage_id=lineage_b, sequence=sequence
    )


# --- Static safety check, extended to the Milestone 2 modules -----------------

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "generate_reviewed_fixture.py"


def _script_source() -> str:
    return _SCRIPT_PATH.read_text()


@pytest.mark.parametrize(
    "source_getter",
    [
        pytest.param(lambda: inspect.getsource(fixtures), id="fixtures"),
        pytest.param(lambda: inspect.getsource(point_in_time), id="point_in_time"),
        pytest.param(lambda: inspect.getsource(audit_boundary), id="audit_boundary"),
        pytest.param(_script_source, id="scripts/generate_reviewed_fixture.py"),
    ],
)
def test_no_milestone2_module_calls_uuid_builtin_hash_id_or_random(
    source_getter: object,
) -> None:
    """Mirrors ``tests/test_hashing.py``'s AST-level check for the Milestone 1
    modules, extended to every module Milestone 2 adds."""
    source = source_getter()  # type: ignore[operator]
    tree = ast.parse(source)

    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)

    assert "uuid" not in imported
    assert "random" not in imported
    assert {"hash", "id", "uuid1", "uuid4", "getrandbits", "random"}.isdisjoint(called)
    assert "def " in source
