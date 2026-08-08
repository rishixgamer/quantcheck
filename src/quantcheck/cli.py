"""The contracted QuantCheck Typer CLI (Recovery Phase 9).

This module is a thin interface over the existing implementation. Every
command below delegates to code that already exists elsewhere in the
package — the four completed fault families, the benchmark dispatcher and
runner, the SEC adapter, and :mod:`quantcheck.saved_case_workflow` — and adds
no scientific behavior, no second configuration format, and no second
persistence path of its own. See ``docs/CLI_CONTRACT.md`` for the frozen
command surface, exit-code taxonomy, and machine/human output contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from quantcheck import saved_case_workflow as workflow
from quantcheck.benchmark_contract import PRIVATE_ROOT_NAME, PUBLIC_ROOT_NAME
from quantcheck.benchmark_runner import run_benchmark
from quantcheck.benchmark_smoke import smoke_benchmark_config
from quantcheck.benchmark_store import AtomicArtifactStore
from quantcheck.cli_support import (
    EXIT_BENCHMARK_FAILURE,
    EXIT_INTERNAL_ERROR,
    ConfigLoadError,
    build_runtime_metadata,
    emit_json,
    fail,
    load_benchmark_config,
    load_case_config,
    load_case_config_by_id,
    load_json_file,
    load_sec_normalization_config,
    load_staged_case_config,
    parse_iso_date,
)
from quantcheck.hashing import dataset_snapshot_identity_matches
from quantcheck.schemas import (
    AuditReport,
    BenchmarkCaseConfig,
    BenchmarkCaseStatus,
    DatasetSnapshot,
)
from quantcheck.sec_adapter import SecClientConfig, SecCompanyFactsAdapter

__all__ = ["app", "main"]

app = typer.Typer(
    name="quantcheck",
    help=("QuantCheck: deterministic point-in-time financial data reliability auditing framework."),
    no_args_is_help=True,
    add_completion=False,
)

ingest_app = typer.Typer(
    help="Ingest an external financial data source into a canonical snapshot.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(ingest_app, name="ingest")

benchmark_app = typer.Typer(
    help="Run the benchmark layer over the four completed fault families.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(benchmark_app, name="benchmark")

_JsonOption = Annotated[
    bool, typer.Option("--json", help="Emit exactly one canonical JSON result on stdout.")
]


# --------------------------------------------------------------------------
# ingest sec
# --------------------------------------------------------------------------


@ingest_app.command("sec")
def ingest_sec(
    cik: Annotated[str, typer.Option(help="Explicit SEC CIK (up to ten ASCII digits).")],
    concepts: Annotated[
        Path, typer.Option("--config", help="SEC normalization allowlist JSON file.")
    ],
    cache_dir: Annotated[
        Path, typer.Option(help="Directory for the exact-byte raw response cache.")
    ],
    user_agent: Annotated[str, typer.Option(help="Contact-identified User-Agent header value.")],
    output: Annotated[Path, typer.Option(help="Output root for the normalized public snapshot.")],
    dataset_name: Annotated[str, typer.Option(help="Logical dataset name for the built snapshot.")],
    as_of_date: Annotated[str, typer.Option(help="ISO as-of date for the built snapshot.")],
    refresh: Annotated[
        bool, typer.Option(help="Bypass a cached response and refetch over the network.")
    ] = False,
    replay_only: Annotated[
        bool,
        typer.Option(
            "--replay-only", help="Never touch the network; require an already-cached response."
        ),
    ] = False,
    json_output: _JsonOption = False,
) -> None:
    """Fetch (or replay) one CIK's Company Facts and build a public snapshot."""
    try:
        if refresh and replay_only:
            raise ConfigLoadError("--refresh and --replay-only cannot be combined")
        normalization = load_sec_normalization_config(concepts)
        client_config = SecClientConfig(user_agent=user_agent, cache_dir=cache_dir)
        adapter = SecCompanyFactsAdapter(client_config)
        fetched = adapter.replay(cik) if replay_only else adapter.fetch(cik, refresh=refresh)
        result = adapter.normalize(fetched, normalization)
        as_of = parse_iso_date(as_of_date, field_name="as_of_date")
        snapshot = adapter.build_snapshot(
            fetched, normalization, dataset_name=dataset_name, as_of_date=as_of
        )
        public = AtomicArtifactStore(Path(output))
        public.write_immutable("snapshot.json", snapshot)
    except Exception as exc:  # noqa: BLE001 - classified and reported by fail()
        raise fail(exc, json_mode=json_output) from exc

    payload: dict[str, object] = {
        "status": "ok",
        "command": "ingest sec",
        "canonical_cik": fetched.canonical_cik,
        "from_cache": fetched.from_cache,
        "normalized_record_count": len(result.records),
        "excluded_record_count": len(result.exclusions),
        "snapshot_id": snapshot.snapshot_id,
    }
    if json_output:
        emit_json(payload)
    else:
        typer.echo(
            f"ingested SEC CIK {fetched.canonical_cik}: "
            f"{len(result.records)} normalized, {len(result.exclusions)} excluded "
            f"(snapshot {snapshot.snapshot_id})"
        )


