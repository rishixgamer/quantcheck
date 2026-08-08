"""A deterministic, self-contained HTML summary over the presentation model.

The output is one offline file: UTF-8, embedded CSS only, no JavaScript, no
remote or CDN resource, no render timestamp, no random identifier, and no
environment-specific path. Given logically identical public artifacts, two
renders produce byte-identical output regardless of destination directory,
process, or ``PYTHONHASHSEED``.

Determinism comes from the input rather than from sorting here: the presentation
model is built from artifacts the benchmark already sorted, and every loop below
walks them in that order. Nothing consults the clock, the environment, the
filesystem, or a random source.

Every artifact-derived string is escaped. The model is public by construction,
but escaping is applied anyway: a renderer that trusts its input is one schema
change away from injecting markup.
"""

from __future__ import annotations

from decimal import Decimal
from html import escape
from pathlib import Path

from quantcheck.benchmark_store import (
    ArtifactIntegrityError,
    ArtifactPersistenceError,
    atomic_write_bytes,
)
from quantcheck.presentation import (
    BenchmarkPresentation,
    PresentationCase,
    PresentationGroup,
    PresentationMetrics,
    metric_text,
)

__all__ = [
    "HTML_SUMMARY_SUFFIX",
    "HtmlSummaryError",
    "render_html_summary",
    "write_html_summary",
]

#: The only accepted output suffix. A summary written as ``.json`` or with no
#: suffix at all would misrepresent its own format to whatever opens it next.
HTML_SUMMARY_SUFFIX = ".html"


class HtmlSummaryError(ValueError):
    """Raised when an HTML summary cannot be rendered or written safely."""


_STYLE = """
:root { color-scheme: light; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial,
  sans-serif; margin: 0 auto; max-width: 60rem; padding: 2rem 1.25rem 4rem; line-height: 1.5;
  color: #16191d; background: #ffffff; }
h1 { font-size: 1.7rem; margin-bottom: 0.25rem; }
h2 { font-size: 1.25rem; margin-top: 2.5rem; border-bottom: 1px solid #d7dbe0;
  padding-bottom: 0.3rem; }
h3 { font-size: 1.02rem; margin-top: 1.5rem; }
p, li { font-size: 0.95rem; }
code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.86rem; }
table { border-collapse: collapse; width: 100%; margin: 0.75rem 0 1.25rem; font-size: 0.86rem; }
th, td { border: 1px solid #d7dbe0; padding: 0.35rem 0.55rem; text-align: left;
  vertical-align: top; }
th { background: #f2f4f7; font-weight: 600; }
.subtitle { color: #55606c; margin-top: 0; }
.counts { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1rem 0; padding: 0;
  list-style: none; }
.counts li { border: 1px solid #d7dbe0; border-radius: 6px; padding: 0.55rem 0.9rem;
  min-width: 7.5rem; }
.counts .label { display: block; color: #55606c; font-size: 0.76rem;
  text-transform: uppercase; letter-spacing: 0.04em; }
.counts .value { font-size: 1.35rem; font-weight: 600; }
.null { color: #6b7480; font-style: italic; }
.status-succeeded { color: #14622f; font-weight: 600; }
.status-failed { color: #8c1c1c; font-weight: 600; }
.status-incomplete { color: #7a5200; font-weight: 600; }
.case { border: 1px solid #d7dbe0; border-radius: 6px; padding: 0.9rem 1.1rem; margin: 1rem 0; }
.notice { border-left: 4px solid #55606c; background: #f7f8fa; padding: 0.75rem 1rem;
  margin: 1rem 0; }
"""


def _text(value: str) -> str:
    """Escape one artifact-derived string for HTML text or attribute use."""
    return escape(value, quote=True)


def _metric(value: Decimal | None) -> str:
    """Render one metric, marking an undefined metric as undefined."""
    if value is None:
        return '<span class="null">n/a</span>'
    return f'<span class="mono">{_text(metric_text(value))}</span>'


def _status(status: str) -> str:
    known = {"succeeded", "failed", "incomplete"}
    css = f"status-{status}" if status in known else "status-incomplete"
    return f'<span class="{css}">{_text(status)}</span>'


def _count_tile(label: str, value: int) -> str:
    return f'<li><span class="label">{_text(label)}</span><span class="value">{value}</span></li>'


def _metrics_row(metrics: PresentationMetrics) -> str:
    return (
        f"<td>{metrics.injected_faults}</td>"
        f"<td>{metrics.findings}</td>"
        f"<td>{metrics.true_positive_findings}</td>"
        f"<td>{metrics.false_positive_findings}</td>"
        f"<td>{metrics.false_negative_faults}</td>"
        f"<td>{_metric(metrics.precision)}</td>"
        f"<td>{_metric(metrics.recall)}</td>"
        f"<td>{_metric(metrics.f1)}</td>"
        f"<td>{_metric(metrics.false_positive_rate)}</td>"
    )


_METRIC_HEADERS = (
    "<th>injected</th><th>findings</th><th>TP</th><th>FP</th><th>FN</th>"
    "<th>precision</th><th>recall</th><th>F1</th><th>FP rate</th>"
)


