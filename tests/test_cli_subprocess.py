"""Subprocess execution, stdout/stderr separation, and PYTHONHASHSEED determinism."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.cli_helpers import fault_case, write_case_config


def _run(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run(  # noqa: S603 - fixed, non-shell, test-only invocation
        [sys.executable, "-m", "quantcheck.cli", *args],
        capture_output=True,
        text=True,
        env=full_env,
        timeout=60,
    )


def test_root_help_exits_zero_via_subprocess() -> None:
    result = _run(["--help"])
    assert result.returncode == 0
    assert "inject" in result.stdout
    assert "benchmark" in result.stdout


def test_installed_console_script_help_exits_zero() -> None:
    result = subprocess.run(  # noqa: S603, S607
        ["quantcheck", "--help"], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0


_HELP_COMMANDS = [
    ["inject", "--help"],
    ["audit", "--help"],
    ["evaluate", "--help"],
    ["explain", "--help"],
    ["ingest", "sec", "--help"],
    ["benchmark", "run", "--help"],
    ["benchmark", "smoke", "--help"],
]


@pytest.mark.parametrize("command", _HELP_COMMANDS)
def test_every_command_help_exits_zero(command: list[str]) -> None:
    result = _run(command)
    assert result.returncode == 0, result.stderr


def test_benchmark_smoke_json_stdout_is_parseable_and_stderr_is_separate(tmp_path: Path) -> None:
    output = tmp_path / "smoke"
    result = _run(["benchmark", "smoke", "--output", str(output), "--json"])
    assert result.returncode == 0
    parsed = json.loads(result.stdout)
    assert parsed["status"] == "ok"
    # stdout must contain exactly one JSON line and nothing else.
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    json.loads(lines[0])


def test_user_error_json_is_stdout_only_no_traceback_on_stderr(tmp_path: Path) -> None:
    result = _run(
        [
            "inject",
            "--case",
            str(tmp_path / "missing.json"),
            "--output",
            str(tmp_path / "out"),
            "--json",
        ]
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout


@pytest.mark.parametrize("hashseed", ["0", "1", "987654"])
def test_saved_stage_bytes_are_identical_across_hashseeds(tmp_path: Path, hashseed: str) -> None:
    case = fault_case("lookahead_timestamp")
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)

    output_a = tmp_path / "a"
    output_b = tmp_path / "b"
    for output, seed in ((output_a, "0"), (output_b, hashseed)):
        env = {"PYTHONHASHSEED": seed}
        assert (
            _run(["inject", "--case", str(case_path), "--output", str(output)], env=env).returncode
            == 0
        )
        assert _run(["audit", "--dir", str(output)], env=env).returncode == 0
        assert _run(["evaluate", "--dir", str(output)], env=env).returncode == 0

    for relative in (
        "public/cases/{}/audit_report.json",
        "public/cases/{}/score.json",
        "public/cases/{}/research_summary.json",
        "private/cases/{}/manifest.json",
    ):
        path_suffix = relative.format(case.benchmark_case_id)
        assert (output_a / path_suffix).read_bytes() == (output_b / path_suffix).read_bytes()


def test_option_order_independence_for_json_flag(tmp_path: Path) -> None:
    output = tmp_path / "smoke"
    result_a = _run(["benchmark", "smoke", "--output", str(output), "--json"])
    output2 = tmp_path / "smoke2"
    result_b = _run(["benchmark", "smoke", "--json", "--output", str(output2)])
    assert result_a.returncode == result_b.returncode == 0
    payload_a = json.loads(result_a.stdout)
    payload_b = json.loads(result_b.stdout)
    assert payload_a["benchmark_id"] == payload_b["benchmark_id"]
