"""The strict public-only trust boundary for saved benchmark artifacts.

This module is the *only* way the presentation layer learns anything about a
benchmark. It reads below one selected public root, validates every artifact
against the schema the benchmark already wrote it with, re-verifies every
recorded SHA-256, and rejects anything it does not recognize.

Three properties are structural rather than promised:

* **It cannot reach private truth.** It addresses artifacts by role, every role
  resolves to a path below the selected public root, and the path grammar
  cannot express ``..``, an absolute path, a drive letter, or a ``private``
  segment at all. A symlink that tries to escape is caught by resolution.
* **It re-derives nothing scientific.** It imports no injector, detector,
  scorer, replay, or research module, and it never recomputes an aggregate: the
  saved ``aggregate_report.json`` is read as evidence, not rebuilt.
* **It works with the private tree deleted.** Nothing here opens a manifest, a
  clean/corrupted/repaired snapshot, a private research impact, or a private
  diagnostic, so removing ``private/`` entirely changes no result.

Reading is deliberately unforgiving. A malformed, mislinked, or hash-mismatched
artifact raises :class:`PublicArtifactError` instead of being guessed at, and an
unknown artifact role is refused rather than skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from quantcheck.benchmark_contract import (
    PRIVATE_ROOT_NAME,
    PUBLIC_CASE_ARTIFACT_NAMES,
    PUBLIC_ROOT_ARTIFACT_NAMES,
    PUBLIC_ROOT_NAME,
    REQUIRED_PUBLIC_CASE_ARTIFACTS,
    public_case_directory,
)
from quantcheck.benchmark_store import (
    ArtifactIntegrityError,
    ArtifactPersistenceError,
    AtomicArtifactStore,
)
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.json_types import CanonicalizationError
from quantcheck.schemas import (
    PUBLIC_RELATIVE_PATH_PATTERN,
    AuditInputSnapshot,
    AuditReport,
    BenchmarkAggregateReport,
    BenchmarkArtifactReference,
    BenchmarkCaseConfig,
    BenchmarkCaseMatrix,
    BenchmarkCaseScore,
    BenchmarkCaseStatus,
    BenchmarkConfig,
    BenchmarkPublicFailure,
    BenchmarkPublicIndex,
    BenchmarkResearchSummary,
    BenchmarkRuntimeMetadata,
    CanonicalModel,
)
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

__all__ = [
    "PUBLIC_ARTIFACT_ROLES",
    "PublicArtifactError",
    "PublicBenchmarkArtifacts",
    "PublicCaseArtifacts",
    "read_public_benchmark",
    "resolve_public_path",
    "validate_public_relative_path",
]

#: Every artifact role presentation is allowed to address, and nothing else. A
#: role outside this set is rejected rather than guessed, so a future private
#: artifact kind cannot become readable by being named in an index.
PUBLIC_ARTIFACT_ROLES: frozenset[str] = frozenset(PUBLIC_ROOT_ARTIFACT_NAMES) | frozenset(
    PUBLIC_CASE_ARTIFACT_NAMES
)


class PublicArtifactError(ValueError):
    """Raised when a public artifact tree cannot be trusted as read."""


def validate_public_relative_path(relative_path: object) -> str:
    """Validate one store-relative public path, or refuse it outright.

    The grammar does the heavy lifting: :data:`PUBLIC_RELATIVE_PATH_PATTERN`
    requires every segment to start with an alphanumeric character, which makes
    ``..``, a leading ``/``, a backslash, a ``C:`` drive letter, and ``~``
    *unrepresentable* rather than merely filtered. A ``private`` segment is
    refused separately.

    An unsafe path is never rewritten into a safe-looking one.
    """
    if not isinstance(relative_path, str):
        raise PublicArtifactError(
            f"a public artifact path must be a string, got {type(relative_path).__name__}"
        )
    if not relative_path:
        raise PublicArtifactError("a public artifact path must not be empty")
    if PUBLIC_RELATIVE_PATH_PATTERN.fullmatch(relative_path) is None:
        raise PublicArtifactError(f"unsafe or malformed public artifact path: {relative_path!r}")
    if any(segment == PRIVATE_ROOT_NAME for segment in relative_path.split("/")):
        raise PublicArtifactError(
            f"public artifact path {relative_path!r} addresses private storage"
        )
    return relative_path


def resolve_public_path(public_root: Path, relative_path: object) -> Path:
    """Resolve one validated relative path strictly below ``public_root``.

    Grammar validation alone cannot see a symlink, so the resolved location is
    checked too: a link inside the public tree pointing at the private tree, or
    anywhere else outside the root, resolves outside and is rejected.
    """
    validated = validate_public_relative_path(relative_path)
    root = Path(public_root)
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise PublicArtifactError("the selected public artifact root does not exist") from exc
    resolved = (root / validated).resolve()
    if resolved != resolved_root and not resolved.is_relative_to(resolved_root):
        raise PublicArtifactError(
            f"public artifact path {validated!r} resolves outside the selected public root"
        )
    return resolved


@dataclass(frozen=True, slots=True)
class PublicCaseArtifacts:
    """One case's public evidence, exactly as saved.

    ``terminal_status`` is ``succeeded``, ``failed``, or ``incomplete``. A case
    is only ever ``incomplete`` because the benchmark never wrote its terminal
    status; a status that exists but does not validate is an error, never a
    quietly downgraded case.
    """

    case: BenchmarkCaseConfig
    terminal_status: str
    status: BenchmarkCaseStatus | None = None
    audit_input: AuditInputSnapshot | None = None
    audit_report: AuditReport | None = None
    score: BenchmarkCaseScore | None = None
    research_summary: BenchmarkResearchSummary | None = None
    failure: BenchmarkPublicFailure | None = None


@dataclass(frozen=True, slots=True)
class PublicBenchmarkArtifacts:
    """Everything presentation is allowed to know about one saved benchmark.

    No filesystem root, destination, temporary directory, or other local path
    is retained: a path that is never carried cannot later be rendered.
    """

    config: BenchmarkConfig
    matrix: BenchmarkCaseMatrix
    aggregate: BenchmarkAggregateReport
    index: BenchmarkPublicIndex
    runtime: BenchmarkRuntimeMetadata | None
    cases: tuple[PublicCaseArtifacts, ...]


def _case_artifact_path(case_id: str, role: str) -> str:
    return f"{public_case_directory(case_id)}/{PUBLIC_CASE_ARTIFACT_NAMES[role]}"


def _select_public_root(artifact_root: Path) -> Path:
    """Accept either an output root containing ``public/`` or the tree itself.

    This is the convention ``aggregate_from_public_root`` already uses, so a
    copied-out public tree and a full run root are both readable.
    """
    root = Path(artifact_root)
    matrix_name = PUBLIC_ROOT_ARTIFACT_NAMES["case_matrix"]
    nested = root / PUBLIC_ROOT_NAME
    if (nested / matrix_name).is_file():
        return nested
    if (root / matrix_name).is_file():
        return root
    raise PublicArtifactError(
        "no public benchmark tree was found: expected a directory containing "
        f"{matrix_name!r}, or an output root containing {PUBLIC_ROOT_NAME}/"
    )


def _read_bytes(store: AtomicArtifactStore, root: Path, relative_path: str) -> bytes:
    destination = resolve_public_path(root, relative_path)
    if not destination.is_file():
        raise PublicArtifactError(f"public artifact {relative_path} is absent")
    try:
        return store.read_bytes(relative_path)
    except (ArtifactPersistenceError, ArtifactIntegrityError) as exc:
        raise PublicArtifactError(f"public artifact {relative_path} could not be read") from exc


def _read_model[ModelT: CanonicalModel](
    store: AtomicArtifactStore,
    root: Path,
    relative_path: str,
    model: type[ModelT],
) -> ModelT:
    payload = _read_bytes(store, root, relative_path)
    try:
        parsed = parse_canonical_json(payload)
    except CanonicalizationError as exc:
        raise PublicArtifactError(f"public artifact {relative_path} is not canonical JSON") from exc
    try:
        return model.model_validate(parsed)
    except ValidationError as exc:
        raise PublicArtifactError(
            f"public artifact {relative_path} does not validate as {model.__name__}"
        ) from exc


def _verify_reference(
    store: AtomicArtifactStore,
    root: Path,
    reference: BenchmarkArtifactReference,
    *,
    expected_path: str | None = None,
) -> None:
    """Verify one artifact reference's role, path, presence, and content hash."""
    if reference.kind not in PUBLIC_ARTIFACT_ROLES:
        raise PublicArtifactError(f"unknown public artifact role: {reference.kind!r}")
    validate_public_relative_path(reference.relative_path)
    if expected_path is not None and reference.relative_path != expected_path:
        raise PublicArtifactError(
            f"artifact reference {reference.relative_path!r} is not the expected path "
            f"{expected_path!r} for role {reference.kind!r}"
        )
    payload = _read_bytes(store, root, reference.relative_path)
    if sha256_hex_of_bytes(payload) != reference.content_hash:
        raise PublicArtifactError(
            f"public artifact {reference.relative_path} does not match its recorded content hash"
        )


