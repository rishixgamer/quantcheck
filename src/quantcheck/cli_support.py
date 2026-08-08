"""Shared CLI infrastructure: exit codes, JSON output, and strict config loading.

This module owns no scientific behavior. It is the thin layer between the
Typer command bodies in :mod:`quantcheck.cli` and the existing domain code:
one canonical JSON envelope writer (reusing the project's single canonical
serializer, never a competing ``json.dumps`` path), one stable exit-code
taxonomy, and strict loaders that hand parsed JSON straight to the existing
Pydantic schemas rather than inventing a second configuration format.
"""

from __future__ import annotations

import platform
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import typer
from pydantic import ValidationError

from quantcheck import __version__
from quantcheck.benchmark_contract import BenchmarkSeedClassError, public_case_directory
from quantcheck.benchmark_dispatch import BenchmarkDispatchError
from quantcheck.benchmark_expansion import (
    BenchmarkConfigurationError,
    benchmark_case_identity_matches,
    benchmark_config_identity_matches,
)
from quantcheck.benchmark_fixtures import UnknownBenchmarkFixtureError
from quantcheck.benchmark_store import (
    ArtifactIntegrityError,
    ArtifactPersistenceError,
    AtomicArtifactStore,
)
from quantcheck.json_types import CanonicalizationError
from quantcheck.saved_case_workflow import SavedStageError
from quantcheck.schemas import BenchmarkCaseConfig, BenchmarkConfig, RuntimeMetadata
from quantcheck.sec_adapter import (
    SecAdapterError,
    SecConceptSpec,
    SecNormalizationConfig,
)
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

__all__ = [
    "EXIT_ARTIFACT_ERROR",
    "EXIT_BENCHMARK_FAILURE",
    "EXIT_INTERNAL_ERROR",
    "EXIT_SEC_ERROR",
    "EXIT_SUCCESS",
    "EXIT_USER_ERROR",
    "ConfigLoadError",
    "build_runtime_metadata",
    "classify_cli_exception",
    "emit_json",
    "fail",
    "load_benchmark_config",
    "load_case_config",
    "load_case_config_by_id",
    "load_json_file",
    "load_sec_normalization_config",
    "load_staged_case_config",
    "parse_iso_date",
]

#: Stable exit-code taxonomy. Every command maps its outcome onto exactly one
#: of these; none of them changes meaning across commands.
EXIT_SUCCESS = 0
EXIT_USER_ERROR = 2
EXIT_ARTIFACT_ERROR = 3
EXIT_SEC_ERROR = 4
EXIT_BENCHMARK_FAILURE = 5
EXIT_INTERNAL_ERROR = 10

#: The only text an unexpected internal error may show publicly. Its own
#: message is never printed, so a stray exception can never leak a local
#: path, a private value, or an implementation detail.
_GENERIC_INTERNAL_MESSAGE = "an unexpected internal error occurred"


class ConfigLoadError(ValueError):
    """Raised when a user-supplied configuration file is rejected."""


def emit_json(payload: dict[str, object]) -> None:
    """Write exactly one canonical JSON result to stdout, then a newline.

    Reuses :func:`quantcheck.serialization.canonical_json_bytes` — the same
    serializer every artifact on disk is written with — so machine output has
    the identical Decimal/date encoding, key ordering, and null handling as
    saved artifacts.
    """
    sys.stdout.buffer.write(canonical_json_bytes(payload))
    sys.stdout.buffer.write(b"\n")


def build_runtime_metadata() -> RuntimeMetadata:
    """Construct this execution's :class:`RuntimeMetadata`.

    This is the one place the CLI reads the clock or the platform; the
    library itself never does, so tests can hold ``RuntimeMetadata`` fixed.
    """
    return RuntimeMetadata(
        code_version=f"quantcheck-{__version__}",
        python_version=platform.python_version(),
        platform=platform.platform(),
        generated_at=datetime.now(UTC),
    )


def load_json_file(path: Path) -> object:
    """Strictly load one canonical JSON file, rejecting anything ambiguous."""
    if not path.exists():
        raise ConfigLoadError(f"file not found: {path}")
    if path.is_dir():
        raise ConfigLoadError(f"expected a file, found a directory: {path}")
    if path.suffix != ".json":
        raise ConfigLoadError(f"expected a .json file, got: {path}")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigLoadError(f"could not read {path}") from exc
    try:
        return parse_canonical_json(raw)
    except CanonicalizationError as exc:
        raise ConfigLoadError(f"invalid JSON in {path}: {exc}") from exc


def load_case_config(path: Path) -> BenchmarkCaseConfig:
    """Strictly load one fully expanded :class:`BenchmarkCaseConfig`.

    Rejects unknown fields, invalid enum values, and duplicate/prohibited
    seeds through the existing strict schema, and rejects a case whose stored
    identifier does not match its own content.
    """
    parsed = load_json_file(path)
    try:
        case = BenchmarkCaseConfig.model_validate(parsed)
    except ValidationError as exc:
        raise ConfigLoadError(f"invalid case configuration in {path}") from exc
    if not benchmark_case_identity_matches(case):
        raise ConfigLoadError(f"case configuration identity does not match its content: {path}")
    return case


def load_benchmark_config(path: Path) -> BenchmarkConfig:
    """Strictly load one normalized :class:`BenchmarkConfig`."""
    parsed = load_json_file(path)
    try:
        config = BenchmarkConfig.model_validate(parsed)
    except ValidationError as exc:
        raise ConfigLoadError(f"invalid benchmark configuration in {path}") from exc
    if not benchmark_config_identity_matches(config):
        raise ConfigLoadError(
            f"benchmark configuration identity does not match its content: {path}"
        )
    return config


