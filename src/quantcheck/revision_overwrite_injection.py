"""Deterministic later-vintage-in-earlier-state fault injection."""

from __future__ import annotations

from collections.abc import Sequence

from quantcheck.hashing import (
    canonical_sha256,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
    revision_overwrite_fault_id,
    revision_overwrite_manifest_id,
    revision_overwrite_modified_record_id,
)
from quantcheck.revision_overwrite_contract import (
    REVISION_OVERWRITE_SELECTION_NAMESPACE,
    revision_overwrite_severity_profile,
    revision_overwrite_target_count,
)
from quantcheck.revision_overwrite_series import build_revision_history_units
from quantcheck.schemas import (
    DatasetSnapshot,
    FinancialFact,
    RevisionHistoryUnit,
    RevisionOverwriteInjectionConfig,
    RevisionOverwriteManifest,
    RevisionOverwriteManifestEntry,
    RevisionOverwriteMutation,
)

__all__ = [
    "NoEligibleRevisionOverwriteTargetsError",
    "RevisionOverwriteInjectionError",
    "inject_revision_overwrite",
]


class RevisionOverwriteInjectionError(ValueError):
    """Raised when inputs cannot support a valid historical-state corruption."""


class NoEligibleRevisionOverwriteTargetsError(RevisionOverwriteInjectionError):
    """Raised when no explicit adjacent history meets the severity contract."""


def _validate_clean_snapshot(snapshot: DatasetSnapshot) -> None:
    if not dataset_snapshot_identity_matches(snapshot):
        raise RevisionOverwriteInjectionError("clean snapshot identity does not match its content")
    if any(record.available_on > snapshot.as_of_date for record in snapshot.records):
        raise RevisionOverwriteInjectionError(
            "clean snapshot contains a record unavailable at its as_of_date"
        )


def _selection_digest(
    unit: RevisionHistoryUnit,
    config: RevisionOverwriteInjectionConfig,
) -> str:
    return canonical_sha256(
        {
            "namespace": REVISION_OVERWRITE_SELECTION_NAMESPACE,
            "spec_version": config.spec_version,
            "seed": config.seed,
            "eligibility_unit_id": unit.eligibility_unit_id,
        }
    )


def _corrupt_record(
    unit: RevisionHistoryUnit,
    config: RevisionOverwriteInjectionConfig,
) -> FinancialFact:
    historical = unit.historical_record
    later = unit.later_record
    assert later.accession_number is not None
    modified_id = revision_overwrite_modified_record_id(
        historical_record_id=historical.record_id,
        later_record_id=later.record_id,
        spec_version=config.spec_version,
        retained_available_on=historical.available_on,
        later_value=later.value,
        later_filed_on=later.filed_on,
        later_accession_number=later.accession_number,
        later_form=later.form,
        later_source_name=later.source.source_name,
        later_source_locator=later.source.source_locator,
        later_source_row_key=later.source.source_row_key,
    )
    fields = {name: getattr(historical, name) for name in FinancialFact.model_fields}
    fields.update(
        {
            "record_id": modified_id,
            "value": later.value,
            "filed_on": later.filed_on,
            "available_on": historical.available_on,
            "form": later.form,
            "accession_number": later.accession_number,
            "source": later.source,
        }
    )
    return FinancialFact(**fields)


def _mutation(
    unit: RevisionHistoryUnit,
    corrupted: FinancialFact,
) -> RevisionOverwriteMutation:
    historical = unit.historical_record
    later = unit.later_record
    assert historical.accession_number is not None
    assert later.accession_number is not None
    return RevisionOverwriteMutation(
        historical_record_id=historical.record_id,
        later_record_id=later.record_id,
        corrupted_record_id=corrupted.record_id,
        retained_available_on=historical.available_on,
        original_value=historical.value,
        corrupted_value=later.value,
        original_filed_on=historical.filed_on,
        corrupted_filed_on=later.filed_on,
        original_accession_number=historical.accession_number,
        corrupted_accession_number=later.accession_number,
        original_form=historical.form,
        corrupted_form=later.form,
        original_source_locator=historical.source.source_locator,
        corrupted_source_locator=later.source.source_locator,
        original_source_row_key=historical.source.source_row_key,
        corrupted_source_row_key=later.source.source_row_key,
    )