def _expected_index_path(reference: BenchmarkArtifactReference) -> str:
    """Return the one path an indexed role is allowed to occupy.

    A root role has exactly one path. A case role must live under its own
    case's directory, which is what rejects a cross-case reference: the case
    identifier is taken from the path itself and the path is then rebuilt from
    that identifier and the role, so the two must agree.
    """
    if reference.kind in PUBLIC_ROOT_ARTIFACT_NAMES:
        return PUBLIC_ROOT_ARTIFACT_NAMES[reference.kind]
    segments = reference.relative_path.split("/")
    if len(segments) != 3 or segments[0] != "cases":
        raise PublicArtifactError(
            f"public case artifact {reference.relative_path!r} is not under its own case directory"
        )
    return _case_artifact_path(segments[1], reference.kind)


def _read_index(store: AtomicArtifactStore, root: Path) -> BenchmarkPublicIndex:
    index = _read_model(
        store, root, PUBLIC_ROOT_ARTIFACT_NAMES["public_index"], BenchmarkPublicIndex
    )
    for reference in index.entries:
        # The role is checked before the path is derived from it: an unknown
        # role must be reported as unknown, not as a path that happens not to
        # fit the shape a case role would have required.
        if reference.kind not in PUBLIC_ARTIFACT_ROLES:
            raise PublicArtifactError(f"unknown public artifact role: {reference.kind!r}")
        _verify_reference(store, root, reference, expected_path=_expected_index_path(reference))
    return index


