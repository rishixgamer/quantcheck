"""Adversarial privacy tests: CLI stdout/human output must never leak
manifests, pre-corruption values, hidden roles, or local paths."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import quantcheck as q
from tests.cli_helpers import fault_case, invoke, write_case_config

_FAMILIES = ("lookahead_timestamp", "unit_drift", "duplicate_observation", "revision_overwrite")


def _run_full_stage(tmp_path: Path, profile_name: str) -> tuple[q.BenchmarkCaseConfig, Path, str]:
    case = fault_case(profile_name)
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"

    combined_stdout = ""
    for command in (
        ["inject", "--case", str(case_path), "--output", str(output), "--json"],
        ["audit", "--dir", str(output), "--json"],
        ["evaluate", "--dir", str(output), "--json"],
        ["explain", "--dir", str(output), "--json"],
    ):
        result = invoke(command)
        assert result.exit_code == 0, (command, result.stdout, result.stderr)
        combined_stdout += result.stdout
        combined_stdout += result.stderr
    return case, output, combined_stdout


@pytest.mark.parametrize("profile_name", _FAMILIES)
def test_json_stdout_never_contains_manifest_field_names(tmp_path: Path, profile_name: str) -> None:
    _, _, combined_stdout = _run_full_stage(tmp_path, profile_name)
    markers = ("original_record", "corrupted_record", "mutation", "target_rank", "selection_digest")
    for marker in markers:
        assert marker not in combined_stdout, marker


@pytest.mark.parametrize("profile_name", _FAMILIES)
def test_stdout_never_contains_the_private_manifest_id(tmp_path: Path, profile_name: str) -> None:
    case, output, combined_stdout = _run_full_stage(tmp_path, profile_name)
    manifest_path = output / "private" / "cases" / case.benchmark_case_id / "manifest.json"
    manifest_body = json.loads(manifest_path.read_bytes())
    manifest_id = manifest_body["manifest_id"]
    assert manifest_id not in combined_stdout


@pytest.mark.parametrize(
    "profile_name", ("lookahead_timestamp", "unit_drift", "revision_overwrite")
)
def test_stdout_never_contains_the_pre_injection_record_identity(
    tmp_path: Path, profile_name: str
) -> None:
    """The clean, pre-injection ``record_id`` the manifest names as its
    target must never surface in any CLI stdout for these three families:
    each of their injectors mints a fresh ``record_id`` for the corrupted
    record, so the original one has no legitimate public reason to appear
    anywhere once a case is corrupted.

    ``duplicate_observation`` is deliberately excluded: its injector *adds* a
    copy rather than replacing the original, so the original record's own
    ``record_id`` legitimately remains visible in public detector evidence —
    it is one half of the real duplicate pair, not hidden answer-key data.

    (Raw numeric *values* are not checked here either: several detectors,
    most notably Unit Drift, legitimately publish a reconstructed "corrected
    value" as part of their own public evidence — that is the detector
    working, not a manifest leak, and can coincidentally match the private
    original value or an unrelated legitimate duplicate elsewhere in the
    fixture.)
    """
    case, output, combined_stdout = _run_full_stage(tmp_path, profile_name)
    manifest_path = output / "private" / "cases" / case.benchmark_case_id / "manifest.json"
    manifest_body = json.loads(manifest_path.read_bytes())
    for entry in manifest_body.get("entries", []):
        original = entry.get("original_record") or entry.get("historical_record")
        if isinstance(original, dict) and "record_id" in original:
            assert original["record_id"] not in combined_stdout


@pytest.mark.parametrize("profile_name", _FAMILIES)
def test_stdout_never_contains_an_absolute_local_path(tmp_path: Path, profile_name: str) -> None:
    _, _, combined_stdout = _run_full_stage(tmp_path, profile_name)
    home = os.path.expanduser("~")
    assert str(tmp_path) not in combined_stdout
    assert home not in combined_stdout
    assert "/private/tmp" not in combined_stdout or str(tmp_path).startswith("/private/tmp")


@pytest.mark.parametrize("profile_name", _FAMILIES)
def test_evaluate_json_never_carries_raw_research_counts_or_deltas(
    tmp_path: Path, profile_name: str
) -> None:
    """The public research summary carries only method/changed/exact_restoration
    booleans; raw counts and deltas are private research-impact data."""
    case = fault_case(profile_name)
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"
    invoke(["inject", "--case", str(case_path), "--output", str(output)])
    invoke(["audit", "--dir", str(output)])
    result = invoke(["evaluate", "--dir", str(output), "--json"])
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "status",
        "command",
        "benchmark_case_id",
        "fault_profile",
        "precision",
        "recall",
        "f1",
        "false_positive_rate",
        "research_method",
        "research_changed",
        "exact_restoration",
    }


def test_audit_is_manifest_blind_at_the_function_boundary() -> None:
    """Static check: neither audit_snapshot nor its detector calls accept a
    manifest parameter anywhere in their signature."""
    import inspect

    from quantcheck import saved_case_workflow as workflow

    for function in (workflow.audit_snapshot, workflow.audit_case):
        parameters = set(inspect.signature(function).parameters)
        assert "manifest" not in parameters


def test_evaluate_is_the_first_stage_with_manifest_parameters() -> None:
    import inspect

    from quantcheck import saved_case_workflow as workflow

    parameters = set(inspect.signature(workflow.evaluate_case).parameters)
    assert "manifest" not in parameters  # reads it from disk, not as a caller-supplied parameter
    # But its underlying dispatch calls do require it; confirm those directly.
    from quantcheck.benchmark_dispatch import replay_for_case, score_for_case

    assert "manifest" in inspect.signature(score_for_case).parameters
    assert "manifest" in inspect.signature(replay_for_case).parameters


@pytest.mark.parametrize("profile_name", _FAMILIES)
def test_inject_output_never_reveals_the_manifest(tmp_path: Path, profile_name: str) -> None:
    case = fault_case(profile_name)
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"
    result = invoke(["inject", "--case", str(case_path), "--output", str(output), "--json"])
    payload = json.loads(result.stdout)
    assert set(payload) == {
        "status",
        "command",
        "benchmark_case_id",
        "case_kind",
        "fault_profile",
        "clean_snapshot_id",
        "corrupted_snapshot_id",
        "injected",
    }
