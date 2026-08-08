"""A read-only Streamlit forensic dashboard over saved public artifacts.

This app renders the shared presentation model and does nothing else. It runs no
injection, no detector, no matching, no scoring, no replay, and no private
research calculation; it opens no manifest and no private artifact; it mutates
nothing; it makes no network request; and it re-derives no benchmark metric. If
a number appears here, it was read from a saved public artifact.

Launch it standalone (it is deliberately *not* a ``quantcheck`` CLI command)::

    uv run --group dashboard streamlit run dashboard/app.py -- --artifacts <root>

``<root>`` is a benchmark output root containing ``public/``, or a copied-out
public tree. The private tree may be absent.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

import streamlit as st

from quantcheck.presentation import (
    BenchmarkPresentation,
    PresentationCase,
    PresentationGroup,
    PresentationMetrics,
    build_presentation,
    metric_text,
)
from quantcheck.public_artifact_reader import PublicArtifactError, read_public_benchmark

_ALL = "all"


def _parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="quantcheck-dashboard",
        description="Read-only forensic view of saved QuantCheck public benchmark artifacts.",
        add_help=False,
    )
    parser.add_argument(
        "--artifacts",
        required=True,
        help="Benchmark artifact root (containing public/) or a public tree itself.",
    )
    known, _unknown = parser.parse_known_args(argv)
    return known


def _metric(value: Decimal | None) -> str:
    """Render a metric, keeping an undefined metric visibly undefined."""
    return metric_text(value)


def _metrics_row(metrics: PresentationMetrics) -> dict[str, object]:
    return {
        "injected": metrics.injected_faults,
        "findings": metrics.findings,
        "TP": metrics.true_positive_findings,
        "FP": metrics.false_positive_findings,
        "FN": metrics.false_negative_faults,
        "precision": _metric(metrics.precision),
        "recall": _metric(metrics.recall),
        "F1": _metric(metrics.f1),
        "FP rate": _metric(metrics.false_positive_rate),
    }


def _group_rows(groups: tuple[PresentationGroup, ...]) -> list[dict[str, object]]:
    return [
        {
            "key": group.key,
            "configured": group.configured_case_count,
            "succeeded": group.successful_case_count,
            "failed": group.failed_case_count,
            "incomplete": group.incomplete_case_count,
            **_metrics_row(group.metrics),
            "research changed": group.research_changed_count,
            "replay restored": group.replay_restored_count,
        }
        for group in groups
    ]


def _render_overview(presentation: BenchmarkPresentation) -> None:
    st.title("QuantCheck benchmark summary")
    st.caption(presentation.benchmark_name)
    st.text(f"benchmark id: {presentation.benchmark_id}")
    st.text(f"aggregate report id: {presentation.aggregate_report_id}")
    st.text(f"spec version: {presentation.spec_version}")

    st.subheader("Case status")
    columns = st.columns(6)
    tiles = (
        ("configured", presentation.configured_case_count),
        ("succeeded", presentation.successful_case_count),
        ("failed", presentation.failed_case_count),
        ("incomplete", presentation.incomplete_case_count),
        ("fault cases", presentation.fault_case_count),
        ("clean controls", presentation.clean_control_count),
    )
    for column, (label, value) in zip(columns, tiles, strict=True):
        column.metric(label, value)

    st.subheader("Overall detection metrics")
    st.caption(
        "Pooled counts, and metrics computed once from those pooled counts, exactly as the saved "
        "aggregate report records them. Nothing here recomputes them."
    )
    st.table([_metrics_row(presentation.overall)])


def _render_groups(presentation: BenchmarkPresentation) -> None:
    st.subheader("Saved group summaries")
    st.caption("The benchmark's own groupings, preserved rather than re-derived.")
    for title, groups in (
        ("By fault profile", presentation.by_fault_profile),
        ("By severity", presentation.by_severity),
        ("By seed class", presentation.by_seed_class),
        ("By seed", presentation.by_seed),
    ):
        if groups:
            st.markdown(f"**{title}**")
            st.table(_group_rows(groups))


def _select(label: str, values: Sequence[str], key: str) -> str:
    """One filter. Every filter defaults to showing everything."""
    options = [_ALL, *sorted(set(values))]
    return str(st.selectbox(label, options, index=0, key=key))


def _filter_cases(presentation: BenchmarkPresentation) -> tuple[PresentationCase, ...]:
    """Apply case filters, defaulting to hiding nothing at all.

    Failures, incomplete cases, clean controls, and weak results are all visible
    without touching a control: a default that hid any of them would make a
    broken benchmark look healthy.
    """
    st.subheader("Cases")
    columns = st.columns(4)
    with columns[0]:
        profile = _select(
            "fault profile", [case.fault_profile for case in presentation.cases], "filter_profile"
        )
    with columns[1]:
        severity = _select(
            "severity", [case.severity for case in presentation.cases], "filter_severity"
        )
    with columns[2]:
        status = _select(
            "status", [case.terminal_status for case in presentation.cases], "filter_status"
        )
    with columns[3]:
        seed_class = _select(
            "seed class", [case.seed_class for case in presentation.cases], "filter_seed_class"
        )

    return tuple(
        case
        for case in presentation.cases
        if profile in (_ALL, case.fault_profile)
        and severity in (_ALL, case.severity)
        and status in (_ALL, case.terminal_status)
        and seed_class in (_ALL, case.seed_class)
    )


def _render_case(case: PresentationCase) -> None:
    st.markdown(f"### `{case.benchmark_case_id}`")
    st.text(
        f"{case.fault_profile} | {case.case_kind} | severity {case.severity} | "
        f"seed {case.seed} ({case.seed_class}) | status {case.terminal_status}"
    )
    st.text(f"fixture {case.fixture_id} | dataset {case.dataset_name} | as of {case.as_of_date}")
    if case.audit_input_record_count is not None:
        st.text(f"sanitized audit input records: {case.audit_input_record_count}")

    if case.metrics is not None:
        st.markdown("**Case score**")
        st.table([_metrics_row(case.metrics)])

    if case.research is not None:
        st.markdown("**Controlled research comparison**")
        st.table(
            [
                {
                    "method": case.research.method,
                    "output changed": "yes" if case.research.changed else "no",
                    "exact replay restoration": (
                        "yes" if case.research.exact_restoration else "no"
                    ),
                }
            ]
        )
        st.caption("Counts and values stay private; only these booleans are public.")

    if case.failure is not None:
        st.error(
            f"Failure - stage {case.failure.stage}, category {case.failure.category}, "
            f"code {case.failure.error_code}. {case.failure.message}"
        )
    elif case.terminal_status == "incomplete":
        st.warning(
            "This case has no terminal status artifact. It is reported as incomplete rather "
            "than assumed successful."
        )

    if case.findings:
        st.markdown(f"**Findings ({len(case.findings)})**")
        for finding in case.findings:
            with st.expander(f"{finding.finding_id} - {finding.rule_id}"):
                st.text(
                    f"severity {finding.severity} | confidence {finding.confidence} | "
                    f"detector {finding.detector_id} {finding.detector_version}"
                )
                st.write(finding.explanation)
                st.text("affected records: " + ", ".join(finding.affected_record_ids))
                st.table([{"field": item.label, "value": item.value} for item in finding.evidence])
    elif case.terminal_status == "succeeded":
        st.text("No findings were reported for this case.")


_METHODOLOGY = """
Each case starts from a deterministic clean point-in-time snapshot. A fault is injected
deterministically from the case's seed and severity, and the private truth of that injection is
recorded in a manifest that detectors never see. The corrupted snapshot is sanitized into an audit
input, four independent manifest-blind detectors run over it, and only then is the finalized audit
report scored one-to-one against the manifest. A separate controlled research calculation compares
the clean, corrupted, and manifest-assisted repaired states. Clean controls run the identical
detector tuple over an uncorrupted snapshot.
"""

_PRIVACY = """
This dashboard read indexed public artifacts only. It never opened a manifest, an original or
pre-corruption value, a clean/corrupted/repaired snapshot, a private research value, an injector
selection digest or target rank, or a private failure diagnostic, and it shows no filesystem path
from the machine that produced the artifacts. It runs no injection, detection, matching, scoring,
replay, or research logic, mutates nothing, and makes no network request. It works with the entire
private artifact tree deleted.
"""

_LIMITATIONS = """
- Metrics come from the saved aggregate report; this app recomputes nothing.
- `n/a` marks a genuinely undefined metric for that population - not zero, and not a failure.
- Findings and evidence are the detectors' public output. They cannot reconstruct the hidden true
  record; only private manifest-assisted replay can.
