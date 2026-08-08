"""Benchmark aggregation rebuilt exclusively from public saved artifacts.

Nothing here reads a manifest, a clean snapshot, a corrupted snapshot, a
repaired snapshot, a private evaluation, a private research value, or the
private directory at all. The aggregator is handed the *public* store and can
address nothing else, which is what makes "public evidence is sufficient" a
structural property rather than a promise.

Counts are micro-summed and metrics are computed once from the summed counts.
Averaging per-case precision or recall would silently weight a one-record case
the same as a twenty-record case, so it is never done.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from pathlib import Path

from pydantic import ValidationError

from quantcheck.benchmark_contract import (
    BENCHMARK_SPEC_VERSION,
    PUBLIC_CASE_ARTIFACT_NAMES,
    PUBLIC_ROOT_NAME,
    REQUIRED_PUBLIC_CASE_ARTIFACTS,
    public_case_directory,
)
from quantcheck.benchmark_store import (
    ArtifactPersistenceError,
    AtomicArtifactStore,
)
from quantcheck.hashing import benchmark_aggregate_report_id, sha256_hex_of_bytes
from quantcheck.json_types import CanonicalizationError
from quantcheck.schemas import (
    BenchmarkAggregateGroup,
    BenchmarkAggregateReport,
    BenchmarkCaseConfig,
    BenchmarkCaseMatrix,
    BenchmarkCaseScore,
    BenchmarkCaseStatus,
    BenchmarkGrouping,
    BenchmarkResearchSummary,
)

__all__ = [
    "BenchmarkAggregationError",
    "aggregate_from_public_artifacts",
    "aggregate_from_public_root",
]


class BenchmarkAggregationError(ValueError):
    """Raised when public artifacts cannot support an aggregate at all."""


@dataclass(slots=True)
class _Counters:
    """Micro-summed counters for one aggregation group."""

    configured: int = 0
    succeeded: int = 0
    failed: int = 0
    incomplete: int = 0
    injected_faults: int = 0
    findings: int = 0
    true_positive_faults: int = 0
    false_negative_faults: int = 0
    true_positive_findings: int = 0
    false_positive_findings: int = 0
    eligible_clean_denominator: int = 0
    research_summaries: int = 0
    research_changed: int = 0
    replay_restored: int = 0

    def add_case(self) -> None:
        self.configured += 1

    def add_score(self, score: BenchmarkCaseScore) -> None:
        metrics = score.metrics
        self.injected_faults += metrics.injected_faults
        self.findings += metrics.findings
        self.true_positive_faults += metrics.true_positive_faults
        self.false_negative_faults += metrics.false_negative_faults
        self.true_positive_findings += metrics.true_positive_findings
        self.false_positive_findings += metrics.false_positive_findings
        self.eligible_clean_denominator += metrics.eligible_clean_denominator

    def add_research(self, summary: BenchmarkResearchSummary) -> None:
        self.research_summaries += 1
        self.research_changed += int(summary.changed)
        self.replay_restored += int(summary.exact_restoration)


@dataclass(slots=True)
class _CaseOutcome:
    """One case's public outcome, as reconstructed from disk."""

    case: BenchmarkCaseConfig
    status: str
    score: BenchmarkCaseScore | None = None
    research: BenchmarkResearchSummary | None = None
    keys: dict[str, str] = field(default_factory=dict)


def _ratio(numerator: int, denominator: int) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        return Decimal(numerator) / Decimal(denominator)


def _group(grouping: BenchmarkGrouping, key: str, counters: _Counters) -> BenchmarkAggregateGroup:
    """Build one group, applying the exact documented null conventions.

    * precision — the pooled ``TP / findings``. With no findings at all it is
      ``1`` for a successful fault-free group (a clean control that stayed
      quiet is perfectly precise) and null for a fault-bearing group, whose
      precision is genuinely undefined rather than perfect.
    * recall — null when nothing was injected.
    * F1 — null whenever precision or recall is null.
    * false-positive rate — null with no eligible-clean denominator.
    """
    if counters.findings:
        precision = _ratio(counters.true_positive_findings, counters.findings)
    elif counters.injected_faults == 0 and counters.succeeded > 0:
        precision = Decimal(1)
    else:
        precision = None
    recall = (
        _ratio(counters.true_positive_faults, counters.injected_faults)
        if counters.injected_faults
        else None
    )
    if precision is None or recall is None:
        f1 = None
    elif precision + recall == 0:
        f1 = Decimal(0)
    else:
        with localcontext() as context:
            context.prec = 50
            f1 = (Decimal(2) * precision * recall) / (precision + recall)
    false_positive_rate = (
        _ratio(counters.false_positive_findings, counters.eligible_clean_denominator)
        if counters.eligible_clean_denominator
        else None
    )
    return BenchmarkAggregateGroup(
        grouping=grouping,
        key=key,
        configured_case_count=counters.configured,
        successful_case_count=counters.succeeded,
        failed_case_count=counters.failed,
        incomplete_case_count=counters.incomplete,
        injected_faults=counters.injected_faults,
        findings=counters.findings,
        true_positive_faults=counters.true_positive_faults,
        false_negative_faults=counters.false_negative_faults,
        true_positive_findings=counters.true_positive_findings,
        false_positive_findings=counters.false_positive_findings,
        eligible_clean_denominator=counters.eligible_clean_denominator,
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_rate=false_positive_rate,
        research_summary_count=counters.research_summaries,
        research_changed_count=counters.research_changed,
        replay_restored_count=counters.replay_restored,
    )


