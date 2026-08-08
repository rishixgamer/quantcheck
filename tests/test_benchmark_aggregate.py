"""Public-only aggregation, grouping, micro-summing, and null conventions."""

from __future__ import annotations

import shutil
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

import quantcheck as q
from tests.benchmark_support import (
    FIXED_RUNTIME,
    duplicate_profile,
    lookahead_profile,
    public_root,
    revision_overwrite_profile,
    single_profile_config,
    unit_drift_profile,
)


@pytest.fixture(scope="module")
def executed(tmp_path_factory: pytest.TempPathFactory) -> tuple[q.BenchmarkRunResult, Path]:
    config = q.build_benchmark_config(
        benchmark_name="aggregate",
        profiles=(
            lookahead_profile(
                seeds=(0, 100), control=q.BenchmarkCleanControl(severity="medium", seed=0)
            ),
            unit_drift_profile(seeds=(0, 100)),
            duplicate_profile(seeds=(0, 100)),
            revision_overwrite_profile(seeds=(0, 100)),
        ),
    )
    root = tmp_path_factory.mktemp("benchmark-aggregate")
    return q.run_benchmark(config, output_root=root, runtime=FIXED_RUNTIME), root


def test_the_aggregate_rebuilds_without_the_private_tree_at_all(
    executed: tuple[q.BenchmarkRunResult, Path], tmp_path: Path
) -> None:
    result, root = executed
    shutil.copytree(public_root(root), tmp_path / "public")
    assert not (tmp_path / "private").exists()
    rebuilt = q.aggregate_from_public_root(tmp_path)
    assert q.canonical_json_bytes(rebuilt) == q.canonical_json_bytes(result.aggregate)


