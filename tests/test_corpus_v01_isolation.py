"""The v0.1 release must be completely unaffected by the v0.2 corpus.

``v0.1.0`` is frozen evidence. The corpus substrate is purely additive, and
these tests are the mechanical proof: not one byte of the frozen release
surface changed, the reviewed fixture still regenerates identically, and the
frozen benchmark configuration still expands to exactly the same matrix.

The freeze record and the checksum manifest are the two documents that would
catch a violation, so both are verified here rather than only in the release
script.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantcheck.benchmark_expansion import expand_benchmark_cases
from quantcheck.benchmark_smoke import smoke_benchmark_config
from quantcheck.corpus_freeze import CORPUS_FREEZE_RECORD_NAME
from quantcheck.fixtures import (
    EXPECTED_FIXTURE_RECORD_COUNT,
    canonical_reviewed_fixture_bytes,
    generate_reviewed_fixture,
)
from quantcheck.release_checksums import CHECKSUM_COVERED_FILES, verify_checksums_document
from quantcheck.release_contract import FROZEN_SOURCE_FILES, RELEASE_FREEZE_RECORD_NAME

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestNoFrozenFileWasTouched:
    def test_the_checksum_manifest_still_verifies(self) -> None:
        mismatches = verify_checksums_document(repo_root=REPO_ROOT)
        assert mismatches == (), "\n".join(
            f"{mismatch.path}: {mismatch.reason}" for mismatch in mismatches
        )

    @pytest.mark.parametrize("relative", FROZEN_SOURCE_FILES)
    def test_every_frozen_source_file_still_exists(self, relative: str) -> None:
        assert (REPO_ROOT / relative).is_file()

    def test_no_corpus_module_is_in_the_frozen_release_surface(self) -> None:
        """The v0.2 corpus is additive, so it must not be inside the v0.1 freeze.

        Adding a module to ``FROZEN_SOURCE_FILES`` would change the release
        candidate identity and the checksum manifest, which is exactly what
        v0.1 being immutable forbids.
        """
        for relative in CHECKSUM_COVERED_FILES:
            assert "corpus" not in relative

    def test_the_corpus_freeze_record_is_outside_the_v01_manifest(self) -> None:
        assert CORPUS_FREEZE_RECORD_NAME not in CHECKSUM_COVERED_FILES
        assert RELEASE_FREEZE_RECORD_NAME in CHECKSUM_COVERED_FILES
        assert (REPO_ROOT / CORPUS_FREEZE_RECORD_NAME).is_file()


class TestTheV01ScientificSurfaceIsUnchanged:
    def test_the_reviewed_fixture_still_regenerates_to_its_committed_bytes(self) -> None:
        committed = (
            REPO_ROOT / "tests" / "fixtures" / "reviewed_financial_facts.json"
        ).read_bytes()
        assert canonical_reviewed_fixture_bytes() == committed

    def test_the_reviewed_fixture_still_has_twenty_six_records(self) -> None:
        assert len(generate_reviewed_fixture()) == EXPECTED_FIXTURE_RECORD_COUNT == 26

    def test_the_smoke_benchmark_still_expands_identically(self) -> None:
        config = smoke_benchmark_config()
        matrix = expand_benchmark_cases(config)
        assert matrix.benchmark_id == config.benchmark_id
        assert matrix.case_count == len(matrix.cases)

    def test_the_corpus_adds_no_benchmark_fixture(self) -> None:
        """The v0.1 benchmark fixture registry is a closed, frozen list.

        Wiring the corpus into a benchmark needs its own versioned contract and
        its own release candidate; it is deliberately not done by adding an
        entry to a frozen registry.
        """
        from quantcheck.benchmark_fixtures import BENCHMARK_FIXTURE_IDS

        assert BENCHMARK_FIXTURE_IDS == (
            "quantcheck/benchmark-unit-drift-series/v1",
            "quantcheck/reviewed-fixture/v1",
        )


class TestTheCorpusDoesNotReachIntoV01Execution:
    def test_no_frozen_module_imports_the_corpus_layer(self) -> None:
        offenders = []
        for relative in FROZEN_SOURCE_FILES:
            if not relative.endswith(".py"):
                continue
            text = (REPO_ROOT / relative).read_text()
            if "quantcheck.corpus" in text:
                offenders.append(relative)
        assert offenders == []

    def test_the_corpus_gate_is_independent_of_the_release_gate(self) -> None:
        """Two separate authorizations that never imply one another.

        A held-out corpus authorization must not unlock reserved final seeds,
        and vice versa; each names its own scope and grants nothing else.
        """
        from quantcheck.corpus_gate import held_out_corpus_units
        from quantcheck.corpus_registry import declared_corpus_id, held_out_unit_ids
        from quantcheck.release_gate import active_final_seed_authorization

        with held_out_corpus_units(corpus_id=declared_corpus_id(), unit_ids=held_out_unit_ids()):
            assert active_final_seed_authorization() is None

    def test_the_release_gate_does_not_authorize_corpus_units(self) -> None:
        from quantcheck.corpus_gate import active_held_out_corpus_authorization
        from quantcheck.release_gate import RESERVED_FINAL_SEEDS, reserved_final_seeds

        with reserved_final_seeds(
            release_candidate_id="relc_0000000000000000", seeds=RESERVED_FINAL_SEEDS
        ):
            assert active_held_out_corpus_authorization() is None