# --------------------------------------------------------------------------
# inject / audit / evaluate — the saved-stage workflow
# --------------------------------------------------------------------------


def _stores(output: Path) -> tuple[AtomicArtifactStore, AtomicArtifactStore]:
    root = Path(output)
    return (
        AtomicArtifactStore(root / PUBLIC_ROOT_NAME),
        AtomicArtifactStore(root / PRIVATE_ROOT_NAME),
    )


@app.command()
def inject(
    case: Annotated[Path, typer.Option(help="A fully expanded BenchmarkCaseConfig JSON file.")],
    output: Annotated[Path, typer.Option(help="Output root for the saved-stage case tree.")],
    json_output: _JsonOption = False,
) -> None:
    """Inject one saved, fully expanded case and persist its evidence.

    Delegates to the same fault-family injector the benchmark dispatcher
    uses. Never runs detection, scoring, or replay.
    """
    try:
        case_config = load_case_config(case)
        public, private = _stores(output)
        result = workflow.inject_case(case_config, public=public, private=private)
    except Exception as exc:  # noqa: BLE001 - classified and reported by fail()
        raise fail(exc, json_mode=json_output) from exc

    payload: dict[str, object] = {
        "status": "ok",
        "command": "inject",
        "benchmark_case_id": case_config.benchmark_case_id,
        "case_kind": case_config.case_kind,
        "fault_profile": case_config.fault_profile,
        "clean_snapshot_id": result.clean_snapshot.snapshot_id,
        "corrupted_snapshot_id": (
            result.corrupted_snapshot.snapshot_id if result.corrupted_snapshot else None
        ),
        "injected": result.corrupted_snapshot is not None,
    }
    if json_output:
        emit_json(payload)
    else:
        typer.echo(
            f"injected case {case_config.benchmark_case_id} "
            f"({case_config.case_kind}/{case_config.fault_profile})"
        )


@app.command()
def audit(
    dir: Annotated[
        Path | None,
        typer.Option("--dir", help="Continue a saved inject stage found under this output root."),
    ] = None,
    case: Annotated[
        Path | None,
        typer.Option("--case", help="Case configuration JSON (required together with --snapshot)."),
    ] = None,
    snapshot: Annotated[
        Path | None,
        typer.Option("--snapshot", help="A canonical DatasetSnapshot JSON file to audit directly."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", help="Output root to write into (required together with --snapshot)."
        ),
    ] = None,
    json_output: _JsonOption = False,
) -> None:
    """Sanitize and run the manifest-blind detector tuple over a saved input.

    Accepts exactly one of two saved input forms: ``--dir`` continues a prior
    ``inject`` stage's own output root; ``--case``/``--snapshot``/``--output``
    audits an arbitrary canonical snapshot (for example one built by
    ``ingest sec``) directly. Never reads a manifest.
    """
    try:
        if dir is not None:
            if case is not None or snapshot is not None or output is not None:
                raise ConfigLoadError("--dir cannot be combined with --case/--snapshot/--output")
            public, private = _stores(dir)
            case_config = load_staged_case_config(public)
            result = workflow.audit_case(case_config, public=public, private=private)
            audit_input, report = result.audit_input, result.audit_report
        elif snapshot is not None:
            if case is None or output is None:
                raise ConfigLoadError("--snapshot requires both --case and --output")
            case_config = load_case_config(case)
            snapshot_obj = DatasetSnapshot.model_validate(load_json_file(snapshot))
            if not dataset_snapshot_identity_matches(snapshot_obj):
                raise ConfigLoadError(f"snapshot identity does not match its content: {snapshot}")
            public, _private = _stores(output)
            audit_input, report = workflow.audit_snapshot(
                snapshot_obj,
                detector_configs=case_config.detector_configs,
                fault_profile=case_config.fault_profile,
            )
            public.write_immutable(
                workflow.public_artifact_path(case_config.benchmark_case_id, "audit_input"),
                audit_input,
            )
            public.write_immutable(
                workflow.public_artifact_path(case_config.benchmark_case_id, "audit_report"), report
            )
        else:
            raise ConfigLoadError("audit requires either --dir or --case/--snapshot/--output")
    except Exception as exc:  # noqa: BLE001 - classified and reported by fail()
        raise fail(exc, json_mode=json_output) from exc

    payload: dict[str, object] = {
        "status": "ok",
        "command": "audit",
        "benchmark_case_id": case_config.benchmark_case_id,
        "fault_profile": case_config.fault_profile,
        "audit_input_id": audit_input.audit_input_id,
        "audit_report_id": report.audit_report_id,
        "findings": report.findings,
    }
    if json_output:
        emit_json(payload)
    else:
        typer.echo(
            f"audited case {case_config.benchmark_case_id}: {len(report.findings)} finding(s) "
            f"(report {report.audit_report_id})"
        )


