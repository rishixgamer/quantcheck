"""The narrow explicit dispatcher over the four completed fault families.

This module contains no scientific rule of its own. It loads a clean fixture,
calls the completed injector, crosses the existing ``sanitize_for_audit``
boundary exactly once, runs all four detectors on that one sanitized input,
finalizes a single combined :class:`AuditReport`, and only then hands the
private manifest to the fault family's own matcher, replay, and research code.

Two properties are load-bearing and are asserted by tests:

* no detector call receives a manifest, a clean snapshot, or any injector
  metadata — every detector sees only the sanitized
  :class:`AuditInputSnapshot` and its own public configuration; and
* the manifest becomes reachable only after the audit report is finalized,
  which is the order this module's control flow physically enforces.

Cross-detector findings are preserved. A Revision Overwrite corruption that
also satisfies the Duplicate contract legitimately produces both findings; the
primary family's exact scorer then counts the secondary one as a false positive
under strict primary-class precision. Suppressing it would inflate precision by
hiding real detector behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.benchmark_contract import require_seed_execution_authorized
from quantcheck.benchmark_fixtures import benchmark_fixture_records
from quantcheck.duplicate_contract import (
    DUPLICATE_DETECTOR_ID,
    DUPLICATE_DETECTOR_VERSION,
)
from quantcheck.duplicate_detection import detect_duplicate_observations
from quantcheck.duplicate_fingerprint import build_duplicate_groups
from quantcheck.duplicate_injection import inject_duplicate_observations
from quantcheck.duplicate_replay import manifest_assisted_exact_duplicate_replay
from quantcheck.duplicate_research import compare_duplicate_record_count
from quantcheck.duplicate_scoring import score_duplicate_observations
from quantcheck.hashing import (
    duplicate_audit_report_id,
    lookahead_audit_report_id,
    revision_overwrite_audit_report_id,
    unit_drift_audit_report_id,
)
from quantcheck.lookahead_contract import (
    LOOKAHEAD_DETECTOR_ID,
    LOOKAHEAD_DETECTOR_VERSION,
    is_eligible_lookahead_target,
)
from quantcheck.lookahead_detection import detect_lookahead
from quantcheck.lookahead_injection import inject_lookahead
from quantcheck.lookahead_replay import manifest_assisted_exact_replay
from quantcheck.lookahead_research import compare_lookahead_research
from quantcheck.lookahead_scoring import score_lookahead
from quantcheck.point_in_time import build_dataset_snapshot
from quantcheck.revision_overwrite_contract import (
    REVISION_OVERWRITE_DETECTOR_ID,
    REVISION_OVERWRITE_DETECTOR_VERSION,
    revision_overwrite_severity_profile,
)
from quantcheck.revision_overwrite_detection import detect_revision_overwrite
from quantcheck.revision_overwrite_injection import inject_revision_overwrite
from quantcheck.revision_overwrite_replay import (
    manifest_assisted_exact_revision_overwrite_replay,
)
from quantcheck.revision_overwrite_research import (
    build_frozen_vintage_growth_snapshot,
    compare_revision_overwrite_research,
)
from quantcheck.revision_overwrite_scoring import score_revision_overwrite
from quantcheck.revision_overwrite_series import build_revision_history_units
from quantcheck.schemas import (
    AuditInputSnapshot,
    AuditReport,
    BenchmarkCaseConfig,
    BenchmarkCaseScore,
    BenchmarkDetectorConfigs,
    BenchmarkLookAheadResearch,
    BenchmarkResearchSummary,
    BenchmarkUnitDriftResearch,
    CanonicalModel,
    DatasetSnapshot,
    DetectionMetrics,
    DuplicateInjectionConfig,
    FinancialFact,
    Finding,
    LookAheadInjectionConfig,
    RevisionOverwriteInjectionConfig,
    UnitDriftInjectionConfig,
    UnitDriftResearchConfig,
)
from quantcheck.unit_drift_contract import (
    UNIT_DRIFT_DETECTOR_ID,
    UNIT_DRIFT_DETECTOR_VERSION,
)
from quantcheck.unit_drift_detection import detect_unit_drift
from quantcheck.unit_drift_injection import inject_unit_drift
from quantcheck.unit_drift_replay import manifest_assisted_exact_unit_drift_replay
from quantcheck.unit_drift_research import compare_unit_drift_research
from quantcheck.unit_drift_scoring import score_unit_drift
from quantcheck.unit_drift_series import build_comparable_observations

__all__ = [
    "BenchmarkCaseArtifacts",
    "BenchmarkDispatchError",
    "clean_snapshot_for_case",
    "combined_audit_report",
    "control_score",
    "dispatch_benchmark_case",
    "eligible_clean_denominator",
    "fault_score",
    "inject_for_case",
    "lookahead_research_date",
    "replay_for_case",
    "research_for_case",
    "research_summary_for_case",
    "run_all_detectors",
    "score_for_case",
]


class BenchmarkDispatchError(ValueError):
    """Raised when a benchmark case cannot be dispatched to a fault family."""


@dataclass(frozen=True, slots=True)
class BenchmarkCaseArtifacts:
    """The standard in-memory result of one dispatched benchmark case.

    The split below *is* the trust boundary, stated once so that persistence
    and aggregation cannot get it wrong: everything in the public group is safe
    to publish, and every value-bearing piece of hidden truth is in the private
    group. A clean control has no corrupted snapshot, manifest, repaired
    snapshot, or research impact, because it injects nothing.
    """

    case: BenchmarkCaseConfig

    # Public evidence.
    audit_input: AuditInputSnapshot
    audit_report: AuditReport
    score: BenchmarkCaseScore
    research_summary: BenchmarkResearchSummary | None

    # Private truth. Never reachable from a public artifact or index.
    clean_snapshot: DatasetSnapshot
    corrupted_snapshot: DatasetSnapshot | None
    manifest: CanonicalModel | None
    repaired_snapshot: DatasetSnapshot | None
    research_impact: CanonicalModel | None


_REPORT_IDENTITY = {
    "lookahead_timestamp": (
        LOOKAHEAD_DETECTOR_ID,
        LOOKAHEAD_DETECTOR_VERSION,
        lookahead_audit_report_id,
    ),
    "unit_drift": (
        UNIT_DRIFT_DETECTOR_ID,
        UNIT_DRIFT_DETECTOR_VERSION,
        unit_drift_audit_report_id,
    ),
    "duplicate_observation": (
        DUPLICATE_DETECTOR_ID,
        DUPLICATE_DETECTOR_VERSION,
        duplicate_audit_report_id,
    ),
    "revision_overwrite": (
        REVISION_OVERWRITE_DETECTOR_ID,
        REVISION_OVERWRITE_DETECTOR_VERSION,
        revision_overwrite_audit_report_id,
    ),
}


def run_all_detectors(
    audit_input: AuditInputSnapshot,
    detector_configs: BenchmarkDetectorConfigs,
) -> tuple[Finding, ...]:
    """Run all four manifest-blind detectors over one sanitized audit input.

    Each detector receives exactly the sanitized snapshot and its own public
    configuration. There is deliberately no parameter here through which a
    manifest, a clean value, a seed, a severity, or a target could reach a
    detector. Taking ``detector_configs`` directly (rather than a full
    :class:`BenchmarkCaseConfig`) lets a standalone audit over an arbitrary
    canonical snapshot reuse this exact function without fabricating a
    benchmark case.
    """
    detectors = detector_configs
    findings: list[Finding] = []
    findings.extend(detect_lookahead(audit_input).findings)
    findings.extend(detect_unit_drift(audit_input, detectors.unit_drift_detector).findings)
    findings.extend(detect_duplicate_observations(audit_input).findings)
    findings.extend(
        detect_revision_overwrite(audit_input, detectors.revision_overwrite_detector).findings
    )
    return tuple(findings)


def combined_audit_report(
    audit_input: AuditInputSnapshot,
    findings: tuple[Finding, ...],
    *,
    fault_profile: str,
) -> AuditReport:
    """Finalize one immutable report holding every detector's findings.

    The report carries the *primary* family's detector identity and report-id
    namespace, because that family's existing scorer validates both. Findings
    from the other three detectors are kept verbatim; ``AuditReport`` sorts
    them canonically by ``finding_id``, so the combined report's bytes do not
    depend on the order the detectors ran in.
    """
    try:
        detector_id, detector_version, report_id = _REPORT_IDENTITY[fault_profile]
    except KeyError as exc:
        raise BenchmarkDispatchError(f"unsupported fault profile: {fault_profile!r}") from exc
    body: dict[str, object] = {
        "detector_id": detector_id,
        "detector_version": detector_version,
        "audit_input_id": audit_input.audit_input_id,
        "dataset_name": audit_input.dataset_name,
        "as_of_date": audit_input.as_of_date,
        "findings": tuple(sorted(findings, key=lambda finding: finding.finding_id)),
    }
    return AuditReport.model_validate({"audit_report_id": report_id(report_body=body), **body})


def clean_snapshot_for_case(
    case: BenchmarkCaseConfig,
) -> tuple[DatasetSnapshot, tuple[FinancialFact, ...]]:
    records = benchmark_fixture_records(case.fixture.fixture_id)
    snapshot = build_dataset_snapshot(
        records,
        dataset_name=case.fixture.dataset_name,
        as_of_date=case.fixture.as_of_date,
    )
    return snapshot, records


def eligible_clean_denominator(
    case: BenchmarkCaseConfig,
    clean: DatasetSnapshot,
    source_records: tuple[FinancialFact, ...],
) -> int:
    """Count the clean units a control's detectors could raise a finding about.

    This calls the *same* frozen eligibility computation each injector uses, so
    a control's denominator is exactly the population its fault sibling is
    scored against. It re-derives nothing.
    """
    profile = case.fault_profile
    if profile == "lookahead_timestamp":
        assert isinstance(case.research, CanonicalModel)
        config = LookAheadInjectionConfig(
            severity=case.severity,  # type: ignore[arg-type]
            seed=case.seed,
            research_as_of_date=lookahead_research_date(case),
            max_targets=case.max_targets,
        )
        return sum(1 for record in clean.records if is_eligible_lookahead_target(record, config))
    if profile == "unit_drift":
        return len(build_comparable_observations(clean.records, as_of_date=clean.as_of_date))
    if profile == "duplicate_observation":
        groups = build_duplicate_groups(clean.records, as_of_date=clean.as_of_date)
        return sum(1 for group in groups.values() if len(group.records) == 1)
    if profile == "revision_overwrite":
        severity_profile = revision_overwrite_severity_profile(case.severity)  # type: ignore[arg-type]
        units = build_revision_history_units(
            source_records,
            clean_snapshot=clean,
            minimum_relative_revision_size=severity_profile.minimum_relative_revision_size,
        )
        return len(units)
    raise BenchmarkDispatchError(f"unsupported fault profile: {profile!r}")


def lookahead_research_date(case: BenchmarkCaseConfig) -> date:
    research = case.research
    if not isinstance(research, BenchmarkLookAheadResearch):
        raise BenchmarkDispatchError("Look-Ahead cases require an availability-count research date")
    return research.research_as_of_date


def control_score(
    case: BenchmarkCaseConfig,
    findings: tuple[Finding, ...],
    denominator: int,
) -> BenchmarkCaseScore:
    """Score an uncorrupted control: every finding is a false positive.

    A control injects nothing, so recall is null by the existing
    :class:`DetectionMetrics` convention and precision is null exactly when the
    control produced no findings. Nothing here is suppressed: a detector that
    fires on legitimate clean data is exactly what a control exists to reveal.
    """
    finding_count = len(findings)
    metrics = DetectionMetrics(
        injected_faults=0,
        findings=finding_count,
        true_positive_faults=0,
        false_negative_faults=0,
        true_positive_findings=0,
        false_positive_findings=finding_count,
        eligible_clean_denominator=denominator,
        precision=_zero_precision(finding_count),
        recall=None,
        false_positive_rate=_rate(finding_count, denominator),
    )
    return BenchmarkCaseScore(
        benchmark_case_id=case.benchmark_case_id,
        benchmark_id=case.benchmark_id,
        case_kind=case.case_kind,
        fault_profile=case.fault_profile,
        severity=case.severity,
        seed=case.seed,
        seed_class=case.seed_class,
        metrics=metrics,
        f1=None,
        score_report=None,
    )


def _zero_precision(finding_count: int) -> Decimal | None:
    """Precision is null exactly when a control produced no finding at all."""
    return Decimal(0) if finding_count else None


def _rate(numerator: int, denominator: int) -> Decimal | None:
    """The existing exact-Decimal ratio convention; null on a zero denominator."""
    if not denominator:
        return None
    with localcontext() as context:
        context.prec = 50
        return Decimal(numerator) / Decimal(denominator)


def fault_score(case: BenchmarkCaseConfig, score_report: object) -> BenchmarkCaseScore:
    return BenchmarkCaseScore(
        benchmark_case_id=case.benchmark_case_id,
        benchmark_id=case.benchmark_id,
        case_kind=case.case_kind,
        fault_profile=case.fault_profile,
        severity=case.severity,
        seed=case.seed,
        seed_class=case.seed_class,
        metrics=score_report.metrics,  # type: ignore[attr-defined]
        f1=score_report.f1,  # type: ignore[attr-defined]
        score_report=score_report,  # type: ignore[arg-type]
    )


def research_summary_for_case(
    case: BenchmarkCaseConfig,
    impact: CanonicalModel,
) -> BenchmarkResearchSummary:
    """Project a value-bearing research impact onto its safe public facts.

    Only the method, whether the controlled output changed, and whether exact
    replay restored it cross into public evidence. Controlled counts and
    deltas stay private: a Look-Ahead availability delta, for instance, is the
    injected target count, which is answer-key information.
    """
    return BenchmarkResearchSummary(
        benchmark_case_id=case.benchmark_case_id,
        method=impact.method,  # type: ignore[attr-defined]
        changed=impact.changed,  # type: ignore[attr-defined]
        exact_restoration=impact.exact_restoration,  # type: ignore[attr-defined]
    )


def dispatch_benchmark_case(case: BenchmarkCaseConfig) -> BenchmarkCaseArtifacts:
    """Execute one expanded benchmark case end to end.

    The control flow *is* the contract: nothing that touches the manifest can
    run before ``combined_audit_report`` has returned a finalized report.

    A reserved final seed is refused here unless the release path authorized
    it. Reading a saved held-out case is allowed; running one is not.
    """
    require_seed_execution_authorized(case.seed)
    clean, source_records = clean_snapshot_for_case(case)

    if case.case_kind == "clean_control":
        audit_input = sanitize_for_audit(clean)
        findings = run_all_detectors(audit_input, case.detector_configs)
        report = combined_audit_report(audit_input, findings, fault_profile=case.fault_profile)
        denominator = eligible_clean_denominator(case, clean, source_records)
        return BenchmarkCaseArtifacts(
            case=case,
            audit_input=audit_input,
            audit_report=report,
            score=control_score(case, report.findings, denominator),
            research_summary=None,
            clean_snapshot=clean,
            corrupted_snapshot=None,
            manifest=None,
            repaired_snapshot=None,
            research_impact=None,
        )

    corrupted, manifest = inject_for_case(case, clean, source_records)

    # --- trust boundary: everything below `sanitize_for_audit` is public ----
    audit_input = sanitize_for_audit(corrupted)
    findings = run_all_detectors(audit_input, case.detector_configs)
    report = combined_audit_report(audit_input, findings, fault_profile=case.fault_profile)
    # --- audit finalized: the manifest may now be used ----------------------

    score_report = score_for_case(case, report, manifest)
    repaired = replay_for_case(case, corrupted, manifest)
    impact = research_for_case(case, clean, corrupted, repaired, manifest, source_records)

    return BenchmarkCaseArtifacts(
        case=case,
        audit_input=audit_input,
        audit_report=report,
        score=fault_score(case, score_report),
        research_summary=research_summary_for_case(case, impact),
        clean_snapshot=clean,
        corrupted_snapshot=corrupted,
        manifest=manifest,
        repaired_snapshot=repaired,
        research_impact=impact,
    )


def inject_for_case(
    case: BenchmarkCaseConfig,
    clean: DatasetSnapshot,
    source_records: tuple[FinancialFact, ...],
) -> tuple[DatasetSnapshot, CanonicalModel]:
    profile = case.fault_profile
    if profile == "lookahead_timestamp":
        return inject_lookahead(
            clean,
            LookAheadInjectionConfig(
                severity=case.severity,  # type: ignore[arg-type]
                seed=case.seed,
                research_as_of_date=lookahead_research_date(case),
                max_targets=case.max_targets,
            ),
        )
    if profile == "unit_drift":
        return inject_unit_drift(
            clean,
            UnitDriftInjectionConfig(
                severity=case.severity,  # type: ignore[arg-type]
                seed=case.seed,
                max_targets=case.max_targets,
            ),
        )
    if profile == "duplicate_observation":
        return inject_duplicate_observations(
            clean,
            DuplicateInjectionConfig(
                severity=case.severity,  # type: ignore[arg-type]
                seed=case.seed,
                max_targets=case.max_targets,
            ),
        )
    if profile == "revision_overwrite":
        return inject_revision_overwrite(
            clean,
            source_records,
            RevisionOverwriteInjectionConfig(
                severity=case.severity,  # type: ignore[arg-type]
                seed=case.seed,
                max_targets=case.max_targets,
            ),
        )
    raise BenchmarkDispatchError(f"unsupported fault profile: {profile!r}")


def score_for_case(
    case: BenchmarkCaseConfig, report: AuditReport, manifest: CanonicalModel
) -> object:
    profile = case.fault_profile
    if profile == "lookahead_timestamp":
        return score_lookahead(report, manifest)  # type: ignore[arg-type]
    if profile == "unit_drift":
        return score_unit_drift(report, manifest)  # type: ignore[arg-type]
    if profile == "duplicate_observation":
        return score_duplicate_observations(report, manifest)  # type: ignore[arg-type]
    if profile == "revision_overwrite":
        return score_revision_overwrite(report, manifest)  # type: ignore[arg-type]
    raise BenchmarkDispatchError(f"unsupported fault profile: {profile!r}")


def replay_for_case(
    case: BenchmarkCaseConfig,
    corrupted: DatasetSnapshot,
    manifest: CanonicalModel,
) -> DatasetSnapshot:
    profile = case.fault_profile
    if profile == "lookahead_timestamp":
        return manifest_assisted_exact_replay(corrupted, manifest)  # type: ignore[arg-type]
    if profile == "unit_drift":
        return manifest_assisted_exact_unit_drift_replay(corrupted, manifest)  # type: ignore[arg-type]
    if profile == "duplicate_observation":
        return manifest_assisted_exact_duplicate_replay(corrupted, manifest)  # type: ignore[arg-type]
    if profile == "revision_overwrite":
        return manifest_assisted_exact_revision_overwrite_replay(corrupted, manifest)  # type: ignore[arg-type]
    raise BenchmarkDispatchError(f"unsupported fault profile: {profile!r}")


def research_for_case(
    case: BenchmarkCaseConfig,
    clean: DatasetSnapshot,
    corrupted: DatasetSnapshot,
    repaired: DatasetSnapshot,
    manifest: CanonicalModel,
    source_records: tuple[FinancialFact, ...],
) -> CanonicalModel:
    profile = case.fault_profile
    if profile == "lookahead_timestamp":
        return compare_lookahead_research(
            clean,
            corrupted,
            repaired,
            research_as_of_date=lookahead_research_date(case),
        )
    if profile == "unit_drift":
        research = case.research
        assert isinstance(research, BenchmarkUnitDriftResearch)
        # The comparable series under test is the injected target's own series.
        # That is private manifest truth, so it is resolved here — after the
        # audit report is finalized — rather than guessed during expansion.
        entries = manifest.entries  # type: ignore[attr-defined]
        return compare_unit_drift_research(
            clean,
            corrupted,
            repaired,
            UnitDriftResearchConfig(
                comparable_series_key=entries[0].comparable_series_key,
                research_as_of_date=research.research_as_of_date,
            ),
        )
    if profile == "duplicate_observation":
        return compare_duplicate_record_count(clean, corrupted, repaired)
    if profile == "revision_overwrite":
        research = case.research
        config = research.growth_ranking_config  # type: ignore[union-attr]
        frozen = tuple(
            build_frozen_vintage_growth_snapshot(snapshot, source_records, config)
            for snapshot in (clean, corrupted, repaired)
        )
        return compare_revision_overwrite_research(frozen[0], frozen[1], frozen[2], config)
    raise BenchmarkDispatchError(f"unsupported fault profile: {profile!r}")
