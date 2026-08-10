"""Design-partner shadow-mode contracts, privacy, and reporting behavior."""

from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from quantcheck.external_dataset_audit import audit_external_rows
from quantcheck.external_dataset_contract import ExternalDatasetAuditReportV2
from quantcheck.external_dataset_shadow import (
    ShadowModeError,
    build_adjudication_input_template,
    build_pilot_report,
    build_rerun_comparison,
    build_reviewer_notes,
    build_reviewer_notes_input_template,
    build_shadow_finding_bundle,
    finalize_adjudication_export,
    main,
    prepare_shadow_package,
)
from quantcheck.external_dataset_shadow_contract import (
    AdjudicationDispositionV1,
    AdjudicationEntryInputV1,
    AdjudicationExportV1,
    AdjudicationInputV1,
    DecisionImpactV1,
    PilotReportV1,
    ReviewerNoteInputV1,
    ReviewerNotesInputV1,
    ShadowFindingBundleV1,
    ShadowFindingV1,
    adjudication_export_identity_matches,
    finding_bundle_identity_matches,
    pilot_report_identity_matches,
    rerun_comparison_identity_matches,
    reviewer_notes_identity_matches,
)
from quantcheck.hashing import canonical_sha256
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json
from tests.external_dataset_support import mapping, policy, row


def _report(
    *, group_count: int = 6, as_of_date: date = date(2024, 12, 31)
) -> ExternalDatasetAuditReportV2:
    rows: list[dict[str, object]] = []
    for index in range(group_count):
        rows.extend(
            (
                row(
                    f"source-{index}-a",
                    concept=f"PilotConcept{index}",
                    amount=100 + index,
                ),
                row(
                    f"source-{index}-b",
                    concept=f"PilotConcept{index}",
                    amount=100 + index,
                ),
            )
        )
    artifacts = audit_external_rows(
        rows,
        mapping=mapping(),
        as_of_date=as_of_date,
        policy=policy(enabled_detectors=("duplicate_observation",)),
    )
    assert artifacts.public_report.finding_count == group_count
    return artifacts.public_report


def _bundle(
    *,
    version: str = "0.2.0-design-partner",
    revision: str = "a" * 40,
    runtime_ns: int = 12_345_678,
    report: ExternalDatasetAuditReportV2 | None = None,
) -> ShadowFindingBundleV1:
    return build_shadow_finding_bundle(
        dataset_key="design-partner-dataset-001",
        quantcheck_version=version,
        code_revision=revision,
        runtime_ns=runtime_ns,
        reports=(_report() if report is None else report,),
    )


def _completed_adjudication(bundle: ShadowFindingBundleV1) -> AdjudicationInputV1:
    template = build_adjudication_input_template(bundle)
    dispositions: tuple[tuple[AdjudicationDispositionV1, DecisionImpactV1, int], ...] = (
        ("confirmed_issue", "customer_independently_confirmed", 90),
        ("legitimate_data_condition", "reviewed_not_confirmed", 40),
        ("accepted_exception", "reviewed_not_confirmed", 30),
        ("duplicate_correlated_signal", "reviewed_not_confirmed", 20),
        ("unresolved", "not_assessed", 10),
    )
    entries: list[AdjudicationEntryInputV1] = []
    for index, original in enumerate(template.entries):
        if index < len(dispositions):
            disposition, decision_impact, review_seconds = dispositions[index]
            entries.append(
                AdjudicationEntryInputV1(
                    finding_id=original.finding_id,
                    finding_content_hash=original.finding_content_hash,
                    investigation_status="investigated",
                    disposition=disposition,
                    decision_impact=decision_impact,
                    researcher_review_seconds=review_seconds,
                )
            )
        else:
            entries.append(original)
    return AdjudicationInputV1(
        finding_bundle_id=template.finding_bundle_id,
        finding_bundle_hash=template.finding_bundle_hash,
        entries=tuple(entries),
    )


