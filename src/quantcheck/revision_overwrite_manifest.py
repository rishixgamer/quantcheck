"""Private Revision Overwrite manifest integrity validation."""

from __future__ import annotations

from quantcheck.hashing import (
    canonical_sha256,
    revision_history_unit_id,
    revision_id,
    revision_overwrite_fault_id,
    revision_overwrite_manifest_id,
    revision_overwrite_modified_record_id,
)
from quantcheck.point_in_time import parse_declared_revision_lineage
from quantcheck.revision_overwrite_contract import (
    REVISION_OVERWRITE_SELECTION_NAMESPACE,
    revision_overwrite_severity_profile,
    revision_overwrite_target_count,
)
from quantcheck.revision_overwrite_series import revision_history_unit_body
from quantcheck.schemas import FinancialFact, RevisionOverwriteManifest

__all__ = [
    "RevisionOverwriteManifestIntegrityError",
    "revision_overwrite_manifest_identity_matches",
    "validate_revision_overwrite_manifest",
]


class RevisionOverwriteManifestIntegrityError(ValueError):
    """Raised when private Revision Overwrite truth is inconsistent or forged."""


def _manifest_body(manifest: RevisionOverwriteManifest) -> dict[str, object]:
    return {
        name: getattr(manifest, name)
        for name in RevisionOverwriteManifest.model_fields
        if name != "manifest_id"
    }


def revision_overwrite_manifest_identity_matches(
    manifest: RevisionOverwriteManifest,
) -> bool:
    return manifest.manifest_id == revision_overwrite_manifest_id(
        manifest_body=_manifest_body(manifest)
    )


def _selection_digest(unit_id: str, manifest: RevisionOverwriteManifest) -> str:
    return canonical_sha256(
        {
            "namespace": REVISION_OVERWRITE_SELECTION_NAMESPACE,
            "spec_version": manifest.spec_version,
            "seed": manifest.seed,
            "eligibility_unit_id": unit_id,
        }
    )


