"""One immutable presentation model shared by every human-facing surface.

The Streamlit dashboard and the deterministic HTML summary render *this* model
and nothing else. Neither reads artifacts on its own, and neither interprets a
benchmark rule, so there is exactly one place where "what a saved benchmark
means to a human" is decided.

Three rules shape the model:

* **Nothing scientific is recomputed.** Overall and grouped metrics are the
  saved ``aggregate_report.json``'s own numbers, copied across. Re-deriving
  them in the UI would create a second implementation of the aggregate rules.
* **Numbers stay exact.** Metrics are :class:`~decimal.Decimal` from the saved
  canonical strings, never routed through binary ``float``. An undefined metric
  stays ``None``: it is never turned into ``0``, ``NaN``, ``""``, or ``"N/A"``
  here. A renderer may *display* null as text; the model must still hold null.
* **Only approved public information is carried.** There is no manifest, no
  original/pre-corruption value, no private research value, no hidden record
  role, no target rank, no selection digest, no private diagnostic, and no
  filesystem path anywhere in this module's models.
"""

from __future__ import annotations

from decimal import Decimal

from quantcheck.json_types import JsonValue
from quantcheck.public_artifact_reader import (
    PublicBenchmarkArtifacts,
    PublicCaseArtifacts,
)
from quantcheck.schemas import (
    BenchmarkAggregateGroup,
    BenchmarkAggregateReport,
    BenchmarkCaseScore,
    CanonicalDecimal,
    CanonicalModel,
    Finding,
    NonNegativeInteger,
    Token,
)
from quantcheck.serialization import to_canonical_json

__all__ = [
    "BenchmarkPresentation",
    "PresentationCase",
    "PresentationEvidenceItem",
    "PresentationFailure",
    "PresentationFinding",
    "PresentationGroup",
    "PresentationMetrics",
    "PresentationResearch",
    "build_presentation",
    "metric_text",
]


class PresentationMetrics(CanonicalModel):
    """Saved detection counts and metrics for one group or one case.

    Every metric is ``Decimal | None``. ``None`` means the metric is genuinely
    undefined for this population — not zero, and not a placeholder.
    """

    injected_faults: NonNegativeInteger
    findings: NonNegativeInteger
    true_positive_faults: NonNegativeInteger
    false_negative_faults: NonNegativeInteger
    true_positive_findings: NonNegativeInteger
    false_positive_findings: NonNegativeInteger
    eligible_clean_denominator: NonNegativeInteger
    precision: CanonicalDecimal | None
    recall: CanonicalDecimal | None
    f1: CanonicalDecimal | None
    false_positive_rate: CanonicalDecimal | None


class PresentationGroup(CanonicalModel):
    """One saved aggregate grouping, preserved rather than recomputed."""

    grouping: Token
    key: Token
    configured_case_count: NonNegativeInteger
    successful_case_count: NonNegativeInteger
    failed_case_count: NonNegativeInteger
    incomplete_case_count: NonNegativeInteger
    metrics: PresentationMetrics
    research_summary_count: NonNegativeInteger
    research_changed_count: NonNegativeInteger
    replay_restored_count: NonNegativeInteger


class PresentationEvidenceItem(CanonicalModel):
    """One label/value pair of a finding's already-public evidence."""

    label: Token
    value: Token


class PresentationFinding(CanonicalModel):
    """One public detector finding, exactly as the audit report saved it."""

    finding_id: Token
    rule_id: Token
    detector_id: Token
    detector_version: Token
    fault_type: Token
    fault_subtype: Token
    severity: Token
    confidence: Token
    explanation: Token
    affected_record_ids: tuple[Token, ...]
    evidence: tuple[PresentationEvidenceItem, ...]


class PresentationFailure(CanonicalModel):
    """A case's redacted public failure. Never a message, value, or path."""

    stage: Token
    category: Token
    error_code: Token
    message: Token


class PresentationResearch(CanonicalModel):
    """The sanitized controlled-research outcome: two booleans and a method.

    Counts, values, and deltas stay private, because a controlled delta would
    disclose how many faults were injected.
    """

    method: Token
    changed: bool
    exact_restoration: bool


