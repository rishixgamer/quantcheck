"""Strict Duplicate Observations configurations, artifacts, and identity contracts."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.duplicate_support import duplicate_record, reviewed_duplicate_case


@pytest.mark.parametrize(
    ("severity", "fraction"),
    [
        ("low", Decimal("0.01")),
        ("medium", Decimal("0.05")),
        ("high", Decimal("0.15")),
    ],
)
def test_severity_profiles_are_exact(severity: q.DuplicateSeverity, fraction: Decimal) -> None:
    profile = q.duplicate_severity_profile(severity)
    assert profile.target_fraction == fraction


def test_public_finding_severity_is_fixed_medium() -> None:
    assert q.DUPLICATE_FINDING_SEVERITY == "medium"


@pytest.mark.parametrize(
    ("eligible_count", "fraction", "cap", "expected"),
    [
        (0, Decimal("0.05"), 100, 0),
        (1, Decimal("0.01"), 100, 1),
        (21, Decimal("0.15"), 100, 4),
        (24, Decimal("0.05"), 100, 2),
        (24, Decimal("0.05"), 1, 1),
    ],
)
def test_target_count_uses_decimal_ceiling_minimum_one_and_cap(
    eligible_count: int, fraction: Decimal, cap: int, expected: int
) -> None:
    assert (
        q.duplicate_target_count(
            eligible_count=eligible_count, target_fraction=fraction, max_targets=cap
        )
        == expected
    )


@pytest.mark.parametrize("severity", ["tiny", "critical", "MEDIUM"])
def test_invalid_severity_is_rejected(severity: str) -> None:
    with pytest.raises(ValidationError):
        q.DuplicateInjectionConfig.model_validate({"severity": severity, "seed": 1})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("fault_type", "unit_drift"),
        ("fault_subtype", "fuzzy_copy"),
        ("spec_version", "v2"),
    ],
)
def test_unsupported_fault_contract_labels_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        q.DuplicateInjectionConfig.model_validate({"severity": "low", "seed": 1, field: value})


def test_injection_config_is_strict_frozen_and_rejects_bad_seed_and_cap() -> None:
    config = q.DuplicateInjectionConfig(severity="low", seed=1)
    with pytest.raises(ValidationError):
        config.seed = 2
    with pytest.raises(ValidationError, match="Extra inputs"):
        q.DuplicateInjectionConfig.model_validate({"severity": "low", "seed": 1, "copy_ordinal": 2})
    with pytest.raises(ValidationError, match="boolean"):
        q.DuplicateInjectionConfig(severity="low", seed=True)
    with pytest.raises(ValidationError, match="positive"):
        q.DuplicateInjectionConfig(severity="low", seed=1, max_targets=0)


def test_fingerprint_excludes_record_id_form_and_entity_name() -> None:
    original = duplicate_record("row-a")
    copy = duplicate_record("row-a").model_copy(
        update={
            "record_id": q.source_record_id(
                source_name=original.source.source_name,
                source_locator=original.source.source_locator,
                source_row_key="row-a-copy",
            )
        }
    )
    fp_original = q.duplicate_fingerprint(original)
    fp_copy = q.duplicate_fingerprint(copy)
    assert fp_original == fp_copy
    assert q.duplicate_fingerprint_hash(fp_original) == q.duplicate_fingerprint_hash(fp_copy)

    different_form = original.model_copy(update={"form": "10-K"})
    assert q.duplicate_fingerprint(different_form) == fp_original


def test_fingerprint_treats_canonically_equal_decimals_as_identical() -> None:
    a = duplicate_record("row-a", value="100")
    b = duplicate_record("row-b", value="100.00")
    assert q.duplicate_fingerprint(a).value == q.duplicate_fingerprint(b).value
    fp_a = q.duplicate_fingerprint(a).model_copy(update={"source_name": "s", "source_locator": "l"})
    fp_b = q.duplicate_fingerprint(b).model_copy(update={"source_name": "s", "source_locator": "l"})
    assert q.duplicate_fingerprint_hash(fp_a) == q.duplicate_fingerprint_hash(fp_b)


def test_fingerprint_enforces_period_shape() -> None:
    with pytest.raises(ValidationError, match="instant"):
        q.DuplicateFingerprint(
            entity_id="E1",
            concept_namespace="us-gaap",
            concept="Assets",
            value=Decimal("1"),
            unit="USD",
            period_type="instant",
            period_start=q.parse_canonical_date("2024-01-01"),
            period_end=q.parse_canonical_date("2024-03-31"),
            filed_on=q.parse_canonical_date("2024-04-01"),
            available_on=q.parse_canonical_date("2024-04-01"),
            source_name="s",
            source_locator="l",
        )
    with pytest.raises(ValidationError, match="duration"):
        q.DuplicateFingerprint(
            entity_id="E1",
            concept_namespace="us-gaap",
            concept="Revenues",
            value=Decimal("1"),
            unit="USD",
            period_type="duration",
            period_end=q.parse_canonical_date("2024-03-31"),
            filed_on=q.parse_canonical_date("2024-04-01"),
            available_on=q.parse_canonical_date("2024-04-01"),
            source_name="s",
            source_locator="l",
        )


def test_mutation_rejects_equal_ids_and_multi_copy_ordinal() -> None:
    with pytest.raises(ValidationError, match="distinct"):
        q.DuplicateMutation(
            original_record_id="rec_0000000000000000",
            created_record_id="rec_0000000000000000",
            copy_ordinal=1,
        )
    with pytest.raises(ValidationError, match="exactly one copy"):
        q.DuplicateMutation(
            original_record_id="rec_0000000000000000",
            created_record_id="rec_0000000000000001",
            copy_ordinal=2,
        )


def test_finding_evidence_union_accepts_duplicate_evidence_with_matching_ids() -> None:
    case = reviewed_duplicate_case()
    finding = next(
        f
        for f in case.audit_report.findings
        if isinstance(f.evidence, q.DuplicateEvidence) and f.evidence.group_size == 2
    )
    assert isinstance(finding.evidence, q.DuplicateEvidence)
    assert finding.affected_record_ids == finding.evidence.record_ids
    with pytest.raises(ValidationError, match="must equal the evidence record_ids"):
        q.Finding.model_validate(
            {
                **{name: getattr(finding, name) for name in q.Finding.model_fields},
                "affected_record_ids": (finding.affected_record_ids[0],),
                "finding_id": finding.finding_id,
            }
        )


def test_all_duplicate_artifacts_round_trip_with_identical_canonical_bytes() -> None:
    case = reviewed_duplicate_case()
    models: tuple[q.CanonicalModel, ...] = (
        case.config,
        case.manifest.entries[0].mutation,
        case.manifest.entries[0],
        case.manifest,
        case.audit_report.findings[0].evidence,
        case.audit_report.findings[0],
        case.audit_report,
        case.score,
        case.record_count_impact.clean,
        case.record_count_impact,
    )
    for model in models:
        restored = type(model).model_validate(q.parse_canonical_json(q.canonical_json_bytes(model)))
        assert restored == model
        assert q.canonical_json_bytes(restored) == q.canonical_json_bytes(model)


def test_all_duplicate_artifact_identities_verify_and_use_non_role_record_prefix() -> None:
    case = reviewed_duplicate_case()
    entry = case.manifest.entries[0]
    assert entry.original_record.record_id.startswith("rec_")
    assert entry.created_record.record_id.startswith("rec_")
    assert entry.original_record.record_id != entry.created_record.record_id
    assert q.duplicate_manifest_identity_matches(case.manifest)
    assert q.duplicate_audit_report_identity_matches(case.audit_report)
    assert q.duplicate_score_report_identity_matches(case.score)
    assert q.duplicate_research_result_identity_matches(case.record_count_impact.clean)
    assert q.duplicate_impact_identity_matches(case.record_count_impact)
    for finding in case.audit_report.findings:
        assert q.duplicate_finding_identity_matches(finding)
