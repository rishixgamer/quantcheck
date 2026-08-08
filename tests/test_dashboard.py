"""The read-only Streamlit dashboard, via Streamlit's official AppTest.

AppTest runs the real script in-process and exposes the rendered element tree,
so these tests exercise the actual app rather than a stand-in. A real browser is
not required and none is opened.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import quantcheck as q
from tests.presentation_helpers import (
    build_failed_benchmark,
    build_incomplete_benchmark,
    build_smoke_benchmark,
    copy_public_only,
    manifest_answer_key_strings,
)

AppTest = pytest.importorskip(
    "streamlit.testing.v1", reason="Streamlit is required for the dashboard tests"
).AppTest

_APP = Path(__file__).resolve().parent.parent / "dashboard" / "app.py"


@pytest.fixture(scope="module")
def smoke_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("dashboard-smoke")
    build_smoke_benchmark(root)
    return root


def _run(root: Path | str, monkeypatch: pytest.MonkeyPatch) -> object:
    """Run the real app. It reads ``--artifacts`` from ``sys.argv``, as
    Streamlit passes it after the ``--`` separator."""
    monkeypatch.setattr(sys, "argv", ["app.py", "--artifacts", str(root)])
    app = AppTest.from_file(str(_APP), default_timeout=60)
    return app.run()


def _all_text(app: object) -> str:
    """Concatenate everything the app rendered, tables included."""
    chunks: list[str] = []
    for name in (
        "title",
        "header",
        "subheader",
        "caption",
        "markdown",
        "text",
        "error",
        "warning",
        "info",
        "success",
    ):
        for element in getattr(app, name):
            chunks.append(str(getattr(element, "value", "")))
    for element in app.metric:  # type: ignore[attr-defined]
        chunks.append(f"{element.label} {element.value}")
    for element in app.table:  # type: ignore[attr-defined]
        chunks.append(element.value.to_string())
    for element in app.dataframe:  # type: ignore[attr-defined]
        chunks.append(element.value.to_string())
    return "\n".join(chunks)


# --------------------------------------------------------------------------
# Startup and overview
# --------------------------------------------------------------------------


def test_the_app_starts_without_exception_on_valid_artifacts(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    assert not app.exception  # type: ignore[attr-defined]
    assert app.error == []  # type: ignore[attr-defined]


def test_the_overview_shows_the_benchmark_identity(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    text = _all_text(app)
    artifacts = q.read_public_benchmark(smoke_root)
    assert artifacts.config.benchmark_id in text
    assert artifacts.aggregate.aggregate_report_id in text
    assert artifacts.config.benchmark_name in text


def test_the_status_counts_match_the_saved_aggregate(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    overall = q.read_public_benchmark(smoke_root).aggregate.overall
    tiles = {element.label: element.value for element in app.metric}  # type: ignore[attr-defined]
    assert tiles["configured"] == str(overall.configured_case_count)
    assert tiles["succeeded"] == str(overall.successful_case_count)
    assert tiles["failed"] == str(overall.failed_case_count)
    assert tiles["incomplete"] == str(overall.incomplete_case_count)


def test_the_overall_metrics_match_the_saved_aggregate(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    overall = q.read_public_benchmark(smoke_root).aggregate.overall
    text = _all_text(app)
    assert str(overall.precision) in text
    assert str(overall.recall) in text
    assert str(overall.f1) in text


def test_the_saved_group_summaries_are_shown(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    text = _all_text(app)
    for group in q.read_public_benchmark(smoke_root).aggregate.by_fault_profile:
        assert group.key in text


# --------------------------------------------------------------------------
# Cases and filtering
# --------------------------------------------------------------------------


def test_every_case_is_visible_before_any_filter_is_touched(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defaults must hide nothing: no failure, control, or weak result."""
    app = _run(smoke_root, monkeypatch)
    text = _all_text(app)
    artifacts = q.read_public_benchmark(smoke_root)
    for case in artifacts.cases:
        assert case.case.benchmark_case_id in text


