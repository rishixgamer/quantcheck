"""Frozen rules shared by the narrow Duplicate Observations vertical slice.

This is a fault-specific contract, not a generic detector or benchmark
framework. It contains no manifest access and no orchestration state.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import NamedTuple

from quantcheck.schemas import DuplicateSeverity, FindingSeverity

__all__ = [
    "DUPLICATE_DETECTOR_ID",
    "DUPLICATE_DETECTOR_VERSION",
    "DUPLICATE_FAULT_SUBTYPE",
    "DUPLICATE_FAULT_TYPE",
    "DUPLICATE_FINDING_SEVERITY",
    "DUPLICATE_FINGERPRINT_NAMESPACE",
    "DUPLICATE_RULE_ID",
    "DUPLICATE_SCORING_SPEC_VERSION",
    "DUPLICATE_SELECTION_NAMESPACE",
    "DUPLICATE_SPEC_VERSION",
    "DuplicateSeverityProfile",
    "duplicate_severity_profile",
    "duplicate_target_count",
]

DUPLICATE_SPEC_VERSION = "quantcheck/duplicate-exact-occurrence-copy/v1"
DUPLICATE_FAULT_TYPE = "duplicate_observation"
DUPLICATE_FAULT_SUBTYPE = "exact_occurrence_copy"
DUPLICATE_RULE_ID = "occurrence.exact_duplicate"
DUPLICATE_DETECTOR_ID = "quantcheck.duplicate_detector"
DUPLICATE_DETECTOR_VERSION = "quantcheck/duplicate-detector/v1"
DUPLICATE_SCORING_SPEC_VERSION = "quantcheck/duplicate-scoring/v1"
DUPLICATE_SELECTION_NAMESPACE = "quantcheck/duplicate-target-selection/v1"
DUPLICATE_FINGERPRINT_NAMESPACE = "quantcheck/duplicate-fingerprint/v1"

#: The fault specification assigns no severity-bearing signal to a duplicate
#: finding (unlike Look-Ahead's leaked days or Unit Drift's scale factor), so
#: public finding severity is fixed. See ADR-004 in docs/DECISIONS.md.
DUPLICATE_FINDING_SEVERITY: FindingSeverity = "medium"


class DuplicateSeverityProfile(NamedTuple):
    """The fixed selected-record fraction for one severity."""

    target_fraction: Decimal


_SEVERITY_PROFILES: dict[DuplicateSeverity, DuplicateSeverityProfile] = {
    "low": DuplicateSeverityProfile(Decimal("0.01")),
    "medium": DuplicateSeverityProfile(Decimal("0.05")),
    "high": DuplicateSeverityProfile(Decimal("0.15")),
}


def duplicate_severity_profile(severity: DuplicateSeverity) -> DuplicateSeverityProfile:
    """Return the frozen target-fraction profile (Pydantic validates the input)."""
    return _SEVERITY_PROFILES[severity]


def duplicate_target_count(
    *,
    eligible_count: int,
    target_fraction: Decimal,
    max_targets: int,
) -> int:
    """Minimum-one Decimal ceiling, bounded by eligibility and the cap."""
    if eligible_count <= 0:
        return 0
    raw = Decimal(eligible_count) * target_fraction
    ceiling = int(raw.to_integral_value(rounding=ROUND_CEILING))
    return min(eligible_count, max_targets, max(1, ceiling))
