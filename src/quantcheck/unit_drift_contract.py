"""Frozen rules shared by the narrow Unit Drift vertical slice."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import NamedTuple

from quantcheck.schemas import FindingSeverity, UnitDriftSeverity

__all__ = [
    "UNIT_DRIFT_DETECTOR_ID",
    "UNIT_DRIFT_DETECTOR_VERSION",
    "UNIT_DRIFT_FAULT_SUBTYPE",
    "UNIT_DRIFT_FAULT_TYPE",
    "UNIT_DRIFT_RATIO_THRESHOLD",
    "UNIT_DRIFT_RULE_ID",
    "UNIT_DRIFT_SCORING_SPEC_VERSION",
    "UNIT_DRIFT_SELECTION_NAMESPACE",
    "UNIT_DRIFT_SPEC_VERSION",
    "UNIT_DRIFT_SUPPORTED_SCALE_FACTORS",
    "UnitDriftSeverityProfile",
    "unit_drift_finding_severity",
    "unit_drift_severity_profile",
    "unit_drift_target_count",
]

UNIT_DRIFT_SPEC_VERSION = "quantcheck/unit-drift-value-scale/v1"
UNIT_DRIFT_FAULT_TYPE = "unit_drift"
UNIT_DRIFT_FAULT_SUBTYPE = "value_scaled_unit_unchanged"
UNIT_DRIFT_RULE_ID = "value.scale_discontinuity"
UNIT_DRIFT_DETECTOR_ID = "quantcheck.unit_drift_detector"
UNIT_DRIFT_DETECTOR_VERSION = "quantcheck/unit-drift-detector/v1"
UNIT_DRIFT_SCORING_SPEC_VERSION = "quantcheck/unit-drift-scoring/v1"
UNIT_DRIFT_SELECTION_NAMESPACE = "quantcheck/unit-drift-target-selection/v1"
UNIT_DRIFT_RATIO_THRESHOLD = Decimal("50")
UNIT_DRIFT_SUPPORTED_SCALE_FACTORS = (
    Decimal("100"),
    Decimal("1000"),
    Decimal("1000000"),
)


class UnitDriftSeverityProfile(NamedTuple):
    """The fixed value multiplier and selected-record fraction."""

    scale_factor: Decimal
    target_fraction: Decimal


_SEVERITY_PROFILES: dict[UnitDriftSeverity, UnitDriftSeverityProfile] = {
    "low": UnitDriftSeverityProfile(Decimal("100"), Decimal("0.02")),
    "medium": UnitDriftSeverityProfile(Decimal("1000"), Decimal("0.05")),
    "high": UnitDriftSeverityProfile(Decimal("1000000"), Decimal("0.10")),
}
_SEVERITY_BY_FACTOR = {
    profile.scale_factor: severity for severity, profile in _SEVERITY_PROFILES.items()
}


def unit_drift_severity_profile(severity: UnitDriftSeverity) -> UnitDriftSeverityProfile:
    """Return the frozen multiplier/fraction profile."""
    return _SEVERITY_PROFILES[severity]


def unit_drift_finding_severity(scale_factor: Decimal) -> FindingSeverity:
    """Derive public severity from the detector's approved candidate factor."""
    try:
        return _SEVERITY_BY_FACTOR[scale_factor]
    except KeyError as exc:
        raise ValueError(f"unsupported Unit Drift scale factor: {scale_factor}") from exc


def unit_drift_target_count(
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
