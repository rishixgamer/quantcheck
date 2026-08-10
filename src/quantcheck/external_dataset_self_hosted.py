"""Hardened batch entry point for the self-hosted external-audit container.

This module is deliberately only an operational adapter.  It binds the
existing path-free execution plan to files below one read-only input root and
then calls :func:`run_external_audit_execution`.  It contains no network,
authentication, secret, detector, scoring, or persistence implementation of
its own.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, TextIO

from pydantic import AfterValidator, BeforeValidator, ValidationError, model_validator

from quantcheck.benchmark_store import ArtifactIntegrityError, ArtifactPersistenceError
from quantcheck.corpus_schemas import CorpusModel
from quantcheck.external_dataset_execution import (
    ExternalAuditExecutionError,
    ExternalAuditExecutionResult,
    ExternalAuditPartitionInput,
    run_external_audit_execution,
)
from quantcheck.external_dataset_execution_contract import ExternalAuditExecutionPlanV1
from quantcheck.json_types import CanonicalizationError
from quantcheck.serialization import canonical_json_text, parse_canonical_json

__all__ = [
    "SELF_HOSTED_CONFIG_SPEC_VERSION",
    "SelfHostedConfigurationError",
    "SelfHostedPartitionBindingV1",
    "SelfHostedRunConfigV1",
    "load_self_hosted_config",
    "main",
    "run_self_hosted_audit",
]

SELF_HOSTED_CONFIG_SPEC_VERSION: Literal["quantcheck/self-hosted-run/v1"] = (
    "quantcheck/self-hosted-run/v1"
)
MAX_CONFIG_BYTES = 8 * 1024 * 1024
CONFIG_PATH_ENV = "QUANTCHECK_CONFIG_PATH"
INPUT_ROOT_ENV = "QUANTCHECK_INPUT_DIR"
OUTPUT_ROOT_ENV = "QUANTCHECK_OUTPUT_DIR"
WORK_ROOT_ENV = "QUANTCHECK_WORK_DIR"
TELEMETRY_ENV = "QUANTCHECK_TELEMETRY"

DEFAULT_CONFIG_PATH = "/config/run.json"
DEFAULT_INPUT_ROOT = "/input"
DEFAULT_OUTPUT_ROOT = "/output"
DEFAULT_WORK_ROOT = "/work"
SELF_TEST_CONFIG_PATH = "/opt/quantcheck/smoke/config/run.json"
SELF_TEST_INPUT_ROOT = "/opt/quantcheck/smoke/input"


class SelfHostedConfigurationError(ValueError):
    """Raised with a fixed, data-free message for invalid deployment input."""


def _to_tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


def _validate_relative_input_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise ValueError("input path must be a nonempty relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("input path must stay below the configured input root")
    if path.parts[0].startswith("~"):
        raise ValueError("input path must not use home-directory expansion")
    return value


RelativeInputPath = Annotated[str, BeforeValidator(_validate_relative_input_path)]


class SelfHostedPartitionBindingV1(CorpusModel):
    """One logical partition identifier bound to one mount-relative file."""

    partition_id: str
    input_path: RelativeInputPath


def _normalize_bindings(
    value: tuple[SelfHostedPartitionBindingV1, ...],
) -> tuple[SelfHostedPartitionBindingV1, ...]:
    ids = [item.partition_id for item in value]
    paths = [item.input_path for item in value]
    if not value:
        raise ValueError("at least one input binding is required")
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise ValueError("partition identifiers and input paths must be unique")
    return tuple(sorted(value, key=lambda item: item.partition_id))


PartitionBindingsV1 = Annotated[
    tuple[SelfHostedPartitionBindingV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_bindings),
]


class SelfHostedRunConfigV1(CorpusModel):
    """Secret-free operational binding for one existing logical audit plan."""

    spec_version: Literal["quantcheck/self-hosted-run/v1"] = SELF_HOSTED_CONFIG_SPEC_VERSION
    plan: ExternalAuditExecutionPlanV1
    bindings: PartitionBindingsV1
    worker_count: Literal[1, 2, 4] = 1
    telemetry: Literal[False] = False
    network_required: Literal[False] = False

    @model_validator(mode="after")
    def _check_exact_plan_binding(self) -> SelfHostedRunConfigV1:
        expected = {partition.partition_id for partition in self.plan.partitions}
        actual = {binding.partition_id for binding in self.bindings}
        if actual != expected:
            raise ValueError("bindings must exactly cover the execution plan")
        return self


def _read_config_bytes(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise SelfHostedConfigurationError("deployment configuration is invalid")
        if path.stat().st_size > MAX_CONFIG_BYTES:
            raise SelfHostedConfigurationError("deployment configuration is invalid")
        return path.read_bytes()
    except OSError as exc:
        raise SelfHostedConfigurationError("deployment configuration is invalid") from exc


def load_self_hosted_config(path: Path) -> SelfHostedRunConfigV1:
    """Load one bounded JSON config without copying validation details to logs."""
    try:
        document = parse_canonical_json(_read_config_bytes(Path(path)))
        return SelfHostedRunConfigV1.model_validate(document)
    except (CanonicalizationError, ValidationError) as exc:
        raise SelfHostedConfigurationError("deployment configuration is invalid") from exc


def _resolved_directory(path: Path, *, label: str, must_exist: bool) -> Path:
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError as exc:
        raise SelfHostedConfigurationError(f"{label} directory is invalid") from exc
    if must_exist and not resolved.is_dir():
        raise SelfHostedConfigurationError(f"{label} directory is invalid")
    return resolved


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _resolve_input(root: Path, relative_path: str) -> Path:
    candidate = root.joinpath(*PurePosixPath(relative_path).parts)
    try:
        cursor = root
        for part in PurePosixPath(relative_path).parts:
            cursor /= part
            if cursor.is_symlink():
                raise SelfHostedConfigurationError("partition input is invalid")
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise SelfHostedConfigurationError("partition input is invalid") from exc
    if not resolved.is_file():
        raise SelfHostedConfigurationError("partition input is invalid")
    return resolved


def run_self_hosted_audit(
    config: SelfHostedRunConfigV1,
    *,
    input_root: Path,
    output_root: Path,
    work_root: Path | None = None,
) -> ExternalAuditExecutionResult:
    """Run the existing local audit with confined, exact partition bindings."""
    resolved_input = _resolved_directory(Path(input_root), label="input", must_exist=True)
    resolved_output = _resolved_directory(Path(output_root), label="output", must_exist=True)
    if _paths_overlap(resolved_input, resolved_output):
        raise SelfHostedConfigurationError("input and output directories must be separate")
    if not os.access(resolved_output, os.W_OK | os.X_OK):
        raise SelfHostedConfigurationError("output directory is not writable")
    prior_tempdir = tempfile.tempdir
    active_tempdir: str | None = None
    if work_root is not None:
        resolved_work = _resolved_directory(Path(work_root), label="work", must_exist=True)
        if _paths_overlap(resolved_input, resolved_work) or _paths_overlap(
            resolved_output, resolved_work
        ):
            raise SelfHostedConfigurationError(
                "input, output, and work directories must be separate"
            )
        if not os.access(resolved_work, os.W_OK | os.X_OK):
            raise SelfHostedConfigurationError("work directory is not writable")
        active_tempdir = str(resolved_work)

    partitions = {partition.partition_id: partition for partition in config.plan.partitions}
    runtime_inputs = tuple(
        ExternalAuditPartitionInput(
            path=_resolve_input(resolved_input, binding.input_path),
            partition=partitions[binding.partition_id],
        )
        for binding in config.bindings
    )
    try:
        if active_tempdir is not None:
            tempfile.tempdir = active_tempdir
        return run_external_audit_execution(
            config.plan,
            runtime_inputs,
            output_root=resolved_output,
            worker_count=config.worker_count,
        )
    finally:
        tempfile.tempdir = prior_tempdir


def _emit(stream: TextIO, *, event: str, code: str | None = None, **fields: object) -> None:
    payload: dict[str, object] = {
        "event": event,
        "redacted": True,
        "spec_version": SELF_HOSTED_CONFIG_SPEC_VERSION,
        **fields,
    }
    if code is not None:
        payload["code"] = code
    stream.write(canonical_json_text(payload) + "\n")
    stream.flush()


def _telemetry_disabled(environ: Mapping[str, str]) -> bool:
    return environ.get(TELEMETRY_ENV, "0").strip().lower() in {"", "0", "false", "off"}


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Container entry point with fixed-code, data-free structured logging."""
    active_environment = os.environ if environ is None else environ
    stream = sys.stdout if stdout is None else stdout
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if arguments == ("--help",):
        stream.write(
            "usage: quantcheck-self-hosted [--self-test]\n"
            "Run one local, manifest-free QuantCheck external audit.\n"
        )
        return 0
    if arguments not in {(), ("--self-test",)}:
        _emit(stream, event="audit_failed", code="arguments_invalid")
        return 2
    if arguments == ("--self-test",):
        config_path = Path(SELF_TEST_CONFIG_PATH)
        input_root = Path(SELF_TEST_INPUT_ROOT)
    else:
        config_path = Path(active_environment.get(CONFIG_PATH_ENV, DEFAULT_CONFIG_PATH))
        input_root = Path(active_environment.get(INPUT_ROOT_ENV, DEFAULT_INPUT_ROOT))
    output_root = Path(active_environment.get(OUTPUT_ROOT_ENV, DEFAULT_OUTPUT_ROOT))
    work_root = Path(active_environment.get(WORK_ROOT_ENV, DEFAULT_WORK_ROOT))

    if not _telemetry_disabled(active_environment):
        _emit(stream, event="audit_failed", code="telemetry_must_remain_disabled")
        return 2

    try:
        config = load_self_hosted_config(config_path)
        _emit(stream, event="audit_started", run_id=config.plan.run_id)
        result = run_self_hosted_audit(
            config,
            input_root=input_root,
            output_root=output_root,
            work_root=work_root,
        )
    except SelfHostedConfigurationError:
        _emit(stream, event="audit_failed", code="configuration_invalid")
        return 2
    except (
        ArtifactIntegrityError,
        ArtifactPersistenceError,
        ExternalAuditExecutionError,
    ):
        _emit(stream, event="audit_failed", code="execution_failed")
        return 4
    except KeyboardInterrupt:
        _emit(stream, event="audit_failed", code="interrupted")
        return 130
    except Exception:  # pragma: no cover - last-resort redaction boundary
        _emit(stream, event="audit_failed", code="unexpected_internal_error")
        return 4

    _emit(
        stream,
        event="audit_completed",
        finalization_id=result.finalization.finalization_id,
        run_id=result.plan.run_id,
        status=result.finalization.status,
    )
    return 0 if result.finalization.status == "succeeded" else 3


if __name__ == "__main__":  # pragma: no cover - exercised by container/subprocess tests
    raise SystemExit(main())