class PresentationCase(CanonicalModel):
    """One benchmark case as a human may see it."""

    benchmark_case_id: Token
    case_kind: Token
    fault_profile: Token
    severity: Token
    seed: NonNegativeInteger
    seed_class: Token
    fixture_id: Token
    dataset_name: Token
    as_of_date: Token
    terminal_status: Token
    audit_input_record_count: NonNegativeInteger | None
    metrics: PresentationMetrics | None
    research: PresentationResearch | None
    findings: tuple[PresentationFinding, ...]
    failure: PresentationFailure | None


class BenchmarkPresentation(CanonicalModel):
    """The complete public-only view of one saved benchmark."""

    benchmark_id: Token
    benchmark_name: Token
    spec_version: Token
    aggregate_report_id: Token
    configured_case_count: NonNegativeInteger
    successful_case_count: NonNegativeInteger
    failed_case_count: NonNegativeInteger
    incomplete_case_count: NonNegativeInteger
    clean_control_count: NonNegativeInteger
    fault_case_count: NonNegativeInteger
    overall: PresentationMetrics
    by_fault_profile: tuple[PresentationGroup, ...]
    by_severity: tuple[PresentationGroup, ...]
    by_seed_class: tuple[PresentationGroup, ...]
    by_seed: tuple[PresentationGroup, ...]
    cases: tuple[PresentationCase, ...]


def _metrics_from_group(group: BenchmarkAggregateGroup) -> PresentationMetrics:
    return PresentationMetrics(
        injected_faults=group.injected_faults,
        findings=group.findings,
        true_positive_faults=group.true_positive_faults,
        false_negative_faults=group.false_negative_faults,
        true_positive_findings=group.true_positive_findings,
        false_positive_findings=group.false_positive_findings,
        eligible_clean_denominator=group.eligible_clean_denominator,
        precision=group.precision,
        recall=group.recall,
        f1=group.f1,
        false_positive_rate=group.false_positive_rate,
    )


def _metrics_from_score(score: BenchmarkCaseScore) -> PresentationMetrics:
    metrics = score.metrics
    return PresentationMetrics(
        injected_faults=metrics.injected_faults,
        findings=metrics.findings,
        true_positive_faults=metrics.true_positive_faults,
        false_negative_faults=metrics.false_negative_faults,
        true_positive_findings=metrics.true_positive_findings,
        false_positive_findings=metrics.false_positive_findings,
        eligible_clean_denominator=metrics.eligible_clean_denominator,
        precision=metrics.precision,
        recall=metrics.recall,
        f1=score.f1,
        false_positive_rate=metrics.false_positive_rate,
    )


def _group(group: BenchmarkAggregateGroup) -> PresentationGroup:
    return PresentationGroup(
        grouping=group.grouping,
        key=group.key,
        configured_case_count=group.configured_case_count,
        successful_case_count=group.successful_case_count,
        failed_case_count=group.failed_case_count,
        incomplete_case_count=group.incomplete_case_count,
        metrics=_metrics_from_group(group),
        research_summary_count=group.research_summary_count,
        research_changed_count=group.research_changed_count,
        replay_restored_count=group.replay_restored_count,
    )


