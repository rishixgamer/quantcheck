"""Frozen rules shared by every Milestone 8 benchmark stage.

This module owns the benchmark's own conventions — specification version, seed
partitions, the exact four supported fault profiles, the artifact tree layout,
and the public failure taxonomy. It deliberately owns no scientific rule: fault
eligibility, detector thresholds, matching, replay, and research behavior stay
in the four completed fault-family modules and are only *called* from here.
"""

from __future__ import annotations

from typing import Literal

from quantcheck.release_gate import final_seed_authorized
from quantcheck.schemas import (
    DEVELOPMENT_SEED_RANGE,
    FINAL_SEED_RANGE,
    VALIDATION_SEED_RANGE,
    BenchmarkFailureCategory,
    BenchmarkFailureStage,
    BenchmarkFaultProfile,
    BenchmarkSeedClass,
)

__all__ = [
    "ALL_SEED_CLASSES",
    "BENCHMARK_FAULT_PROFILES",
    "BENCHMARK_SPEC_VERSION",
    "PRIVATE_CASE_ARTIFACT_NAMES",
    "PRIVATE_ROOT_NAME",
    "PUBLIC_CASE_ARTIFACT_NAMES",
    "PUBLIC_ROOT_ARTIFACT_NAMES",
    "PUBLIC_ROOT_NAME",
    "REQUIRED_PUBLIC_CASE_ARTIFACTS",
    "SEED_CLASSES",
    "BenchmarkSeedClassError",
    "classify_benchmark_seed",
    "is_final_seed",
    "public_case_directory",
    "redacted_failure_message",
    "require_seed_execution_authorized",
]

#: The benchmark contract version. Every benchmark artifact carries it, and
#: changing it changes every benchmark identifier.
BENCHMARK_SPEC_VERSION: Literal["quantcheck/benchmark/v1"] = "quantcheck/benchmark/v1"

#: The exact fault profiles v0.1 supports, in stable order. This is a closed
#: list on purpose: Milestone 8 dispatches to four completed vertical slices,
#: not to a generic plugin registry.
BENCHMARK_FAULT_PROFILES: tuple[BenchmarkFaultProfile, ...] = (
    "duplicate_observation",
    "lookahead_timestamp",
    "revision_overwrite",
    "unit_drift",
)

#: Seed classes ordinary execution can produce. ``final`` is deliberately
#: absent: it exists as a ``BenchmarkSeedClass`` value only so held-out release
#: artifacts can label themselves, and is reachable only under an active
#: ``quantcheck.release_gate`` authorization.
SEED_CLASSES: tuple[BenchmarkSeedClass, ...] = ("development", "validation")

#: Every seed class a saved benchmark artifact may carry, including the
#: release-only one.
ALL_SEED_CLASSES: tuple[BenchmarkSeedClass, ...] = ("development", "validation", "final")

PUBLIC_ROOT_NAME = "public"
PRIVATE_ROOT_NAME = "private"

#: Public artifacts stored at the root of the public tree. The runner owns the
#: writing of these; the public reader owns the reading. Both address them
#: through this single mapping so a role name can never mean two paths.
PUBLIC_ROOT_ARTIFACT_NAMES: dict[str, str] = {
    "benchmark_config": "benchmark_config.json",
    "case_matrix": "case_matrix.json",
    "runtime_metadata": "runtime_metadata.json",
    "aggregate_report": "aggregate_report.json",
    "public_index": "index.json",
}

#: Public per-case artifacts. ``status.json`` is written last and is the only
#: terminal success marker, but its presence alone never proves success.
PUBLIC_CASE_ARTIFACT_NAMES: dict[str, str] = {
    "case_config": "case_config.json",
    "audit_input": "audit_input.json",
    "audit_report": "audit_report.json",
    "score": "score.json",
    "research_summary": "research_summary.json",
    "status": "status.json",
}

#: Public artifacts every successful case must have persisted before its status
#: may claim success. ``research_summary`` is required for fault cases only,
#: because a clean control injects nothing and therefore compares nothing.
REQUIRED_PUBLIC_CASE_ARTIFACTS: tuple[str, ...] = (
    "case_config",
    "audit_input",
    "audit_report",
    "score",
)