- Controlled research reports only whether an output changed and whether exact replay restored it.
- A case with no terminal status artifact is shown as incomplete, never inferred successful.
"""


def _render_notes() -> None:
    st.subheader("Methodology")
    st.write(_METHODOLOGY)
    st.subheader("Privacy boundary")
    st.write(_PRIVACY)
    st.subheader("Known limitations")
    st.markdown(_LIMITATIONS)


def main(argv: Sequence[str] | None = None) -> None:
    """Render the dashboard, or stop with a sanitized error."""
    st.set_page_config(page_title="QuantCheck forensic dashboard", layout="wide")
    try:
        arguments = _parse_arguments(argv)
    except SystemExit:
        st.error(
            "An artifact root is required. Launch with: streamlit run dashboard/app.py -- "
            "--artifacts <root>"
        )
        return

    try:
        artifacts = read_public_benchmark(Path(arguments.artifacts))
    except PublicArtifactError as exc:
        # The reader's messages name roles and relative paths only, never a
        # local absolute path or a private value, so surfacing one is safe.
        st.error(f"The public artifacts could not be read: {exc}")
        return

    presentation = build_presentation(artifacts)
    _render_overview(presentation)
    _render_groups(presentation)
    for case in _filter_cases(presentation):
        _render_case(case)
    _render_notes()


main()
