"""Look-Ahead configuration and artifact schema contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.lookahead_support import reviewed_lookahead_case


def _round_trip[ModelT: q.CanonicalModel](model: ModelT) -> ModelT:
    parsed = q.parse_canonical_json(q.canonical_json_bytes(model))
    return type(model).model_validate(parsed)


def test_config_is_strict_frozen_and_uses_exact_decimal_profiles() -> None:
    config = q.LookAheadInjectionConfig(
        severity="medium",
        seed=42,
        research_as_of_date=date(2024, 4, 14),
    )
    profile = q.lookahead_severity_profile(config.severity)
    assert profile.target_fraction == Decimal("0.05")
    assert profile.minimum_lag_days == 14
    with pytest.raises(ValidationError):
        config.seed = 43


@pytest.mark.parametrize("severity", ["tiny", "critical", "MEDIUM"])
def test_invalid_severity_is_rejected(severity: str) -> None:
    with pytest.raises(ValidationError):
        q.LookAheadInjectionConfig.model_validate(
            {
                "severity": severity,
                "seed": 1,
                "research_as_of_date": date(2024, 4, 14),
            }
        )


def test_unknown_config_field_and_nonpositive_cap_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        q.LookAheadInjectionConfig.model_validate(
            {
                "severity": "low",
                "seed": 1,
                "research_as_of_date": date(2024, 4, 14),
                "days_shifted": 7,
            }
        )
    with pytest.raises(ValidationError, match="positive"):
        q.LookAheadInjectionConfig(
            severity="low",
            seed=1,
            research_as_of_date=date(2024, 4, 14),
            max_targets=0,
        )


def test_all_new_artifacts_round_trip_to_identical_canonical_bytes() -> None:
    case = reviewed_lookahead_case()
    models: tuple[q.CanonicalModel, ...] = (
        case.config,
        case.manifest.entries[0].mutation,
        case.manifest.entries[0],
        case.manifest,
        case.audit_report.findings[0].evidence,
        case.audit_report.findings[0],
        case.audit_report,
        case.score.metrics,
        case.score.matches[0],
        case.score,
        case.impact.clean,
        case.impact,
    )
    for model in models:
        restored = _round_trip(model)
        assert restored == model
        assert q.canonical_json_bytes(restored) == q.canonical_json_bytes(model)


def test_artifact_tuples_are_canonically_ordered() -> None:
    case = reviewed_lookahead_case()
    finding = case.audit_report.findings[0]
    report = q.AuditReport(
        audit_report_id=case.audit_report.audit_report_id,
        detector_id=case.audit_report.detector_id,
        detector_version=case.audit_report.detector_version,
        audit_input_id=case.audit_report.audit_input_id,
        dataset_name=case.audit_report.dataset_name,
        as_of_date=case.audit_report.as_of_date,
        findings=(finding, finding),
    )
    assert report.findings == (finding, finding)
    assert finding.affected_record_ids == tuple(sorted(finding.affected_record_ids))
    assert case.manifest.eligible_record_ids == tuple(sorted(case.manifest.eligible_record_ids))


def test_all_production_artifact_identities_verify() -> None:
    case = reviewed_lookahead_case()
    assert q.manifest_identity_matches(case.manifest)
    assert q.finding_identity_matches(case.audit_report.findings[0])
    assert q.audit_report_identity_matches(case.audit_report)
    assert q.score_report_identity_matches(case.score)
    assert q.research_result_identity_matches(case.impact.clean)
    assert q.research_impact_identity_matches(case.impact)


def test_modified_record_uses_an_ordinary_non_role_revealing_record_prefix() -> None:
    entry = reviewed_lookahead_case().manifest.entries[0]
    assert entry.original_record.record_id.startswith("rec_")
    assert entry.corrupted_record.record_id.startswith("rec_")
    assert entry.original_record.record_id != entry.corrupted_record.record_id


def test_invalid_mutation_direction_is_rejected() -> None:
    with pytest.raises(ValidationError, match="move available_on backward"):
        q.LookAheadMutation(
            original_date=date(2024, 4, 15),
            corrupted_date=date(2024, 4, 15),
        )


def test_manifest_entry_rejects_a_non_period_end_mutation() -> None:
    entry = reviewed_lookahead_case().manifest.entries[0]
    bad_corrupted = entry.corrupted_record.model_copy(
        update={"available_on": entry.corrupted_record.period_end.replace(day=30)}
    )
    with pytest.raises(ValidationError, match="period-end substitution"):
        q.FaultManifestEntry.model_validate(
            {
                **entry.model_dump(),
                "corrupted_record": bad_corrupted,
                "mutation": q.LookAheadMutation(
                    original_date=entry.original_record.available_on,
                    corrupted_date=bad_corrupted.available_on,
                ),
            }
        )


def test_evidence_rejects_incorrect_leaked_day_count() -> None:
    evidence = reviewed_lookahead_case().audit_report.findings[0].evidence
    with pytest.raises(ValidationError, match="leaked_days"):
        q.LookAheadEvidence.model_validate({**evidence.model_dump(), "leaked_days": 999})


def test_metrics_reject_inconsistent_partitions_and_nulls() -> None:
    with pytest.raises(ValidationError, match="partition"):
        q.DetectionMetrics(
            injected_faults=1,
            findings=1,
            true_positive_faults=1,
            false_negative_faults=1,
            true_positive_findings=1,
            false_positive_findings=0,
            eligible_clean_denominator=1,
            precision=Decimal(1),
            recall=Decimal(1),
            false_positive_rate=Decimal(0),
        )


def test_decimal_artifact_values_never_serialize_as_json_numbers() -> None:
    case = reviewed_lookahead_case()
    text = q.canonical_json_text(case.score)
    assert '"precision":"1"' in text
    assert '"target_fraction":"0.05"' in q.canonical_json_text(case.manifest)