@app.command()
def evaluate(
    dir: Annotated[
        Path, typer.Option("--dir", help="A saved-stage output root with a finalized audit report.")
    ],
    json_output: _JsonOption = False,
) -> None:
    """Score, replay, and compare research impact for one saved fault case.

    Requires ``audit`` to have already finalized a public audit report in
    this output root. This is the first saved-stage command that reads the
    private manifest.
    """
    try:
        public, private = _stores(dir)
        case_config = load_staged_case_config(public)
        result = workflow.evaluate_case(case_config, public=public, private=private)
    except Exception as exc:  # noqa: BLE001 - classified and reported by fail()
        raise fail(exc, json_mode=json_output) from exc

    metrics = result.score.metrics
    payload: dict[str, object] = {
        "status": "ok",
        "command": "evaluate",
        "benchmark_case_id": case_config.benchmark_case_id,
        "fault_profile": case_config.fault_profile,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "f1": result.score.f1,
        "false_positive_rate": metrics.false_positive_rate,
        "research_method": result.research_summary.method,
        "research_changed": result.research_summary.changed,
        "exact_restoration": result.research_summary.exact_restoration,
    }
    if json_output:
        emit_json(payload)
    else:
        typer.echo(
            f"evaluated case {case_config.benchmark_case_id}: "
            f"precision={metrics.precision} recall={metrics.recall} f1={result.score.f1} "
            f"exact_restoration={result.research_summary.exact_restoration}"
        )


# --------------------------------------------------------------------------
# benchmark run / benchmark smoke
# --------------------------------------------------------------------------


def _report_benchmark_result(
    *,
    command: str,
    benchmark_id: str,
    result: object,
    json_output: bool,
) -> None:
    aggregate = result.aggregate  # type: ignore[attr-defined]
    overall = aggregate.overall
    failed_or_incomplete = overall.failed_case_count + overall.incomplete_case_count
    payload: dict[str, object] = {
        "status": "ok" if failed_or_incomplete == 0 else "failed",
        "command": command,
        "benchmark_id": benchmark_id,
        "case_count": overall.configured_case_count,
        "succeeded": overall.successful_case_count,
        "failed": overall.failed_case_count,
        "incomplete": overall.incomplete_case_count,
        "reused_case_count": len(result.reused_case_ids),  # type: ignore[attr-defined]
        "dispatched_case_count": len(result.dispatched_case_ids),  # type: ignore[attr-defined]
        "precision": overall.precision,
        "recall": overall.recall,
        "f1": overall.f1,
        "false_positive_rate": overall.false_positive_rate,
    }
    if json_output:
        emit_json(payload)
    else:
        typer.echo(
            f"{command} {benchmark_id}: {overall.successful_case_count}/"
            f"{overall.configured_case_count} succeeded, {overall.failed_case_count} failed, "
            f"{overall.incomplete_case_count} incomplete"
        )
    if failed_or_incomplete:
        raise typer.Exit(code=EXIT_BENCHMARK_FAILURE)


@benchmark_app.command("run")
def benchmark_run(
    config: Annotated[
        Path, typer.Option("--config", help="A normalized BenchmarkConfig JSON file.")
    ],
    output: Annotated[Path, typer.Option("--output", help="Output root for the benchmark run.")],
    resume: Annotated[
        bool, typer.Option("--resume/--no-resume", help="Reuse and revalidate prior successes.")
    ] = True,
    json_output: _JsonOption = False,
) -> None:
    """Run a benchmark configuration through the existing Milestone 8 runner."""
    try:
        benchmark_config = load_benchmark_config(config)
        runtime = build_runtime_metadata()
        result = run_benchmark(
            benchmark_config, output_root=Path(output), runtime=runtime, resume=resume
        )
    except Exception as exc:  # noqa: BLE001 - classified and reported by fail()
        raise fail(exc, json_mode=json_output) from exc
    _report_benchmark_result(
        command="benchmark run",
        benchmark_id=benchmark_config.benchmark_id,
        result=result,
        json_output=json_output,
    )


@benchmark_app.command("smoke")
def benchmark_smoke(
    output: Annotated[Path, typer.Option("--output", help="Output root for the smoke run.")],
    resume: Annotated[
        bool, typer.Option("--resume/--no-resume", help="Reuse and revalidate prior successes.")
    ] = True,
    json_output: _JsonOption = False,
) -> None:
    """Run the existing deterministic offline smoke benchmark configuration."""
    try:
        smoke_config = smoke_benchmark_config()
        runtime = build_runtime_metadata()
        result = run_benchmark(
            smoke_config, output_root=Path(output), runtime=runtime, resume=resume
        )
    except Exception as exc:  # noqa: BLE001 - classified and reported by fail()
        raise fail(exc, json_mode=json_output) from exc
    _report_benchmark_result(
        command="benchmark smoke",
        benchmark_id=smoke_config.benchmark_id,
        result=result,
        json_output=json_output,
    )


