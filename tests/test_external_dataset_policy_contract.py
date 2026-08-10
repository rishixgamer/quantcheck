"""Strict policy identity, schema separation, and negative contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from quantcheck.benchmark_v2_schemas import BenchmarkV2Config, DetectorExecutionConfigV2
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
    UnitDriftThresholdPolicyV1,
    audit_policy_identity_matches,
    build_audit_policy,
)
from quantcheck.external_dataset_policy_examples import (
    illustrative_governed_policy_v1,
    monitoring_policy_v1,
)
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import policy


def test_policy_is_strict_frozen_versioned_and_separate_from_benchmarks() -> None:
    document = policy()
    assert document.spec_version == "quantcheck/audit-policy/v1"
    assert document.model_config["frozen"] is True
    assert document.model_config["extra"] == "forbid"
    assert not isinstance(document, BenchmarkV2Config)
    assert not isinstance(document, DetectorExecutionConfigV2)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AuditPolicyV1.model_validate({**document.model_dump(), "benchmark_v2_id": "hidden"})


def test_every_detector_must_be_configured_exactly_once() -> None:
    content = AuditPolicyContentV1.model_validate(
        policy().model_dump(
            include=set(AuditPolicyContentV1.model_fields),
            mode="python",
        )
    )
    document = content.model_dump(mode="python")
    document["detector_rules"] = document["detector_rules"][:-1]
    with pytest.raises(ValidationError, match="each supported detector exactly once"):
        AuditPolicyContentV1.model_validate(document)


def test_disablement_is_explicit_and_reasoned() -> None:
    with pytest.raises(ValidationError, match="disabled detectors require a reason"):
        DetectorPolicyRuleV1(
            detector="duplicate_observation",
            rule_id=DUPLICATE_RULE_ID,
            enabled=False,
            action="warning",
            disabled_reason=None,
            threshold=None,
        )
    with pytest.raises(ValidationError, match="enabled detectors forbid one"):
        DetectorPolicyRuleV1(
            detector="duplicate_observation",
            rule_id=DUPLICATE_RULE_ID,
            enabled=True,
            action="warning",
            disabled_reason="stale reason",
            threshold=None,
        )


def test_only_unit_drift_accepts_a_contract_permitted_threshold() -> None:
    threshold = UnitDriftThresholdPolicyV1(ratio_threshold=Decimal("75"))
    with pytest.raises(ValidationError, match="only the Unit Drift"):
        DetectorPolicyRuleV1(
            detector="duplicate_observation",
            rule_id=DUPLICATE_RULE_ID,
            enabled=True,
            action="warning",
            disabled_reason=None,
            threshold=threshold,
        )
    with pytest.raises(ValidationError, match="greater than one"):
        UnitDriftThresholdPolicyV1(ratio_threshold=Decimal("1"))
    with pytest.raises(ValidationError, match="requires an explicit threshold"):
        DetectorPolicyRuleV1(
            detector="unit_drift",
            rule_id="value.scale_discontinuity",
            enabled=True,
            action="warning",
            disabled_reason=None,
            threshold=None,
        )


def test_detector_rule_id_cannot_be_relabelled() -> None:
    with pytest.raises(ValidationError, match="must match"):
        DetectorPolicyRuleV1(
            detector="duplicate_observation",
            rule_id="policy.detector.renamed",
            enabled=True,
            action="warning",
            disabled_reason=None,
            threshold=None,
        )


def test_concept_units_are_nonempty_unique_and_canonically_sorted() -> None:
    scope = ConceptScopeV1(concept_namespace="us-gaap", concept="Assets")
    expectation = ConceptUnitExpectationV1(
        rule_id="policy.concept_unit.assets",
        scope=scope,
        accepted_units=("USDm", "USD"),
        action="warning",
    )
    assert expectation.accepted_units == ("USD", "USDm")
    with pytest.raises(ValidationError, match="non-empty and unique"):
        ConceptUnitExpectationV1(
            rule_id="policy.concept_unit.assets",
            scope=scope,
            accepted_units=(),
            action="warning",
        )
    with pytest.raises(ValidationError, match="accepted_units"):
        ConceptUnitExpectationV1(
            rule_id="policy.concept_unit.assets",
            scope=ConceptScopeV1(
                concept_namespace="us-gaap",
                concept="Assets",
                unit="USD",
            ),
            accepted_units=("USD",),
            action="warning",
        )


def test_policy_version_actions_thresholds_and_reasons_change_identity() -> None:
    baseline = policy()
    version = policy(policy_version="1.0.1")
    action = policy(detector_action="blocking")
    threshold = policy(unit_drift_threshold=Decimal("75"))
    disabled = policy(enabled_detectors=("duplicate_observation",))
    identities = {item.policy_id for item in (baseline, version, action, threshold, disabled)}
    hashes = {item.policy_content_hash for item in (baseline, version, action, threshold, disabled)}
    assert len(identities) == 5
    assert len(hashes) == 5


def test_logically_reordered_policy_content_has_identical_bytes_and_identity() -> None:
    baseline = policy()
    document = baseline.model_dump(mode="python")
    document["detector_rules"] = tuple(reversed(document["detector_rules"]))
    rebuilt_content = AuditPolicyContentV1.model_validate(
        {name: document[name] for name in AuditPolicyContentV1.model_fields}
    )
    rebuilt = build_audit_policy(rebuilt_content)
    assert canonical_json_bytes(rebuilt) == canonical_json_bytes(baseline)
    assert rebuilt.policy_id == baseline.policy_id


def test_tampered_identity_and_content_hash_fail_closed() -> None:
    baseline = policy()
    for field, value in (
        ("policy_id", "apol_0000000000000000"),
        ("policy_content_hash", "0" * 64),
    ):
        document = baseline.model_dump(mode="python")
        document[field] = value
        with pytest.raises(ValidationError, match="does not match"):
            AuditPolicyV1.model_validate(document)
    assert audit_policy_identity_matches(baseline)


def test_exception_target_effect_and_reason_are_strict() -> None:
    scope = DatasetPolicyExceptionScopeV1()
    with pytest.raises(ValidationError, match="requires action_override"):
        DatasetPolicyExceptionV1(
            exception_id="bad-override",
            dataset_name="dataset",
            rule_id=DUPLICATE_RULE_ID,
            scope=scope,
            effect="override_action",
            action_override=None,
            reason="reviewed reason",
        )
    with pytest.raises(ValidationError, match="non-blank"):
        DatasetPolicyExceptionV1(
            exception_id="blank-reason",
            dataset_name="dataset",
            rule_id=DUPLICATE_RULE_ID,
            scope=scope,
            effect="waive",
            action_override=None,
            reason=" ",
        )


def test_exception_cannot_target_unknown_or_disabled_rule() -> None:
    unknown = DatasetPolicyExceptionV1(
        exception_id="unknown-rule",
        dataset_name="dataset",
        rule_id="policy.concept_unit.missing",
        scope=DatasetPolicyExceptionScopeV1(),
        effect="waive",
        action_override=None,
        reason="reviewed reason",
    )
    with pytest.raises(ValidationError, match="unknown policy rule"):
        policy(dataset_exceptions=(unknown,))
    disabled = DatasetPolicyExceptionV1(
        exception_id="disabled-rule",
        dataset_name="dataset",
        rule_id=DUPLICATE_RULE_ID,
        scope=DatasetPolicyExceptionScopeV1(),
        effect="waive",
        action_override=None,
        reason="reviewed reason",
    )
    with pytest.raises(ValidationError, match="disabled rule"):
        policy(enabled_detectors=("lookahead_timestamp",), dataset_exceptions=(disabled,))


def test_lag_range_is_explicit_and_ordered() -> None:
    with pytest.raises(ValidationError, match="must not exceed"):
        PublicationLagExpectationV1(
            rule_id="policy.publication_lag.assets",
            scope=ConceptScopeV1(concept_namespace="us-gaap", concept="Assets"),
            basis="availability_after_filing",
            minimum_days=5,
            maximum_days=2,
            action="warning",
        )


def test_policy_schema_has_no_private_truth_or_benchmark_identity_fields() -> None:
    field_names = set(AuditPolicyV1.model_fields)
    forbidden = {
        "manifest",
        "manifest_id",
        "fault_id",
        "seed",
        "severity",
        "target_count",
        "benchmark_id",
        "benchmark_v2_id",
        "clean_snapshot",
        "corrupted_snapshot",
    }
    assert not field_names & forbidden
    serialized = canonical_json_bytes(policy())
    for marker in forbidden:
        assert f'"{marker}"'.encode() not in serialized


def test_representative_policies_are_fictional_deterministic_and_feature_complete() -> None:
    monitoring = monitoring_policy_v1()
    governed = illustrative_governed_policy_v1()
    assert monitoring == monitoring_policy_v1()
    assert governed == illustrative_governed_policy_v1()
    assert all(rule.enabled for rule in monitoring.detector_rules)
    assert any(not rule.enabled for rule in governed.detector_rules)
    assert governed.concept_unit_expectations
    assert governed.publication_lag_expectations
    assert governed.reporting_frequency_expectations
    assert governed.dataset_exceptions
    assert b"customer" not in canonical_json_bytes(governed).lower()