def test_bundle_binds_versioned_reproducible_identity_and_preserves_evidence() -> None:
    report = _report(group_count=2)
    report_before = canonical_json_bytes(report)
    first = build_shadow_finding_bundle(
        dataset_key="design-partner-dataset-001",
        quantcheck_version="0.2.0-design-partner",
        code_revision="a" * 40,
        runtime_ns=100,
        reports=(report,),
    )
    repeated = build_shadow_finding_bundle(
        dataset_key="design-partner-dataset-001",
        quantcheck_version="0.2.0-design-partner",
        code_revision="a" * 40,
        runtime_ns=200,
        reports=(report,),
    )

    assert finding_bundle_identity_matches(first)
    assert first.shadow_audit_id == repeated.shadow_audit_id
    assert first.audit_context_id == repeated.audit_context_id
    assert first.finding_bundle_id != repeated.finding_bundle_id
    assert first.runtime_ns == 100
    assert first.records_audited == 4
    assert first.finding_count == 2
    assert canonical_json_bytes(report) == report_before
    assert tuple(item.finding for item in first.findings) == tuple(
        finding for run in report.detector_runs for finding in run.report.findings
    )
    assert first.source_modified is False
    assert first.production_blocking_used is False


def test_bundle_refuses_report_identity_drift_and_finding_hash_drift() -> None:
    report = _report(group_count=1)
    drifted = report.model_copy(update={"finding_count": 0})
    with pytest.raises(ShadowModeError, match="identity mismatch"):
        build_shadow_finding_bundle(
            dataset_key="design-partner-dataset-001",
            quantcheck_version="0.2.0",
            code_revision="a" * 40,
            runtime_ns=100,
            reports=(drifted,),
        )

    bundle = build_shadow_finding_bundle(
        dataset_key="design-partner-dataset-001",
        quantcheck_version="0.2.0",
        code_revision="a" * 40,
        runtime_ns=100,
        reports=(report,),
    )
    original = bundle.findings[0]
    changed_finding = original.finding.model_copy(update={"explanation": "changed after audit"})
    with pytest.raises(ValidationError, match="finding content hash mismatch"):
        ShadowFindingV1(
            **{
                **original.model_dump(mode="python", exclude={"finding"}),
                "finding": changed_finding,
            }
        )

    changed_item = ShadowFindingV1(
        **{
            **original.model_dump(mode="python", exclude={"finding", "finding_content_hash"}),
            "finding": changed_finding,
            "finding_content_hash": canonical_sha256(changed_finding),
        }
    )
    bundle_document = bundle.model_dump(mode="python")
    bundle_document["findings"] = (changed_item,)
    with pytest.raises(ValidationError, match="differs from source report"):
        ShadowFindingBundleV1.model_validate(bundle_document)


def test_adjudication_is_complete_sanitized_and_separate_from_finding_evidence() -> None:
    bundle = _bundle()
    template = build_adjudication_input_template(bundle)
    exported = finalize_adjudication_export(bundle, template)
    payload = canonical_json_bytes(exported)

    assert adjudication_export_identity_matches(exported)
    assert len(exported.entries) == bundle.finding_count
    assert all(entry.disposition == "unresolved" for entry in exported.entries)
    assert exported.finding_evidence_included is False
    assert exported.reviewer_notes_included is False
    for prohibited in (
        b'"evidence"',
        b'"explanation"',
        b'"affected_record_ids"',
        b"customer-financial-facts-v1",
        b"PilotConcept0",
    ):
        assert prohibited not in payload

    incomplete = AdjudicationInputV1(
        finding_bundle_id=template.finding_bundle_id,
        finding_bundle_hash=template.finding_bundle_hash,
        entries=template.entries[:-1],
    )
    with pytest.raises(ShadowModeError, match="cover every finding"):
        finalize_adjudication_export(bundle, incomplete)


def test_adjudication_state_requires_explicit_customer_confirmation() -> None:
    bundle = _bundle()
    template = build_adjudication_input_template(bundle)
    first = template.entries[0]
    with pytest.raises(ValidationError, match="not-started review"):
        AdjudicationEntryInputV1(
            finding_id=first.finding_id,
            finding_content_hash=first.finding_content_hash,
            investigation_status="not_started",
            disposition="confirmed_issue",
            decision_impact="not_assessed",
            researcher_review_seconds=1,
        )
    with pytest.raises(ValidationError, match="only for a confirmed issue"):
        AdjudicationEntryInputV1(
            finding_id=first.finding_id,
            finding_content_hash=first.finding_content_hash,
            investigation_status="investigated",
            disposition="legitimate_data_condition",
            decision_impact="customer_independently_confirmed",
            researcher_review_seconds=1,
        )