def _read_status(
    store: AtomicArtifactStore, root: Path, case: BenchmarkCaseConfig
) -> BenchmarkCaseStatus | None:
    """Read one case's terminal status, or ``None`` if it was never written."""
    relative = _case_artifact_path(case.benchmark_case_id, "status")
    if not (root / relative).is_file():
        return None
    status = _read_model(store, root, relative, BenchmarkCaseStatus)
    if (
        status.benchmark_case_id != case.benchmark_case_id
        or status.benchmark_id != case.benchmark_id
    ):
        raise PublicArtifactError(
            f"stored status at {relative} describes a different case than the matrix does"
        )
    return status


def _read_successful_case(
    store: AtomicArtifactStore,
    root: Path,
    case: BenchmarkCaseConfig,
    status: BenchmarkCaseStatus,
) -> PublicCaseArtifacts | None:
    """Read a case whose status claims success, verifying that claim in full.

    Returns ``None`` when the success claim is not substantiated by the saved
    evidence. The caller then reports the case as ``incomplete``, which is
    exactly what ``benchmark_aggregate`` independently does, so the reader can
    never contradict the saved aggregate report about a case's outcome.

    Structural problems are different and still raise: an unknown artifact
    role, a reference into another case's directory, and an unsafe path are
    defects in how the tree *addresses* evidence, not in the evidence itself.
    """
    referenced: dict[str, BenchmarkArtifactReference] = {}
    for reference in status.artifacts:
        if reference.kind not in PUBLIC_CASE_ARTIFACT_NAMES:
            raise PublicArtifactError(f"unknown public case artifact role: {reference.kind!r}")
        expected = _case_artifact_path(case.benchmark_case_id, reference.kind)
        validate_public_relative_path(reference.relative_path)
        if reference.relative_path != expected:
            raise PublicArtifactError(
                f"case {case.benchmark_case_id} references {reference.relative_path!r}, which is "
                f"not its own {reference.kind!r} artifact"
            )
        referenced[reference.kind] = reference

    required = list(REQUIRED_PUBLIC_CASE_ARTIFACTS)
    if case.case_kind == "fault":
        required.append("research_summary")
    if any(role not in referenced for role in required):
        return None

    try:
        for reference in status.artifacts:
            payload = _read_bytes(store, root, reference.relative_path)
            if sha256_hex_of_bytes(payload) != reference.content_hash:
                return None

        if _read_bytes(store, root, referenced["case_config"].relative_path) != (
            canonical_json_bytes(case)
        ):
            return None

        audit_input = _read_model(
            store, root, referenced["audit_input"].relative_path, AuditInputSnapshot
        )
        audit_report = _read_model(
            store, root, referenced["audit_report"].relative_path, AuditReport
        )
        score = _read_model(store, root, referenced["score"].relative_path, BenchmarkCaseScore)
        research: BenchmarkResearchSummary | None = None
        if "research_summary" in referenced:
            research = _read_model(
                store, root, referenced["research_summary"].relative_path, BenchmarkResearchSummary
            )
    except PublicArtifactError:
        return None

    if audit_report.audit_input_id != audit_input.audit_input_id:
        return None
    if score.benchmark_case_id != case.benchmark_case_id or score.benchmark_id != case.benchmark_id:
        return None
    if score.case_kind != case.case_kind or score.fault_profile != case.fault_profile:
        return None
    if research is not None and research.benchmark_case_id != case.benchmark_case_id:
        return None

    return PublicCaseArtifacts(
        case=case,
        terminal_status="succeeded",
        status=status,
        audit_input=audit_input,
        audit_report=audit_report,
        score=score,
        research_summary=research,
    )


