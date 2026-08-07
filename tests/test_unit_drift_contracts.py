"""Strict Unit Drift configurations, artifacts, and identity contracts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.unit_drift_support import reviewed_unit_drift_case


@pytest.mark.parametrize(
    ("severity", "factor", "fraction"),
    [
        ("low", Decimal("100"), Decimal("0.02")),
        ("medium", Decimal("1000"), Decimal("0.05")),
        ("high", Decimal("1000000"), Decimal("0.10")),
    ],
)
def test_severity_profiles_are_exact(
    severity: q.UnitDriftSeverity,
    factor: Decimal,
    fraction: Decimal,
) -> None:
    profile = q.unit_drift_severity_profile(severity)
    assert profile.scale_factor == factor
    assert profile.target_fraction == fraction
    assert q.unit_drift_finding_severity(factor) == severity


@pytest.mark.parametrize("severity", ["tiny", "critical", "MEDIUM"])
def test_invalid_severity_is_rejected(severity: str) -> None:
    with pytest.raises(ValidationError):
        q.UnitDriftInjectionConfig.model_validate({"severity": severity, "seed": 1})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fault_type", "lookahead_timestamp"),
        ("fault_subtype", "unit_label_only"),
        ("spec_version", "v2"),
    ],
)
def test_unsupported_fault_contract_labels_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        q.UnitDriftInjectionConfig.model_validate({"severity": "low", "seed": 1, field: value})


def test_injection_config_is_strict_frozen_and_rejects_bad_seed_and_cap() -> None:
    config = q.UnitDriftInjectionConfig(severity="low", seed=1)
    with pytest.raises(ValidationError):
        config.seed = 2
    with pytest.raises(ValidationError, match="Extra inputs"):
        q.UnitDriftInjectionConfig.model_validate(
            {"severity": "low", "seed": 1, "scale_factor": "100"}
        )
    with pytest.raises(ValidationError, match="boolean"):
        q.UnitDriftInjectionConfig(severity="low", seed=True)
    with pytest.raises(ValidationError, match="positive"):
        q.UnitDriftInjectionConfig(severity="low", seed=1, max_targets=0)


def test_detector_config_copies_sorts_and_canonicalizes_factors() -> None:
    caller_owned = [Decimal("1000000"), Decimal("100")]
    config = q.UnitDriftDetectorConfig.model_validate({"supported_scale_factors": caller_owned})
    caller_owned.reverse()
    assert config.supported_scale_factors == (Decimal("100"), Decimal("1000000"))
    assert isinstance(config.supported_scale_factors, tuple)
    assert config.ratio_threshold == Decimal("50")


@pytest.mark.parametrize(
    "factors",
    [(), (Decimal("100"), Decimal("100")), (Decimal("10"),), (Decimal("1.5"),)],
)
def test_detector_rejects_empty_duplicate_or_unsupported_factors(
    factors: tuple[Decimal, ...],
) -> None:
    with pytest.raises(ValidationError):
        q.UnitDriftDetectorConfig(supported_scale_factors=factors)


@pytest.mark.parametrize("threshold", [Decimal("0"), Decimal("1"), Decimal("-2")])
def test_detector_rejects_invalid_thresholds(threshold: Decimal) -> None:
    with pytest.raises(ValidationError, match="greater than one"):
        q.UnitDriftDetectorConfig(ratio_threshold=threshold)


def test_detector_rejects_float_boolean_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        q.UnitDriftDetectorConfig.model_validate({"ratio_threshold": 50.0})
    with pytest.raises(ValidationError):
        q.UnitDriftDetectorConfig.model_validate({"ratio_threshold": True})
    with pytest.raises(ValidationError, match="Extra inputs"):
        q.UnitDriftDetectorConfig.model_validate(
            {"ratio_threshold": "50", "target_fraction": "0.1"}
        )


def test_comparable_series_key_normalizes_dimensions_and_enforces_period_shape() -> None:
    dimensions = [
        q.Dimension(axis="Segment", member="Cloud"),
        q.Dimension(axis="Region", member="US"),
    ]
    key = q.ComparableSeriesKey.model_validate(
        {
            "entity_id": "E1",
            "concept_namespace": "us-gaap",
            "concept": "Revenues",
            "unit": "USD",
            "dimensions": dimensions,
            "period_type": "duration",
            "period_length_days": 30,
        }
    )
    dimensions.reverse()
    assert tuple(item.axis for item in key.dimensions) == ("Region", "Segment")
    with pytest.raises(ValidationError, match="instant"):
        q.ComparableSeriesKey(
            entity_id="E1",
            concept_namespace="us-gaap",
            concept="Assets",
            unit="USD",
            period_type="instant",
            period_length_days=1,
        )
    with pytest.raises(ValidationError, match="duration"):
        q.ComparableSeriesKey(
            entity_id="E1",
            concept_namespace="us-gaap",
            concept="Revenues",
            unit="USD",
            period_type="duration",
        )


def test_mutation_rejects_zero_fractional_negative_and_inconsistent_scales() -> None:
    for factor in (Decimal("0"), Decimal("-100"), Decimal("1.5")):
        with pytest.raises(ValidationError):
            q.UnitDriftMutation(
                original_value=Decimal("2"),
                corrupted_value=Decimal("200"),
                scale_factor=factor,
            )
    with pytest.raises(ValidationError, match="zero"):
        q.UnitDriftMutation(
            original_value=Decimal("0"),
            corrupted_value=Decimal("0"),
            scale_factor=Decimal("100"),
        )
    with pytest.raises(ValidationError, match="must equal"):
        q.UnitDriftMutation(
            original_value=Decimal("2"),
            corrupted_value=Decimal("201"),
            scale_factor=Decimal("100"),
        )


def test_all_unit_drift_artifacts_round_trip_with_identical_canonical_bytes() -> None:
    case = reviewed_unit_drift_case()
    models: tuple[q.CanonicalModel, ...] = (
        case.config,
        q.UnitDriftDetectorConfig(),
        case.manifest.entries[0].comparable_series_key,
        case.manifest.entries[0].mutation,
        case.manifest.entries[0],
        case.manifest,
        case.audit_report.findings[0].evidence,
        case.audit_report.findings[0],
        case.audit_report,
        case.score,
        case.research_config,
        case.impact.clean,
        case.impact,
    )
    for model in models:
        restored = type(model).model_validate(q.parse_canonical_json(q.canonical_json_bytes(model)))
        assert restored == model
        assert q.canonical_json_bytes(restored) == q.canonical_json_bytes(model)


def test_high_precision_decimal_evidence_round_trips_without_context_rounding() -> None:
    value = Decimal("1.0909090909090909090909090909090909090909090909091")
    encoded = q.canonical_decimal_string(value)
    assert q.parse_canonical_decimal(encoded) == value


def test_all_unit_drift_artifact_identities_verify_and_use_non_role_record_prefix() -> None:
    case = reviewed_unit_drift_case()
    entry = case.manifest.entries[0]
    finding = case.audit_report.findings[0]
    assert entry.original_record.record_id.startswith("rec_")
    assert entry.corrupted_record.record_id.startswith("rec_")
    assert entry.original_record.record_id != entry.corrupted_record.record_id
    assert q.unit_drift_manifest_identity_matches(case.manifest)
    assert q.unit_drift_finding_identity_matches(finding)
    assert q.unit_drift_audit_report_identity_matches(case.audit_report)
    assert q.unit_drift_score_report_identity_matches(case.score)
    assert q.unit_drift_research_result_identity_matches(case.impact.clean)
    assert q.unit_drift_impact_identity_matches(case.impact)


def test_research_config_is_strict_and_day_level() -> None:
    key = reviewed_unit_drift_case().research_config.comparable_series_key
    config = q.UnitDriftResearchConfig(
        comparable_series_key=key,
        research_as_of_date=date(2024, 12, 31),
    )
    assert config.method == "aggregate_value_v0_1"
    with pytest.raises(ValidationError, match="Extra inputs"):
        q.UnitDriftResearchConfig.model_validate(
            {
                **config.model_dump(),
                "currency_conversion": True,
            }
        )