def test_reviewer_notes_are_private_separate_and_excluded_from_metrics() -> None:
    bundle = _bundle()
    bundle_before = canonical_json_bytes(bundle)
    template = build_reviewer_notes_input_template(bundle)
    note_input = ReviewerNotesInputV1(
        finding_bundle_id=template.finding_bundle_id,
        finding_bundle_hash=template.finding_bundle_hash,
        notes=(
            ReviewerNoteInputV1(
                finding_id=bundle.findings[0].finding.finding_id,
                note_revision=1,
                reviewer_role="customer-researcher",
                note="Private customer context\nkept outside immutable finding evidence.",
            ),
        ),
    )
    notes = build_reviewer_notes(bundle, note_input)
    adjudication = finalize_adjudication_export(
        bundle,
        build_adjudication_input_template(bundle),
    )
    pilot = build_pilot_report(
        pilot_key="pilot-001",
        bundles=(bundle,),
        adjudication_exports=(adjudication,),
    )

    assert reviewer_notes_identity_matches(notes)
    assert notes.private is True
    assert notes.included_in_pilot_metrics is False
    assert canonical_json_bytes(bundle) == bundle_before
    assert notes.notes[0].note not in canonical_json_bytes(adjudication).decode()
    assert notes.notes[0].note not in canonical_json_bytes(pilot).decode()


def test_rerun_comparison_is_exact_versioned_and_reports_context_drift() -> None:
    report = _report(group_count=2)
    baseline = _bundle(version="0.2.0", revision="a" * 40, report=report)
    candidate = _bundle(version="0.2.1", revision="b" * 40, report=report)
    comparison = build_rerun_comparison(baseline, candidate)

    assert rerun_comparison_identity_matches(comparison)
    assert comparison.audit_context_matches is True
    assert comparison.unchanged_count == 2
    assert comparison.changed_count == 0
    assert comparison.added_count == 0
    assert comparison.removed_count == 0
    assert comparison.original_evidence_modified is False

    changed_context = _bundle(
        version="0.2.1",
        revision="c" * 40,
        report=_report(group_count=1, as_of_date=date(2024, 12, 30)),
    )
    drift = build_rerun_comparison(baseline, changed_context)
    assert drift.audit_context_matches is False
    assert drift.removed_count > 0
    assert drift.added_count > 0


def test_same_version_and_revision_are_not_misrepresented_as_version_comparison() -> None:
    baseline = _bundle(runtime_ns=100)
    candidate = _bundle(runtime_ns=200)
    with pytest.raises(ValidationError, match="different version or code revision"):
        build_rerun_comparison(baseline, candidate)


def test_pilot_report_derives_every_required_metric_from_supplied_adjudication() -> None:
    bundle = _bundle(runtime_ns=987_654_321)
    supplied = _completed_adjudication(bundle)
    exported = finalize_adjudication_export(bundle, supplied)
    report = build_pilot_report(
        pilot_key="pilot-001",
        bundles=(bundle,),
        adjudication_exports=(exported,),
    )

    assert pilot_report_identity_matches(report)
    assert report.datasets_audited == 1
    assert report.records_audited == 12
    assert report.runtime_ns == 987_654_321
    assert report.total_findings == 6
    assert {item.detector: item.finding_count for item in report.findings_by_detector} == {
        "duplicate_observation": 6,
        "lookahead_timestamp": 0,
        "revision_overwrite": 0,
        "unit_drift": 0,
    }
    assert report.findings_investigated == 5
    assert report.confirmed_issues == 1
    assert report.legitimate_data_conditions == 1
    assert report.accepted_exceptions == 1
    assert report.legitimate_exceptions == 2
    assert report.duplicate_correlated_signals == 1
    assert report.unresolved_investigated_alerts == 1
    assert report.findings_not_investigated == 1
    assert report.unexplained_or_noisy_alerts == 2
    assert report.customer_confirmed_research_decision_issues == 1
    assert report.researcher_review_seconds == 190
    report_payload = canonical_json_bytes(report)
    assert b"design-partner-dataset-001" not in report_payload
    assert b"customer-financial-facts-v1" not in report_payload
    assert b'"evidence"' not in report_payload


