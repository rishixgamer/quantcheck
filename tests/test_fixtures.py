"""Validity, determinism, and regeneration of the reviewed fixture."""

from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

from quantcheck.fixtures import (
    DEFAULT_FIXTURE_SEED,
    EXPECTED_FIXTURE_RECORD_COUNT,
    build_fixture_records,
    canonical_reviewed_fixture_bytes,
    default_row_specs,
    generate_reviewed_fixture,
)
from quantcheck.hashing import revision_id
from quantcheck.point_in_time import parse_declared_revision_lineage
from quantcheck.schemas import FinancialFact
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_FILE = REPO_ROOT / "tests" / "fixtures" / "reviewed_financial_facts.json"
SCRIPT_FILE = REPO_ROOT / "scripts" / "generate_reviewed_fixture.py"

_FIXTURE = generate_reviewed_fixture()


def _load_checked_in_payload() -> dict[str, object]:
    parsed = parse_canonical_json(FIXTURE_FILE.read_bytes())
    assert isinstance(parsed, dict)
    return parsed


def _load_checked_in_records() -> list[FinancialFact]:
    payload = _load_checked_in_payload()
    records = payload["records"]
    assert isinstance(records, list)
    return [FinancialFact.model_validate(item) for item in records]


# --- Basic shape --------------------------------------------------------------


def test_fixture_has_the_expected_record_count() -> None:
    assert len(_FIXTURE) == EXPECTED_FIXTURE_RECORD_COUNT == 26


def test_every_generated_record_is_a_financial_fact() -> None:
    assert all(isinstance(record, FinancialFact) for record in _FIXTURE)


def test_every_record_has_a_unique_record_id() -> None:
    ids = [record.record_id for record in _FIXTURE]
    assert len(set(ids)) == len(ids)


# --- Checked-in file ------------------------------------------------------------


def test_checked_in_fixture_file_exists() -> None:
    assert FIXTURE_FILE.exists()


def test_checked_in_fixture_matches_regenerated_canonical_bytes() -> None:
    assert FIXTURE_FILE.read_bytes() == canonical_reviewed_fixture_bytes(seed=DEFAULT_FIXTURE_SEED)


def test_checked_in_fixture_was_generated_through_the_canonical_path() -> None:
    """The file is exactly `canonical_json_bytes` of the wrapped record list, not
    hand-edited or produced by a competing serializer."""
    payload = {
        "fixture_name": "quantcheck-reviewed-fixture",
        "spec_version": "quantcheck/reviewed-fixture/v1",
        "seed": DEFAULT_FIXTURE_SEED,
        "record_count": EXPECTED_FIXTURE_RECORD_COUNT,
        "records": _FIXTURE,
    }
    assert FIXTURE_FILE.read_bytes() == canonical_json_bytes(payload)


def test_checked_in_fixture_parses_under_strict_schemas() -> None:
    records = _load_checked_in_records()
    assert len(records) == EXPECTED_FIXTURE_RECORD_COUNT
    assert all(isinstance(record, FinancialFact) for record in records)


def test_checked_in_fixture_round_trips_to_identical_canonical_bytes() -> None:
    records = _load_checked_in_records()
    ordered = tuple(sorted(records, key=lambda record: record.record_id))
    payload = {
        "fixture_name": "quantcheck-reviewed-fixture",
        "spec_version": "quantcheck/reviewed-fixture/v1",
        "seed": DEFAULT_FIXTURE_SEED,
        "record_count": len(ordered),
        "records": ordered,
    }
    assert canonical_json_bytes(payload) == FIXTURE_FILE.read_bytes()


# --- Content coverage -----------------------------------------------------------


def test_fixture_covers_multiple_entities() -> None:
    assert len({record.entity_id for record in _FIXTURE}) >= 3


def test_fixture_covers_multiple_concepts() -> None:
    assert len({record.concept for record in _FIXTURE}) >= 4


def test_fixture_covers_multiple_periods() -> None:
    periods = {(record.period_start, record.period_end) for record in _FIXTURE}
    assert len(periods) >= 2


def test_fixture_covers_multiple_units() -> None:
    assert {record.unit for record in _FIXTURE} == {"USD", "USD/shares"}