#: Private per-case artifacts: hidden truth for exact replay and forensics.
PRIVATE_CASE_ARTIFACT_NAMES: dict[str, str] = {
    "clean_snapshot": "clean_snapshot.json",
    "corrupted_snapshot": "corrupted_snapshot.json",
    "manifest": "manifest.json",
    "repaired_snapshot": "repaired_snapshot.json",
    "research_impact": "research_impact.json",
    "private_index": "private_index.json",
    "diagnostics": "diagnostics.json",
}


class BenchmarkSeedClassError(ValueError):
    """Raised for a seed outside every partition ordinary execution allows."""


def is_final_seed(seed: int) -> bool:
    """Report whether a seed belongs to the reserved final/release partition."""
    return seed in FINAL_SEED_RANGE


def classify_benchmark_seed(seed: int) -> BenchmarkSeedClass:
    """Classify one benchmark seed.

    Development seeds are ``0-9`` and validation seeds are ``100-109``. Final
    seeds ``1000-1009`` are held-out release evidence: they are rejected here
    unless ``quantcheck.release_gate`` has an authorization active for the
    complete reserved partition, which only the Milestone 11 release path can
    open. There is still no flag, environment variable, or parameter on this
    function that authorizes them, because an escape hatch is exactly how
    held-out evidence stops being held out.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise BenchmarkSeedClassError(f"seed must be an integer, got {type(seed).__name__}")
    if seed in DEVELOPMENT_SEED_RANGE:
        return "development"
    if seed in VALIDATION_SEED_RANGE:
        return "validation"
    if seed in FINAL_SEED_RANGE:
        if final_seed_authorized(seed):
            return "final"
        raise BenchmarkSeedClassError(
            f"final/release seed {seed} is reserved and is not authorized for ordinary execution"
        )
    raise BenchmarkSeedClassError(f"unclassified benchmark seed: {seed}")


def require_seed_execution_authorized(seed: int) -> None:
    """Refuse to *execute* a reserved final seed without release authorization.

    This is the security boundary, and it is deliberately about execution
    rather than representation. A reserved seed may appear in a saved artifact
    — the public reader, the presentation model, the HTML summary, and the
    dashboard all have to read released held-out evidence, and refusing to
    deserialize it would make the public evidence package unreadable by the
    very surfaces built to present it. What must never happen without an
    authorization is *running* a case at one of those seeds.

    Every execution entry point calls this: benchmark configuration building,
    expansion (via :func:`classify_benchmark_seed`), the case dispatcher, and
    each saved-stage workflow function.
    """
    if seed in FINAL_SEED_RANGE and not final_seed_authorized(seed):
        raise BenchmarkSeedClassError(
            f"final/release seed {seed} is reserved and is not authorized for ordinary execution"
        )


def public_case_directory(benchmark_case_id: str) -> str:
    """Return the public tree's relative directory for one case."""
    return f"cases/{benchmark_case_id}"


#: Fixed, human-safe public failure sentences. Public failure text is a stable
#: constant per category so that no exception message, value, or local path can
#: reach a public artifact through string formatting.
_REDACTED_MESSAGES: dict[BenchmarkFailureCategory, str] = {
    "configuration": "the case configuration was rejected before execution",
    "no_eligible_targets": "no clean unit satisfied the fault family's eligibility rules",
    "integrity": "an artifact identity or content check failed",
    "persistence": "a benchmark artifact could not be persisted safely",
    "internal": "the case failed with an unexpected internal error",
}


def redacted_failure_message(category: BenchmarkFailureCategory) -> str:
    """Return the fixed public sentence for one failure category."""
    return _REDACTED_MESSAGES[category]


#: Every stage the benchmark can fail in, used only for validation and tests.
BENCHMARK_FAILURE_STAGES: tuple[BenchmarkFailureStage, ...] = (
    "fixture_load",
    "expansion",
    "dispatch",
    "injection",
    "audit_sanitization",
    "detection",
    "scoring",
    "repair",
    "research",
    "serialization",
    "persistence",
    "aggregation",
)
