"""Versioned conventions for detector execution and evaluation in v0.2.

This module is additive.  The frozen ``quantcheck/benchmark/v1`` dispatcher,
schemas, identifiers, artifacts, and scoring functions are not changed.  V2
calls those scientific implementations through an explicit detector selection
and records a second, production-oriented interpretation beside the unchanged
strict primary-family score.
"""

from __future__ import annotations

from typing import Literal

from quantcheck.duplicate_contract import (
    DUPLICATE_DETECTOR_ID,
    DUPLICATE_DETECTOR_VERSION,
)
from quantcheck.lookahead_contract import (
    LOOKAHEAD_DETECTOR_ID,
    LOOKAHEAD_DETECTOR_VERSION,
)
from quantcheck.revision_overwrite_contract import (
    REVISION_OVERWRITE_DETECTOR_ID,
    REVISION_OVERWRITE_DETECTOR_VERSION,
)
from quantcheck.unit_drift_contract import (
    UNIT_DRIFT_DETECTOR_ID,
    UNIT_DRIFT_DETECTOR_VERSION,
)

__all__ = [
    "ALL_V2_DETECTORS",
    "BENCHMARK_V2_CASE_NAMESPACE",
    "BENCHMARK_V2_CONFIG_NAMESPACE",
    "BENCHMARK_V2_SPEC_VERSION",
    "DETECTOR_EXECUTION_V2_NAMESPACE",
    "DETECTOR_EXECUTION_V2_SPEC_VERSION",
    "DETECTOR_IDENTITY_BY_KEY",
    "EVALUATION_V2_NAMESPACE",
    "EVALUATION_V2_SPEC_VERSION",
    "FINDING_INTERPRETATION_V2_NAMESPACE",
    "INJECTOR_SPEC_VERSION_BY_PROFILE",
    "V2_DEVELOPMENT_PARTITIONS",
    "BenchmarkV2ContractError",
    "DetectorKeyV2",
    "FindingCategoryV2",
]

DetectorKeyV2 = Literal[
    "duplicate_observation",
    "lookahead_timestamp",
    "revision_overwrite",
    "unit_drift",
]
FindingCategoryV2 = Literal[
    "primary_matched",
    "secondary_corroborating",
    "independent_background",
    "unmatched",
]

ALL_V2_DETECTORS: tuple[DetectorKeyV2, ...] = (
    "duplicate_observation",
    "lookahead_timestamp",
    "revision_overwrite",
    "unit_drift",
)

DETECTOR_IDENTITY_BY_KEY: dict[DetectorKeyV2, tuple[str, str]] = {
    "duplicate_observation": (DUPLICATE_DETECTOR_ID, DUPLICATE_DETECTOR_VERSION),
    "lookahead_timestamp": (LOOKAHEAD_DETECTOR_ID, LOOKAHEAD_DETECTOR_VERSION),
    "revision_overwrite": (
        REVISION_OVERWRITE_DETECTOR_ID,
        REVISION_OVERWRITE_DETECTOR_VERSION,
    ),
    "unit_drift": (UNIT_DRIFT_DETECTOR_ID, UNIT_DRIFT_DETECTOR_VERSION),
}

INJECTOR_SPEC_VERSION_BY_PROFILE: dict[DetectorKeyV2, str] = {
    "duplicate_observation": "quantcheck/duplicate-exact-occurrence-copy/v1",
    "lookahead_timestamp": "quantcheck/lookahead-period-end/v1",
    "revision_overwrite": "quantcheck/revision-overwrite-later-vintage/v1",
    "unit_drift": "quantcheck/unit-drift-value-scale/v1",
}

BENCHMARK_V2_SPEC_VERSION: Literal["quantcheck/benchmark/v2"] = "quantcheck/benchmark/v2"
DETECTOR_EXECUTION_V2_SPEC_VERSION: Literal["quantcheck/detector-execution/v2"] = (
    "quantcheck/detector-execution/v2"
)
EVALUATION_V2_SPEC_VERSION: Literal["quantcheck/finding-evaluation/v2"] = (
    "quantcheck/finding-evaluation/v2"
)

BENCHMARK_V2_CONFIG_NAMESPACE = "quantcheck/benchmark-config/v2"
BENCHMARK_V2_CASE_NAMESPACE = "quantcheck/benchmark-case/v2"
DETECTOR_EXECUTION_V2_NAMESPACE = "quantcheck/detector-execution/v2"
FINDING_INTERPRETATION_V2_NAMESPACE = "quantcheck/finding-interpretation/v2"
EVALUATION_V2_NAMESPACE = "quantcheck/evaluation/v2"

# Held-out execution is a later release step requiring both gates.  This task
# intentionally produces development and validation evidence only.
V2_DEVELOPMENT_PARTITIONS: tuple[str, ...] = ("development", "validation")


class BenchmarkV2ContractError(ValueError):
    """Raised when a v0.2 execution/evaluation contract is violated."""
