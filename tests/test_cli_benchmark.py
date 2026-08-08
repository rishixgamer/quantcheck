"""CLI ``benchmark run`` / ``benchmark smoke`` over the existing Milestone 8 runner."""

from __future__ import annotations

import json
from pathlib import Path

import quantcheck as q
from tests.benchmark_support import lookahead_profile, single_profile_config
from tests.cli_helpers import invoke


def test_benchmark_smoke_succeeds_and_matches_the_library_smoke_config(tmp_path: Path) -> None:
    output = tmp_path / "smoke"
    result = invoke(["benchmark", "smoke", "--output", str(output), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["failed"] == 0
    assert payload["incomplete"] == 0
    assert payload["case_count"] == q.SMOKE_CASE_COUNT
    assert payload["benchmark_id"] == q.smoke_benchmark_config().benchmark_id


def test_benchmark_smoke_is_logically_identical_across_output_roots(tmp_path: Path) -> None:
    first = tmp_path / "root-a"
    second = tmp_path / "root-b"
    result_a = invoke(["benchmark", "smoke", "--output", str(first), "--json"])
    result_b = invoke(["benchmark", "smoke", "--output", str(second), "--json"])
    payload_a = json.loads(result_a.stdout)
    payload_b = json.loads(result_b.stdout)
    assert payload_a["benchmark_id"] == payload_b["benchmark_id"]
    assert payload_a["precision"] == payload_b["precision"]
    assert payload_a["recall"] == payload_b["recall"]


def test_benchmark_smoke_resumes_without_redispatching(tmp_path: Path) -> None:
    output = tmp_path / "smoke"
    first = invoke(["benchmark", "smoke", "--output", str(output), "--json"])
    second = invoke(["benchmark", "smoke", "--output", str(output), "--json"])
    assert first.exit_code == 0
    assert second.exit_code == 0
    second_payload = json.loads(second.stdout)
    assert second_payload["dispatched_case_count"] == 0
    assert second_payload["reused_case_count"] == q.SMOKE_CASE_COUNT


def test_benchmark_run_over_a_hand_built_config(tmp_path: Path) -> None:
    config = single_profile_config(lookahead_profile())
    config_path = tmp_path / "config.json"
    config_path.write_bytes(q.canonical_json_bytes(config))
    output = tmp_path / "run"
    result = invoke(
        ["benchmark", "run", "--config", str(config_path), "--output", str(output), "--json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["benchmark_id"] == config.benchmark_id
    assert payload["succeeded"] == payload["case_count"]


def test_benchmark_run_rejects_a_final_seed_configuration(tmp_path: Path) -> None:
    config = single_profile_config(lookahead_profile())
    body = json.loads(q.canonical_json_text(config))
    body["profiles"][0]["seeds"] = [1000]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(body))
    result = invoke(["benchmark", "run", "--config", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_benchmark_run_reports_a_broken_config_identity(tmp_path: Path) -> None:
    config = single_profile_config(lookahead_profile())
    body = json.loads(q.canonical_json_text(config))
    body["benchmark_name"] = "tampered-name"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(body))
    result = invoke(["benchmark", "run", "--config", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_benchmark_run_reports_exit_5_for_a_tampered_prior_success(tmp_path: Path) -> None:
    """A structured failed/incomplete outcome is a stable nonzero exit (5),
    distinct from a configuration error (2) or an artifact error (3)."""
    config = single_profile_config(lookahead_profile())
    config_path = tmp_path / "config.json"
    config_path.write_bytes(q.canonical_json_bytes(config))
    output = tmp_path / "run"
    first = invoke(["benchmark", "run", "--config", str(config_path), "--output", str(output)])
    assert first.exit_code == 0

    matrix = q.expand_benchmark_cases(config)
    case_id = matrix.cases[0].benchmark_case_id
    audit_report_path = output / "public" / "cases" / case_id / "audit_report.json"
    tampered = json.loads(audit_report_path.read_bytes())
    tampered["dataset_name"] = "tampered-dataset-name"
    audit_report_path.write_bytes(json.dumps(tampered).encode())

    second = invoke(
        ["benchmark", "run", "--config", str(config_path), "--output", str(output), "--json"]
    )
    assert second.exit_code == 5
    payload = json.loads(second.stdout)
    assert payload["status"] == "failed"
    assert payload["failed"] + payload["incomplete"] >= 1


def test_benchmark_run_and_smoke_never_expose_a_no_resume_bypass_of_immutability(
    tmp_path: Path,
) -> None:
    """``--no-resume`` re-dispatches, but the underlying store is still
    immutable: identical logical content is a no-op, never an overwrite."""
    output = tmp_path / "smoke"
    invoke(["benchmark", "smoke", "--output", str(output)])
    result = invoke(["benchmark", "smoke", "--output", str(output), "--no-resume", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