def _read_case(
    store: AtomicArtifactStore, root: Path, case: BenchmarkCaseConfig
) -> PublicCaseArtifacts:
    status = _read_status(store, root, case)
    if status is None:
        # The benchmark never wrote a terminal status for this case. That is a
        # legitimate incomplete outcome and is preserved as one: a case that
        # vanished from the denominator is how a broken run would come to look
        # successful.
        return PublicCaseArtifacts(case=case, terminal_status="incomplete")
    if status.status == "succeeded":
        substantiated = _read_successful_case(store, root, case, status)
        if substantiated is not None:
            return substantiated
        return PublicCaseArtifacts(case=case, terminal_status="incomplete", status=status)
    terminal = "failed" if status.status == "failed" else "incomplete"
    return PublicCaseArtifacts(
        case=case,
        terminal_status=terminal,
        status=status,
        failure=status.failure,
    )


def read_public_benchmark(artifact_root: Path) -> PublicBenchmarkArtifacts:
    """Read one saved benchmark's public evidence, strictly and completely.

    ``artifact_root`` may be a benchmark output root containing ``public/`` or a
    copied-out public tree itself. Nothing below ``private/`` is opened, so the
    call behaves identically whether or not a private tree exists.

    Raises:
        PublicArtifactError: for a missing, malformed, mislinked, hash-mismatched,
            unsafely addressed, or unknown-role artifact.
    """
    root = _select_public_root(artifact_root)
    store = AtomicArtifactStore(root)

    config = _read_model(
        store, root, PUBLIC_ROOT_ARTIFACT_NAMES["benchmark_config"], BenchmarkConfig
    )
    matrix = _read_model(
        store, root, PUBLIC_ROOT_ARTIFACT_NAMES["case_matrix"], BenchmarkCaseMatrix
    )
    aggregate = _read_model(
        store, root, PUBLIC_ROOT_ARTIFACT_NAMES["aggregate_report"], BenchmarkAggregateReport
    )
    index = _read_index(store, root)

    runtime: BenchmarkRuntimeMetadata | None = None
    runtime_path = PUBLIC_ROOT_ARTIFACT_NAMES["runtime_metadata"]
    if (root / runtime_path).is_file():
        runtime = _read_model(store, root, runtime_path, BenchmarkRuntimeMetadata)

    identities = {
        "benchmark configuration": config.benchmark_id,
        "case matrix": matrix.benchmark_id,
        "aggregate report": aggregate.benchmark_id,
        "public index": index.benchmark_id,
    }
    if runtime is not None:
        identities["runtime metadata"] = runtime.benchmark_id
    mismatched = sorted(name for name, value in identities.items() if value != config.benchmark_id)
    if mismatched:
        raise PublicArtifactError(
            f"public artifacts disagree about the benchmark identity: {mismatched}"
        )
    if matrix.spec_version != config.spec_version or aggregate.spec_version != config.spec_version:
        raise PublicArtifactError("public artifacts disagree about the benchmark spec version")

    cases = tuple(_read_case(store, root, case) for case in matrix.cases)

    # The presentation shows the saved aggregate's own numbers. If those numbers
    # no longer describe the saved case statuses, the tree is stale or tampered
    # and a rendered page would be quietly self-contradictory, so it is refused
    # rather than displayed.
    observed = {
        "configured": len(cases),
        "succeeded": sum(1 for case in cases if case.terminal_status == "succeeded"),
        "failed": sum(1 for case in cases if case.terminal_status == "failed"),
        "incomplete": sum(1 for case in cases if case.terminal_status == "incomplete"),
    }
    recorded = {
        "configured": aggregate.overall.configured_case_count,
        "succeeded": aggregate.overall.successful_case_count,
        "failed": aggregate.overall.failed_case_count,
        "incomplete": aggregate.overall.incomplete_case_count,
    }
    if observed != recorded:
        raise PublicArtifactError(
            "the saved aggregate report does not describe the saved case statuses: "
            f"statuses report {observed}, the aggregate reports {recorded}"
        )

    return PublicBenchmarkArtifacts(
        config=config,
        matrix=matrix,
        aggregate=aggregate,
        index=index,
        runtime=runtime,
        cases=cases,
    )