def _overall_section(presentation: BenchmarkPresentation) -> list[str]:
    lines = [
        "<h2>Overall detection metrics</h2>",
        "<p>Pooled counts, and metrics computed once from those pooled counts, exactly as the "
        "saved aggregate report records them. Per-case metrics are never averaged, and nothing "
        "on this page recomputes them.</p>",
        "<table>",
        f"<thead><tr>{_METRIC_HEADERS}</tr></thead>",
        f"<tbody><tr>{_metrics_row(presentation.overall)}</tr></tbody>",
        "</table>",
    ]
    return lines


def _group_table(title: str, groups: tuple[PresentationGroup, ...]) -> list[str]:
    if not groups:
        return []
    lines = [
        f"<h3>{_text(title)}</h3>",
        "<table>",
        "<thead><tr><th>key</th><th>configured</th><th>succeeded</th><th>failed</th>"
        f"<th>incomplete</th>{_METRIC_HEADERS}</tr></thead>",
        "<tbody>",
    ]
    for group in groups:
        lines.append(
            f'<tr><td class="mono">{_text(group.key)}</td>'
            f"<td>{group.configured_case_count}</td>"
            f"<td>{group.successful_case_count}</td>"
            f"<td>{group.failed_case_count}</td>"
            f"<td>{group.incomplete_case_count}</td>"
            f"{_metrics_row(group.metrics)}</tr>"
        )
    lines.extend(["</tbody>", "</table>"])
    return lines


def _case_section(case: PresentationCase) -> list[str]:
    lines = [
        '<div class="case">',
        f'<h3><span class="mono">{_text(case.benchmark_case_id)}</span></h3>',
        "<p>"
        f"{_text(case.fault_profile)} &middot; {_text(case.case_kind)} &middot; "
        f"severity {_text(case.severity)} &middot; seed {case.seed} "
        f"({_text(case.seed_class)}) &middot; fixture "
        f'<span class="mono">{_text(case.fixture_id)}</span> &middot; dataset '
        f"{_text(case.dataset_name)} &middot; as of {_text(case.as_of_date)} &middot; "
        f"status {_status(case.terminal_status)}"
        "</p>",
    ]
    if case.audit_input_record_count is not None:
        lines.append(f"<p>Sanitized audit input: {case.audit_input_record_count} records.</p>")
    if case.metrics is not None:
        lines.extend(
            [
                "<table>",
                f"<thead><tr>{_METRIC_HEADERS}</tr></thead>",
                f"<tbody><tr>{_metrics_row(case.metrics)}</tr></tbody>",
                "</table>",
            ]
        )
    if case.research is not None:
        lines.append(
            "<p>Controlled research comparison "
            f'(<span class="mono">{_text(case.research.method)}</span>): output changed = '
            f"{'yes' if case.research.changed else 'no'}; exact replay restoration = "
            f"{'yes' if case.research.exact_restoration else 'no'}. "
            "Counts and values stay private.</p>"
        )
    if case.failure is not None:
        lines.append(
            '<div class="notice"><strong>Failure</strong> &mdash; stage '
            f"{_text(case.failure.stage)}, category {_text(case.failure.category)}, code "
            f'<span class="mono">{_text(case.failure.error_code)}</span>. '
            f"{_text(case.failure.message)}</div>"
        )
    elif case.terminal_status == "incomplete":
        lines.append(
            '<div class="notice">This case has no terminal status artifact. It is reported as '
            "incomplete rather than assumed successful.</div>"
        )
    if case.findings:
        lines.append(f"<h4>Findings ({len(case.findings)})</h4>")
        for finding in case.findings:
            lines.extend(
                [
                    "<p>"
                    f'<span class="mono">{_text(finding.finding_id)}</span> &middot; rule '
                    f'<span class="mono">{_text(finding.rule_id)}</span> &middot; '
                    f"{_text(finding.severity)} severity &middot; "
                    f"{_text(finding.confidence)} confidence &middot; detector "
                    f'<span class="mono">{_text(finding.detector_id)} '
                    f"{_text(finding.detector_version)}</span>"
                    "</p>",
                    f"<p>{_text(finding.explanation)}</p>",
                    "<p>Affected records: "
                    + ", ".join(
                        f'<span class="mono">{_text(record_id)}</span>'
                        for record_id in finding.affected_record_ids
                    )
                    + "</p>",
                    "<table><thead><tr><th>evidence field</th><th>value</th></tr></thead><tbody>",
                ]
            )
            for item in finding.evidence:
                lines.append(
                    f'<tr><td class="mono">{_text(item.label)}</td>'
                    f'<td class="mono">{_text(item.value)}</td></tr>'
                )
            lines.append("</tbody></table>")
    elif case.terminal_status == "succeeded":
        lines.append("<p>No findings were reported for this case.</p>")
    lines.append("</div>")
    return lines


