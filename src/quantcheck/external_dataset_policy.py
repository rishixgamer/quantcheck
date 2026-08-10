"""Manifest-blind resolution and evaluation of production audit policies."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import NamedTuple

from quantcheck.benchmark_v2_schemas import (
    DetectorExecutionConfigV2,
    DetectorRunV2,
)
from quantcheck.external_dataset_contract import (
    AvailabilityColumnMappingV1,
    AvailabilityEqualsFilingMappingV1,
    DatasetMappingV1,
)
from quantcheck.external_dataset_policy_contract import (
    AuditPolicyV1,
    ConceptScopeV1,
    ConceptUnitExpectationV1,
    ConceptUnitPolicyEvidenceV1,
    DatasetPolicyExceptionScopeV1,
    DatasetPolicyExceptionV1,
    DetectorFindingPolicyEvidenceV1,
    PolicyActionV1,
    PolicyAuditResultV1,
    PolicyRuleEvaluationV1,
    PublicationLagExpectationV1,
    PublicationLagPolicyEvidenceV1,
    ReportingFrequencyExpectationV1,
    ReportingFrequencyPolicyEvidenceV1,
    policy_result_id,
)
from quantcheck.schemas import (
    AuditInputRecord,
    AuditInputSnapshot,
    BenchmarkDetectorConfigs,
    UnitDriftDetectorConfig,
)

__all__ = [
    "PolicyEvaluationError",
    "PolicyEvaluationOutputV1",
    "evaluate_audit_policy",
    "policy_detector_configs",
    "policy_detector_execution_config",
    "validate_publication_lag_semantics",
]


class PolicyEvaluationError(ValueError):
    """Raised when policy resolution would otherwise require guessing."""


class PolicyEvaluationOutputV1(NamedTuple):
    rule_evaluations: tuple[PolicyRuleEvaluationV1, ...]
    results: tuple[PolicyAuditResultV1, ...]


def policy_detector_configs(policy: AuditPolicyV1) -> BenchmarkDetectorConfigs:
    """Resolve public detector parameters while leaving benchmark configs untouched."""
    unit_rule = next(rule for rule in policy.detector_rules if rule.detector == "unit_drift")
    if unit_rule.threshold is None:  # pragma: no cover - strict policy schema guard
        raise PolicyEvaluationError("Unit Drift policy threshold is missing")
    default_unit_config = UnitDriftDetectorConfig()
    unit_config = UnitDriftDetectorConfig(
        ratio_threshold=unit_rule.threshold.ratio_threshold,
        supported_scale_factors=default_unit_config.supported_scale_factors,
    )
    return BenchmarkDetectorConfigs(unit_drift_detector=unit_config)


def policy_detector_execution_config(policy: AuditPolicyV1) -> DetectorExecutionConfigV2 | None:
    """Resolve enabled detectors without making the policy a benchmark config."""
    enabled = tuple(rule.detector for rule in policy.detector_rules if rule.enabled)
    if not enabled:
        return None
    return DetectorExecutionConfigV2(
        selected_detectors=enabled,
        detector_configs=policy_detector_configs(policy),
    )


def validate_publication_lag_semantics(
    policy: AuditPolicyV1,
    mapping: DatasetMappingV1,
) -> None:
    """Fail closed unless every configured availability basis is source-supported."""
    availability_is_explicit = isinstance(
        mapping.available_on,
        AvailabilityColumnMappingV1 | AvailabilityEqualsFilingMappingV1,
    )
    for rule in policy.publication_lag_expectations:
        if rule.basis.startswith("availability_") and not availability_is_explicit:
            raise PolicyEvaluationError(
                f"publication-lag rule {rule.rule_id!r} requires evidenced availability semantics"
            )


def _matches_scope(record: AuditInputRecord, scope: ConceptScopeV1) -> bool:
    return (
        record.concept_namespace == scope.concept_namespace
        and record.concept == scope.concept
        and (scope.entity_id is None or record.entity_id == scope.entity_id)
        and (scope.unit is None or record.unit == scope.unit)
    )


def _exception_scope_matches(
    scope: DatasetPolicyExceptionScopeV1,
    affected_records: tuple[AuditInputRecord, ...],
) -> bool:
    if scope.record_id is not None and all(
        record.record_id != scope.record_id for record in affected_records
    ):
        return False
    predicates = (
        ("entity_id", scope.entity_id),
        ("concept_namespace", scope.concept_namespace),
        ("concept", scope.concept),
        ("unit", scope.unit),
    )
    return all(
        expected is None or all(getattr(record, field) == expected for record in affected_records)
        for field, expected in predicates
    )


def _exception_specificity(exception: DatasetPolicyExceptionV1) -> int:
    return sum(
        value is not None
        for value in (
            exception.scope.record_id,
            exception.scope.entity_id,
            exception.scope.concept_namespace,
            exception.scope.concept,
            exception.scope.unit,
        )
    )


def _resolve_exception(
    *,
    policy: AuditPolicyV1,
    dataset_name: str,
    rule_id: str,
    affected_records: tuple[AuditInputRecord, ...],
) -> DatasetPolicyExceptionV1 | None:
    candidates = tuple(
        exception
        for exception in policy.dataset_exceptions
        if exception.dataset_name == dataset_name
        and exception.rule_id == rule_id
        and _exception_scope_matches(exception.scope, affected_records)
    )
    if not candidates:
        return None
    maximum = max(_exception_specificity(exception) for exception in candidates)
    winners = tuple(
        exception for exception in candidates if _exception_specificity(exception) == maximum
    )
    if len(winners) != 1:
        raise PolicyEvaluationError(
            f"ambiguous equally specific dataset exceptions for rule {rule_id!r}"
        )
    return winners[0]


def _build_result(
    *,
    policy: AuditPolicyV1,
    audit_input: AuditInputSnapshot,
    rule_id: str,
    rule_kind: str,
    affected_record_ids: Iterable[str],
    base_action: PolicyActionV1,
    evidence: object,
) -> PolicyAuditResultV1:
    record_ids = tuple(sorted(set(affected_record_ids)))
    records_by_id = {record.record_id: record for record in audit_input.records}
    try:
        affected_records = tuple(records_by_id[record_id] for record_id in record_ids)
    except KeyError as exc:  # pragma: no cover - frozen finding integrity guard
        raise PolicyEvaluationError("policy result references a missing audit record") from exc
    exception = _resolve_exception(
        policy=policy,
        dataset_name=audit_input.dataset_name,
        rule_id=rule_id,
        affected_records=affected_records,
    )
    body: dict[str, object] = {
        "spec_version": "quantcheck/policy-result/v1",
        "rule_id": rule_id,
        "rule_kind": rule_kind,
        "affected_record_ids": record_ids,
        "base_action": base_action,
        "effective_action": (
            base_action
            if exception is None
            else exception.action_override
            if exception.effect == "override_action"
            else None
        ),
        "disposition": "active" if exception is None else "exception_applied",
        "exception_id": exception.exception_id if exception is not None else None,
        "exception_effect": exception.effect if exception is not None else None,
        "exception_reason": exception.reason if exception is not None else None,
        "evidence": evidence,
    }
    return PolicyAuditResultV1.model_validate(
        {"policy_result_id": policy_result_id(body=body), **body}
    )


def _evaluation(
    *,
    rule_id: str,
    rule_kind: str,
    action: PolicyActionV1,
    status: str,
    reason: str | None,
    evaluated_record_count: int,
    result_count: int,
) -> PolicyRuleEvaluationV1:
    return PolicyRuleEvaluationV1.model_validate(
        {
            "rule_id": rule_id,
            "rule_kind": rule_kind,
            "configured_action": action,
            "status": status,
            "reason": reason,
            "evaluated_record_count": evaluated_record_count,
            "result_count": result_count,
        }
    )


def _detector_results(
    *,
    policy: AuditPolicyV1,
    audit_input: AuditInputSnapshot,
    runs: tuple[DetectorRunV2, ...],
) -> tuple[list[PolicyRuleEvaluationV1], list[PolicyAuditResultV1]]:
    runs_by_detector = {run.detector: run for run in runs}
    evaluations: list[PolicyRuleEvaluationV1] = []
    results: list[PolicyAuditResultV1] = []
    for rule in policy.detector_rules:
        if not rule.enabled:
            evaluations.append(
                _evaluation(
                    rule_id=rule.rule_id,
                    rule_kind="detector",
                    action=rule.action,
                    status="disabled",
                    reason=rule.disabled_reason,
                    evaluated_record_count=0,
                    result_count=0,
                )
            )
            continue
        run = runs_by_detector.get(rule.detector)
        if run is None:
            raise PolicyEvaluationError(f"enabled detector {rule.detector!r} did not execute")
        detector_results = [
            _build_result(
                policy=policy,
                audit_input=audit_input,
                rule_id=rule.rule_id,
                rule_kind="detector",
                affected_record_ids=finding.affected_record_ids,
                base_action=rule.action,
                evidence=DetectorFindingPolicyEvidenceV1(finding_id=finding.finding_id),
            )
            for finding in run.report.findings
        ]
        results.extend(detector_results)
        evaluations.append(
            _evaluation(
                rule_id=rule.rule_id,
                rule_kind="detector",
                action=rule.action,
                status="evaluated",
                reason=None,
                evaluated_record_count=len(audit_input.records),
                result_count=len(detector_results),
            )
        )
    if set(runs_by_detector) != {rule.detector for rule in policy.detector_rules if rule.enabled}:
        raise PolicyEvaluationError("detector execution does not match policy enablement")
    return evaluations, results


def _concept_unit_results(
    *,
    policy: AuditPolicyV1,
    audit_input: AuditInputSnapshot,
    rule: ConceptUnitExpectationV1,
) -> tuple[PolicyRuleEvaluationV1, list[PolicyAuditResultV1]]:
    records = tuple(record for record in audit_input.records if _matches_scope(record, rule.scope))
    results = [
        _build_result(
            policy=policy,
            audit_input=audit_input,
            rule_id=rule.rule_id,
            rule_kind="concept_unit",
            affected_record_ids=(record.record_id,),
            base_action=rule.action,
            evidence=ConceptUnitPolicyEvidenceV1(
                record_id=record.record_id,
                concept_namespace=record.concept_namespace,
                concept=record.concept,
                observed_unit=record.unit,
                accepted_units=rule.accepted_units,
            ),
        )
        for record in records
        if record.unit not in rule.accepted_units
    ]
    status = "evaluated" if records else "not_evaluated"
    return (
        _evaluation(
            rule_id=rule.rule_id,
            rule_kind="concept_unit",
            action=rule.action,
            status=status,
            reason=None if records else "no_matching_records",
            evaluated_record_count=len(records),
            result_count=len(results),
        ),
        results,
    )


def _lag_days(record: AuditInputRecord, rule: PublicationLagExpectationV1) -> int:
    if rule.basis == "filing_after_period_end":
        return (record.filed_on - record.period_end).days
    if rule.basis == "availability_after_filing":
        return (record.available_on - record.filed_on).days
    return (record.available_on - record.period_end).days


def _publication_lag_results(
    *,
    policy: AuditPolicyV1,
    audit_input: AuditInputSnapshot,
    rule: PublicationLagExpectationV1,
) -> tuple[PolicyRuleEvaluationV1, list[PolicyAuditResultV1]]:
    records = tuple(record for record in audit_input.records if _matches_scope(record, rule.scope))
    results: list[PolicyAuditResultV1] = []
    for record in records:
        observed_days = _lag_days(record, rule)
        if rule.minimum_days <= observed_days <= rule.maximum_days:
            continue
        results.append(
            _build_result(
                policy=policy,
                audit_input=audit_input,
                rule_id=rule.rule_id,
                rule_kind="publication_lag",
                affected_record_ids=(record.record_id,),
                base_action=rule.action,
                evidence=PublicationLagPolicyEvidenceV1(
                    record_id=record.record_id,
                    basis=rule.basis,
                    period_end=record.period_end,
                    filed_on=record.filed_on,
                    available_on=record.available_on,
                    observed_days=observed_days,
                    minimum_days=rule.minimum_days,
                    maximum_days=rule.maximum_days,
                ),
            )
        )
    return (
        _evaluation(
            rule_id=rule.rule_id,
            rule_kind="publication_lag",
            action=rule.action,
            status="evaluated" if records else "not_evaluated",
            reason=None if records else "no_matching_records",
            evaluated_record_count=len(records),
            result_count=len(results),
        ),
        results,
    )


def _frequency_group_key(record: AuditInputRecord) -> tuple[object, ...]:
    return (
        record.entity_id,
        record.concept_namespace,
        record.concept,
        record.unit,
        record.dimensions,
        record.period_type,
    )


def _reporting_frequency_results(
    *,
    policy: AuditPolicyV1,
    audit_input: AuditInputSnapshot,
    rule: ReportingFrequencyExpectationV1,
) -> tuple[PolicyRuleEvaluationV1, list[PolicyAuditResultV1]]:
    records = tuple(
        record
        for record in audit_input.records
        if record.period_type == rule.period_type and _matches_scope(record, rule.scope)
    )
    groups: dict[tuple[object, ...], list[AuditInputRecord]] = {}
    for record in records:
        groups.setdefault(_frequency_group_key(record), []).append(record)
    evaluated_group_count = 0
    results: list[PolicyAuditResultV1] = []
    for key in sorted(groups, key=repr):
        by_period: dict[date, list[AuditInputRecord]] = {}
        for record in groups[key]:
            by_period.setdefault(record.period_end, []).append(record)
        ordered = sorted(by_period.items())
        if len(ordered) < 2:
            continue
        evaluated_group_count += 1
        for (previous_date, previous_records), (current_date, current_records) in zip(
            ordered,
            ordered[1:],
            strict=False,
        ):
            gap_days = (current_date - previous_date).days
            if gap_days <= rule.maximum_gap_days:
                continue
            representative = sorted(
                previous_records + current_records,
                key=lambda item: item.record_id,
            )[0]
            affected = tuple(
                record.record_id
                for record in sorted(
                    previous_records + current_records,
                    key=lambda item: item.record_id,
                )
            )
            results.append(
                _build_result(
                    policy=policy,
                    audit_input=audit_input,
                    rule_id=rule.rule_id,
                    rule_kind="reporting_frequency",
                    affected_record_ids=affected,
                    base_action=rule.action,
                    evidence=ReportingFrequencyPolicyEvidenceV1(
                        entity_id=representative.entity_id,
                        concept_namespace=representative.concept_namespace,
                        concept=representative.concept,
                        unit=representative.unit,
                        dimensions=representative.dimensions,
                        period_type=representative.period_type,
                        previous_period_end=previous_date,
                        current_period_end=current_date,
                        gap_days=gap_days,
                        maximum_gap_days=rule.maximum_gap_days,
                    ),
                )
            )
    return (
        _evaluation(
            rule_id=rule.rule_id,
            rule_kind="reporting_frequency",
            action=rule.action,
            status="evaluated" if evaluated_group_count else "not_evaluated",
            reason=None if evaluated_group_count else "insufficient_distinct_periods",
            evaluated_record_count=len(records),
            result_count=len(results),
        ),
        results,
    )


def evaluate_audit_policy(
    *,
    policy: AuditPolicyV1,
    audit_input: AuditInputSnapshot,
    detector_runs: tuple[DetectorRunV2, ...],
) -> PolicyEvaluationOutputV1:
    """Evaluate all configured rules over sanitized input and frozen findings."""
    evaluations, results = _detector_results(
        policy=policy,
        audit_input=audit_input,
        runs=detector_runs,
    )
    for concept_unit_rule in policy.concept_unit_expectations:
        evaluation, rule_results = _concept_unit_results(
            policy=policy,
            audit_input=audit_input,
            rule=concept_unit_rule,
        )
        evaluations.append(evaluation)
        results.extend(rule_results)
    for lag_rule in policy.publication_lag_expectations:
        evaluation, rule_results = _publication_lag_results(
            policy=policy,
            audit_input=audit_input,
            rule=lag_rule,
        )
        evaluations.append(evaluation)
        results.extend(rule_results)
    for frequency_rule in policy.reporting_frequency_expectations:
        evaluation, rule_results = _reporting_frequency_results(
            policy=policy,
            audit_input=audit_input,
            rule=frequency_rule,
        )
        evaluations.append(evaluation)
        results.extend(rule_results)
    return PolicyEvaluationOutputV1(
        rule_evaluations=tuple(sorted(evaluations, key=lambda item: item.rule_id)),
        results=tuple(sorted(results, key=lambda item: item.policy_result_id)),
    )
