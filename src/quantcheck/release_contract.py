"""Frozen conventions for the Milestone 11 release evidence path.

This module owns the release's own rules — specification version, the clean
control policy, the artifact names of a release evidence tree, and the exact
list of repository files whose bytes a release candidate freezes. It owns no
scientific rule: fault eligibility, detector thresholds, matching, replay, and
research behaviour stay in the four completed fault families and are only
*recorded* here.
"""

from __future__ import annotations

from typing import Literal

from quantcheck.benchmark_contract import BENCHMARK_FAULT_PROFILES
from quantcheck.release_gate import RESERVED_FINAL_SEEDS
from quantcheck.schemas import BenchmarkFaultProfile

__all__ = [
    "FROZEN_SOURCE_FILES",
    "RELEASE_CLEAN_CONTROL_POLICY",
    "RELEASE_CONTROL_CASE_COUNT",
    "RELEASE_FAULT_CASE_COUNT",
    "RELEASE_FAULT_PROFILES",
    "RELEASE_FREEZE_RECORD_NAME",
    "RELEASE_SEEDS",
    "RELEASE_SEVERITIES",
    "RELEASE_SPEC_VERSION",
    "RELEASE_TOTAL_CASE_COUNT",
    "ReleaseContractError",
]

#: The release contract version. Every release artifact carries it, and
#: changing it changes the release candidate identity.
RELEASE_SPEC_VERSION: Literal["quantcheck/release/v1"] = "quantcheck/release/v1"

#: The release matrix dimensions, derived from the current repository
#: contracts rather than from historical release documentation.
RELEASE_FAULT_PROFILES: tuple[BenchmarkFaultProfile, ...] = BENCHMARK_FAULT_PROFILES
RELEASE_SEVERITIES: tuple[str, ...] = ("low", "medium", "high")
RELEASE_SEEDS: tuple[int, ...] = RESERVED_FINAL_SEEDS

#: **Clean control policy: one clean control per fault profile.**
#:
#: This is derived, not chosen. ``schemas.BenchmarkProfile.clean_control`` is a
#: single optional ``BenchmarkCleanControl`` carrying one severity and one
#: seed, so the current benchmark contract can express at most one control per
#: profile. The historical 0.1.0 documentation implies twelve controls (one per
#: profile per severity, for 132 total cases); reproducing that count would
#: require widening a completed Milestone 8 schema, which Milestone 11 must not
#: do for presentation reasons. The policy is therefore frozen at four
#: controls, and the divergence from the historical target is recorded rather
#: than hidden. See ADR-009.
RELEASE_CLEAN_CONTROL_POLICY: Literal["one_per_fault_profile"] = "one_per_fault_profile"

RELEASE_FAULT_CASE_COUNT = (
    len(RELEASE_FAULT_PROFILES) * len(RELEASE_SEVERITIES) * len(RELEASE_SEEDS)
)
RELEASE_CONTROL_CASE_COUNT = len(RELEASE_FAULT_PROFILES)
RELEASE_TOTAL_CASE_COUNT = RELEASE_FAULT_CASE_COUNT + RELEASE_CONTROL_CASE_COUNT

#: The file name of a committed release freeze record.
RELEASE_FREEZE_RECORD_NAME = "release_freeze.json"

#: Repository files whose exact bytes a release candidate freezes.
#:
#: This is every module that can change a scientific result or a saved
#: artifact's bytes, plus the packaging and lock state. It is an explicit list
#: rather than a glob so that adding a module is a deliberate act that changes
#: the release candidate identity, and so that a missing file is an error
#: instead of a silently smaller frozen set.
FROZEN_SOURCE_FILES: tuple[str, ...] = (
    "pyproject.toml",
    "uv.lock",
    "src/quantcheck/__init__.py",
    "src/quantcheck/audit_boundary.py",
    "src/quantcheck/benchmark_aggregate.py",
    "src/quantcheck/benchmark_contract.py",
    "src/quantcheck/benchmark_dispatch.py",
    "src/quantcheck/benchmark_expansion.py",
    "src/quantcheck/benchmark_fixtures.py",
    "src/quantcheck/benchmark_runner.py",
    "src/quantcheck/benchmark_smoke.py",
    "src/quantcheck/benchmark_store.py",
    "src/quantcheck/cli.py",
    "src/quantcheck/cli_support.py",
    "src/quantcheck/duplicate_contract.py",
    "src/quantcheck/duplicate_detection.py",
    "src/quantcheck/duplicate_fingerprint.py",
    "src/quantcheck/duplicate_injection.py",
    "src/quantcheck/duplicate_manifest.py",
    "src/quantcheck/duplicate_replay.py",
    "src/quantcheck/duplicate_research.py",
    "src/quantcheck/duplicate_scoring.py",
    "src/quantcheck/fixtures.py",
    "src/quantcheck/hashing.py",
    "src/quantcheck/html_summary.py",
    "src/quantcheck/json_types.py",
    "src/quantcheck/lookahead_contract.py",
    "src/quantcheck/lookahead_detection.py",
    "src/quantcheck/lookahead_injection.py",
    "src/quantcheck/lookahead_manifest.py",
    "src/quantcheck/lookahead_replay.py",
    "src/quantcheck/lookahead_research.py",
    "src/quantcheck/lookahead_scoring.py",
    "src/quantcheck/point_in_time.py",
    "src/quantcheck/presentation.py",
    "src/quantcheck/public_artifact_reader.py",
    "src/quantcheck/release_checksums.py",
    "src/quantcheck/release_config.py",
    "src/quantcheck/release_contract.py",
    "src/quantcheck/release_evidence.py",
    "src/quantcheck/release_freeze.py",
    "src/quantcheck/release_gate.py",
    "src/quantcheck/release_run.py",
    "src/quantcheck/revision_overwrite_contract.py",
    "src/quantcheck/revision_overwrite_detection.py",
    "src/quantcheck/revision_overwrite_injection.py",
    "src/quantcheck/revision_overwrite_manifest.py",
    "src/quantcheck/revision_overwrite_replay.py",
    "src/quantcheck/revision_overwrite_research.py",
    "src/quantcheck/revision_overwrite_scoring.py",
    "src/quantcheck/revision_overwrite_series.py",
    "src/quantcheck/saved_case_workflow.py",
    "src/quantcheck/schemas.py",
    "src/quantcheck/sec_adapter.py",
    "src/quantcheck/sec_fixture.py",
    "src/quantcheck/serialization.py",
    "src/quantcheck/unit_drift_contract.py",
    "src/quantcheck/unit_drift_detection.py",
    "src/quantcheck/unit_drift_injection.py",
    "src/quantcheck/unit_drift_manifest.py",
    "src/quantcheck/unit_drift_math.py",
    "src/quantcheck/unit_drift_replay.py",
    "src/quantcheck/unit_drift_research.py",
    "src/quantcheck/unit_drift_scoring.py",
    "src/quantcheck/unit_drift_series.py",
    "tests/fixtures/reviewed_financial_facts.json",
    "tests/fixtures/sec_companyfacts_curated.json",
)


class ReleaseContractError(ValueError):
    """Raised when a release input violates a frozen release convention."""
