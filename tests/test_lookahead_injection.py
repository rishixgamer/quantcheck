"""Deterministic Look-Ahead eligibility, selection, and mutation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

import quantcheck as q
from tests.lookahead_support import (
    REVIEWED_RESEARCH_DATE,
    REVIEWED_SOURCE_HORIZON,
    reviewed_lookahead_case,
)
from tests.support import financial_fact


def _snapshot(records: tuple[q.FinancialFact, ...], as_of_date: date) -> q.DatasetSnapshot:
    return q.DatasetSnapshot(
        snapshot_id=q.dataset_snapshot_id(
            dataset_name="focused", as_of_date=as_of_date, records=records
        ),
        dataset_name="focused",
        as_of_date=as_of_date,
        records=records,
    )


def _config(
    *,
    severity: q.LookAheadSeverity = "medium",
    seed: int = 42,
    research_as_of_date: date = REVIEWED_RESEARCH_DATE,
    max_targets: int = 100,
) -> q.LookAheadInjectionConfig:
    return q.LookAheadInjectionConfig(
        severity=severity,
        seed=seed,
        research_as_of_date=research_as_of_date,
        max_targets=max_targets,
    )


def test_eligibility_includes_period_end_boundary_and_excludes_availability_boundary() -> None:
    eligible = financial_fact(
        period_end=date(2024, 4, 14),
        period_start=date(2024, 1, 1),
        filed_on=date(2024, 4, 30),
        available_on=date(2024, 4, 30),
    )
    same_day_available = eligible.model_copy(
        update={"filed_on": date(2024, 4, 14), "available_on": date(2024, 4, 14)}
    )
    config = _config(research_as_of_date=date(2024, 4, 14))
    assert q.is_eligible_lookahead_target(eligible, config)
    assert not q.is_eligible_lookahead_target(same_day_available, config)


@pytest.mark.parametrize(
    ("severity", "filing_day", "expected"),
    [
        ("low", date(2024, 4, 7), True),
        ("low", date(2024, 4, 6), False),
        ("medium", date(2024, 4, 14), True),
        ("medium", date(2024, 4, 13), False),
        ("high", date(2024, 4, 30), True),
        ("high", date(2024, 4, 29), False),
    ],
)
def test_severity_minimum_lag_boundaries(
    severity: q.LookAheadSeverity, filing_day: date, expected: bool
) -> None:
    record = financial_fact(
        period_start=date(2023, 12, 1),
        period_end=date(2024, 3, 31),
        filed_on=filing_day,
        available_on=filing_day,
    )
    config = _config(severity=severity, research_as_of_date=date(2024, 4, 1))
    assert q.is_eligible_lookahead_target(record, config) is expected


@pytest.mark.parametrize(
    ("eligible", "fraction", "cap", "expected"),
    [
        (0, Decimal("0.05"), 100, 0),
        (1, Decimal("0.01"), 100, 1),
        (20, Decimal("0.05"), 100, 1),
        (21, Decimal("0.05"), 100, 2),
        (1000, Decimal("0.10"), 3, 3),
    ],
)
def test_target_count_minimum_ceiling_and_cap(
    eligible: int, fraction: Decimal, cap: int, expected: int
) -> None:
    assert (
        q.lookahead_target_count(
            eligible_count=eligible,
            target_fraction=fraction,
            max_targets=cap,
        )
        == expected
    )


def test_no_eligible_targets_is_rejected() -> None:
    clean = q.build_dataset_snapshot(
        q.generate_reviewed_fixture(),
        dataset_name="reviewed",
        as_of_date=REVIEWED_SOURCE_HORIZON,
    )
    with pytest.raises(q.NoEligibleLookAheadTargetsError):
        q.inject_lookahead(clean, _config(research_as_of_date=date(2024, 3, 30)))


def test_repeated_seed_produces_byte_identical_snapshot_and_manifest() -> None:
    first = reviewed_lookahead_case(seed=42)
    second = reviewed_lookahead_case(seed=42)
    assert q.canonical_json_bytes(first.corrupted) == q.canonical_json_bytes(second.corrupted)
    assert q.canonical_json_bytes(first.manifest) == q.canonical_json_bytes(second.manifest)


def test_documented_seed_can_change_selection_when_enough_units_exist() -> None:
    selected = {
        reviewed_lookahead_case(seed=seed).manifest.entries[0].original_record.record_id
        for seed in range(20)
    }
    assert len(selected) > 1


def test_multi_target_case_keeps_manifest_and_report_identities_canonical() -> None:
    clean = q.build_dataset_snapshot(
        q.generate_reviewed_fixture(),
        dataset_name="reviewed",
        as_of_date=date(2024, 8, 31),
    )
    config = _config(
        severity="high",
        research_as_of_date=date(2024, 6, 30),
    )
    corrupted, manifest = q.inject_lookahead(clean, config)
    report = q.detect_lookahead(q.sanitize_for_audit(corrupted))
    assert manifest.target_count == 2
    assert len(report.findings) == 2
    assert q.manifest_identity_matches(manifest)
    assert q.audit_report_identity_matches(report)
    assert q.score_lookahead(report, manifest).metrics.true_positive_faults == 2


def test_reversing_snapshot_records_does_not_change_any_logical_output() -> None:
    case = reviewed_lookahead_case()
    reversed_clean = q.DatasetSnapshot(
        snapshot_id=case.clean.snapshot_id,
        dataset_name=case.clean.dataset_name,
        as_of_date=case.clean.as_of_date,
        records=tuple(reversed(case.clean.records)),
    )
    corrupted, manifest = q.inject_lookahead(reversed_clean, case.config)
    assert q.canonical_json_bytes(corrupted) == q.canonical_json_bytes(case.corrupted)
    assert q.canonical_json_bytes(manifest) == q.canonical_json_bytes(case.manifest)


def test_only_record_id_and_available_on_change_for_selected_records() -> None:
    entry = reviewed_lookahead_case().manifest.entries[0]
    changed = {
        name
        for name in q.FinancialFact.model_fields
        if getattr(entry.original_record, name) != getattr(entry.corrupted_record, name)
    }
    assert changed == {"record_id", "available_on"}
    assert entry.corrupted_record.available_on == entry.original_record.period_end
    assert entry.corrupted_record.filed_on == entry.original_record.filed_on


def test_unaffected_records_are_preserved_logically_byte_for_byte() -> None:
    case = reviewed_lookahead_case()
    targeted = {entry.original_record.record_id for entry in case.manifest.entries}
    clean_unaffected = [record for record in case.clean.records if record.record_id not in targeted]
    corrupt_ids = {entry.corrupted_record.record_id for entry in case.manifest.entries}
    corrupted_unaffected = [
        record for record in case.corrupted.records if record.record_id not in corrupt_ids
    ]
    assert q.canonical_json_bytes(clean_unaffected) == q.canonical_json_bytes(corrupted_unaffected)


def test_injection_does_not_mutate_clean_snapshot() -> None:
    case = reviewed_lookahead_case()
    before = q.canonical_json_bytes(case.clean)
    q.inject_lookahead(case.clean, case.config)
    assert q.canonical_json_bytes(case.clean) == before


def test_invalid_snapshot_identity_and_future_research_cutoff_are_rejected() -> None:
    case = reviewed_lookahead_case()
    forged = case.clean.model_copy(update={"snapshot_id": "snap_0000000000000000"})
    with pytest.raises(q.LookAheadInjectionError, match="identity"):
        q.inject_lookahead(forged, case.config)
    with pytest.raises(q.LookAheadInjectionError, match="must not follow"):
        q.inject_lookahead(
            case.clean,
            _config(research_as_of_date=case.clean.as_of_date.replace(year=2025)),
        )


def test_preexisting_available_before_filing_violation_is_rejected() -> None:
    record = financial_fact(
        filed_on=date(2024, 4, 30),
        available_on=date(2024, 4, 1),
    )
    clean = _snapshot((record,), date(2024, 4, 30))
    with pytest.raises(q.LookAheadInjectionError, match="already contains"):
        q.inject_lookahead(clean, _config())


def test_delayed_availability_semantics_are_ineligible_not_guessed() -> None:
    record = financial_fact(
        filed_on=date(2024, 4, 15),
        available_on=date(2024, 4, 16),
    )
    clean = _snapshot((record,), date(2024, 4, 30))
    with pytest.raises(q.NoEligibleLookAheadTargetsError):
        q.inject_lookahead(clean, _config())


def test_irrelevant_ineligible_record_does_not_change_selected_target_or_mutation() -> None:
    case = reviewed_lookahead_case()
    extra = financial_fact(
        record_id="rec_ffffffffffffffff",
        period_start=date(2024, 1, 1),
        period_end=REVIEWED_RESEARCH_DATE,
        filed_on=REVIEWED_RESEARCH_DATE,
        available_on=REVIEWED_RESEARCH_DATE,
    )
    expanded = _snapshot(case.clean.records + (extra,), case.clean.as_of_date)
    config = q.LookAheadInjectionConfig(
        severity=case.config.severity,
        seed=case.config.seed,
        research_as_of_date=case.config.research_as_of_date,
    )
    _corrupted, manifest = q.inject_lookahead(expanded, config)
    baseline_entry = case.manifest.entries[0]
    expanded_entry = manifest.entries[0]
    assert expanded_entry.original_record.record_id == baseline_entry.original_record.record_id
    assert expanded_entry.selection_digest == baseline_entry.selection_digest
    assert expanded_entry.corrupted_record.record_id == baseline_entry.corrupted_record.record_id


def test_modified_record_identity_is_deterministic_and_mutation_sensitive() -> None:
    entry = reviewed_lookahead_case().manifest.entries[0]
    identifier = q.lookahead_modified_record_id(
        original_record_id=entry.original_record.record_id,
        spec_version=entry.spec_version,
        true_available_on=entry.original_record.available_on,
        corrupted_available_on=entry.corrupted_record.available_on,
    )
    changed = q.lookahead_modified_record_id(
        original_record_id=entry.original_record.record_id,
        spec_version=entry.spec_version,
        true_available_on=entry.original_record.available_on,
        corrupted_available_on=date(2024, 3, 30),
    )
    assert identifier == entry.corrupted_record.record_id
    assert identifier != changed