def _scalar_text(value: JsonValue) -> str:
    """Render one already-canonical evidence scalar as display text.

    The input is the canonical JSON form, so a Decimal is already its exact
    canonical string and a date is already ISO-8601. Nothing is reformatted,
    rounded, or passed through ``float``.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | str):
        return str(value)
    return ""


def _flatten_evidence(prefix: str, value: JsonValue) -> list[PresentationEvidenceItem]:
    """Flatten a finding's public evidence into ordered label/value pairs.

    The evidence models are themselves public benchmark artifacts, already
    written into the public tree by the benchmark, so exposing their fields
    introduces no new judgment about what may be published. Ordering follows
    the canonical form, which sorts object keys, so it is deterministic.
    """
    if isinstance(value, dict):
        items: list[PresentationEvidenceItem] = []
        for key in sorted(value):
            label = f"{prefix}.{key}" if prefix else key
            items.extend(_flatten_evidence(label, value[key]))
        return items
    if isinstance(value, list):
        items = []
        for position, entry in enumerate(value):
            items.extend(_flatten_evidence(f"{prefix}[{position}]", entry))
        return items
    return [PresentationEvidenceItem(label=prefix or "value", value=_scalar_text(value) or "null")]


def _finding(finding: Finding) -> PresentationFinding:
    return PresentationFinding(
        finding_id=finding.finding_id,
        rule_id=finding.rule_id,
        detector_id=finding.detector_id,
        detector_version=finding.detector_version,
        fault_type=finding.fault_type,
        fault_subtype=finding.fault_subtype,
        severity=finding.severity,
        confidence=finding.confidence,
        explanation=finding.explanation,
        affected_record_ids=finding.affected_record_ids,
        evidence=tuple(_flatten_evidence("", to_canonical_json(finding.evidence))),
    )


def _case(case_artifacts: PublicCaseArtifacts) -> PresentationCase:
    case = case_artifacts.case
    score = case_artifacts.score
    research = case_artifacts.research_summary
    report = case_artifacts.audit_report
    failure = case_artifacts.failure
    audit_input = case_artifacts.audit_input
    return PresentationCase(
        benchmark_case_id=case.benchmark_case_id,
        case_kind=case.case_kind,
        fault_profile=case.fault_profile,
        severity=case.severity,
        seed=case.seed,
        seed_class=case.seed_class,
        fixture_id=case.fixture.fixture_id,
        dataset_name=case.fixture.dataset_name,
        as_of_date=case.fixture.as_of_date.isoformat(),
        terminal_status=case_artifacts.terminal_status,
        audit_input_record_count=None if audit_input is None else len(audit_input.records),
        metrics=None if score is None else _metrics_from_score(score),
        research=(
            None
            if research is None
            else PresentationResearch(
                method=research.method,
                changed=research.changed,
                exact_restoration=research.exact_restoration,
            )
        ),
        findings=() if report is None else tuple(_finding(item) for item in report.findings),
        failure=(
            None
            if failure is None
            else PresentationFailure(
                stage=failure.stage,
                category=failure.category,
                error_code=failure.error_code,
                message=failure.message,
            )
        ),
    )


def _overall(aggregate: BenchmarkAggregateReport) -> PresentationMetrics:
    return _metrics_from_group(aggregate.overall)


def build_presentation(artifacts: PublicBenchmarkArtifacts) -> BenchmarkPresentation:
    """Transform strictly-read public artifacts into the shared model.

    Case order follows the saved matrix, which the benchmark already sorted by
    ``benchmark_case_id``, so the model is deterministic without sorting here.
    """
    overall = artifacts.aggregate.overall
    cases = tuple(_case(case_artifacts) for case_artifacts in artifacts.cases)
    return BenchmarkPresentation(
        benchmark_id=artifacts.config.benchmark_id,
        benchmark_name=artifacts.config.benchmark_name,
        spec_version=artifacts.config.spec_version,
        aggregate_report_id=artifacts.aggregate.aggregate_report_id,
        configured_case_count=overall.configured_case_count,
        successful_case_count=overall.successful_case_count,
        failed_case_count=overall.failed_case_count,
        incomplete_case_count=overall.incomplete_case_count,
        clean_control_count=sum(1 for case in cases if case.case_kind == "clean_control"),
        fault_case_count=sum(1 for case in cases if case.case_kind == "fault"),
        overall=_overall(artifacts.aggregate),
        by_fault_profile=tuple(_group(group) for group in artifacts.aggregate.by_fault_profile),
        by_severity=tuple(_group(group) for group in artifacts.aggregate.by_severity),
        by_seed_class=tuple(_group(group) for group in artifacts.aggregate.by_seed_class),
        by_seed=tuple(_group(group) for group in artifacts.aggregate.by_seed),
        cases=cases,
    )


def metric_text(value: Decimal | None) -> str:
    """Render one metric for display, preserving an undefined metric as such.

    This is the *display* policy, applied at the edge. The model itself keeps
    ``None``; only text rendered for a human ever says "n/a".
    """
    return "n/a" if value is None else str(value)