# --------------------------------------------------------------------------
# explain
# --------------------------------------------------------------------------


def _resolve_case_for_explain(
    public: AtomicArtifactStore, case_id: str | None
) -> BenchmarkCaseConfig:
    if case_id is not None:
        return load_case_config_by_id(public, case_id)
    return load_staged_case_config(public)


@app.command()
def explain(
    dir: Annotated[Path, typer.Option("--dir", help="A saved-stage or benchmark-run output root.")],
    finding: Annotated[
        str | None, typer.Option("--finding", help="Explain one finding by its finding_id.")
    ] = None,
    case_id: Annotated[
        str | None,
        typer.Option(
            "--case-id",
            help="The case id, when --dir holds more than one saved case (e.g. a benchmark run).",
        ),
    ] = None,
    json_output: _JsonOption = False,
) -> None:
    """Explain one saved public finding, or one case's saved public status.

    Reads only public saved artifacts. Never loads a manifest, never reveals
    a pre-corruption value or a hidden target role, and never reruns a
    detector or the benchmark.
    """
    try:
        public = AtomicArtifactStore(Path(dir) / PUBLIC_ROOT_NAME)
        case_config = _resolve_case_for_explain(public, case_id)
        report_path = workflow.public_artifact_path(case_config.benchmark_case_id, "audit_report")
        if not public.exists(report_path):
            raise ConfigLoadError(
                f"no finalized audit report for case {case_config.benchmark_case_id}"
            )
        report = AuditReport.model_validate(public.read_canonical(report_path))
        if finding is not None:
            matches = [item for item in report.findings if item.finding_id == finding]
            if not matches:
                raise ConfigLoadError(
                    f"no finding {finding!r} in case {case_config.benchmark_case_id}'s audit report"
                )
            target = matches[0]
            payload: dict[str, object] = {
                "status": "ok",
                "command": "explain",
                "benchmark_case_id": case_config.benchmark_case_id,
                "finding_id": target.finding_id,
                "rule_id": target.rule_id,
                "severity": target.severity,
                "confidence": target.confidence,
                "explanation": target.explanation,
                "affected_record_ids": target.affected_record_ids,
            }
        else:
            status_path = workflow.public_artifact_path(case_config.benchmark_case_id, "status")
            case_status = None
            if public.exists(status_path):
                case_status = BenchmarkCaseStatus.model_validate(
                    public.read_canonical(status_path)
                ).status
            payload = {
                "status": "ok",
                "command": "explain",
                "benchmark_case_id": case_config.benchmark_case_id,
                "case_kind": case_config.case_kind,
                "fault_profile": case_config.fault_profile,
                "finding_count": len(report.findings),
                "finding_ids": tuple(item.finding_id for item in report.findings),
                "case_status": case_status,
            }
    except Exception as exc:  # noqa: BLE001 - classified and reported by fail()
        raise fail(exc, json_mode=json_output) from exc

    if json_output:
        emit_json(payload)
    elif finding is not None:
        typer.echo(f"{payload['finding_id']} [{payload['severity']}]: {payload['explanation']}")
    else:
        typer.echo(
            f"case {payload['benchmark_case_id']} ({payload['fault_profile']}): "
            f"{payload['finding_count']} finding(s), status={payload['case_status']}"
        )


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """The installed console-script entry point.

    Invokes the Typer app in non-standalone mode so this function returns a
    plain exit code rather than calling ``sys.exit`` itself, which keeps it
    directly testable (``main([...]) == 0``) as well as usable as
    ``[project.scripts]``'s target. In non-standalone mode, a ``typer.Exit``
    raised inside a command is already converted into a returned exit code
    rather than propagated as an exception — only a usage error (unknown
    option, missing required option, and the like) still raises, and is
    addressed here only by its public, documented shape (an ``exit_code``
    attribute, and an optional ``show()`` method), never by importing
    Typer's private internal exception module.
    """
    command = typer.main.get_command(app)
    try:
        result = command.main(
            args=list(argv) if argv is not None else None,
            prog_name="quantcheck",
            standalone_mode=False,
        )
    except Exception as exc:  # noqa: BLE001 - a raised failure here is a usage error
        show = getattr(exc, "show", None)
        if callable(show):
            show()
        exit_code = getattr(exc, "exit_code", None)
        return int(exit_code) if isinstance(exit_code, int) else EXIT_INTERNAL_ERROR
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
