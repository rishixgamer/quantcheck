"""CLI ``inject``/``audit``/``evaluate`` saved-stage workflow and equivalence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import quantcheck as q
from tests.cli_helpers import clean_control_case, fault_case, invoke, write_case_config

_FAMILIES = ("lookahead_timestamp", "unit_drift", "duplicate_observation", "revision_overwrite")


@pytest.mark.parametrize("profile_name", _FAMILIES)
def test_staged_workflow_matches_dispatch_benchmark_case(tmp_path: Path, profile_name: str) -> None:
    case = fault_case(profile_name)
    direct = q.dispatch_benchmark_case(case)

    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"

    assert invoke(["inject", "--case", str(case_path), "--output", str(output)]).exit_code == 0
    assert invoke(["audit", "--dir", str(output)]).exit_code == 0
    assert invoke(["evaluate", "--dir", str(output)]).exit_code == 0

    public = output / "public" / "cases" / case.benchmark_case_id
    private = output / "private" / "cases" / case.benchmark_case_id

    audit_input = q.AuditInputSnapshot.model_validate(
        json.loads((public / "audit_input.json").read_bytes())
    )
    audit_report = q.AuditReport.model_validate(
        json.loads((public / "audit_report.json").read_bytes())
    )
    score = q.BenchmarkCaseScore.model_validate(json.loads((public / "score.json").read_bytes()))
    research_summary = q.BenchmarkResearchSummary.model_validate(
        json.loads((public / "research_summary.json").read_bytes())
    )

    assert q.canonical_json_bytes(audit_input) == q.canonical_json_bytes(direct.audit_input)
    assert q.canonical_json_bytes(audit_report) == q.canonical_json_bytes(direct.audit_report)
    assert q.canonical_json_bytes(score) == q.canonical_json_bytes(direct.score)
    assert q.canonical_json_bytes(research_summary) == q.canonical_json_bytes(
        direct.research_summary
    )
    assert (private / "clean_snapshot.json").read_bytes() == q.canonical_json_bytes(
        direct.clean_snapshot
    )
    assert (private / "corrupted_snapshot.json").read_bytes() == q.canonical_json_bytes(
        direct.corrupted_snapshot
    )
    assert (private / "manifest.json").read_bytes() == q.canonical_json_bytes(direct.manifest)
    assert (private / "repaired_snapshot.json").read_bytes() == q.canonical_json_bytes(
        direct.repaired_snapshot
    )
    assert (private / "research_impact.json").read_bytes() == q.canonical_json_bytes(
        direct.research_impact
    )


@pytest.mark.parametrize("profile_name", _FAMILIES)
def test_clean_control_audit_matches_dispatch(tmp_path: Path, profile_name: str) -> None:
    case = clean_control_case(profile_name)
    direct = q.dispatch_benchmark_case(case)

    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"

    assert invoke(["inject", "--case", str(case_path), "--output", str(output)]).exit_code == 0
    assert invoke(["audit", "--dir", str(output)]).exit_code == 0

    public = output / "public" / "cases" / case.benchmark_case_id
    private = output / "private" / "cases" / case.benchmark_case_id
    assert not (private / "corrupted_snapshot.json").exists()
    assert not (private / "manifest.json").exists()

    audit_report = q.AuditReport.model_validate(
        json.loads((public / "audit_report.json").read_bytes())
    )
    assert q.canonical_json_bytes(audit_report) == q.canonical_json_bytes(direct.audit_report)


@pytest.mark.parametrize("profile_name", _FAMILIES)
def test_evaluate_rejects_a_clean_control(tmp_path: Path, profile_name: str) -> None:
    case = clean_control_case(profile_name)
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"
    invoke(["inject", "--case", str(case_path), "--output", str(output)])
    invoke(["audit", "--dir", str(output)])

    result = invoke(["evaluate", "--dir", str(output), "--json"])
    assert result.exit_code == 3
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert "clean control" in payload["message"]


def test_evaluate_before_audit_is_rejected(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"
    invoke(["inject", "--case", str(case_path), "--output", str(output)])

    result = invoke(["evaluate", "--dir", str(output), "--json"])
    assert result.exit_code == 3
    assert "audit report" in json.loads(result.stdout)["message"]


def test_audit_before_inject_is_rejected(tmp_path: Path) -> None:
    """With no saved case at all, this is a usage error (exit 2): the
    directory does not describe any case to continue, rather than a known
    case whose evidence is missing (exit 3, covered by the next test)."""
    output = tmp_path / "run"
    output.mkdir()
    result = invoke(["audit", "--dir", str(output), "--json"])
    assert result.exit_code == 2


def test_audit_after_partial_inject_is_an_artifact_error(tmp_path: Path) -> None:
    """A case configuration exists but its injected snapshot is missing: this
    is a saved-artifact problem (exit 3), not a configuration problem."""
    case = fault_case("lookahead_timestamp")
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"
    invoke(["inject", "--case", str(case_path), "--output", str(output)])

    corrupted_path = (
        output / "private" / "cases" / case.benchmark_case_id / "corrupted_snapshot.json"
    )
    corrupted_path.unlink()

    result = invoke(["audit", "--dir", str(output), "--json"])
    assert result.exit_code == 3


def test_rerunning_inject_with_identical_input_is_a_safe_no_op(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"
    first = invoke(["inject", "--case", str(case_path), "--output", str(output)])
    second = invoke(["inject", "--case", str(case_path), "--output", str(output)])
    assert first.exit_code == 0
    assert second.exit_code == 0


def test_conflicting_manual_edit_is_rejected_as_an_integrity_error(tmp_path: Path) -> None:
    case = fault_case("lookahead_timestamp")
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    output = tmp_path / "run"
    invoke(["inject", "--case", str(case_path), "--output", str(output)])

    corrupted_path = (
        output / "private" / "cases" / case.benchmark_case_id / "corrupted_snapshot.json"
    )
    corrupted_path.write_bytes(b'{"tampered": true}')

    result = invoke(["audit", "--dir", str(output), "--json"])
    assert result.exit_code != 0


def test_audit_snapshot_mode_matches_dir_mode(tmp_path: Path) -> None:
    """The generic ``--snapshot`` audit path and the ``--dir`` continuation
    path must sanitize and detect identically over the same logical input."""
    case = fault_case("lookahead_timestamp")
    case_path = tmp_path / "case.json"
    write_case_config(case_path, case)
    staged_output = tmp_path / "staged"
    invoke(["inject", "--case", str(case_path), "--output", str(staged_output)])
    invoke(["audit", "--dir", str(staged_output)])

    corrupted_path = (
        staged_output / "private" / "cases" / case.benchmark_case_id / "corrupted_snapshot.json"
    )
    snapshot_output = tmp_path / "snapshot-mode"
    result = invoke(
        [
            "audit",
            "--case",
            str(case_path),
            "--snapshot",
            str(corrupted_path),
            "--output",
            str(snapshot_output),
            "--json",
        ]
    )
    assert result.exit_code == 0

    staged_report = json.loads(
        (
            staged_output / "public" / "cases" / case.benchmark_case_id / "audit_report.json"
        ).read_bytes()
    )
    snapshot_report = json.loads(
        (
            snapshot_output / "public" / "cases" / case.benchmark_case_id / "audit_report.json"
        ).read_bytes()
    )
    assert staged_report == snapshot_report
