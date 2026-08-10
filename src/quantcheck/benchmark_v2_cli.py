"""Additive CLI for the versioned v0.2 execution/evaluation contract.

The installed v0.1 ``quantcheck`` command is checksum-frozen and remains
byte-for-byte unchanged.  This module is invoked as
``python -m quantcheck.benchmark_v2_cli`` and consumes the exact same v0.2
Pydantic models the Python API uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from quantcheck.benchmark_store import (
    ArtifactIntegrityError,
    ArtifactPersistenceError,
    AtomicArtifactStore,
)
from quantcheck.benchmark_v2_case import run_benchmark_v2_case
from quantcheck.benchmark_v2_config import benchmark_v2_case_identity_matches
from quantcheck.benchmark_v2_contract import ALL_V2_DETECTORS, DetectorKeyV2
from quantcheck.benchmark_v2_execution import run_selected_detectors_v2
from quantcheck.benchmark_v2_schemas import (
    BenchmarkV2CaseConfig,
    DetectorExecutionConfigV2,
)
from quantcheck.schemas import AuditInputSnapshot, BenchmarkDetectorConfigs
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

__all__ = ["app", "main"]

app = typer.Typer(
    name="quantcheck-v2",
    help="Versioned v0.2 selected-detector execution and finding evaluation.",
    no_args_is_help=True,
    add_completion=False,
)


class V2CliInputError(ValueError):
    """A stable user-input failure for the additive v0.2 CLI."""


def _load(path: Path) -> object:
    if not path.is_file() or path.suffix != ".json":
        raise V2CliInputError("expected an existing canonical .json file")
    try:
        return parse_canonical_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise V2CliInputError("could not read canonical JSON input") from exc


def _selection(text: str) -> tuple[DetectorKeyV2, ...]:
    if text == "all":
        return ALL_V2_DETECTORS
    values = tuple(part for part in text.split(",") if part)
    try:
        config = DetectorExecutionConfigV2.model_validate({"selected_detectors": values})
    except ValidationError as exc:
        raise V2CliInputError("invalid detector selection") from exc
    return config.selected_detectors


def _detector_config(path: Path | None) -> BenchmarkDetectorConfigs:
    if path is None:
        return BenchmarkDetectorConfigs()
    try:
        return BenchmarkDetectorConfigs.model_validate(_load(path))
    except ValidationError as exc:
        raise V2CliInputError("invalid frozen detector configuration") from exc


def _emit(payload: dict[str, object], *, json_output: bool) -> None:
    if json_output:
        typer.echo(canonical_json_bytes(payload).decode("utf-8"))
    else:
        typer.echo(str(payload["message"]))


def _fail(exc: Exception, *, json_output: bool) -> typer.Exit:
    if isinstance(exc, V2CliInputError | ValidationError):
        code = 2
        message = "v0.2 input configuration was rejected"
    elif isinstance(exc, ArtifactIntegrityError | ArtifactPersistenceError):
        code = 3
        message = "a v0.2 artifact could not be persisted safely"
    else:
        code = 10
        message = "an unexpected internal error occurred"
    if json_output:
        typer.echo(
            canonical_json_bytes({"status": "error", "exit_code": code, "message": message}).decode(
                "utf-8"
            ),
            err=True,
        )
    else:
        typer.echo(message, err=True)
    return typer.Exit(code=code)


@app.command("audit")
def audit(
    audit_input: Annotated[
        Path, typer.Option("--audit-input", help="Canonical sanitized AuditInputSnapshot JSON.")
    ],
    output: Annotated[Path, typer.Option(help="Immutable detector-execution JSON destination.")],
    detectors: Annotated[
        str,
        typer.Option(
            help=(
                "'all' or a comma-separated selection of duplicate_observation, "
                "lookahead_timestamp, revision_overwrite, unit_drift."
            )
        ),
    ] = "all",
    detector_config: Annotated[
        Path | None,
        typer.Option(
            "--detector-config",
            help="Optional canonical frozen BenchmarkDetectorConfigs JSON.",
        ),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Run an explicit detector selection on the unchanged audit boundary."""
    try:
        snapshot = AuditInputSnapshot.model_validate(_load(audit_input))
        config = DetectorExecutionConfigV2(
            selected_detectors=_selection(detectors),
            detector_configs=_detector_config(detector_config),
        )
        execution = run_selected_detectors_v2(snapshot, config)
        store = AtomicArtifactStore(output.parent)
        store.write_immutable(output.name, execution)
    except Exception as exc:  # noqa: BLE001 - stable public mapping above
        raise _fail(exc, json_output=json_output) from exc
    _emit(
        {
            "status": "ok",
            "command": "audit",
            "detector_execution_id": execution.detector_execution_id,
            "selected_detectors": execution.config.selected_detectors,
            "finding_count": execution.finding_count,
            "message": (
                f"detector execution {execution.detector_execution_id}: "
                f"{execution.finding_count} finding(s)"
            ),
        },
        json_output=json_output,
    )


@app.command("run-case")
def run_case(
    case_path: Annotated[
        Path, typer.Option("--case", help="Canonical expanded BenchmarkV2CaseConfig JSON.")
    ],
    output: Annotated[Path, typer.Option(help="Root for canonical public/private v0.2 evidence.")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Run one corpus-backed case and its mandatory paired clean control."""
    try:
        case = BenchmarkV2CaseConfig.model_validate(_load(case_path))
        if not benchmark_v2_case_identity_matches(case):
            raise V2CliInputError("case identity does not match its content")
        result = run_benchmark_v2_case(case)
        public = AtomicArtifactStore(output / "public")
        private = AtomicArtifactStore(output / "private")
        public.write_immutable("case_config.json", result.case)
        public.write_immutable("clean_control_execution.json", result.clean_control_execution)
        public.write_immutable("corrupted_execution.json", result.corrupted_execution)
        public.write_immutable("evaluation.json", result.evaluation)
        private.write_immutable("clean_snapshot.json", result.clean_snapshot)
        private.write_immutable("corrupted_snapshot.json", result.corrupted_snapshot)
        private.write_immutable("manifest.json", result.manifest)
    except Exception as exc:  # noqa: BLE001 - stable public mapping above
        raise _fail(exc, json_output=json_output) from exc
    interpretation = result.evaluation.production_interpretation
    _emit(
        {
            "status": "ok",
            "command": "run-case",
            "benchmark_v2_case_id": case.benchmark_v2_case_id,
            "evaluation_id": result.evaluation.evaluation_id,
            "primary_matched_fault_count": result.evaluation.primary_matched_fault_count,
            "secondary_corroborating_count": interpretation.secondary_corroborating_count,
            "independent_background_count": interpretation.independent_background_count,
            "unmatched_count": interpretation.unmatched_count,
            "message": (
                f"case {case.benchmark_v2_case_id}: "
                f"primary={result.evaluation.primary_matched_fault_count}/"
                f"{result.evaluation.injected_fault_count}, "
                f"secondary={interpretation.secondary_corroborating_count}, "
                f"background={interpretation.independent_background_count}, "
                f"unmatched={interpretation.unmatched_count}"
            ),
        },
        json_output=json_output,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = app(args=list(argv) if argv is not None else None, standalone_mode=False)
    except typer.Exit as exc:
        return int(exc.exit_code)
    return 0 if result is None else int(result)


if __name__ == "__main__":  # pragma: no cover - exercised by subprocess tests
    raise SystemExit(main())
