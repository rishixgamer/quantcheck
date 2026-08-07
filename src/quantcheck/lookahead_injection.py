"""Deterministic period-end Look-Ahead fault injection.

The public detector never imports this module.  It returns a corrupted
snapshot plus the private answer-key manifest as two distinct artifacts.
"""

from __future__ import annotations

from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
    fault_manifest_id,
    lookahead_fault_id,
    lookahead_modified_record_id,
)
from quantcheck.lookahead_contract import (
    LOOKAHEAD_SELECTION_NAMESPACE,
    is_eligible_lookahead_target,
    lookahead_severity_profile,
    lookahead_target_count,
)
from quantcheck.schemas import (
    DatasetSnapshot,
    FaultManifest,
    FaultManifestEntry,
    FinancialFact,
    LookAheadInjectionConfig,
    LookAheadMutation,
)

__all__ = [
    "LookAheadInjectionError",
    "NoEligibleLookAheadTargetsError",
    "inject_lookahead",
]


class LookAheadInjectionError(ValueError):
    """Raised when an input is not a valid clean Look-Ahead source snapshot."""


class NoEligibleLookAheadTargetsError(LookAheadInjectionError):
    """Raised when the configured clean snapshot has no supported targets."""


def _validate_clean_snapshot(
    snapshot: DatasetSnapshot,
    config: LookAheadInjectionConfig,
) -> None:
    if not dataset_snapshot_identity_matches(snapshot):
        raise LookAheadInjectionError("clean snapshot identity does not match its content")
    if config.research_as_of_date > snapshot.as_of_date:
        raise LookAheadInjectionError(
            "research_as_of_date must not follow the clean snapshot as_of_date"
        )
    for record in snapshot.records:
        if record.available_on > snapshot.as_of_date:
            raise LookAheadInjectionError(
                "clean snapshot contains a record unavailable at its as_of_date"
            )
        if record.available_on < record.filed_on:
            raise LookAheadInjectionError(
                "clean snapshot already contains an available-before-filing violation"
            )


def _selection_digest(record: FinancialFact, config: LookAheadInjectionConfig) -> str:
    return canonical_sha256(
        {
            "namespace": LOOKAHEAD_SELECTION_NAMESPACE,
            "spec_version": config.spec_version,
            "seed": config.seed,
            "eligibility_unit_id": record.record_id,
        }
    )


def _corrupt_record(record: FinancialFact, config: LookAheadInjectionConfig) -> FinancialFact:
    modified_id = lookahead_modified_record_id(
        original_record_id=record.record_id,
        spec_version=config.spec_version,
        true_available_on=record.available_on,
        corrupted_available_on=record.period_end,
    )
    fields = {name: getattr(record, name) for name in FinancialFact.model_fields}
    fields["record_id"] = modified_id
    fields["available_on"] = record.period_end
    return FinancialFact(**fields)


def inject_lookahead(
    clean_snapshot: DatasetSnapshot,
    config: LookAheadInjectionConfig,
) -> tuple[DatasetSnapshot, FaultManifest]:
    """Inject deterministic Look-Ahead faults without mutating the clean input.

    Eligible records are ranked by the full SHA-256 selection digest and then
    stable record ID.  Selected records are replaced by derived ``mod_``
    records whose only semantic change is ``available_on = period_end``.  The
    derived ID keeps the normal ``rec_`` prefix so it does not reveal a hidden
    injected-record role at the audit boundary.
    """
    _validate_clean_snapshot(clean_snapshot, config)
    profile = lookahead_severity_profile(config.severity)
    eligible = [
        record for record in clean_snapshot.records if is_eligible_lookahead_target(record, config)
    ]
    if not eligible:
        raise NoEligibleLookAheadTargetsError(
            "no clean records satisfy the configured Look-Ahead eligibility rule"
        )

    ranked = sorted(
        ((_selection_digest(record, config), record.record_id, record) for record in eligible),
        key=lambda item: (item[0], item[1]),
    )
    target_count = lookahead_target_count(
        eligible_count=len(ranked),
        target_fraction=profile.target_fraction,
        max_targets=config.max_targets,
    )
    selected = ranked[:target_count]

    replacements: dict[str, FinancialFact] = {}
    entries: list[FaultManifestEntry] = []
    for target_rank, (selection_digest, _record_id, original) in enumerate(selected):
        corrupted = _corrupt_record(original, config)
        replacements[original.record_id] = corrupted
        entries.append(
            FaultManifestEntry(
                fault_id=lookahead_fault_id(
                    clean_snapshot_id=clean_snapshot.snapshot_id,
                    original_record_id=original.record_id,
                    corrupted_record_id=corrupted.record_id,
                    seed=config.seed,
                    spec_version=config.spec_version,
                ),
                severity=config.severity,
                target_rank=target_rank,
                selection_digest=selection_digest,
                eligibility_unit_id=original.record_id,
                research_as_of_date=config.research_as_of_date,
                original_record=original,
                corrupted_record=corrupted,
                mutation=LookAheadMutation(
                    original_date=original.available_on,
                    corrupted_date=corrupted.available_on,
                ),
            )
        )

    corrupted_records = tuple(
        replacements.get(record.record_id, record) for record in clean_snapshot.records
    )
    corrupted_snapshot = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name=clean_snapshot.dataset_name,
            as_of_date=clean_snapshot.as_of_date,
            records=corrupted_records,
        ),
        dataset_name=clean_snapshot.dataset_name,
        as_of_date=clean_snapshot.as_of_date,
        records=corrupted_records,
    )

    manifest_fields: dict[str, object] = {
        "fault_type": "lookahead_timestamp",
        "fault_subtype": "period_end_substitution",
        "spec_version": config.spec_version,
        "dataset_name": clean_snapshot.dataset_name,
        "snapshot_as_of_date": clean_snapshot.as_of_date,
        "research_as_of_date": config.research_as_of_date,
        "clean_snapshot_id": clean_snapshot.snapshot_id,
        "clean_snapshot_hash": canonical_sha256(clean_snapshot),
        "corrupted_snapshot_id": corrupted_snapshot.snapshot_id,
        "corrupted_snapshot_hash": canonical_sha256(corrupted_snapshot),
        "seed": config.seed,
        "severity": config.severity,
        "target_fraction": profile.target_fraction,
        "minimum_lag_days": profile.minimum_lag_days,
        "max_targets": config.max_targets,
        "eligible_record_ids": tuple(record.record_id for record in eligible),
        "eligible_record_count": len(eligible),
        "target_count": target_count,
        "entries": tuple(sorted(entries, key=lambda entry: entry.fault_id)),
    }
    manifest = FaultManifest.model_validate(
        {
            "manifest_id": fault_manifest_id(manifest_body=manifest_fields),
            **manifest_fields,
        }
    )
    return corrupted_snapshot, manifest
