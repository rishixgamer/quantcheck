"""Fictional, non-customer policy examples for documentation and tests.

Nothing in this module is an active or implicit default.  Callers must choose
and pass a returned immutable policy explicitly.
"""

from __future__ import annotations

from decimal import Decimal

from quantcheck.duplicate_contract import DUPLICATE_RULE_ID
from quantcheck.external_dataset_policy_contract import (
    AuditPolicyContentV1,
    AuditPolicyV1,
    ConceptScopeV1,
    ConceptUnitExpectationV1,
    DatasetPolicyExceptionScopeV1,
    DatasetPolicyExceptionV1,
    DetectorPolicyRuleV1,
    PublicationLagExpectationV1,
    ReportingFrequencyExpectationV1,
    UnitDriftThresholdPolicyV1,
    build_audit_policy,
)
from quantcheck.lookahead_contract import LOOKAHEAD_RULE_ID
from quantcheck.revision_overwrite_contract import REVISION_OVERWRITE_RULE_ID
from quantcheck.unit_drift_contract import UNIT_DRIFT_RULE_ID

__all__ = [
    "illustrative_governed_policy_v1",
    "monitoring_policy_v1",
]


def monitoring_policy_v1() -> AuditPolicyV1:
    """Run all frozen detectors as informational monitoring only."""
    return build_audit_policy(
        AuditPolicyContentV1(
            policy_name="illustrative-all-detector-monitoring",
            policy_version="1.0.0",
            detector_rules=(
                DetectorPolicyRuleV1(
                    detector="duplicate_observation",
                    rule_id=DUPLICATE_RULE_ID,
                    enabled=True,
                    action="informational",
                    disabled_reason=None,
                    threshold=None,
                ),
                DetectorPolicyRuleV1(
                    detector="lookahead_timestamp",
                    rule_id=LOOKAHEAD_RULE_ID,
                    enabled=True,
                    action="informational",
                    disabled_reason=None,
                    threshold=None,
                ),
                DetectorPolicyRuleV1(
                    detector="revision_overwrite",
                    rule_id=REVISION_OVERWRITE_RULE_ID,
                    enabled=True,
                    action="informational",
                    disabled_reason=None,
                    threshold=None,
                ),
                DetectorPolicyRuleV1(
                    detector="unit_drift",
                    rule_id=UNIT_DRIFT_RULE_ID,
                    enabled=True,
                    action="informational",
                    disabled_reason=None,
                    threshold=UnitDriftThresholdPolicyV1(ratio_threshold=Decimal("50")),
                ),
            ),
            concept_unit_expectations=(),
            publication_lag_expectations=(),
            reporting_frequency_expectations=(),
            dataset_exceptions=(),
        )
    )


def illustrative_governed_policy_v1() -> AuditPolicyV1:
    """Exercise every policy feature with explicitly fictional semantics."""
    scope = ConceptScopeV1(
        concept_namespace="example-taxonomy",
        concept="IllustrativeQuarterlyRevenue",
    )
    unit_rule_id = "policy.concept_unit.illustrative_quarterly_revenue"
    return build_audit_policy(
        AuditPolicyContentV1(
            policy_name="illustrative-governed-quarterly-source",
            policy_version="1.0.0",
            detector_rules=(
                DetectorPolicyRuleV1(
                    detector="duplicate_observation",
                    rule_id=DUPLICATE_RULE_ID,
                    enabled=True,
                    action="blocking",
                    disabled_reason=None,
                    threshold=None,
                ),
                DetectorPolicyRuleV1(
                    detector="lookahead_timestamp",
                    rule_id=LOOKAHEAD_RULE_ID,
                    enabled=True,
                    action="blocking",
                    disabled_reason=None,
                    threshold=None,
                ),
                DetectorPolicyRuleV1(
                    detector="revision_overwrite",
                    rule_id=REVISION_OVERWRITE_RULE_ID,
                    enabled=False,
                    action="warning",
                    disabled_reason=(
                        "illustrative source contract declares independent occurrences only"
                    ),
                    threshold=None,
                ),
                DetectorPolicyRuleV1(
                    detector="unit_drift",
                    rule_id=UNIT_DRIFT_RULE_ID,
                    enabled=True,
                    action="warning",
                    disabled_reason=None,
                    threshold=UnitDriftThresholdPolicyV1(ratio_threshold=Decimal("75")),
                ),
            ),
            concept_unit_expectations=(
                ConceptUnitExpectationV1(
                    rule_id=unit_rule_id,
                    scope=scope,
                    accepted_units=("USD",),
                    action="warning",
                ),
            ),
            publication_lag_expectations=(
                PublicationLagExpectationV1(
                    rule_id="policy.publication_lag.illustrative_quarterly_revenue",
                    scope=scope,
                    basis="availability_after_period_end",
                    minimum_days=0,
                    maximum_days=120,
                    action="warning",
                ),
            ),
            reporting_frequency_expectations=(
                ReportingFrequencyExpectationV1(
                    rule_id="policy.reporting_frequency.illustrative_quarterly_revenue",
                    scope=scope,
                    period_type="duration",
                    maximum_gap_days=120,
                    action="warning",
                ),
            ),
            dataset_exceptions=(
                DatasetPolicyExceptionV1(
                    exception_id="illustrative_legacy_unit_transition",
                    dataset_name="illustrative-legacy-quarterly-source",
                    rule_id=unit_rule_id,
                    scope=DatasetPolicyExceptionScopeV1(entity_id="LEGACY-ENTITY"),
                    effect="override_action",
                    action_override="informational",
                    reason="documented fictional unit transition during a reviewed migration",
                ),
            ),
        )
    )