def test_pilot_report_rejects_missing_or_mutated_adjudication_sources() -> None:
    bundle = _bundle()
    exported = finalize_adjudication_export(
        bundle,
        build_adjudication_input_template(bundle),
    )
    with pytest.raises(ShadowModeError, match="exactly one adjudication"):
        build_pilot_report(
            pilot_key="pilot-001",
            bundles=(bundle,),
            adjudication_exports=(),
        )
    mutated = exported.model_copy(update={"export_content_hash": "0" * 64})
    with pytest.raises(ShadowModeError, match="identity mismatch"):
        build_pilot_report(
            pilot_key="pilot-001",
            bundles=(bundle,),
            adjudication_exports=(mutated,),
        )

    rerun = _bundle(version="0.2.1", revision="b" * 40)
    rerun_export = finalize_adjudication_export(
        rerun,
        build_adjudication_input_template(rerun),
    )
    with pytest.raises(ShadowModeError, match="one evaluated bundle per dataset key"):
        build_pilot_report(
            pilot_key="pilot-001",
            bundles=(bundle, rerun),
            adjudication_exports=(exported, rerun_export),
        )


def test_prepare_package_stores_notes_under_separate_private_path(tmp_path: Path) -> None:
    report = _report(group_count=1)
    bundle = prepare_shadow_package(
        output_directory=tmp_path,
        dataset_key="design-partner-dataset-001",
        quantcheck_version="0.2.0",
        code_revision="a" * 40,
        runtime_ns=100,
        reports=(report,),
    )
    assert (tmp_path / "researcher_finding_bundle.json").is_file()
    assert (tmp_path / "adjudication_input.json").is_file()
    assert (tmp_path / "private" / "reviewer_notes_input.json").is_file()
    assert not (tmp_path / "reviewer_notes_input.json").exists()
    assert finding_bundle_identity_matches(bundle)
    with pytest.raises(ShadowModeError, match="already exists"):
        prepare_shadow_package(
            output_directory=tmp_path,
            dataset_key="design-partner-dataset-001",
            quantcheck_version="0.2.0",
            code_revision="a" * 40,
            runtime_ns=100,
            reports=(report,),
        )


def test_module_cli_runs_prepare_adjudicate_report_without_echoing_customer_data(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "audit-report.json"
    report_path.write_bytes(canonical_json_bytes(_report(group_count=1)))
    package_path = tmp_path / "package"
    stdout = io.StringIO()
    assert (
        main(
            (
                "prepare",
                "--audit-report",
                str(report_path),
                "--dataset-key",
                "design-partner-dataset-001",
                "--quantcheck-version",
                "0.2.0",
                "--code-revision",
                "a" * 40,
                "--runtime-ns",
                "100",
                "--output-directory",
                str(package_path),
            ),
            stdout=stdout,
        )
        == 0
    )
    adjudication_path = tmp_path / "adjudication.json"
    assert (
        main(
            (
                "adjudicate",
                "--bundle",
                str(package_path / "researcher_finding_bundle.json"),
                "--input",
                str(package_path / "adjudication_input.json"),
                "--output",
                str(adjudication_path),
            ),
            stdout=stdout,
        )
        == 0
    )
    pilot_path = tmp_path / "pilot-report.json"
    assert (
        main(
            (
                "report",
                "--pilot-key",
                "pilot-001",
                "--bundle",
                str(package_path / "researcher_finding_bundle.json"),
                "--adjudication",
                str(adjudication_path),
                "--output",
                str(pilot_path),
            ),
            stdout=stdout,
        )
        == 0
    )
    output = stdout.getvalue()
    assert "customer-financial-facts-v1" not in output
    assert "PilotConcept0" not in output
    assert all(json.loads(line)["redacted"] is True for line in output.splitlines())
    assert AdjudicationExportV1.model_validate(
        parse_canonical_json(adjudication_path.read_bytes())
    ).sanitized
    saved_pilot = PilotReportV1.model_validate(parse_canonical_json(pilot_path.read_bytes()))
    assert saved_pilot.datasets_audited == 1


def test_cli_failure_does_not_echo_invalid_customer_artifact(tmp_path: Path) -> None:
    secret = "customer-secret-value-918273"
    bad = tmp_path / "bad.json"
    bad.write_text('{"secret":"' + secret + '"}', encoding="utf-8")
    stdout = io.StringIO()
    assert (
        main(
            (
                "adjudicate",
                "--bundle",
                str(bad),
                "--input",
                str(bad),
                "--output",
                str(tmp_path / "output.json"),
            ),
            stdout=stdout,
        )
        == 2
    )
    assert secret not in stdout.getvalue()
    assert json.loads(stdout.getvalue())["event"] == "shadow_command_failed"
