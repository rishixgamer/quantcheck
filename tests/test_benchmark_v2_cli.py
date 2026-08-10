"""The additive module CLI uses the same v0.2 schemas and artifact store."""

from __future__ import annotations

from pathlib import Path

from _pytest.capture import CaptureFixture

from quantcheck.benchmark_v2_cli import main
from quantcheck.benchmark_v2_schemas import BenchmarkV2Evaluation, DetectorExecutionV2
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json
from tests.benchmark_v2_support import case_for, case_result


def _write(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def test_audit_cli_selects_one_detector_and_writes_the_execution(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    audit_input = case_result(
        "lookahead_timestamp", "development-stress"
    ).corrupted_execution.audit_input
    input_path = tmp_path / "audit_input.json"
    output_path = tmp_path / "execution.json"
    _write(input_path, audit_input)
    assert (
        main(
            [
                "audit",
                "--audit-input",
                str(input_path),
                "--output",
                str(output_path),
                "--detectors",
                "lookahead_timestamp",
                "--json",
            ]
        )
        == 0
    )
    execution = DetectorExecutionV2.model_validate(parse_canonical_json(output_path.read_bytes()))
    assert execution.config.selected_detectors == ("lookahead_timestamp",)
    stdout = capsys.readouterr().out
    assert execution.detector_execution_id in stdout
    assert "manifest" not in stdout


def test_audit_cli_accepts_an_explicit_pair(tmp_path: Path) -> None:
    audit_input = case_result(
        "lookahead_timestamp", "development-stress"
    ).corrupted_execution.audit_input
    input_path = tmp_path / "audit_input.json"
    output_path = tmp_path / "execution.json"
    _write(input_path, audit_input)
    assert (
        main(
            [
                "audit",
                "--audit-input",
                str(input_path),
                "--output",
                str(output_path),
                "--detectors",
                "unit_drift,duplicate_observation",
            ]
        )
        == 0
    )
    execution = DetectorExecutionV2.model_validate(parse_canonical_json(output_path.read_bytes()))
    assert execution.config.selected_detectors == (
        "duplicate_observation",
        "unit_drift",
    )


def test_run_case_cli_preserves_public_private_separation(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    case = case_for(
        "lookahead_timestamp",
        unit_name="development-stress",
    )
    case_path = tmp_path / "case.json"
    output = tmp_path / "result"
    _write(case_path, case)
    assert (
        main(
            [
                "run-case",
                "--case",
                str(case_path),
                "--output",
                str(output),
                "--json",
            ]
        )
        == 0
    )
    assert sorted(path.name for path in (output / "public").glob("*.json")) == [
        "case_config.json",
        "clean_control_execution.json",
        "corrupted_execution.json",
        "evaluation.json",
    ]
    assert sorted(path.name for path in (output / "private").glob("*.json")) == [
        "clean_snapshot.json",
        "corrupted_snapshot.json",
        "manifest.json",
    ]
    evaluation = BenchmarkV2Evaluation.model_validate(
        parse_canonical_json((output / "public" / "evaluation.json").read_bytes())
    )
    assert evaluation.all_primary_faults_detected is True
    stdout = capsys.readouterr().out
    assert evaluation.evaluation_id in stdout
    assert "manifest_id" not in stdout
    assert "selection_digest" not in stdout


def test_invalid_detector_selection_is_a_user_error(
    tmp_path: Path,
    capsys: CaptureFixture[str],
) -> None:
    audit_input = case_result(
        "lookahead_timestamp", "development-stress"
    ).corrupted_execution.audit_input
    input_path = tmp_path / "audit_input.json"
    _write(input_path, audit_input)
    code = main(
        [
            "audit",
            "--audit-input",
            str(input_path),
            "--output",
            str(tmp_path / "execution.json"),
            "--detectors",
            "unknown",
            "--json",
        ]
    )
    assert code == 2
    stderr = capsys.readouterr().err
    assert "input configuration was rejected" in stderr
    assert "Traceback" not in stderr