_METHODOLOGY = """
<h2>Methodology</h2>
<p>Each case starts from a deterministic clean point-in-time snapshot. A fault is injected
deterministically from the case's seed and severity, and the private truth of that injection is
recorded in a manifest that detectors never see. The corrupted snapshot is sanitized into an
audit input, four independent manifest-blind detectors run over it, and only then is the
finalized audit report scored one-to-one against the manifest. A separate controlled research
calculation compares the clean, corrupted, and manifest-assisted repaired states.</p>
<p>Clean controls run the identical detector tuple over an uncorrupted snapshot, so a detector
that fires without a fault present is counted against it.</p>

<h2>Privacy boundary</h2>
<p>This page was rendered from indexed public artifacts only. It never opened a manifest, an
original or pre-corruption value, a clean/corrupted/repaired snapshot, a private research value,
an injector selection digest or target rank, or a private failure diagnostic, and it contains no
filesystem path from the machine that produced it. Rendering succeeds with the entire private
artifact tree deleted.</p>
<p>Failure descriptions are the benchmark's own fixed public sentences. No exception message or
stack trace reaches this page.</p>

<h2>Known limitations</h2>
<ul>
<li>Metrics are read from the saved aggregate report. This page performs no injection, detection,
matching, scoring, replay, or research calculation of its own.</li>
<li>An undefined metric is shown as <span class="null">n/a</span> and is genuinely undefined for
that population: it is not zero and not a failure.</li>
<li>Findings and evidence are the detectors' public output. They cannot reconstruct the hidden
true record; only private manifest-assisted replay can do that.</li>
<li>Controlled research results report only whether a controlled output changed and whether exact
replay restored it. The underlying counts and values stay private.</li>
<li>A case with no terminal status artifact is reported as incomplete. It is never inferred to
have succeeded.</li>
</ul>
"""


def render_html_summary(presentation: BenchmarkPresentation) -> str:
    """Render one presentation model as a deterministic self-contained page."""
    lines: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>QuantCheck benchmark summary &mdash; {_text(presentation.benchmark_name)}</title>",
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body>",
        "<h1>QuantCheck benchmark summary</h1>",
        f'<p class="subtitle">{_text(presentation.benchmark_name)}</p>',
        "<table>",
        "<tbody>",
        f'<tr><th>benchmark id</th><td class="mono">{_text(presentation.benchmark_id)}</td></tr>',
        f"<tr><th>aggregate report id</th>"
        f'<td class="mono">{_text(presentation.aggregate_report_id)}</td></tr>',
        f'<tr><th>spec version</th><td class="mono">{_text(presentation.spec_version)}</td></tr>',
        "</tbody>",
        "</table>",
        "<h2>Case status</h2>",
        '<ul class="counts">',
        _count_tile("configured", presentation.configured_case_count),
        _count_tile("succeeded", presentation.successful_case_count),
        _count_tile("failed", presentation.failed_case_count),
        _count_tile("incomplete", presentation.incomplete_case_count),
        _count_tile("fault cases", presentation.fault_case_count),
        _count_tile("clean controls", presentation.clean_control_count),
        "</ul>",
    ]
    lines.extend(_overall_section(presentation))
    lines.append("<h2>Saved group summaries</h2>")
    lines.extend(_group_table("By fault profile", presentation.by_fault_profile))
    lines.extend(_group_table("By severity", presentation.by_severity))
    lines.extend(_group_table("By seed class", presentation.by_seed_class))
    lines.extend(_group_table("By seed", presentation.by_seed))
    lines.append(f"<h2>Cases ({len(presentation.cases)})</h2>")
    for case in presentation.cases:
        lines.extend(_case_section(case))
    lines.append(_METHODOLOGY)
    lines.extend(["</body>", "</html>", ""])
    return "\n".join(lines)


def write_html_summary(presentation: BenchmarkPresentation, destination: Path) -> bytes:
    """Write the summary atomically, never over conflicting existing bytes.

    Identical existing bytes are reused untouched, which makes re-rendering a
    safe no-op. Different existing bytes mean two renders disagree about the
    same output, which is reported rather than resolved by overwriting: there
    is deliberately no force option.

    Raises:
        HtmlSummaryError: for a destination that is not a writable ``.html`` file.
        ArtifactIntegrityError: when the destination holds different bytes.
    """
    target = Path(destination)
    if target.suffix != HTML_SUMMARY_SUFFIX:
        raise HtmlSummaryError(
            f"an HTML summary destination must end in {HTML_SUMMARY_SUFFIX}, got {target.name!r}"
        )
    if target.is_dir():
        raise HtmlSummaryError("the HTML summary destination is a directory")

    payload = render_html_summary(presentation).encode("utf-8")
    if target.is_file():
        if target.read_bytes() == payload:
            return payload
        raise ArtifactIntegrityError(
            f"{target.name} already exists with different content; it was not overwritten"
        )
    try:
        atomic_write_bytes(target, payload)
    except ArtifactPersistenceError as exc:
        raise HtmlSummaryError("the HTML summary could not be written") from exc
    except OSError as exc:
        raise HtmlSummaryError("the HTML summary destination is not writable") from exc
    return payload
