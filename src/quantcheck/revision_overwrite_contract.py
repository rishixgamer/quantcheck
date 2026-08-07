"""Frozen rules for the narrow Revision Overwrite vertical slice."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import NamedTuple

from quantcheck.schemas import FindingSeverity, RevisionOverwriteSeverity

__all__ = [
    "REVISION_OVERWRITE_DETECTOR_ID",
    "REVISION_OVERWRITE_DETECTOR_VERSION",
    "REVISION_OVERWRITE_FAULT_SUBTYPE",
    "REVISION_OVERWRITE_FAULT_TYPE",
    "REVISION_OVERWRITE_FINDING_SEVERITY",
    "REVISION_OVERWRITE_PROVENANCE_NAMESPACE",
    "REVISION_OVERWRITE_RULE_ID",
    "REVISION_OVERWRITE_SCORING_SPEC_VERSION",
    "REVISION_OVERWRITE_SELECTION_NAMESPACE",
    "REVISION_OVERWRITE_SPEC_VERSION",
    "RevisionOverwriteSeverityProfile",
    "revision_overwrite_severity_profile",
    "revision_overwrite_target_count",
]

REVISION_OVERWRITE_SPEC_VERSION = "quantcheck/revision-overwrite-later-vintage/v1"
REVISION_OVERWRITE_FAULT_TYPE = "revision_overwrite"
REVISION_OVERWRITE_FAULT_SUBTYPE = "later_vintage_in_earlier_state"
REVISION_OVERWRITE_RULE_ID = "revision.later_vintage_in_earlier_state"
REVISION_OVERWRITE_DETECTOR_ID = "quantcheck.revision_overwrite_detector"
REVISION_OVERWRITE_DETECTOR_VERSION = "quantcheck/revision-overwrite-detector/v1"
REVISION_OVERWRITE_SCORING_SPEC_VERSION = "quantcheck/revision-overwrite-scoring/v1"
REVISION_OVERWRITE_SELECTION_NAMESPACE = "quantcheck/revision-overwrite-target-selection/v1"
REVISION_OVERWRITE_PROVENANCE_NAMESPACE = "quantcheck/revision-overwrite-public-provenance/v1"

# The detector can prove a direct temporal contradiction. Case severity is
# private selection policy and therefore cannot determine public severity.
REVISION_OVERWRITE_FINDING_SEVERITY: FindingSeverity = "high"


class RevisionOverwriteSeverityProfile(NamedTuple):
    """Minimum relative revision size and selected-history fraction."""

    minimum_relative_revision_size: Decimal
    target_fraction: Decimal


_SEVERITY_PROFILES: dict[RevisionOverwriteSeverity, RevisionOverwriteSeverityProfile] = {
    "low": RevisionOverwriteSeverityProfile(Decimal("0.01"), Decimal("0.02")),
    "medium": RevisionOverwriteSeverityProfile(Decimal("0.05"), Decimal("0.05")),
    "high": RevisionOverwriteSeverityProfile(Decimal("0.20"), Decimal("0.10")),
}


def revision_overwrite_severity_profile(
    severity: RevisionOverwriteSeverity,
) -> RevisionOverwriteSeverityProfile:
    """Return the exact threshold/fraction pair for one severity."""
    return _SEVERITY_PROFILES[severity]


def revision_overwrite_target_count(
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
