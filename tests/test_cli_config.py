"""Strict CLI configuration loading and the stable exit-code taxonomy."""

from __future__ import annotations

import json
from pathlib import Path

import quantcheck as q
from tests.cli_helpers import fault_case, invoke, write_case_config


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    result = invoke(
        ["inject", "--case", str(tmp_path / "missing.json"), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 2


def test_directory_instead_of_file_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "a-directory.json"
    directory.mkdir()
    result = invoke(["inject", "--case", str(directory), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_non_json_suffix_is_rejected(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    path = tmp_path / "case.txt"
    path.write_bytes(q.canonical_json_bytes(case))
    result = invoke(["inject", "--case", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_malformed_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "case.json"
    path.write_text("{not valid json")
    result = invoke(["inject", "--case", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_invalid_utf8_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "case.json"
    path.write_bytes(b"\xff\xfe\x00\x01")
    result = invoke(["inject", "--case", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_json_float_is_rejected_rather_than_silently_widened(tmp_path: Path) -> None:
    """A JSON float in a Decimal-typed field must be rejected, never coerced."""
    case = fault_case("lookahead_timestamp")
    body = json.loads(q.canonical_json_text(case))
    body["max_targets"] = 1.5
    path = tmp_path / "case.json"
    path.write_text(json.dumps(body))
    result = invoke(["inject", "--case", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    body = json.loads(q.canonical_json_text(case))
    body["unexpected_extra_field"] = "surprise"
    path = tmp_path / "case.json"
    path.write_text(json.dumps(body))
    result = invoke(["inject", "--case", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_invalid_enum_value_is_rejected(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    body = json.loads(q.canonical_json_text(case))
    body["case_kind"] = "not_a_real_kind"
    path = tmp_path / "case.json"
    path.write_text(json.dumps(body))
    result = invoke(["inject", "--case", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_broken_identity_relationship_is_rejected(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    body = json.loads(q.canonical_json_text(case))
    body["severity"] = "high" if case.severity != "high" else "low"
    path = tmp_path / "case.json"
    path.write_text(json.dumps(body))
    result = invoke(["inject", "--case", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_prohibited_final_seed_is_rejected(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    body = json.loads(q.canonical_json_text(case))
    body["seed"] = 1000
    body["seed_class"] = "validation"
    path = tmp_path / "case.json"
    path.write_text(json.dumps(body))
    result = invoke(["inject", "--case", str(path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_every_final_seed_is_rejected(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    for seed in range(1000, 1010):
        body = json.loads(q.canonical_json_text(case))
        body["seed"] = seed
        body["seed_class"] = "validation"
        path = tmp_path / f"case-{seed}.json"
        path.write_text(json.dumps(body))
        result = invoke(["inject", "--case", str(path), "--output", str(tmp_path / f"out-{seed}")])
        assert result.exit_code == 2, seed


def test_there_is_no_flag_to_authorize_a_final_seed() -> None:
    """No CLI option anywhere can bypass the final-seed prohibition."""
    for command in (
        ["inject", "--help"],
        ["audit", "--help"],
        ["evaluate", "--help"],
        ["benchmark", "run", "--help"],
        ["benchmark", "smoke", "--help"],
    ):
        result = invoke(command)
        assert result.exit_code == 0
        lowered = result.stdout.lower()
        for forbidden in ("--held-out", "--release", "--final", "--allow-final", "--force-seed"):
            assert forbidden not in lowered

    assert not hasattr(q, "authorize_final_seed")
    assert not hasattr(q, "release_seed_override")


def test_case_config_identity_is_recomputed_and_verified(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    result = invoke(["inject", "--case", str(case_path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 0
