"""The held-out gate and the committed corpus freeze record.

The gate is deliberately the same shape as ``quantcheck.release_gate``, which
ADR-010 froze for reserved final seeds, and it draws the same line: a held-out
unit may be *described* freely, but its records may not be *materialized*
without an authorization covering the complete held-out partition.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from quantcheck.corpus_contract import (
    CORPUS_FAULT_PROFILES,
    CORPUS_PARTITIONS,
    CORPUS_SEVERITIES,
)
from quantcheck.corpus_eligibility import census_identity_matches
from quantcheck.corpus_freeze import (
    CORPUS_FREEZE_RECORD_NAME,
    CorpusFreezeError,
    build_corpus_freeze_record,
    load_corpus_freeze_record,
    render_corpus_freeze_bytes,
    verify_corpus_freeze_record,
)
from quantcheck.corpus_gate import (
    HeldOutCorpusAuthorizationError,
    active_held_out_corpus_authorization,
    held_out_corpus_units,
    held_out_unit_authorized,
)
from quantcheck.corpus_registry import (
    corpus_definition_identity_matches,
    corpus_unit_records,
    corpus_unit_spec,
    declared_corpus_id,
    held_out_unit_ids,
    partition_unit_ids,
    require_unit_materialization_authorized,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FREEZE_PATH = REPO_ROOT / CORPUS_FREEZE_RECORD_NAME


def _open_gate(corpus_id: str, unit_ids: Sequence[str]) -> None:
    """Enter and immediately leave the gate, so nesting can be tested directly."""
    with held_out_corpus_units(corpus_id=corpus_id, unit_ids=unit_ids):
        pass


def _capture(function: Callable[..., object], *arguments: object) -> BaseException | None:
    """Return the exception a call raised, or ``None``."""
    try:
        function(*arguments)
    except BaseException as exception:  # noqa: BLE001 - the exception is the assertion subject
        return exception
    return None


class TestTheGateBlocksExecutionNotDescription:
    def test_a_held_out_unit_may_be_named_without_authorization(self) -> None:
        # Identity is committed evidence. Refusing to name it would make the
        # freeze record unreadable by the tooling built to report it.
        assert len(held_out_unit_ids()) == 4
        for unit_id in held_out_unit_ids():
            assert unit_id.startswith("cunit_")

    def test_a_held_out_unit_cannot_be_materialized_without_authorization(self) -> None:
        for unit_id in held_out_unit_ids():
            with pytest.raises(HeldOutCorpusAuthorizationError, match="not authorized"):
                corpus_unit_records(unit_id)

    def test_a_held_out_specification_cannot_be_built_without_authorization(self) -> None:
        with pytest.raises(HeldOutCorpusAuthorizationError):
            corpus_unit_spec(held_out_unit_ids()[0])

    def test_ordinary_partitions_need_no_authorization(self) -> None:
        for partition in ("development", "validation"):
            for unit_id in partition_unit_ids(partition):
                require_unit_materialization_authorized(unit_id)

    def test_an_authorization_covering_a_subset_is_useless(self) -> None:
        subset = held_out_unit_ids()[:2]
        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=subset):
            problem = _capture(corpus_unit_records, subset[0])
        assert isinstance(problem, HeldOutCorpusAuthorizationError)
        assert "complete held-out" in str(problem)

    def test_the_complete_partition_authorizes_materialization(self) -> None:
        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            for unit_id in held_out_unit_ids():
                assert corpus_unit_records(unit_id)

    def test_the_authorization_is_removed_on_the_way_out(self) -> None:
        unit_id = held_out_unit_ids()[0]
        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            assert held_out_unit_authorized(unit_id)
        assert active_held_out_corpus_authorization() is None
        assert not held_out_unit_authorized(unit_id)

    def test_the_authorization_is_removed_even_when_the_block_raises(self) -> None:
        with (
            pytest.raises(RuntimeError, match="boom"),
            held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()),
        ):
            raise RuntimeError("boom")
        assert active_held_out_corpus_authorization() is None

    def test_nesting_is_refused_rather_than_counted(self) -> None:
        # Nesting is the behaviour under test, so the inner block is entered
        # through a helper rather than a second `with` statement.
        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            problem = _capture(_open_gate, declared_corpus_id(), held_out_unit_ids())
        assert isinstance(problem, HeldOutCorpusAuthorizationError)
        assert "already active" in str(problem)

    def test_an_authorization_can_never_be_anonymous(self) -> None:
        problem = _capture(_open_gate, "", held_out_unit_ids())
        assert isinstance(problem, HeldOutCorpusAuthorizationError)
        assert "frozen corpus identifier" in str(problem)

    @pytest.mark.parametrize(
        "unit_ids",
        [
            [],
            ["not-a-unit"],
            ["cunit_0123456789abcdef", "cunit_0123456789abcdef"],
        ],
    )
    def test_a_malformed_partition_is_refused(self, unit_ids: list[str]) -> None:
        assert isinstance(
            _capture(_open_gate, declared_corpus_id(), unit_ids),
            HeldOutCorpusAuthorizationError,
        )


class TestOnlyTheScriptOpensTheGate:
    def test_no_package_module_outside_the_gate_opens_it(self) -> None:
        package = REPO_ROOT / "src" / "quantcheck"
        openers = [
            path.name
            for path in package.glob("*.py")
            if "with held_out_corpus_units(" in path.read_text()
        ]
        assert openers == []

    def test_the_cli_cannot_reach_the_corpus_gate(self) -> None:
        cli = (REPO_ROOT / "src" / "quantcheck" / "cli.py").read_text()
        assert "corpus_gate" not in cli
        assert "held_out_corpus_units" not in cli

    def test_no_environment_variable_can_open_the_gate(self) -> None:
        gate = (REPO_ROOT / "src" / "quantcheck" / "corpus_gate.py").read_text()
        # The module imports nothing that could read process configuration, so
        # there is no environment variable, dotfile, or flag that opens it.
        assert "import os" not in gate
        assert "os.environ" not in gate
        assert "getenv" not in gate
        assert "sys.argv" not in gate

    def test_the_only_script_opener_is_the_corpus_freeze_script(self) -> None:
        scripts = REPO_ROOT / "scripts"
        openers = sorted(
            path.name
            for path in scripts.glob("*.py")
            if "with held_out_corpus_units(" in path.read_text()
        )
        assert openers == ["corpus_freeze.py"]


class TestTheCommittedFreezeRecord:
    def test_the_record_exists_and_reads_without_authorization(self) -> None:
        record = load_corpus_freeze_record(FREEZE_PATH)
        assert active_held_out_corpus_authorization() is None
        assert record.freeze_id.startswith("cfrz_")

    def test_a_missing_record_is_an_explicit_error(self, tmp_path: Path) -> None:
        with pytest.raises(CorpusFreezeError, match="does not exist"):
            load_corpus_freeze_record(tmp_path / "absent.json")

    def test_the_record_is_current(self) -> None:
        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            problems = verify_corpus_freeze_record(FREEZE_PATH)
        assert problems == (), "\n".join(problems)

    def test_the_committed_bytes_round_trip_exactly(self) -> None:
        record = load_corpus_freeze_record(FREEZE_PATH)
        assert render_corpus_freeze_bytes(record) == FREEZE_PATH.read_bytes()

    def test_saved_identities_match_their_own_content(self) -> None:
        record = load_corpus_freeze_record(FREEZE_PATH)
        assert corpus_definition_identity_matches(record.corpus)
        assert census_identity_matches(record.census)

    def test_the_record_freezes_every_partition(self) -> None:
        record = load_corpus_freeze_record(FREEZE_PATH)
        assert {p.partition for p in record.corpus.partitions} == set(CORPUS_PARTITIONS)
        assert set(record.census.covered_partitions) == set(CORPUS_PARTITIONS)

    def test_the_record_lists_exactly_the_held_out_partition(self) -> None:
        record = load_corpus_freeze_record(FREEZE_PATH)
        assert set(record.held_out_unit_ids) == set(held_out_unit_ids())

    def test_every_frozen_cell_is_settled_before_the_freeze(self) -> None:
        """No cell may be left unaccounted for in the frozen record.

        This is the property the whole freeze exists to establish: eligibility
        was decided from clean data, before any detector could be run on the
        held-out partition.
        """
        record = load_corpus_freeze_record(FREEZE_PATH)
        keys = {(r.partition, r.fault_profile, r.severity) for r in record.census.rollups}
        expected = {
            (partition, profile, severity)
            for partition in CORPUS_PARTITIONS
            for profile in CORPUS_FAULT_PROFILES
            for severity in CORPUS_SEVERITIES
        }
        assert keys == expected
        for rollup in record.census.rollups:
            assert rollup.status in {"eligible", "declared_unsupported"}

    def test_the_held_out_partition_is_eligible_in_every_cell(self) -> None:
        record = load_corpus_freeze_record(FREEZE_PATH)
        held_out = [r for r in record.census.rollups if r.partition == "heldout"]
        assert len(held_out) == 12
        assert all(rollup.status == "eligible" for rollup in held_out)

    def test_every_committed_unit_publishes_a_content_hash(self) -> None:
        record = load_corpus_freeze_record(FREEZE_PATH)
        for partition in record.corpus.partitions:
            for unit in partition.units:
                assert unit.provenance.in_repository is True
                assert unit.content_hash is not None
                assert re.fullmatch(r"[0-9a-f]{64}", unit.content_hash)
                assert unit.diversity is not None

    def test_the_record_contains_no_held_out_record_content(self) -> None:
        """The freeze commits hashes and counts, never rows.

        A frozen corpus is evidence about a dataset, not a copy of it; the
        held-out records themselves stay behind the gate.
        """
        payload = FREEZE_PATH.read_bytes().decode()
        assert '"records"' not in payload
        assert '"record_id"' not in payload
        assert '"source_row_key"' not in payload

    def test_rebuilding_reproduces_the_committed_record(self) -> None:
        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            rebuilt = build_corpus_freeze_record()
        assert render_corpus_freeze_bytes(rebuilt) == FREEZE_PATH.read_bytes()

    def test_a_tampered_record_is_reported_rather_than_accepted(self, tmp_path: Path) -> None:
        tampered = tmp_path / CORPUS_FREEZE_RECORD_NAME
        original = FREEZE_PATH.read_bytes().decode()
        tampered.write_text(original.replace('"eligible"', '"declared_unsupported"', 1))
        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            problems = verify_corpus_freeze_record(tampered)
        assert problems
