"""The additive v0.2 execution contract cannot alter the frozen v0.1 surface."""

from __future__ import annotations

from pathlib import Path

from quantcheck.release_checksums import CHECKSUM_COVERED_FILES
from quantcheck.release_contract import FROZEN_SOURCE_FILES
from tests.release_support import historical_v01_checksums_match_tag

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_v01_checksum_manifest_remains_valid_for_its_tag() -> None:
    assert historical_v01_checksums_match_tag() == ()


def test_no_v2_execution_module_is_checksum_covered_as_v01() -> None:
    assert not [path for path in CHECKSUM_COVERED_FILES if "benchmark_v2_" in path]


def test_no_frozen_v01_module_imports_the_v2_execution_contract() -> None:
    offenders = []
    for relative in FROZEN_SOURCE_FILES:
        if (
            relative.endswith(".py")
            and "quantcheck.benchmark_v2" in (REPO_ROOT / relative).read_text()
        ):
            offenders.append(relative)
    assert offenders == []


def test_installed_v01_cli_entry_module_does_not_route_to_v2() -> None:
    text = (REPO_ROOT / "src" / "quantcheck" / "cli.py").read_text()
    assert "benchmark_v2" not in text