def test_the_disk_only_rebuild_reproduces_the_saved_aggregate_bytes(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    _, root = executed
    saved = (public_root(root) / "aggregate_report.json").read_bytes()
    rebuilt = q.aggregate_from_public_root(root)
    assert q.canonical_json_bytes(rebuilt) == saved


def test_the_aggregator_never_reads_a_manifest_or_a_private_path(
    executed: tuple[q.BenchmarkRunResult, Path], tmp_path: Path
) -> None:
    """Copy only the public tree, then delete the original entirely."""
    result, root = executed
    isolated = tmp_path / "public-only"
    shutil.copytree(public_root(root), isolated)
    rebuilt = q.aggregate_from_public_artifacts(q.AtomicArtifactStore(isolated))
    assert rebuilt.overall.configured_case_count == result.matrix.case_count
    names = {path.name for path in isolated.rglob("*.json")}
    assert "manifest.json" not in names
    assert "clean_snapshot.json" not in names
    assert "corrupted_snapshot.json" not in names
    assert "repaired_snapshot.json" not in names
    assert "research_impact.json" not in names


def test_overall_counts_are_micro_sums_of_every_successful_case(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, root = executed
    expected = {
        "injected_faults": 0,
        "findings": 0,
        "true_positive_findings": 0,
        "false_positive_findings": 0,
        "eligible_clean_denominator": 0,
    }
    for status in result.statuses:
        assert status.status == "succeeded"
        score = q.BenchmarkCaseScore.model_validate(
            q.parse_canonical_json(
                (public_root(root) / "cases" / status.benchmark_case_id / "score.json").read_bytes()
            )
        )
        for key in expected:
            expected[key] += getattr(score.metrics, key)
    overall = result.aggregate.overall
    for key, value in expected.items():
        assert getattr(overall, key) == value, key


def test_aggregate_metrics_come_from_summed_counts_not_averaged_per_case(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, root = executed
    overall = result.aggregate.overall
    with localcontext() as context:
        context.prec = 50
        assert overall.precision == Decimal(overall.true_positive_findings) / Decimal(
            overall.findings
        )
        assert overall.recall == Decimal(overall.true_positive_faults) / Decimal(
            overall.injected_faults
        )
        assert overall.false_positive_rate == Decimal(overall.false_positive_findings) / Decimal(
            overall.eligible_clean_denominator
        )

    # A macro-average of per-case precision really is a different number here,
    # so this test would fail if anyone switched the aggregator to averaging.
    per_case = []
    for status in result.statuses:
        score = q.BenchmarkCaseScore.model_validate(
            q.parse_canonical_json(
                (public_root(root) / "cases" / status.benchmark_case_id / "score.json").read_bytes()
            )
        )
        if score.metrics.precision is not None:
            per_case.append(score.metrics.precision)
    assert per_case
    with localcontext() as context:
        context.prec = 50
        macro = sum(per_case, Decimal(0)) / Decimal(len(per_case))
    assert overall.precision != macro


def test_every_grouping_partitions_the_configured_matrix(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = executed
    total = result.aggregate.overall.configured_case_count
    for groups in (
        result.aggregate.by_fault_profile,
        result.aggregate.by_severity,
        result.aggregate.by_seed_class,
        result.aggregate.by_seed,
    ):
        assert sum(group.configured_case_count for group in groups) == total


def test_grouping_keys_cover_the_configured_dimensions(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = executed
    assert {g.key for g in result.aggregate.by_fault_profile} == set(q.BENCHMARK_FAULT_PROFILES)
    assert {g.key for g in result.aggregate.by_severity} == {"low", "medium"}
    assert {g.key for g in result.aggregate.by_seed_class} == {"development", "validation"}
    assert {g.key for g in result.aggregate.by_seed} == {"0", "100"}


def test_seed_class_grouping_separates_development_from_validation(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = executed
    development = next(g for g in result.aggregate.by_seed_class if g.key == "development")
    validation = next(g for g in result.aggregate.by_seed_class if g.key == "validation")
    assert development.configured_case_count == 5  # four faults plus the control
    assert validation.configured_case_count == 4
    assert development.configured_case_count + validation.configured_case_count == (
        result.aggregate.overall.configured_case_count
    )


def test_a_clean_control_contributes_false_positives_and_a_clean_denominator(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, root = executed
    control = next(s for s in result.statuses if s.case_kind == "clean_control")
    score = q.BenchmarkCaseScore.model_validate(
        q.parse_canonical_json(
            (public_root(root) / "cases" / control.benchmark_case_id / "score.json").read_bytes()
        )
    )
    assert score.metrics.injected_faults == 0
    assert score.metrics.recall is None
    assert score.metrics.eligible_clean_denominator > 0
    assert score.score_report is None


def test_a_fault_free_successful_group_uses_the_documented_precision_of_one(
    tmp_path: Path,
) -> None:
    """A quiet clean control is perfectly precise; it is not left undefined."""
    config = single_profile_config(
        unit_drift_profile(control=q.BenchmarkCleanControl(severity="medium", seed=0)),
        name="control-only",
    )
    result = q.run_benchmark(config, output_root=tmp_path, runtime=FIXED_RUNTIME)
    rebuilt = q.aggregate_from_public_root(tmp_path)
    control_seed_group = next(g for g in rebuilt.by_seed_class if g.key == "development")
    assert control_seed_group.configured_case_count == 2
    # The Unit Drift series control produces no finding at all.
    control = next(s for s in result.statuses if s.case_kind == "clean_control")
    score = q.BenchmarkCaseScore.model_validate(
        q.parse_canonical_json(
            (
                public_root(tmp_path) / "cases" / control.benchmark_case_id / "score.json"
            ).read_bytes()
        )
    )
    assert score.metrics.findings == 0
    assert score.metrics.precision is None  # per-case convention: undefined


def test_group_null_conventions_are_exactly_the_documented_ones() -> None:
    fault_free_quiet = q.BenchmarkAggregateGroup(
        grouping="overall",
        key="overall",
        configured_case_count=1,
        successful_case_count=1,
        failed_case_count=0,
        incomplete_case_count=0,
        injected_faults=0,
        findings=0,
        true_positive_faults=0,
        false_negative_faults=0,
        true_positive_findings=0,
        false_positive_findings=0,
        eligible_clean_denominator=5,
        precision=Decimal(1),
        recall=None,
        f1=None,
        false_positive_rate=Decimal(0),
        research_summary_count=0,
        research_changed_count=0,
        replay_restored_count=0,
    )
    assert fault_free_quiet.precision == 1
    assert fault_free_quiet.recall is None
    assert fault_free_quiet.f1 is None

    fault_bearing_quiet = q.BenchmarkAggregateGroup(
        grouping="overall",
        key="overall",
        configured_case_count=1,
        successful_case_count=1,
        failed_case_count=0,
        incomplete_case_count=0,
        injected_faults=2,
        findings=0,
        true_positive_faults=0,
        false_negative_faults=2,
        true_positive_findings=0,
        false_positive_findings=0,
        eligible_clean_denominator=0,
        precision=None,
        recall=Decimal(0),
        f1=None,
        false_positive_rate=None,
        research_summary_count=0,
        research_changed_count=0,
        replay_restored_count=0,
    )
    assert fault_bearing_quiet.precision is None
    assert fault_bearing_quiet.f1 is None
    assert fault_bearing_quiet.false_positive_rate is None


def test_a_group_rejects_a_precision_that_breaks_the_convention() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="precision"):
        q.BenchmarkAggregateGroup(
            grouping="overall",
            key="overall",
            configured_case_count=1,
            successful_case_count=1,
            failed_case_count=0,
            incomplete_case_count=0,
            injected_faults=2,
            findings=0,
            true_positive_faults=0,
            false_negative_faults=2,
            true_positive_findings=0,
            false_positive_findings=0,
            eligible_clean_denominator=0,
            precision=Decimal(1),
            recall=Decimal(0),
            f1=None,
            false_positive_rate=None,
            research_summary_count=0,
            research_changed_count=0,
            replay_restored_count=0,
        )


def test_research_summary_counts_come_only_from_fault_cases(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = executed
    overall = result.aggregate.overall
    fault_cases = sum(1 for case in result.matrix.cases if case.case_kind == "fault")
    assert overall.research_summary_count == fault_cases
    assert overall.research_changed_count <= overall.research_summary_count
    assert overall.replay_restored_count <= overall.research_summary_count


def test_aggregation_rejects_a_public_tree_without_a_case_matrix(tmp_path: Path) -> None:
    (tmp_path / "public").mkdir()
    with pytest.raises(q.BenchmarkAggregationError, match="case matrix"):
        q.aggregate_from_public_root(tmp_path)


def test_the_aggregate_identifier_is_derived_from_its_own_content(
    executed: tuple[q.BenchmarkRunResult, Path],
) -> None:
    result, _ = executed
    report = result.aggregate
    body = {
        name: getattr(report, name)
        for name in q.BenchmarkAggregateReport.model_fields
        if name != "aggregate_report_id"
    }
    assert report.aggregate_report_id == q.benchmark_aggregate_report_id(report_body=body)
    assert q.BENCHMARK_AGGREGATE_ID_PATTERN.fullmatch(report.aggregate_report_id)