def test_every_filter_defaults_to_showing_everything(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    assert [box.value for box in app.selectbox] == ["all"] * 4  # type: ignore[attr-defined]


def test_filtering_by_fault_profile_narrows_the_selection(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    app.selectbox(key="filter_profile").select("unit_drift").run()  # type: ignore[attr-defined]
    text = _all_text(app)
    artifacts = q.read_public_benchmark(smoke_root)
    for case in artifacts.cases:
        present = case.case.benchmark_case_id in text
        assert present == (case.case.fault_profile == "unit_drift"), case.case.benchmark_case_id


def test_a_selected_case_shows_its_findings_and_evidence(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    text = _all_text(app)
    artifacts = q.read_public_benchmark(smoke_root)
    findings = [
        finding
        for case in artifacts.cases
        if case.audit_report is not None
        for finding in case.audit_report.findings
    ]
    assert findings
    assert any(finding.rule_id in text for finding in findings)
    assert any(finding.explanation in text for finding in findings)


def test_clean_controls_remain_visible(smoke_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run(smoke_root, monkeypatch)
    text = _all_text(app)
    controls = [
        case
        for case in q.read_public_benchmark(smoke_root).cases
        if case.case.case_kind == "clean_control"
    ]
    assert controls
    for control in controls:
        assert control.case.benchmark_case_id in text


def test_a_failed_case_is_shown_with_its_redacted_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_failed_benchmark(tmp_path)
    app = _run(tmp_path, monkeypatch)
    assert not app.exception  # type: ignore[attr-defined]
    errors = "\n".join(str(element.value) for element in app.error)  # type: ignore[attr-defined]
    assert "no_eligible_targets" in errors
    assert q.redacted_failure_message("no_eligible_targets") in errors


def test_an_incomplete_case_is_shown_as_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_id = build_incomplete_benchmark(tmp_path)
    app = _run(tmp_path, monkeypatch)
    assert not app.exception  # type: ignore[attr-defined]
    text = _all_text(app)
    assert case_id in text
    warnings = "\n".join(str(element.value) for element in app.warning)  # type: ignore[attr-defined]
    assert "incomplete rather than assumed successful" in warnings


def test_a_null_metric_is_shown_as_undefined(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_failed_benchmark(tmp_path)
    app = _run(tmp_path, monkeypatch)
    assert "n/a" in _all_text(app)


# --------------------------------------------------------------------------
# Errors, privacy, and offline behaviour
# --------------------------------------------------------------------------


def test_a_missing_artifact_root_is_reported_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(tmp_path / "nothing-here", monkeypatch)
    assert not app.exception  # type: ignore[attr-defined]
    errors = "\n".join(str(element.value) for element in app.error)  # type: ignore[attr-defined]
    assert "could not be read" in errors
    assert "Traceback" not in errors


def test_an_invalid_artifact_tree_is_reported_with_a_sanitized_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    build_smoke_benchmark(tmp_path)
    (tmp_path / "public" / "benchmark_config.json").write_bytes(b"{not json")
    app = _run(tmp_path, monkeypatch)
    assert not app.exception  # type: ignore[attr-defined]
    errors = "\n".join(str(element.value) for element in app.error)  # type: ignore[attr-defined]
    assert "could not be read" in errors
    assert str(tmp_path) not in errors


def test_a_missing_artifacts_argument_is_reported_rather_than_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["app.py"])
    app = AppTest.from_file(str(_APP), default_timeout=60).run()
    assert not app.exception
    errors = "\n".join(str(element.value) for element in app.error)
    assert "artifact root is required" in errors


def test_the_dashboard_renders_with_the_private_tree_absent(
    smoke_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copied = copy_public_only(smoke_root, tmp_path / "public-only")
    assert not (copied / q.PRIVATE_ROOT_NAME).exists()
    app = _run(copied, monkeypatch)
    assert not app.exception  # type: ignore[attr-defined]
    assert q.read_public_benchmark(smoke_root).config.benchmark_id in _all_text(app)


def test_the_dashboard_shows_no_private_answer_key_value(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    text = _all_text(app)
    secrets = manifest_answer_key_strings(smoke_root)
    assert secrets
    leaked = sorted(secret for secret in secrets if secret in text)
    assert not leaked, leaked


def test_the_dashboard_shows_no_local_filesystem_path(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    text = _all_text(app)
    assert str(smoke_root) not in text
    for marker in ("/Users/", "/home/", "/var/folders", "/private/var"):
        assert marker not in text, marker


def test_the_dashboard_shows_its_methodology_privacy_and_limitations(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = _run(smoke_root, monkeypatch)
    text = _all_text(app)
    assert "Methodology" in text
    assert "Privacy boundary" in text
    assert "Known limitations" in text
    assert "manifest-blind" in text


def test_the_dashboard_mutates_no_artifact(
    smoke_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read-only means read-only: every public byte is unchanged afterwards."""
    before = {path: path.read_bytes() for path in sorted((smoke_root / "public").rglob("*.json"))}
    _run(smoke_root, monkeypatch)
    after = {path: path.read_bytes() for path in sorted((smoke_root / "public").rglob("*.json"))}
    assert before == after
