"""Frozen rules shared by the narrow Look-Ahead vertical slice.

This is a fault-specific contract, not a generic detector or benchmark
framework.  It contains no manifest access and no orchestration state.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import NamedTuple

from quantcheck.schemas import (
    FinancialFact,
    FindingSeverity,
    LookAheadInjectionConfig,
    LookAheadSeverity,
)

__all__ = [
    "LOOKAHEAD_DETECTOR_ID",
    "LOOKAHEAD_DETECTOR_VERSION",
    "LOOKAHEAD_FAULT_SUBTYPE",
    "LOOKAHEAD_FAULT_TYPE",
    "LOOKAHEAD_RULE_ID",
    "LOOKAHEAD_SCORING_SPEC_VERSION",
    "LOOKAHEAD_SELECTION_NAMESPACE",
    "LOOKAHEAD_SPEC_VERSION",
    "LookAheadSeverityProfile",
    "finding_severity",
    "is_eligible_lookahead_target",
    "lookahead_severity_profile",
    "lookahead_target_count",
]

LOOKAHEAD_SPEC_VERSION = "quantcheck/lookahead-period-end/v1"
LOOKAHEAD_FAULT_TYPE = "lookahead_timestamp"
LOOKAHEAD_FAULT_SUBTYPE = "period_end_substitution"
LOOKAHEAD_RULE_ID = "temporal.period_end_available_before_filing"
LOOKAHEAD_DETECTOR_ID = "quantcheck.lookahead_detector"
LOOKAHEAD_DETECTOR_VERSION = "quantcheck/lookahead-detector/v1"
LOOKAHEAD_SCORING_SPEC_VERSION = "quantcheck/lookahead-scoring/v1"
LOOKAHEAD_SELECTION_NAMESPACE = "quantcheck/lookahead-target-selection/v1"


class LookAheadSeverityProfile(NamedTuple):
    """The fixed fraction and minimum natural filing lag for one severity."""

    target_fraction: Decimal
    minimum_lag_days: int


_SEVERITY_PROFILES: dict[LookAheadSeverity, LookAheadSeverityProfile] = {
    "low": LookAheadSeverityProfile(Decimal("0.02"), 7),
    "medium": LookAheadSeverityProfile(Decimal("0.05"), 14),
    "high": LookAheadSeverityProfile(Decimal("0.10"), 30),
}


def lookahead_severity_profile(severity: LookAheadSeverity) -> LookAheadSeverityProfile:
    """Return the frozen severity profile (Pydantic validates the input)."""
    return _SEVERITY_PROFILES[severity]


def is_eligible_lookahead_target(
    record: FinancialFact,
    config: LookAheadInjectionConfig,
) -> bool:
    """Apply the complete clean-input eligibility rule.

    ``available_on == filed_on`` is the narrow source-semantic prerequisite:
    the detector can then use the preserved public filing date as independent
    proof without receiving a hidden true-availability field.  The research
    cutoff must lie after period end but before true availability, ensuring
    that period-end substitution manufactures an actually visible record.
    """
    profile = lookahead_severity_profile(config.severity)
    filing_lag_days = (record.filed_on - record.period_end).days
    return (
        record.available_on == record.filed_on
        and record.period_end <= config.research_as_of_date < record.available_on
        and filing_lag_days >= profile.minimum_lag_days
    )


def lookahead_target_count(
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


def finding_severity(leaked_days: int) -> FindingSeverity:
    """Map public leaked days to the documented 7/14/30-day bands.

    Any positive violation below 14 days is low.  Injection itself requires
    at least the configured 7/14/30-day natural filing lag; the detector stays
    useful for independently supplied one-to-six-day violations as well.
    """
    if leaked_days >= 30:
        return "high"
    if leaked_days >= 14:
        return "medium"
    return "low"