def test_fixture_covers_both_period_types() -> None:
    assert {record.period_type for record in _FIXTURE} == {"instant", "duration"}


def test_fixture_covers_dimensioned_and_dimension_free_facts() -> None:
    with_dims = [record for record in _FIXTURE if record.dimensions]
    without_dims = [record for record in _FIXTURE if not record.dimensions]
    assert with_dims and without_dims


def test_fixture_covers_a_multi_dimension_record() -> None:
    assert any(len(record.dimensions) >= 2 for record in _FIXTURE)


def test_fixture_covers_multiple_filing_and_availability_dates() -> None:
    assert len({record.filed_on for record in _FIXTURE}) > 1
    assert len({record.available_on for record in _FIXTURE}) > 1


def test_fixture_includes_same_day_availability_cases() -> None:
    assert any(record.filed_on == record.available_on for record in _FIXTURE)


def test_fixture_includes_hard_negative_zero_value() -> None:
    assert any(record.value == Decimal("0.00") for record in _FIXTURE)


def test_fixture_includes_hard_negative_negative_value() -> None:
    assert any(record.value < 0 for record in _FIXTURE)


# --- Revision histories -----------------------------------------------------------


def _lineage_groups() -> dict[str, list[FinancialFact]]:
    groups: dict[str, list[FinancialFact]] = {}
    for record in _FIXTURE:
        lineage = parse_declared_revision_lineage(record.source.source_row_key)
        if lineage is not None:
            groups.setdefault(lineage.lineage_id, []).append(record)
    return groups


def test_fixture_declares_at_least_one_revision_history() -> None:
    groups = _lineage_groups()
    assert len(groups) >= 1


def test_fixture_declares_a_history_with_more_than_one_revision() -> None:
    groups = _lineage_groups()
    assert any(len(members) > 1 for members in groups.values())


def test_fixture_declares_two_independent_revision_histories() -> None:
    assert len(_lineage_groups()) == 2


def test_every_declared_revision_has_a_stable_revision_id() -> None:
    for _lineage_id, members in _lineage_groups().items():
        for record in members:
            lineage = parse_declared_revision_lineage(record.source.source_row_key)
            assert lineage is not None
            identifier = revision_id(lineage_id=lineage.lineage_id, sequence=lineage.sequence)
            assert identifier.startswith("rev_")


def test_revision_sequence_numbers_within_a_history_are_unique() -> None:
    for members in _lineage_groups().values():
        sequences = []
        for record in members:
            lineage = parse_declared_revision_lineage(record.source.source_row_key)
            assert lineage is not None
            sequences.append(lineage.sequence)
        assert len(set(sequences)) == len(sequences)


# --- Independent occurrences / duplicate candidates --------------------------------


def _economic_key(record: FinancialFact) -> tuple[object, ...]:
    return (
        record.entity_id,
        record.concept_namespace,
        record.concept,
        record.unit,
        tuple((d.axis, d.member) for d in record.dimensions),
        record.period_type,
        record.period_start,
        record.period_end,
    )


def test_fixture_contains_an_independent_duplicate_candidate_pair() -> None:
    non_lineage = [
        record
        for record in _FIXTURE
        if parse_declared_revision_lineage(record.source.source_row_key) is None
    ]
    keys = [_economic_key(record) for record in non_lineage]
    values = [record.value for record in non_lineage]
    matches = [
        (a, b)
        for i, a in enumerate(non_lineage)
        for j, b in enumerate(non_lineage)
        if i < j and keys[i] == keys[j] and values[i] == values[j]
    ]
    assert len(matches) >= 1
    for a, b in matches:
        assert a.record_id != b.record_id


def test_fixture_contains_a_same_business_key_different_dimension_pair() -> None:
    """Looks similar (same entity/concept/period/unit); differs only in dimensions."""
    non_lineage = [
        record
        for record in _FIXTURE
        if parse_declared_revision_lineage(record.source.source_row_key) is None
    ]
    business_keys = [
        (r.entity_id, r.concept, r.unit, r.period_type, r.period_start, r.period_end)
        for r in non_lineage
    ]
    matches = [
        (a, b)
        for i, (a, ka) in enumerate(zip(non_lineage, business_keys, strict=True))
        for j, (b, kb) in enumerate(zip(non_lineage, business_keys, strict=True))
        if i < j and ka == kb and a.dimensions != b.dimensions
    ]
    assert len(matches) >= 1


