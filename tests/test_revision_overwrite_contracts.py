"""Strict contracts and configuration for Revision Overwrite."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.revision_overwrite_support import reviewed_revision_overwrite_case


@pytest.mark.parametrize(
    ("severity", "minimum", "fraction"),
    [
        ("low", Decimal("0.01"), Decimal("0.02")),
        ("medium", Decimal("0.05"), Decimal("0.05")),
        ("high", Decimal("0.20"), Decimal("0.10")),
    ],
)
def test_severity_profiles_are_exact(
    severity: q.RevisionOverwriteSeverity,
    minimum: Decimal,
    fraction: Decimal,
) -> None:
    profile = q.revision_overwrite_severity_profile(severity)
    assert profile.minimum_relative_revision_size == minimum
    assert profile.target_fraction == fraction


def test_injection_config_freezes_exact_labels() -> None:
    config = q.RevisionOverwriteInjectionConfig(severity="low", seed=0)
    assert config.fault_type == "revision_overwrite"
    assert config.fault_subtype == "later_vintage_in_earlier_state"
    assert config.spec_version == "quantcheck/revision-overwrite-later-vintage/v1"
    assert config.max_targets == 100


@pytest.mark.parametrize(
    "updates",
    [
        {"fault_type": "restatement"},
        {"fault_subtype": "generic_restatement"},
        {"spec_version": "0.1.0"},
        {"severity": "critical"},
        {"seed": -1},
        {"max_targets": 0},
        {"unknown": True},
    ],
)
def test_injection_config_rejects_unsupported_or_unknown_fields(
    updates: dict[str, object],
) -> None:
    fields: dict[str, object] = {"severity": "low", "seed": 0}
    fields.update(updates)
    with pytest.raises(ValidationError):
        q.RevisionOverwriteInjectionConfig.model_validate(fields)


def test_detector_config_is_strictly_empty() -> None:
    assert q.RevisionOverwriteDetectorConfig() == q.RevisionOverwriteDetectorConfig()
    with pytest.raises(ValidationError):
        q.RevisionOverwriteDetectorConfig.model_validate({"threshold": "1"})


def test_manifest_and_public_artifacts_round_trip_canonically() -> None:
    case = reviewed_revision_overwrite_case()
    for artifact in (
        case.manifest,
        case.audit_input,
        case.audit_report,
        case.score,
        case.research_impact,
    ):
        restored = type(artifact).model_validate(
            q.parse_canonical_json(q.canonical_json_bytes(artifact))
        )
        assert restored == artifact
        assert q.canonical_json_bytes(restored) == q.canonical_json_bytes(artifact)


def test_manifest_units_and_entries_are_canonically_ordered() -> None:
    case = reviewed_revision_overwrite_case()
    reversed_manifest = q.RevisionOverwriteManifest.model_validate(
        {
            name: (
                tuple(reversed(case.manifest.eligible_units))
                if name == "eligible_units"
                else tuple(reversed(case.manifest.entries))
                if name == "entries"
                else getattr(case.manifest, name)
            )
            for name in q.RevisionOverwriteManifest.model_fields
        }
    )
    assert reversed_manifest.eligible_units == case.manifest.eligible_units
    assert reversed_manifest.entries == case.manifest.entries


@pytest.mark.parametrize("private_identity", ["source_row", "revision_id"])
def test_manifest_validator_rejects_forged_private_revision_identity(
    private_identity: str,
) -> None:
    case = reviewed_revision_overwrite_case()
    unit = case.manifest.eligible_units[0]
    if private_identity == "source_row":
        forged_history = unit.historical_record.model_copy(
            update={
                "source": unit.historical_record.source.model_copy(
                    update={"source_row_key": "FORGED-LINEAGE#r1"}
                )
            }
        )
        forged_unit = unit.model_copy(update={"historical_record": forged_history})
    else:
        forged_unit = unit.model_copy(
            update={
                "historical_revision_id": q.revision_id(
                    lineage_id=unit.lineage_id,
                    sequence=unit.historical_sequence + 10,
                )
            }
        )
    body: dict[str, object] = {
        name: getattr(case.manifest, name)
        for name in q.RevisionOverwriteManifest.model_fields
        if name != "manifest_id"
    }
    body["eligible_units"] = (forged_unit,)
    forged_manifest = case.manifest.model_copy(
        update={
            "eligible_units": (forged_unit,),
            "manifest_id": q.revision_overwrite_manifest_id(manifest_body=body),
        }
    )
    with pytest.raises(q.RevisionOverwriteManifestIntegrityError):
        q.validate_revision_overwrite_manifest(forged_manifest)


@pytest.mark.parametrize(
    "updates",
    [
        {"prior_period_end": date(2023, 12, 31)},
        {"current_period_start": date(2024, 3, 31)},
        {"current_period_end": date(2024, 6, 29)},
        {"top_n": 0},
        {"period_type": "instant"},
        {"unknown": "x"},
    ],
)
def test_growth_config_rejects_invalid_semantics(updates: dict[str, object]) -> None:
    fields: dict[str, object] = {
        "concept_namespace": "us-gaap",
        "concept": "Revenues",
        "unit": "USD",
        "prior_period_start": date(2024, 1, 1),
        "prior_period_end": date(2024, 3, 31),
        "current_period_start": date(2024, 4, 1),
        "current_period_end": date(2024, 6, 30),
        "research_as_of_date": date(2024, 8, 31),
    }
    fields.update(updates)
    with pytest.raises(ValidationError):
        q.GrowthRankingConfig.model_validate(fields)


def test_revision_history_unit_rejects_forged_relative_size() -> None:
    unit = reviewed_revision_overwrite_case().manifest.eligible_units[0]
    fields = {name: getattr(unit, name) for name in q.RevisionHistoryUnit.model_fields}
    fields["relative_revision_size"] = Decimal("0.99")
    with pytest.raises(ValidationError, match="relative_revision_size"):
        q.RevisionHistoryUnit.model_validate(fields)