def _public_case_path(case_id: str, artifact: str) -> str:
    return f"{public_case_directory(case_id)}/{PUBLIC_CASE_ARTIFACT_NAMES[artifact]}"


def _read_status(public: AtomicArtifactStore, case_id: str) -> BenchmarkCaseStatus | None:
    relative = _public_case_path(case_id, "status")
    if not public.exists(relative):
        return None
    try:
        return BenchmarkCaseStatus.model_validate(public.read_canonical(relative))
    except (ValidationError, CanonicalizationError, ArtifactPersistenceError):
        return None


def _case_outcome(public: AtomicArtifactStore, case: BenchmarkCaseConfig) -> _CaseOutcome:
    """Reconstruct one case's outcome from public evidence alone.

    A case whose terminal status is missing, unreadable, invalid, or
    unsupported by its own referenced artifacts becomes ``incomplete``. It is
    never dropped: disappearing from the denominator is how a broken benchmark
    would come to look successful.
    """
    outcome = _CaseOutcome(case=case, status="incomplete")
    status = _read_status(public, case.benchmark_case_id)
    if status is None or status.benchmark_case_id != case.benchmark_case_id:
        return outcome
    if status.status == "failed":
        outcome.status = "failed"
        return outcome
    if status.status != "succeeded":
        return outcome

    referenced = {reference.kind: reference for reference in status.artifacts}
    required = list(REQUIRED_PUBLIC_CASE_ARTIFACTS)
    if case.case_kind == "fault":
        required.append("research_summary")
    if any(kind not in referenced for kind in required):
        return outcome
    for reference in status.artifacts:
        if not public.exists(reference.relative_path):
            return outcome
        payload = public.read_bytes(reference.relative_path)
        if sha256_hex_of_bytes(payload) != reference.content_hash:
            return outcome

    try:
        score = BenchmarkCaseScore.model_validate(
            public.read_canonical(referenced["score"].relative_path)
        )
    except (ValidationError, CanonicalizationError, ArtifactPersistenceError):
        return outcome
    if score.benchmark_case_id != case.benchmark_case_id or score.case_kind != case.case_kind:
        return outcome

    research: BenchmarkResearchSummary | None = None
    if "research_summary" in referenced:
        try:
            research = BenchmarkResearchSummary.model_validate(
                public.read_canonical(referenced["research_summary"].relative_path)
            )
        except (ValidationError, CanonicalizationError, ArtifactPersistenceError):
            return outcome
        if research.benchmark_case_id != case.benchmark_case_id:
            return outcome

    outcome.status = "succeeded"
    outcome.score = score
    outcome.research = research
    return outcome


def aggregate_from_public_artifacts(
    public: AtomicArtifactStore,
) -> BenchmarkAggregateReport:
    """Rebuild the aggregate report from one public artifact tree."""
    try:
        matrix = BenchmarkCaseMatrix.model_validate(public.read_canonical("case_matrix.json"))
    except (ValidationError, CanonicalizationError, ArtifactPersistenceError) as exc:
        raise BenchmarkAggregationError(
            "the public case matrix is missing or does not validate"
        ) from exc

    overall = _Counters()
    grouped: dict[BenchmarkGrouping, dict[str, _Counters]] = {
        "fault_profile": {},
        "severity": {},
        "seed_class": {},
        "seed": {},
    }

    for case in matrix.cases:
        outcome = _case_outcome(public, case)
        keys = {
            "fault_profile": case.fault_profile,
            "severity": case.severity,
            "seed_class": case.seed_class,
            "seed": str(case.seed),
        }
        buckets = [overall]
        for grouping, key in keys.items():
            buckets.append(grouped[grouping].setdefault(key, _Counters()))  # type: ignore[index]
        for bucket in buckets:
            bucket.add_case()
            if outcome.status == "succeeded":
                bucket.succeeded += 1
                assert outcome.score is not None
                bucket.add_score(outcome.score)
                if outcome.research is not None:
                    bucket.add_research(outcome.research)
            elif outcome.status == "failed":
                bucket.failed += 1
            else:
                bucket.incomplete += 1

    body: dict[str, object] = {
        "benchmark_id": matrix.benchmark_id,
        "spec_version": BENCHMARK_SPEC_VERSION,
        "overall": _group("overall", "overall", overall),
        "by_fault_profile": tuple(
            _group("fault_profile", key, counters)
            for key, counters in sorted(grouped["fault_profile"].items())
        ),
        "by_severity": tuple(
            _group("severity", key, counters)
            for key, counters in sorted(grouped["severity"].items())
        ),
        "by_seed_class": tuple(
            _group("seed_class", key, counters)
            for key, counters in sorted(grouped["seed_class"].items())
        ),
        "by_seed": tuple(
            _group("seed", key, counters) for key, counters in sorted(grouped["seed"].items())
        ),
    }
    return BenchmarkAggregateReport.model_validate(
        {"aggregate_report_id": benchmark_aggregate_report_id(report_body=body), **body}
    )


def aggregate_from_public_root(public_root: Path) -> BenchmarkAggregateReport:
    """Rebuild the aggregate from a public tree on disk, private tree absent.

    ``public_root`` may be either an output root containing ``public/`` or the
    public directory itself, so a caller can copy just the public tree
    somewhere else and reproduce the aggregate from it.
    """
    root = Path(public_root)
    candidate = root / PUBLIC_ROOT_NAME
    if candidate.is_dir() and (candidate / "case_matrix.json").is_file():
        root = candidate
    return aggregate_from_public_artifacts(AtomicArtifactStore(root))
