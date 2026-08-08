"""CLI ``explain`` — public-only, manifest-free, never reruns detection."""

from __future__ import annotations

import json
from pathlib import Path

import quantcheck as q
from tests.cli_helpers import fault_case, invoke, write_case_config


def _staged_case(
    tmp_path: Path, profile_name: str = "lookahead_timestamp"
) -> tuple[q.BenchmarkCaseConfig, Path]:
    case = fault_case(profile_name)
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"
    invoke(["inject", "--case", str(case_path), "--output", str(output)])
    invoke(["audit", "--dir", str(output)])
    return case, output


def test_explain_case_status_without_a_finding(tmp_path: Path) -> None:
    case, output = _staged_case(tmp_path)
    result = invoke(["explain", "--dir", str(output), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["benchmark_case_id"] == case.benchmark_case_id
    assert payload["finding_count"] >= 1
    assert isinstance(payload["finding_ids"], list)


def test_explain_one_finding_by_id(tmp_path: Path) -> None:
    case, output = _staged_case(tmp_path)
    status = invoke(["explain", "--dir", str(output), "--json"])
    finding_id = json.loads(status.stdout)["finding_ids"][0]

    result = invoke(["explain", "--dir", str(output), "--finding", finding_id, "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["finding_id"] == finding_id
    assert "explanation" in payload
    assert "rule_id" in payload
    assert "severity" in payload


def test_explain_unknown_finding_id_is_a_user_error(tmp_path: Path) -> None:
    _, output = _staged_case(tmp_path)
    result = invoke(["explain", "--dir", str(output), "--finding", "find_doesnotexist", "--json"])
    assert result.exit_code == 2


def test_explain_before_audit_is_rejected(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"
    invoke(["inject", "--case", str(case_path), "--output", str(output)])

    result = invoke(["explain", "--dir", str(output), "--json"])
    assert result.exit_code == 2


def test_explain_never_touches_the_private_store(tmp_path: Path) -> None:
    """Deleting the private tree entirely must not affect explain."""
    import shutil

    case, output = _staged_case(tmp_path)
    invoke(["evaluate", "--dir", str(output)])
    shutil.rmtree(output / "private")

    result = invoke(["explain", "--dir", str(output), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["benchmark_case_id"] == case.benchmark_case_id