def parse_iso_date(value: object, *, field_name: str) -> date:
    if not isinstance(value, str):
        raise ConfigLoadError(f"{field_name} must be an ISO calendar date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigLoadError(f"{field_name} must be an ISO calendar date string") from exc


def load_sec_normalization_config(path: Path) -> SecNormalizationConfig:
    """Strictly load one :class:`SecNormalizationConfig` from a JSON file.

    ``SecNormalizationConfig`` is a plain dataclass, not a Pydantic schema, so
    this loader enforces the exact expected field set itself before handing
    validated values to the dataclass's own ``__post_init__`` normalization —
    it never widens what the adapter accepts.
    """
    parsed = load_json_file(path)
    if not isinstance(parsed, dict):
        raise ConfigLoadError(f"SEC normalization configuration must be a JSON object: {path}")
    required = {"cik", "concepts", "forms", "filed_from", "filed_through"}
    if set(parsed) != required:
        raise ConfigLoadError(
            f"SEC normalization configuration must have exactly the fields "
            f"{sorted(required)}: {path}"
        )
    concepts_raw = parsed["concepts"]
    if not isinstance(concepts_raw, list) or not concepts_raw:
        raise ConfigLoadError(f"concepts must be a nonempty JSON array: {path}")
    concept_fields = {"taxonomy", "concept", "unit", "period_type"}
    concepts: list[SecConceptSpec] = []
    for item in concepts_raw:
        if not isinstance(item, dict) or set(item) != concept_fields:
            raise ConfigLoadError(
                f"each concept entry must have exactly the fields {sorted(concept_fields)}: {path}"
            )
        try:
            concepts.append(SecConceptSpec(**item))
        except SecAdapterError as exc:
            raise ConfigLoadError(f"invalid concept entry in {path}") from exc
    forms_raw = parsed["forms"]
    if not isinstance(forms_raw, list) or not all(isinstance(form, str) for form in forms_raw):
        raise ConfigLoadError(f"forms must be a JSON array of strings: {path}")
    filed_from = parse_iso_date(parsed["filed_from"], field_name="filed_from")
    filed_through = parse_iso_date(parsed["filed_through"], field_name="filed_through")
    try:
        return SecNormalizationConfig(
            cik=parsed["cik"],
            concepts=tuple(concepts),
            forms=tuple(forms_raw),
            filed_from=filed_from,
            filed_through=filed_through,
        )
    except SecAdapterError as exc:
        raise ConfigLoadError(f"invalid SEC normalization configuration in {path}") from exc


def load_case_config_by_id(public: AtomicArtifactStore, case_id: str) -> BenchmarkCaseConfig:
    """Load one saved case's public configuration by its case id.

    Reads only ``public/`` — this is safe for ``explain`` and any other
    public-only reader, since it never opens the private store.
    """
    relative = f"{public_case_directory(case_id)}/case_config.json"
    if not public.exists(relative):
        raise ConfigLoadError(f"no saved case {case_id!r} under {public.root}")
    try:
        case = BenchmarkCaseConfig.model_validate(public.read_canonical(relative))
    except ValidationError as exc:
        raise ConfigLoadError(f"saved case configuration for {case_id!r} is invalid") from exc
    if not benchmark_case_identity_matches(case):
        raise ConfigLoadError(
            f"saved case configuration for {case_id!r} does not match its content"
        )
    return case


def load_staged_case_config(public: AtomicArtifactStore) -> BenchmarkCaseConfig:
    """Locate and load the single saved case under one public store root.

    A saved-stage ``inject``/``audit``/``evaluate`` output root holds exactly
    one case. Zero or more than one is rejected rather than guessed.
    """
    cases_dir = public.root / "cases"
    matches = sorted(cases_dir.glob("*/case_config.json")) if cases_dir.is_dir() else []
    if len(matches) != 1:
        raise ConfigLoadError(
            f"expected exactly one saved case under {public.root}, found {len(matches)}"
        )
    case_id = matches[0].parent.name
    return load_case_config_by_id(public, case_id)


def classify_cli_exception(exc: BaseException) -> tuple[int, str]:
    """Map one exception onto its stable public exit code and message.

    User/configuration problems keep their own message, because these are
    ordinary Pydantic/domain validation messages describing a field or an
    identity mismatch — never a private manifest value. An unexpected
    exception always reports the fixed generic sentence instead of its own
    message, so a stray internal error can never leak arbitrary detail.
    """
    if isinstance(
        exc,
        ConfigLoadError
        | ValidationError
        | BenchmarkConfigurationError
        | BenchmarkSeedClassError
        | UnknownBenchmarkFixtureError
        | BenchmarkDispatchError,
    ):
        return EXIT_USER_ERROR, str(exc)
    if isinstance(exc, SavedStageError | ArtifactIntegrityError | ArtifactPersistenceError):
        return EXIT_ARTIFACT_ERROR, str(exc)
    if isinstance(exc, SecAdapterError):
        return EXIT_SEC_ERROR, str(exc)
    return EXIT_INTERNAL_ERROR, _GENERIC_INTERNAL_MESSAGE


def fail(exc: BaseException, *, json_mode: bool) -> typer.Exit:
    """Report one exception on the correct stream and return its ``typer.Exit``.

    Callers must ``raise fail(exc, json_mode=...)``: this function returns
    rather than raises so the call site's own ``raise`` is what stops
    execution, keeping control flow visible at the call site.
    """
    exit_code, message = classify_cli_exception(exc)
    if json_mode:
        emit_json({"status": "error", "exit_code": exit_code, "message": message})
    else:
        typer.echo(f"error: {message}", err=True)
    return typer.Exit(code=exit_code)
