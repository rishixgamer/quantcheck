"""Strict comparability and production-oriented finding interpretation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.benchmark_dispatch import dispatch_benchmark_case
from quantcheck.benchmark_v2_case import run_benchmark_v2_case
from quantcheck.benchmark_v2_evaluation import evaluate_detector_execution_v2
from quantcheck.benchmark_v2_execution import run_selected_detectors_v2
from quantcheck.benchmark_v2_schemas import (
    BenchmarkV2Evaluation,
    FaultUnitOutcomeV2,
    ProductionFindingInterpretationV2,
)
from quantcheck.revision_overwrite_injection import inject_revision_overwrite
from quantcheck.schemas import RevisionOverwriteInjectionConfig
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json
from tests.benchmark_support import case_of, lookahead_profile, single_profile_config
from tests.benchmark_v2_support import case_for, case_result, unit_named
from tests.revision_overwrite_support import focused_history, focused_snapshot


def test_all_detector_strict_report_and_score_are_byte_identical_to_v01() -> None:
    v1_case = case_of(single_profile_config(lookahead_profile()), "lookahead_timestamp")
    v1 = dispatch_benchmark_case(v1_case)
    assert v1.manifest is not None

    corrupted_execution = run_selected_detectors_v2(v1.audit_input)
    clean_execution = run_selected_detectors_v2(sanitize_for_audit(v1.clean_snapshot))
    evaluation = evaluate_detector_execution_v2(
        primary_fault_profile="lookahead_timestamp",
        corrupted_execution=corrupted_execution,
        clean_control_execution=clean_execution,
        manifest=v1.manifest,  # type: ignore[arg-type]
    )
    assert evaluation.v0_1_all_detector_comparable is True
    assert canonical_json_bytes(evaluation.strict_primary_audit_report) == canonical_json_bytes(
        v1.audit_report
    )
    assert v1.score.score_report is not None
    assert canonical_json_bytes(evaluation.strict_primary_score) == canonical_json_bytes(
        v1.score.score_report
    )


def test_correlated_secondary_rule_stays_visible_without_changing_recall() -> None:
    # Historical availability equals period end. Revision overwrite retains
    # it while substituting later filing provenance, so the corrupted record
    # proves both the primary revision rule and the Look-Ahead rule.
    source = focused_history(
        historical_filed_on=date(2024, 3, 31),
        later_filed_on=date(2024, 6, 1),
    )
    clean = focused_snapshot(source, as_of_date=date(2024, 4, 30))
    corrupted, manifest = inject_revision_overwrite(
        clean,
        source,
        RevisionOverwriteInjectionConfig(severity="low", seed=0),
    )
    clean_execution = run_selected_detectors_v2(sanitize_for_audit(clean))
    corrupted_execution = run_selected_detectors_v2(sanitize_for_audit(corrupted))
    evaluation = evaluate_detector_execution_v2(
        primary_fault_profile="revision_overwrite",
        corrupted_execution=corrupted_execution,
        clean_control_execution=clean_execution,
        manifest=manifest,
    )

    strict = evaluation.strict_primary_score.metrics
    interpretation = evaluation.production_interpretation
    assert strict.true_positive_faults == 1
    assert strict.false_negative_faults == 0
    assert strict.findings == 2
    assert strict.false_positive_findings == 1
    assert strict.precision == Decimal("0.5")
    assert strict.recall == Decimal(1)
    assert interpretation.primary_matched_count == 1
    assert interpretation.secondary_corroborating_count == 1
    assert interpretation.independent_background_count == 0
    assert interpretation.unmatched_count == 0
    outcome = interpretation.fault_units[0]
    assert outcome.primary_finding_id is not None
    assert len(outcome.secondary_finding_ids) == 1
    assert set(outcome.violated_rule_ids) == {
        "revision.later_vintage_in_earlier_state",
        "temporal.period_end_available_before_filing",
    }
    secondary = next(
        item for item in interpretation.findings if item.category == "secondary_corroborating"
    )
    assert secondary.finding in evaluation.strict_primary_audit_report.findings


def test_legitimate_unusual_clean_findings_are_classified_as_background() -> None:
    unit = unit_named("development-stress")
    assert unit.diversity is not None
    assert unit.diversity.hard_negative_count == 14
    result = case_result("lookahead_timestamp", "development-stress")
    interpretation = result.evaluation.production_interpretation
    assert result.clean_control_execution.finding_count == 4
    assert interpretation.primary_matched_count == 1
    assert interpretation.independent_background_count == 4
    assert interpretation.secondary_corroborating_count == 0
    assert interpretation.unmatched_count == 0
    assert result.evaluation.strict_primary_score.metrics.false_positive_findings == 4
    for item in interpretation.findings:
        if item.category == "independent_background":
            assert item.clean_control_finding_ids


def test_genuinely_unexplained_findings_remain_explicit() -> None:
    result = case_result("unit_drift", "development-broad")
    interpretation = result.evaluation.production_interpretation
    assert interpretation.unmatched_count > 0
    assert interpretation.genuinely_unexplained_finding_ids
    assert set(interpretation.genuinely_unexplained_finding_ids) == {
        item.finding.finding_id for item in interpretation.findings if item.category == "unmatched"
    }


def test_one_finding_cannot_corroborate_multiple_fault_units() -> None:
    finding_id = "find_0000000000000000"
    with pytest.raises(ValidationError, match="cannot corroborate multiple"):
        ProductionFindingInterpretationV2.model_validate(
            {
                "finding_interpretation_id": "fint2_0000000000000000",
                "corrupted_execution_id": "dexec2_0000000000000000",
                "clean_control_execution_id": "dexec2_1111111111111111",
                "findings": (),
                "fault_units": (
                    FaultUnitOutcomeV2(
                        fault_id="fault_0000000000000000",
                        secondary_finding_ids=(finding_id,),
                    ),
                    FaultUnitOutcomeV2(
                        fault_id="fault_1111111111111111",
                        secondary_finding_ids=(finding_id,),
                    ),
                ),
                "primary_matched_count": 0,
                "secondary_corroborating_count": 0,
                "independent_background_count": 0,
                "unmatched_count": 0,
                "genuinely_unexplained_finding_ids": (),
            }
        )


def test_multi_fault_recall_remains_exactly_one_to_one() -> None:
    result = run_benchmark_v2_case(case_for("duplicate_observation"))
    score = result.evaluation.strict_primary_score
    assert score.metrics.injected_faults > 1
    assert score.metrics.true_positive_faults == len(score.matches)
    assert score.metrics.true_positive_findings == len(score.matches)
    assert len({match.fault_id for match in score.matches}) == len(score.matches)
    assert len({match.finding_id for match in score.matches}) == len(score.matches)


def test_single_primary_detector_has_strict_semantics_but_not_v01_suite_comparability() -> None:
    case = case_for(
        "lookahead_timestamp",
        selected_detectors=("lookahead_timestamp",),
    )
    result = run_benchmark_v2_case(case)
    assert result.evaluation.v0_1_all_detector_comparable is False
    assert result.evaluation.strict_primary_score.metrics.recall == Decimal(1)
    assert result.evaluation.production_interpretation.secondary_corroborating_count == 0


def test_evaluation_round_trips_canonically_with_all_four_categories() -> None:
    result = case_result("lookahead_timestamp", "development-stress")
    payload = canonical_json_bytes(result.evaluation)
    loaded = BenchmarkV2Evaluation.model_validate(parse_canonical_json(payload))
    assert loaded == result.evaluation
    assert canonical_json_bytes(loaded) == payload