# --- Stable provenance -----------------------------------------------------------


def test_fixture_uses_one_stable_source_name_and_locator() -> None:
    assert {record.source.source_name for record in _FIXTURE} == {"quantcheck-reviewed-fixture"}
    assert {record.source.source_locator for record in _FIXTURE} == {
        "tests/fixtures/reviewed_financial_facts.json"
    }


def test_every_row_has_a_unique_source_row_key() -> None:
    row_keys = [record.source.source_row_key for record in _FIXTURE]
    assert len(set(row_keys)) == len(row_keys)


# --- Determinism and reordering ----------------------------------------------------


def test_same_seed_always_reproduces_the_same_fixture() -> None:
    first = generate_reviewed_fixture(seed=DEFAULT_FIXTURE_SEED)
    second = generate_reviewed_fixture(seed=DEFAULT_FIXTURE_SEED)
    assert canonical_json_bytes(list(first)) == canonical_json_bytes(list(second))


def test_different_seed_only_changes_the_one_documented_field() -> None:
    seed_0 = generate_reviewed_fixture(seed=0)
    seed_1 = generate_reviewed_fixture(seed=1)
    assert len(seed_0) == len(seed_1)

    by_id_0 = {record.record_id: record for record in seed_0}
    by_id_1 = {record.record_id: record for record in seed_1}
    assert by_id_0.keys() == by_id_1.keys()

    changed_fields: set[str] = set()
    for record_id, record_0 in by_id_0.items():
        record_1 = by_id_1[record_id]
        if record_0 != record_1:
            for field in type(record_0).model_fields:
                if getattr(record_0, field) != getattr(record_1, field):
                    changed_fields.add(field)

    assert changed_fields == {"entity_name"}


def test_reordering_generator_inputs_does_not_change_canonical_output() -> None:
    forward = build_fixture_records(default_row_specs())
    backward = build_fixture_records(tuple(reversed(default_row_specs())))
    assert canonical_json_bytes(list(forward)) == canonical_json_bytes(list(backward))
    assert [r.record_id for r in forward] == [r.record_id for r in backward]


def test_generated_records_are_already_sorted_by_record_id() -> None:
    ids = [record.record_id for record in _FIXTURE]
    assert ids == sorted(ids)


# --- Regeneration script -----------------------------------------------------------


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("quantcheck_fixture_regen_script", SCRIPT_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_check_mode_passes_against_the_real_checked_in_fixture() -> None:
    module = _load_script_module()
    assert module.main(["--check"]) == 0


def test_script_check_mode_fails_when_the_checked_in_file_is_missing(tmp_path: Path) -> None:
    module = _load_script_module()
    module.FIXTURE_PATH = tmp_path / "missing.json"  # type: ignore[attr-defined]
    assert module.main(["--check"]) == 1


def test_script_check_mode_fails_when_the_checked_in_file_drifts(tmp_path: Path) -> None:
    module = _load_script_module()
    drifted = tmp_path / "reviewed_financial_facts.json"
    drifted.write_bytes(b'{"fixture_name":"not-canonical"}')
    module.FIXTURE_PATH = drifted  # type: ignore[attr-defined]
    assert module.main(["--check"]) == 1


def test_script_write_mode_produces_bytes_that_then_pass_check(tmp_path: Path) -> None:
    module = _load_script_module()
    module.FIXTURE_PATH = tmp_path / "nested" / "reviewed_financial_facts.json"  # type: ignore[attr-defined]
    assert module.main([]) == 0
    assert module.FIXTURE_PATH.read_bytes() == canonical_reviewed_fixture_bytes()
    assert module.main(["--check"]) == 0


@pytest.mark.parametrize("seed", [0, 1, 2, 42])
def test_script_check_mode_respects_the_seed_argument(tmp_path: Path, seed: int) -> None:
    module = _load_script_module()
    target = tmp_path / "reviewed_financial_facts.json"
    target.write_bytes(canonical_reviewed_fixture_bytes(seed=seed))
    module.FIXTURE_PATH = target  # type: ignore[attr-defined]
    assert module.main(["--check", "--seed", str(seed)]) == 0
