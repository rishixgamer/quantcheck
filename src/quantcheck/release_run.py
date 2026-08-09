"""The release-only path that executes the reserved final seeds.

This is the single place in QuantCheck where held-out seeds run. It is
deliberately not reachable from the CLI, from ``run_benchmark``, or from any
ordinary API: a caller must hand it a saved freeze record, and the record must
still verify against the current repository byte for byte.

The order below is the whole point of the module, so it is enforced by control
flow rather than by documentation:

1. validate the release configuration's *shape* — with no authorization open,
   so a malformed release request does no final-seed work at all;
2. open the final-seed authorization for the complete reserved partition;
3. build the release benchmark configuration;
4. verify the frozen candidate against that configuration and the repository;
5. only then dispatch the first final case, through the ordinary
   ``run_benchmark`` engine with no scientific behaviour changed.

Step 4 raises before any case dispatches, so a drifted repository cannot
produce held-out evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quantcheck.benchmark_expansion import expand_benchmark_cases
from quantcheck.benchmark_runner import BenchmarkRunResult, run_benchmark
from quantcheck.release_config import release_benchmark_config
from quantcheck.release_contract import (
    RELEASE_CONTROL_CASE_COUNT,
    RELEASE_FAULT_CASE_COUNT,
    RELEASE_SEEDS,
    RELEASE_TOTAL_CASE_COUNT,
)
from quantcheck.release_freeze import (
    ReleaseFreezeError,
    ReleaseFreezeRecord,
    build_release_freeze_record,
    read_release_freeze_record,
    verify_release_freeze_record,
)
from quantcheck.release_gate import reserved_final_seeds
from quantcheck.schemas import BenchmarkConfig, RuntimeMetadata

__all__ = [
    "ReleaseRunError",
    "ReleaseRunResult",
    "build_authorized_release_config",
    "build_authorized_release_freeze",
    "run_release_benchmark",
    "verify_authorized_release_freeze",
]

#: The label an authorization carries while the candidate it will freeze does
#: not exist yet. It never reaches an artifact: the real identity is derived
#: from the frozen content once the record is built.
_PROVISIONAL_CANDIDATE = "pending-release-freeze"


class ReleaseRunError(RuntimeError):
    """Raised when a release run is requested without a valid frozen candidate."""


@dataclass(frozen=True, slots=True)
class ReleaseRunResult:
    """One held-out release run and the candidate it was produced under."""

    release_candidate_id: str
    freeze_record: ReleaseFreezeRecord
    benchmark: BenchmarkRunResult


def _check_release_request(*, repo_root: Path, freeze_record_path: Path) -> ReleaseFreezeRecord:
    """Validate the release request before any authorization is opened.

    Everything here is deliberately final-seed-free: a missing repository, a
    missing or malformed freeze record, or a record for the wrong seed
    partition is rejected while the gate is still closed, so a malformed
    release configuration can never cause held-out work.
    """
    if not repo_root.is_dir():
        raise ReleaseRunError("the release path requires an existing repository root")
    record = read_release_freeze_record(freeze_record_path)
    if tuple(record.final_seeds) != RELEASE_SEEDS:
        raise ReleaseRunError("the freeze record does not cover the reserved final seed partition")
    if record.total_case_count != RELEASE_TOTAL_CASE_COUNT:
        raise ReleaseRunError("the freeze record's case total does not match the release contract")
    if record.fault_case_count != RELEASE_FAULT_CASE_COUNT:
        raise ReleaseRunError("the freeze record's fault case count does not match the contract")
    if record.control_case_count != RELEASE_CONTROL_CASE_COUNT:
        raise ReleaseRunError("the freeze record's control case count does not match the contract")
    return record


def build_authorized_release_config(
    *,
    release_candidate_id: str,
) -> BenchmarkConfig:
    """Build the release configuration under a scoped final-seed authorization.

    Exposed for the freeze script and for tests. It opens and closes the
    authorization itself, so no reserved seed stays permitted after it returns.
    """
    with reserved_final_seeds(
        release_candidate_id=release_candidate_id,
        seeds=RELEASE_SEEDS,
    ):
        return release_benchmark_config()


def build_authorized_release_freeze(
    *,
    repo_root: Path,
    package_version: str,
    python_requirement: str,
) -> ReleaseFreezeRecord:
    """Freeze a release candidate under a scoped final-seed authorization.

    ``release_freeze`` itself is authorization-agnostic — it is a set of pure
    functions over a configuration — so that this module stays the only one
    that can open the gate. Building the record needs the authorization because
    expanding the release matrix classifies reserved seeds.
    """
    with reserved_final_seeds(
        release_candidate_id=_PROVISIONAL_CANDIDATE,
        seeds=RELEASE_SEEDS,
    ):
        return build_release_freeze_record(
            repo_root=repo_root,
            package_version=package_version,
            python_requirement=python_requirement,
            config=release_benchmark_config(),
        )


def verify_authorized_release_freeze(
    record: ReleaseFreezeRecord,
    *,
    repo_root: Path,
) -> None:
    """Verify a saved candidate under a scoped final-seed authorization.

    Raises:
        ReleaseFreezeError: when any frozen input has drifted.
    """
    with reserved_final_seeds(
        release_candidate_id=record.release_candidate_id,
        seeds=RELEASE_SEEDS,
    ):
        verify_release_freeze_record(
            record,
            repo_root=repo_root,
            config=release_benchmark_config(),
        )


def run_release_benchmark(
    *,
    repo_root: Path,
    freeze_record_path: Path,
    output_root: Path,
    runtime: RuntimeMetadata,
    resume: bool = True,
) -> ReleaseRunResult:
    """Execute the frozen release matrix against a verified release candidate.

    No scientific behaviour differs from an ordinary benchmark run: this calls
    the same ``run_benchmark`` engine, the same dispatcher, the same detectors,
    the same scorers, and the same persistence. The only difference is that the
    reserved final seeds are representable inside the authorization block.
    """
    record = _check_release_request(repo_root=repo_root, freeze_record_path=freeze_record_path)

    with reserved_final_seeds(
        release_candidate_id=record.release_candidate_id,
        seeds=RELEASE_SEEDS,
    ):
        config = release_benchmark_config()
        # Verification happens *inside* the authorization because it needs to
        # canonicalize the reserved-seed configuration, and *before* any
        # dispatch because a drifted candidate must produce no evidence.
        try:
            verify_release_freeze_record(record, repo_root=repo_root, config=config)
        except ReleaseFreezeError as exc:
            raise ReleaseRunError(
                f"the frozen release candidate no longer verifies: {exc}"
            ) from exc

        matrix = expand_benchmark_cases(config)
        if matrix.case_count != RELEASE_TOTAL_CASE_COUNT:
            raise ReleaseRunError(
                f"the release matrix must expand to {RELEASE_TOTAL_CASE_COUNT} cases, "
                f"got {matrix.case_count}"
            )
        if any(case.seed_class != "final" for case in matrix.cases):
            raise ReleaseRunError("every release case must carry the final seed class")

        benchmark = run_benchmark(
            config,
            output_root=output_root,
            runtime=runtime,
            resume=resume,
        )

    return ReleaseRunResult(
        release_candidate_id=record.release_candidate_id,
        freeze_record=record,
        benchmark=benchmark,
    )
