"""The shared presentation model: exactness, null handling, and completeness.

The model is the single interpretation both surfaces render, so these tests
check that it reproduces the saved artifacts rather than reinterpreting them —
including the parts a prettier UI would be tempted to smooth over: failed
cases, incomplete cases, and undefined metrics.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

import quantcheck as q
from quantcheck.presentation import build_presentation, metric_text
from quantcheck.public_artifact_reader import read_public_benchmark
from tests.presentation_helpers import (
    build_failed_benchmark,
    build_incomplete_benchmark,
    build_smoke_benchmark,
    copy_public_only,
)


@pytest.fixture(scope="module")
def smoke_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("presentation-smoke")
    build_smoke_benchmark(root)
    return root


@pytest.fixture(scope="module")
def presentation(smoke_root: Path) -> q.BenchmarkPresentation:
    return build_presentation(read_public_benchmark(smoke_root))


def test_the_headline_numbers_are_the_saved_aggregate_report(
    smoke_root: Path, presentation: q.BenchmarkPresentation
) -> None:
    """Not "close to" the saved aggregate — identical to it, field by field."""
    aggregate = read_public_benchmark(smoke_root).aggregate
    overall = aggregate.overall
    assert presentation.benchmark_id == aggregate.benchmark_id
    assert presentation.aggregate_report_id == aggregate.aggregate_report_id
    assert presentation.configured_case_count == overall.configured_case_count
    assert presentation.successful_case_count == overall.successful_case_count
    assert presentation.failed_case_count == overall.failed_case_count
    assert presentation.incomplete_case_count == overall.incomplete_case_count
    assert presentation.overall.precision == overall.precision
    assert presentation.overall.recall == overall.recall
    assert presentation.overall.f1 == overall.f1
    assert presentation.overall.false_positive_rate == overall.false_positive_rate
    assert presentation.overall.findings == overall.findings
    assert presentation.overall.injected_faults == overall.injected_faults


def test_metrics_are_exact_decimals_never_routed_through_float(
    presentation: q.BenchmarkPresentation,
) -> None:
    precision = presentation.overall.precision
    assert isinstance(precision, Decimal)
    # A float round-trip of a repeating aggregate metric loses digits; the model
    # must still hold every one of them.
    assert precision == Decimal(str(precision))
    for group in presentation.by_fault_profile:
        for value in (
            group.metrics.precision,
            group.metrics.recall,
            group.metrics.f1,
            group.metrics.false_positive_rate,
        ):
            assert value is None or isinstance(value, Decimal)


def test_a_repeating_metric_keeps_its_full_saved_precision(
    smoke_root: Path, presentation: q.BenchmarkPresentation
) -> None:
    saved = read_public_benchmark(smoke_root).aggregate.overall.f1
    assert presentation.overall.f1 == saved
    if saved is not None:
        assert str(presentation.overall.f1) == str(saved)
        assert Decimal(float(saved)) != saved or saved == saved.quantize(Decimal(1))


def test_the_saved_groupings_are_preserved_not_recomputed(
    smoke_root: Path, presentation: q.BenchmarkPresentation
) -> None:
    aggregate = read_public_benchmark(smoke_root).aggregate
    for saved_groups, model_groups in (
        (aggregate.by_fault_profile, presentation.by_fault_profile),
        (aggregate.by_severity, presentation.by_severity),
        (aggregate.by_seed_class, presentation.by_seed_class),
        (aggregate.by_seed, presentation.by_seed),
    ):
        assert [group.key for group in saved_groups] == [group.key for group in model_groups]
        for saved, model in zip(saved_groups, model_groups, strict=True):
            assert model.metrics.precision == saved.precision
            assert model.metrics.recall == saved.recall
            assert model.metrics.f1 == saved.f1
            assert model.metrics.false_positive_rate == saved.false_positive_rate
            assert model.configured_case_count == saved.configured_case_count
            assert model.research_changed_count == saved.research_changed_count
            assert model.replay_restored_count == saved.replay_restored_count


def test_every_configured_case_appears_including_clean_controls(
    presentation: q.BenchmarkPresentation,
) -> None:
    assert len(presentation.cases) == presentation.configured_case_count == q.SMOKE_CASE_COUNT
    assert presentation.clean_control_count == 4
    assert presentation.fault_case_count == 8
    assert presentation.clean_control_count + presentation.fault_case_count == len(
        presentation.cases
    )


def test_clean_controls_carry_their_metrics_and_no_injected_faults(
    presentation: q.BenchmarkPresentation,
) -> None:
    controls = [case for case in presentation.cases if case.case_kind == "clean_control"]
    assert controls
    for control in controls:
        assert control.metrics is not None
        assert control.metrics.injected_faults == 0
        assert control.research is None


def test_fault_cases_carry_only_the_sanitized_research_booleans(
    presentation: q.BenchmarkPresentation,
) -> None:
    faults = [case for case in presentation.cases if case.case_kind == "fault"]
    assert faults
    for case in faults:
        assert case.research is not None
        assert isinstance(case.research.changed, bool)
        assert isinstance(case.research.exact_restoration, bool)
        assert set(type(case.research).model_fields) == {
            "method",
            "changed",
            "exact_restoration",
        }


def test_at_least_one_controlled_research_output_actually_changed(
    presentation: q.BenchmarkPresentation,
) -> None:
    assert any(case.research is not None and case.research.changed for case in presentation.cases)


def test_findings_carry_rule_confidence_evidence_and_explanation(
    presentation: q.BenchmarkPresentation,
) -> None:
    findings = [finding for case in presentation.cases for finding in case.findings]
    assert findings
    for finding in findings:
        assert finding.rule_id
        assert finding.confidence
        assert finding.explanation
        assert finding.evidence
        assert all(item.label and item.value for item in finding.evidence)


def test_case_order_is_deterministic_and_matches_the_saved_matrix(
    smoke_root: Path, presentation: q.BenchmarkPresentation
) -> None:
    matrix = read_public_benchmark(smoke_root).matrix
    assert [case.benchmark_case_id for case in presentation.cases] == [
        case.benchmark_case_id for case in matrix.cases
    ]


def test_building_the_model_twice_produces_identical_bytes(smoke_root: Path) -> None:
    first = build_presentation(read_public_benchmark(smoke_root))
    second = build_presentation(read_public_benchmark(smoke_root))
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)


def test_a_public_only_copy_produces_an_identical_model(smoke_root: Path, tmp_path: Path) -> None:
    copied = copy_public_only(smoke_root, tmp_path / "public-only")
    from_copy = build_presentation(read_public_benchmark(copied))
    from_original = build_presentation(read_public_benchmark(smoke_root))
    assert q.canonical_json_bytes(from_copy) == q.canonical_json_bytes(from_original)


def test_a_failed_case_survives_into_the_model_with_its_redacted_failure(
    tmp_path: Path,
) -> None:
    build_failed_benchmark(tmp_path)
    model = build_presentation(read_public_benchmark(tmp_path))
    failed = [case for case in model.cases if case.terminal_status == "failed"]
    assert len(failed) == 1 == model.failed_case_count
    assert failed[0].failure is not None
    assert failed[0].failure.message == q.redacted_failure_message("no_eligible_targets")
    assert failed[0].metrics is None


def test_an_incomplete_case_survives_into_the_model_and_is_not_called_successful(
    tmp_path: Path,
) -> None:
    case_id = build_incomplete_benchmark(tmp_path)
    model = build_presentation(read_public_benchmark(tmp_path))
    by_id = {case.benchmark_case_id: case for case in model.cases}
    assert by_id[case_id].terminal_status == "incomplete"
    assert model.incomplete_case_count == 1
    assert model.successful_case_count == len(model.cases) - 1


def test_an_undefined_metric_stays_null_in_the_model(tmp_path: Path) -> None:
    """A group with no eligible clean denominator has an undefined FP rate.

    The model must hold ``None`` for it — not zero, not NaN, not "n/a".
    """
    build_failed_benchmark(tmp_path)
    model = build_presentation(read_public_benchmark(tmp_path))
    nulls = [
        value
        for group in (*model.by_fault_profile, *model.by_seed, *model.by_severity)
        for value in (
            group.metrics.precision,
            group.metrics.recall,
            group.metrics.f1,
            group.metrics.false_positive_rate,
        )
        if value is None
    ]
    assert nulls, "the failed-case benchmark should leave at least one metric undefined"
    serialized = q.canonical_json_bytes(model)
    assert b"NaN" not in serialized
    assert b'"n/a"' not in serialized


def test_the_display_policy_renders_null_without_changing_the_model() -> None:
    assert metric_text(None) == "n/a"
    assert metric_text(Decimal("0")) == "0"
    assert metric_text(Decimal("0.5")) == "0.5"


def test_the_model_is_immutable(presentation: q.BenchmarkPresentation) -> None:
    with pytest.raises(ValidationError):
        presentation.benchmark_id = "bench_" + "0" * 16