def _expected_corrupted_record(
    unit: object,
    spec_version: str,
) -> FinancialFact:
    from quantcheck.schemas import RevisionHistoryUnit

    assert isinstance(unit, RevisionHistoryUnit)
    historical = unit.historical_record
    later = unit.later_record
    assert later.accession_number is not None
    modified_id = revision_overwrite_modified_record_id(
        historical_record_id=historical.record_id,
        later_record_id=later.record_id,
        spec_version=spec_version,
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


def validate_revision_overwrite_manifest(manifest: RevisionOverwriteManifest) -> None:
    """Recompute profile, history identities, selection, corruption, and faults."""
    if not revision_overwrite_manifest_identity_matches(manifest):
        raise RevisionOverwriteManifestIntegrityError(
            "manifest identity does not match its content"
        )

    profile = revision_overwrite_severity_profile(manifest.severity)
    if (
        manifest.minimum_relative_revision_size != profile.minimum_relative_revision_size
        or manifest.target_fraction != profile.target_fraction
    ):
        raise RevisionOverwriteManifestIntegrityError("manifest severity profile is inconsistent")
    expected_count = revision_overwrite_target_count(
        eligible_count=manifest.eligible_unit_count,
        target_fraction=manifest.target_fraction,
        max_targets=manifest.max_targets,
    )
    if manifest.target_count != expected_count:
        raise RevisionOverwriteManifestIntegrityError("manifest target_count is inconsistent")

    units_by_id = {unit.eligibility_unit_id: unit for unit in manifest.eligible_units}
    for unit in manifest.eligible_units:
        historical_lineage = parse_declared_revision_lineage(
            unit.historical_record.source.source_row_key
        )
        later_lineage = parse_declared_revision_lineage(unit.later_record.source.source_row_key)
        if (
            historical_lineage is None
            or later_lineage is None
            or historical_lineage.lineage_id != unit.lineage_id
            or later_lineage.lineage_id != unit.lineage_id
            or historical_lineage.sequence != unit.historical_sequence
            or later_lineage.sequence != unit.later_sequence
        ):
            raise RevisionOverwriteManifestIntegrityError(
                "history unit source-declared lineage is inconsistent"
            )
        expected_historical_revision = revision_id(
            lineage_id=unit.lineage_id, sequence=unit.historical_sequence
        )
        expected_later_revision = revision_id(
            lineage_id=unit.lineage_id, sequence=unit.later_sequence
        )
        if (
            unit.historical_revision_id != expected_historical_revision
            or unit.later_revision_id != expected_later_revision
        ):
            raise RevisionOverwriteManifestIntegrityError(
                "history unit revision identity is inconsistent"
            )
        body = revision_history_unit_body(
            lineage_id=unit.lineage_id,
            economic_key=unit.economic_fact_key,
            snapshot_as_of_date=unit.snapshot_as_of_date,
            historical_sequence=unit.historical_sequence,
            later_sequence=unit.later_sequence,
            historical_revision_id=unit.historical_revision_id,
            later_revision_id=unit.later_revision_id,
            historical_record=unit.historical_record,
            later_record=unit.later_record,
            relative_revision_size=unit.relative_revision_size,
        )
        if unit.eligibility_unit_id != revision_history_unit_id(unit_body=body):
            raise RevisionOverwriteManifestIntegrityError("history unit identity is inconsistent")

    ranked = sorted((_selection_digest(unit_id, manifest), unit_id) for unit_id in units_by_id)
    selected_by_rank = sorted(manifest.entries, key=lambda entry: entry.target_rank)
    if [entry.eligibility_unit_id for entry in selected_by_rank] != [
        unit_id for _digest, unit_id in ranked[: manifest.target_count]
    ]:
        raise RevisionOverwriteManifestIntegrityError(
            "manifest selected targets do not match SHA-256 rank"
        )

    for entry in manifest.entries:
        unit = units_by_id[entry.eligibility_unit_id]
        if entry.selection_digest != _selection_digest(unit.eligibility_unit_id, manifest):
            raise RevisionOverwriteManifestIntegrityError(
                "manifest selection digest is inconsistent"
            )
        expected_corrupted = _expected_corrupted_record(unit, manifest.spec_version)
        if entry.corrupted_record != expected_corrupted:
            raise RevisionOverwriteManifestIntegrityError(
                "corrupted record does not implement the exact later-vintage substitution"
            )
        historical = unit.historical_record
        later = unit.later_record
        mutation = entry.mutation
        if (
            mutation.historical_record_id != historical.record_id
            or mutation.later_record_id != later.record_id
            or mutation.retained_available_on != historical.available_on
            or mutation.original_value != historical.value
            or mutation.corrupted_value != later.value
            or mutation.original_filed_on != historical.filed_on
            or mutation.corrupted_filed_on != later.filed_on
            or mutation.original_accession_number != historical.accession_number
            or mutation.corrupted_accession_number != later.accession_number
            or mutation.original_form != historical.form
            or mutation.corrupted_form != later.form
            or mutation.original_source_locator != historical.source.source_locator
            or mutation.corrupted_source_locator != later.source.source_locator
            or mutation.original_source_row_key != historical.source.source_row_key
            or mutation.corrupted_source_row_key != later.source.source_row_key
        ):
            raise RevisionOverwriteManifestIntegrityError(
                "manifest mutation does not match historical/reference roles"
            )
        expected_fault = revision_overwrite_fault_id(
            clean_snapshot_id=manifest.clean_snapshot_id,
            eligibility_unit_id=unit.eligibility_unit_id,
            corrupted_record_id=entry.corrupted_record.record_id,
            seed=manifest.seed,
            spec_version=manifest.spec_version,
        )
        if entry.fault_id != expected_fault:
            raise RevisionOverwriteManifestIntegrityError("fault identity is inconsistent")