def inject_revision_overwrite(
    clean_snapshot: DatasetSnapshot,
    source_records: Sequence[FinancialFact],
    config: RevisionOverwriteInjectionConfig,
) -> tuple[DatasetSnapshot, RevisionOverwriteManifest]:
    """Substitute later value/provenance into an earlier historical state.

    ``source_records`` is the full explicit source history used only to prove
    adjacency and obtain the later reference. It is never mutated, and the
    legitimate later record is never removed from it. The returned corrupted
    snapshot retains the historical cutoff and contains only records visible
    in that state.
    """
    _validate_clean_snapshot(clean_snapshot)
    profile = revision_overwrite_severity_profile(config.severity)
    units = build_revision_history_units(
        source_records,
        clean_snapshot=clean_snapshot,
        minimum_relative_revision_size=profile.minimum_relative_revision_size,
    )
    if not units:
        raise NoEligibleRevisionOverwriteTargetsError(
            "no explicit adjacent history meets the Revision Overwrite eligibility rules"
        )

    ranked = sorted(
        (_selection_digest(unit, config), unit.eligibility_unit_id, unit) for unit in units
    )
    target_count = revision_overwrite_target_count(
        eligible_count=len(ranked),
        target_fraction=profile.target_fraction,
        max_targets=config.max_targets,
    )

    replacements: dict[str, FinancialFact] = {}
    entries: list[RevisionOverwriteManifestEntry] = []
    for target_rank, (selection_digest, _unit_id, unit) in enumerate(ranked[:target_count]):
        corrupted = _corrupt_record(unit, config)
        replacements[unit.historical_record.record_id] = corrupted
        entries.append(
            RevisionOverwriteManifestEntry(
                fault_id=revision_overwrite_fault_id(
                    clean_snapshot_id=clean_snapshot.snapshot_id,
                    eligibility_unit_id=unit.eligibility_unit_id,
                    corrupted_record_id=corrupted.record_id,
                    seed=config.seed,
                    spec_version=config.spec_version,
                ),
                severity=config.severity,
                target_rank=target_rank,
                selection_digest=selection_digest,
                eligibility_unit_id=unit.eligibility_unit_id,
                snapshot_as_of_date=clean_snapshot.as_of_date,
                corrupted_record=corrupted,
                mutation=_mutation(unit, corrupted),
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
    manifest_body: dict[str, object] = {
        "fault_type": config.fault_type,
        "fault_subtype": config.fault_subtype,
        "spec_version": config.spec_version,
        "dataset_name": clean_snapshot.dataset_name,
        "snapshot_as_of_date": clean_snapshot.as_of_date,
        "clean_snapshot_id": clean_snapshot.snapshot_id,
        "clean_snapshot_hash": canonical_sha256(clean_snapshot),
        "corrupted_snapshot_id": corrupted_snapshot.snapshot_id,
        "corrupted_snapshot_hash": canonical_sha256(corrupted_snapshot),
        "seed": config.seed,
        "severity": config.severity,
        "minimum_relative_revision_size": profile.minimum_relative_revision_size,
        "target_fraction": profile.target_fraction,
        "max_targets": config.max_targets,
        "eligible_units": units,
        "eligible_unit_count": len(units),
        "target_count": target_count,
        "entries": tuple(sorted(entries, key=lambda entry: entry.fault_id)),
    }
    manifest = RevisionOverwriteManifest.model_validate(
        {
            "manifest_id": revision_overwrite_manifest_id(manifest_body=manifest_body),
            **manifest_body,
        }
    )
    return corrupted_snapshot, manifest
