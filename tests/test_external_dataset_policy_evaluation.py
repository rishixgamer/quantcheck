"""Production policy evaluation, precedence, and fail-closed behavior."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from quantcheck.benchmark_v2_schemas import DetectorExecutionConfigV2
from quantcheck.external_dataset_audit import audit_external_rows
from quantcheck.external_dataset_contract import DatasetMappingV1
from quantcheck.external_dataset_policy import PolicyEvaluationError
from quantcheck.external_dataset_policy_contract import (
    ConceptScopeV1,
    ConceptUnitExpectationV1,
    DatasetPolicyExceptionScopeV1,
    DatasetPolicyExceptionV1,
    PublicationLagExpectationV1,
    ReportingFrequencyExpectationV1,
)
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import mapping, policy, row

DEFAULT_CONCEPT = "RevenueFromContractWithCustomerExcludingAssessedTax"
DEFAULT_SCOPE = ConceptScopeV1(
    concept_namespace="us-gaap",
    concept=DEFAULT_CONCEPT,
)
DATASET_NAME = "customer-financial-facts-v1"


def _quarterly_rows(*, amounts: tuple[Decimal, ...]) -> list[dict[str, object]]:
    periods = (
        ("2024-01-01", "2024-03-30", "2024-04-30", "2024-05-02"),
        ("2024-04-01", "2024-06-29", "2024-07-30", "2024-08-01"),
        ("2024-07-01", "2024-09-28", "2024-10-30", "2024-11-01"),
    )
    return [
        row(
            f"quarter-{index}",
            amount=amount,
            period_start=start,
            period_end=end,
            filed_date=filed,
            available_date=available,
            accession=f"0000000000-24-00000{index}",
        )
        for index, (amount, (start, end, filed, available)) in enumerate(
            zip(amounts, periods, strict=True),
            start=1,
        )
    ]


def test_report_records_exact_policy_identity_hash_version_and_rule_statuses() -> None:
    audit_policy = policy(enabled_detectors=("duplicate_observation",))
    artifacts = audit_external_rows(
        [row("row-1")],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=audit_policy,
    )
    report = artifacts.public_report
    assert (report.policy_id, report.policy_content_hash, report.policy_version) == (
        audit_policy.policy_id,
        audit_policy.policy_content_hash,
        audit_policy.policy_version,
    )
    assert len(report.rule_evaluations) == 4
    statuses = {item.rule_id: item.status for item in report.rule_evaluations}
    assert statuses["occurrence.exact_duplicate"] == "evaluated"
    assert tuple(statuses.values()).count("disabled") == 3


def test_detector_action_controls_disposition_without_changing_finding() -> None:
    audit_policy = policy(
        enabled_detectors=("lookahead_timestamp",),
        detector_action="blocking",
    )
    report = audit_external_rows(
        [
            row(
                "leaked-row",
                filed_date="2024-04-30",
                available_date="2024-03-31",
            )
        ],
        mapping=mapping(),
        as_of_date=date(2024, 4, 15),
        policy=audit_policy,
    ).public_report
    assert report.finding_count == 1
    assert report.blocking_count == 1
    assert report.disposition == "blocked"
    assert report.policy_results[0].evidence.kind == "detector_finding"


def test_disabled_detectors_are_absent_and_reasoned_not_silently_skipped() -> None:
    report = audit_external_rows(
        [row("row-1")],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(enabled_detectors=()),
    ).public_report
    assert report.selected_detectors == ()
    assert report.detector_runs == ()
    assert report.disposition == "passed"
    assert all(item.status == "disabled" and item.reason for item in report.rule_evaluations)


def test_unit_drift_threshold_changes_production_behavior_only() -> None:
    rows = _quarterly_rows(amounts=(Decimal("100"), Decimal("6000"), Decimal("100")))
    default_report = audit_external_rows(
        rows,
        mapping=mapping(),
        as_of_date=date(2024, 12, 31),
        policy=policy(enabled_detectors=("unit_drift",)),
    ).public_report
    stricter_policy = policy(
        enabled_detectors=("unit_drift",),
        unit_drift_threshold=Decimal("75"),
    )
    stricter_report = audit_external_rows(
        rows,
        mapping=mapping(),
        as_of_date=date(2024, 12, 31),
        policy=stricter_policy,
    ).public_report
    assert default_report.finding_count == 3
    assert stricter_report.finding_count == 0
    assert stricter_report.detector_configs.unit_drift_detector.ratio_threshold == Decimal("75")
    assert (
        DetectorExecutionConfigV2().detector_configs.unit_drift_detector.ratio_threshold
        == Decimal("50")
    )


def test_concept_unit_expectation_produces_a_blocking_policy_result() -> None:
    unit_rule = ConceptUnitExpectationV1(
        rule_id="policy.concept_unit.revenue",
        scope=DEFAULT_SCOPE,
        accepted_units=("USD",),
        action="blocking",
    )
    report = audit_external_rows(
        [row("wrong-unit", unit="shares")],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(
            enabled_detectors=(),
            concept_unit_expectations=(unit_rule,),
        ),
    ).public_report
    assert report.blocking_count == 1
    result = report.policy_results[0]
    assert result.rule_id == unit_rule.rule_id
    assert result.evidence.kind == "concept_unit"
    assert result.effective_action == "blocking"


def test_publication_lag_uses_explicit_availability_semantics() -> None:
    lag_rule = PublicationLagExpectationV1(
        rule_id="policy.publication_lag.revenue",
        scope=DEFAULT_SCOPE,
        basis="availability_after_filing",
        minimum_days=0,
        maximum_days=1,
        action="warning",
    )
    report = audit_external_rows(
        [row("late-row", filed_date="2024-04-30", available_date="2024-05-03")],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(
            enabled_detectors=(),
            publication_lag_expectations=(lag_rule,),
        ),
    ).public_report
    assert report.warning_count == 1
    assert report.policy_results[0].evidence.kind == "publication_lag"
    assert report.policy_results[0].evidence.observed_days == 3


def test_same_as_filing_source_contract_supports_availability_lag_evaluation() -> None:
    document = mapping(unmapped_columns="allow").model_dump(mode="python")
    document["available_on"] = {
        "kind": "same_as_filing",
        "basis": "source_contract_confirms_filing_date_equals_availability_date",
        "evidence_reference": "illustrative-source-contract-section-4",
    }
    same_as_filing = DatasetMappingV1.model_validate(document)
    lag_rule = PublicationLagExpectationV1(
        rule_id="policy.publication_lag.same_day",
        scope=DEFAULT_SCOPE,
        basis="availability_after_filing",
        minimum_days=0,
        maximum_days=0,
        action="blocking",
    )
    report = audit_external_rows(
        [row("same-day")],
        mapping=same_as_filing,
        as_of_date=date(2024, 6, 30),
        policy=policy(
            enabled_detectors=(),
            publication_lag_expectations=(lag_rule,),
        ),
    ).public_report
    assert report.policy_results == ()
    assert (
        next(item for item in report.rule_evaluations if item.rule_id == lag_rule.rule_id).status
        == "evaluated"
    )


def test_reporting_frequency_flags_adjacent_period_end_gap() -> None:
    frequency_rule = ReportingFrequencyExpectationV1(
        rule_id="policy.reporting_frequency.revenue",
        scope=DEFAULT_SCOPE,
        period_type="duration",
        maximum_gap_days=120,
        action="warning",
    )
    first, _, third = _quarterly_rows(amounts=(Decimal("100"), Decimal("110"), Decimal("120")))
    report = audit_external_rows(
        [first, third],
        mapping=mapping(),
        as_of_date=date(2024, 12, 31),
        policy=policy(
            enabled_detectors=(),
            reporting_frequency_expectations=(frequency_rule,),
        ),
    ).public_report
    assert report.warning_count == 1
    evidence = report.policy_results[0].evidence
    assert evidence.kind == "reporting_frequency"
    assert evidence.gap_days == 182


def test_frequency_with_insufficient_history_is_explicitly_not_evaluated() -> None:
    frequency_rule = ReportingFrequencyExpectationV1(
        rule_id="policy.reporting_frequency.revenue",
        scope=DEFAULT_SCOPE,
        period_type="duration",
        maximum_gap_days=120,
        action="warning",
    )
    report = audit_external_rows(
        [row("only-period")],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(
            enabled_detectors=(),
            reporting_frequency_expectations=(frequency_rule,),
        ),
    ).public_report
    evaluation = next(
        item for item in report.rule_evaluations if item.rule_id == frequency_rule.rule_id
    )
    assert evaluation.status == "not_evaluated"
    assert evaluation.reason == "insufficient_distinct_periods"


def test_exception_waives_but_preserves_the_policy_result_and_reason() -> None:
    rule = ConceptUnitExpectationV1(
        rule_id="policy.concept_unit.revenue",
        scope=DEFAULT_SCOPE,
        accepted_units=("USD",),
        action="blocking",
    )
    exception = DatasetPolicyExceptionV1(
        exception_id="reviewed-unit-exception",
        dataset_name=DATASET_NAME,
        rule_id=rule.rule_id,
        scope=DatasetPolicyExceptionScopeV1(),
        effect="waive",
        action_override=None,
        reason="reviewed source contract documents this alternate unit",
    )
    report = audit_external_rows(
        [row("wrong-unit", unit="shares")],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(
            enabled_detectors=(),
            concept_unit_expectations=(rule,),
            dataset_exceptions=(exception,),
        ),
    ).public_report
    assert report.disposition == "passed"
    assert report.waived_count == 1
    assert report.exception_applied_count == 1
    result = report.policy_results[0]
    assert result.base_action == "blocking"
    assert result.effective_action is None
    assert result.exception_reason == exception.reason


def test_more_specific_exception_precedes_general_exception() -> None:
    rule = ConceptUnitExpectationV1(
        rule_id="policy.concept_unit.revenue",
        scope=DEFAULT_SCOPE,
        accepted_units=("USD",),
        action="blocking",
    )
    general = DatasetPolicyExceptionV1(
        exception_id="general-waiver",
        dataset_name=DATASET_NAME,
        rule_id=rule.rule_id,
        scope=DatasetPolicyExceptionScopeV1(),
        effect="waive",
        action_override=None,
        reason="general reviewed waiver",
    )
    specific = DatasetPolicyExceptionV1(
        exception_id="entity-override",
        dataset_name=DATASET_NAME,
        rule_id=rule.rule_id,
        scope=DatasetPolicyExceptionScopeV1(entity_id="ENTITY-001"),
        effect="override_action",
        action_override="informational",
        reason="entity-specific reviewed override",
    )
    report = audit_external_rows(
        [row("wrong-unit", unit="shares")],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(
            enabled_detectors=(),
            concept_unit_expectations=(rule,),
            dataset_exceptions=(general, specific),
        ),
    ).public_report
    result = report.policy_results[0]
    assert result.exception_id == specific.exception_id
    assert result.effective_action == "informational"
    assert report.disposition == "passed_with_information"


def test_equally_specific_matching_exceptions_fail_closed() -> None:
    rule = ConceptUnitExpectationV1(
        rule_id="policy.concept_unit.revenue",
        scope=DEFAULT_SCOPE,
        accepted_units=("USD",),
        action="blocking",
    )
    exceptions = (
        DatasetPolicyExceptionV1(
            exception_id="entity-waiver",
            dataset_name=DATASET_NAME,
            rule_id=rule.rule_id,
            scope=DatasetPolicyExceptionScopeV1(entity_id="ENTITY-001"),
            effect="waive",
            action_override=None,
            reason="entity-scoped reviewed reason",
        ),
        DatasetPolicyExceptionV1(
            exception_id="unit-waiver",
            dataset_name=DATASET_NAME,
            rule_id=rule.rule_id,
            scope=DatasetPolicyExceptionScopeV1(unit="shares"),
            effect="waive",
            action_override=None,
            reason="unit-scoped reviewed reason",
        ),
    )
    with pytest.raises(PolicyEvaluationError, match="ambiguous equally specific"):
        audit_external_rows(
            [row("wrong-unit", unit="shares")],
            mapping=mapping(),
            as_of_date=date(2024, 6, 30),
            policy=policy(
                enabled_detectors=(),
                concept_unit_expectations=(rule,),
                dataset_exceptions=exceptions,
            ),
        )


def test_dataset_exception_does_not_apply_to_another_dataset() -> None:
    rule = ConceptUnitExpectationV1(
        rule_id="policy.concept_unit.revenue",
        scope=DEFAULT_SCOPE,
        accepted_units=("USD",),
        action="blocking",
    )
    exception = DatasetPolicyExceptionV1(
        exception_id="other-dataset-waiver",
        dataset_name="another-dataset",
        rule_id=rule.rule_id,
        scope=DatasetPolicyExceptionScopeV1(),
        effect="waive",
        action_override=None,
        reason="reviewed only for another dataset",
    )
    report = audit_external_rows(
        [row("wrong-unit", unit="shares")],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(
            enabled_detectors=(),
            concept_unit_expectations=(rule,),
            dataset_exceptions=(exception,),
        ),
    ).public_report
    assert report.blocking_count == 1
    assert report.policy_results[0].disposition == "active"


def test_malformed_input_is_rejected_even_when_every_detector_is_disabled() -> None:
    with pytest.raises(ValueError):
        audit_external_rows(
            [row("binary-float", amount=123.45)],
            mapping=mapping(),
            as_of_date=date(2024, 6, 30),
            policy=policy(enabled_detectors=()),
        )


def test_policy_report_serialization_contains_no_hidden_source_or_manifest_truth() -> None:
    secret = "PRIVATE_POLICY_SOURCE_ROW_12345"
    report = audit_external_rows(
        [row(secret)],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(enabled_detectors=()),
    ).public_report
    serialized = canonical_json_bytes(report)
    assert secret.encode() not in serialized
    assert b'"manifest"' not in serialized
    assert b'"seed"' not in serialized
    assert b'"target_count"' not in serialized
    assert b'"manifest_used":false' in serialized
