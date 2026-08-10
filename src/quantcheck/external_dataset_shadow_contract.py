"""Immutable contracts for design-partner shadow-mode evaluation artifacts.

The contracts in this module are additive to the external-dataset production
path.  QuantCheck findings remain embedded, immutable evidence.  Human
adjudication and reviewer notes link to hashes of that evidence but never
replace or annotate the findings themselves.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BeforeValidator, model_validator

from quantcheck.benchmark_v2_contract import ALL_V2_DETECTORS, DetectorKeyV2
from quantcheck.corpus_schemas import (
    ContentHash,
    CorpusDate,
    CorpusModel,
    NonNegativeInteger,
    PositiveInteger,
    Token,
)
from quantcheck.external_dataset_contract import (
    EXTERNAL_AUDIT_V2_NAMESPACE,
    ExternalDatasetAuditReportV2,
)
from quantcheck.external_dataset_policy_contract import PolicyAuditResultV1
from quantcheck.hashing import canonical_sha256, stable_id
from quantcheck.schemas import Finding

__all__ = [
    "ADJUDICATION_EXPORT_SPEC_VERSION",
    "ADJUDICATION_INPUT_SPEC_VERSION",
    "FINDING_BUNDLE_SPEC_VERSION",
    "PILOT_REPORT_SPEC_VERSION",
    "REVIEWER_NOTES_INPUT_SPEC_VERSION",
    "REVIEWER_NOTES_SPEC_VERSION",
    "RERUN_COMPARISON_SPEC_VERSION",
    "AdjudicationDispositionV1",
    "AdjudicationEntryInputV1",
    "AdjudicationEntryV1",
    "AdjudicationExportV1",
    "AdjudicationInputV1",
    "AuditReportEvidenceV1",
    "DecisionImpactV1",
    "DetectorPilotMetricV1",
    "FindingRerunComparisonV1",
    "InvestigationStatusV1",
    "PilotArtifactReferenceV1",
    "PilotReportV1",
    "ReviewerNoteInputV1",
    "ReviewerNoteV1",
    "ReviewerNotesInputV1",
    "ReviewerNotesV1",
    "RerunComparisonV1",
    "ShadowFindingV1",
    "ShadowFindingBundleV1",
    "adjudication_export_identity_matches",
    "finding_bundle_identity_matches",
    "pilot_report_identity_matches",
    "reviewer_notes_identity_matches",
    "rerun_comparison_identity_matches",
    "shadow_finding_key",
]

FINDING_BUNDLE_SPEC_VERSION: Literal["quantcheck/shadow-finding-bundle/v1"] = (
    "quantcheck/shadow-finding-bundle/v1"
)
ADJUDICATION_INPUT_SPEC_VERSION: Literal["quantcheck/shadow-adjudication-input/v1"] = (
    "quantcheck/shadow-adjudication-input/v1"
)
ADJUDICATION_EXPORT_SPEC_VERSION: Literal["quantcheck/shadow-adjudication-export/v1"] = (
    "quantcheck/shadow-adjudication-export/v1"
)
REVIEWER_NOTES_INPUT_SPEC_VERSION: Literal["quantcheck/shadow-reviewer-notes-input/v1"] = (
    "quantcheck/shadow-reviewer-notes-input/v1"
)
REVIEWER_NOTES_SPEC_VERSION: Literal["quantcheck/shadow-reviewer-notes/v1"] = (
    "quantcheck/shadow-reviewer-notes/v1"
)
RERUN_COMPARISON_SPEC_VERSION: Literal["quantcheck/shadow-rerun-comparison/v1"] = (
    "quantcheck/shadow-rerun-comparison/v1"
)
PILOT_REPORT_SPEC_VERSION: Literal["quantcheck/shadow-pilot-report/v1"] = (
    "quantcheck/shadow-pilot-report/v1"
)

_AUDIT_ID_NAMESPACE = "quantcheck/shadow-audit/v1"
_AUDIT_CONTEXT_NAMESPACE = "quantcheck/shadow-audit-context/v1"
_FINDING_KEY_NAMESPACE = "quantcheck/shadow-finding-key/v1"
_FINDING_BUNDLE_NAMESPACE = "quantcheck/shadow-finding-bundle/v1"
_ADJUDICATION_EXPORT_NAMESPACE = "quantcheck/shadow-adjudication-export/v1"
_REVIEWER_NOTE_NAMESPACE = "quantcheck/shadow-reviewer-note/v1"
_REVIEWER_NOTES_NAMESPACE = "quantcheck/shadow-reviewer-notes/v1"
_RERUN_COMPARISON_NAMESPACE = "quantcheck/shadow-rerun-comparison/v1"
_PILOT_REPORT_NAMESPACE = "quantcheck/shadow-pilot-report/v1"

_IDENTITY_PATTERNS = {
    "shadow_audit_id": re.compile(r"^shaudit_[0-9a-f]{16}$"),
    "audit_context_id": re.compile(r"^shctx_[0-9a-f]{16}$"),
    "finding_key": re.compile(r"^shfind_[0-9a-f]{16}$"),
    "finding_bundle_id": re.compile(r"^shbundle_[0-9a-f]{16}$"),
    "adjudication_export_id": re.compile(r"^shadj_[0-9a-f]{16}$"),
    "reviewer_note_id": re.compile(r"^shnote_[0-9a-f]{16}$"),
    "reviewer_notes_id": re.compile(r"^shnotes_[0-9a-f]{16}$"),
    "rerun_comparison_id": re.compile(r"^shcmp_[0-9a-f]{16}$"),
    "pilot_report_id": re.compile(r"^shpilot_[0-9a-f]{16}$"),
}


def _to_tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


def _identity_validator(label: str) -> BeforeValidator:
    def validate(value: object) -> str:
        if not isinstance(value, str) or _IDENTITY_PATTERNS[label].fullmatch(value) is None:
            raise ValueError(f"malformed {label}")
        return value

    return BeforeValidator(validate)


ShadowAuditId = Annotated[str, _identity_validator("shadow_audit_id")]
AuditContextId = Annotated[str, _identity_validator("audit_context_id")]
ShadowFindingKey = Annotated[str, _identity_validator("finding_key")]
FindingBundleId = Annotated[str, _identity_validator("finding_bundle_id")]
AdjudicationExportId = Annotated[str, _identity_validator("adjudication_export_id")]
ReviewerNoteId = Annotated[str, _identity_validator("reviewer_note_id")]
ReviewerNotesId = Annotated[str, _identity_validator("reviewer_notes_id")]
RerunComparisonId = Annotated[str, _identity_validator("rerun_comparison_id")]
PilotReportId = Annotated[str, _identity_validator("pilot_report_id")]

AdjudicationDispositionV1 = Literal[
    "confirmed_issue",
    "legitimate_data_condition",
    "accepted_exception",
    "duplicate_correlated_signal",
    "unresolved",
]
InvestigationStatusV1 = Literal["not_started", "investigated"]
DecisionImpactV1 = Literal[
    "not_assessed",
    "reviewed_not_confirmed",
    "customer_independently_confirmed",
]


def _normalize_tokens(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return tuple(sorted(value))


UniqueTokens = Annotated[
    tuple[Token, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_tokens),
]


class AuditReportEvidenceV1(CorpusModel):
    """One unchanged public audit report and its exact canonical hash."""

    report: ExternalDatasetAuditReportV2
    report_content_hash: ContentHash

    @model_validator(mode="after")
    def _check_hash(self) -> AuditReportEvidenceV1:
        if canonical_sha256(self.report) != self.report_content_hash:
            raise ValueError("audit report content hash mismatch")
        report_body = {
            name: getattr(self.report, name)
            for name in type(self.report).model_fields
            if name != "external_audit_report_id"
        }
        if self.report.external_audit_report_id != stable_id(
            prefix="xaudit2",
            namespace=EXTERNAL_AUDIT_V2_NAMESPACE,
            payload=report_body,
        ):
            raise ValueError("audit report identity mismatch")
        return self


def _normalize_reports(
    value: tuple[AuditReportEvidenceV1, ...],
) -> tuple[AuditReportEvidenceV1, ...]:
    if not value:
        raise ValueError("a finding bundle requires at least one audit report")
    ids = [item.report.external_audit_report_id for item in value]
    if len(set(ids)) != len(ids):
        raise ValueError("audit report identifiers must be unique")
    return tuple(sorted(value, key=lambda item: item.report.external_audit_report_id))


AuditReportEvidence = Annotated[
    tuple[AuditReportEvidenceV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_reports),
]


def shadow_finding_key(*, detector: DetectorKeyV2, finding: Finding) -> str:
    """Build the exact, non-fuzzy key used only for cross-version comparison."""
    return stable_id(
        prefix="shfind",
        namespace=_FINDING_KEY_NAMESPACE,
        payload={
            "detector": detector,
            "detector_id": finding.detector_id,
            "fault_type": finding.fault_type,
            "fault_subtype": finding.fault_subtype,
            "rule_id": finding.rule_id,
            "affected_record_ids": finding.affected_record_ids,
            "evidence_hash": canonical_sha256(finding.evidence),
        },
    )


class ShadowFindingV1(CorpusModel):
    """Researcher-facing immutable finding plus separate policy context."""

    finding_key: ShadowFindingKey
    detector: DetectorKeyV2
    source_report_id: Token
    finding: Finding
    finding_content_hash: ContentHash
    policy_result_id: Token
    base_action: Literal["blocking", "warning", "informational"]
    effective_action: Literal["blocking", "warning", "informational"] | None
    policy_exception_applied: bool

    @model_validator(mode="after")
    def _check_finding(self) -> ShadowFindingV1:
        if canonical_sha256(self.finding) != self.finding_content_hash:
            raise ValueError("finding content hash mismatch")
        if shadow_finding_key(detector=self.detector, finding=self.finding) != self.finding_key:
            raise ValueError("finding comparison key mismatch")
        return self


def _normalize_findings(value: tuple[ShadowFindingV1, ...]) -> tuple[ShadowFindingV1, ...]:
    finding_ids = [item.finding.finding_id for item in value]
    finding_keys = [item.finding_key for item in value]
    if len(set(finding_ids)) != len(finding_ids):
        raise ValueError("finding identifiers must be unique across the bundle")
    if len(set(finding_keys)) != len(finding_keys):
        raise ValueError("exact comparison keys must be unique across the bundle")
    return tuple(sorted(value, key=lambda item: item.finding.finding_id))


ShadowFindings = Annotated[
    tuple[ShadowFindingV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_findings),
]


class ShadowFindingBundleV1(CorpusModel):
    """One researcher-facing, version-bound shadow audit package."""

    finding_bundle_id: FindingBundleId
    bundle_content_hash: ContentHash
    spec_version: Literal["quantcheck/shadow-finding-bundle/v1"] = FINDING_BUNDLE_SPEC_VERSION
    shadow_audit_id: ShadowAuditId
    audit_context_id: AuditContextId
    dataset_key: Token
    quantcheck_version: Token
    code_revision: Token
    execution_run_id: Token | None
    execution_finalization_id: Token | None
    runtime_ns: PositiveInteger
    mapping_id: Token
    policy_id: Token
    policy_content_hash: ContentHash
    as_of_date: CorpusDate
    source_record_count: NonNegativeInteger
    records_audited: NonNegativeInteger
    audit_reports: AuditReportEvidence
    findings: ShadowFindings
    finding_count: NonNegativeInteger
    shadow_mode: Literal[True] = True
    source_modified: Literal[False] = False
    production_blocking_used: Literal[False] = False
    manifest_used: Literal[False] = False
    benchmark_claim: Literal[False] = False

    @model_validator(mode="after")
    def _check_bundle(self) -> ShadowFindingBundleV1:
        reports = tuple(item.report for item in self.audit_reports)
        if self.finding_count != len(self.findings):
            raise ValueError("finding_count must equal bundle findings")
        if self.source_record_count != sum(report.source_record_count for report in reports):
            raise ValueError("source record count must equal the report total")
        if self.records_audited != sum(report.snapshot_record_count for report in reports):
            raise ValueError("records_audited must equal point-in-time report records")
        for report in reports:
            if (
                report.mapping_id != self.mapping_id
                or report.policy_id != self.policy_id
                or report.policy_content_hash != self.policy_content_hash
                or report.as_of_date != self.as_of_date
            ):
                raise ValueError("all reports must share the bundle audit context")
        report_ids = {report.external_audit_report_id for report in reports}
        if any(item.source_report_id not in report_ids for item in self.findings):
            raise ValueError("every finding must link to a source report")

        source_findings: dict[str, tuple[str, DetectorKeyV2, Finding, PolicyAuditResultV1]] = {}
        for report in reports:
            for run in report.detector_runs:
                for finding in run.report.findings:
                    if finding.finding_id in source_findings:
                        raise ValueError("source reports contain a duplicate finding identifier")
                    policy_results = tuple(
                        result
                        for result in report.policy_results
                        if result.evidence.kind == "detector_finding"
                        and result.evidence.finding_id == finding.finding_id
                    )
                    if len(policy_results) != 1:
                        raise ValueError("source finding must have exactly one policy result")
                    source_findings[finding.finding_id] = (
                        report.external_audit_report_id,
                        run.detector,
                        finding,
                        policy_results[0],
                    )
        bundled_findings = {item.finding.finding_id: item for item in self.findings}
        if set(bundled_findings) != set(source_findings):
            raise ValueError("bundle findings must exactly equal source report findings")
        for finding_id, item in bundled_findings.items():
            source_report_id, detector, source_finding, policy_result_object = source_findings[
                finding_id
            ]
            policy_result = policy_result_object
            if (
                item.source_report_id != source_report_id
                or item.detector != detector
                or item.finding != source_finding
                or item.finding_content_hash != canonical_sha256(source_finding)
                or item.policy_result_id != policy_result.policy_result_id
                or item.base_action != policy_result.base_action
                or item.effective_action != policy_result.effective_action
                or item.policy_exception_applied
                != (policy_result.disposition == "exception_applied")
            ):
                raise ValueError("bundle finding or policy context differs from source report")
        if (self.execution_run_id is None) != (self.execution_finalization_id is None):
            raise ValueError("execution run and finalization identifiers must be paired")
        return self


def _finding_bundle_body(bundle: ShadowFindingBundleV1) -> dict[str, object]:
    return {
        name: getattr(bundle, name)
        for name in type(bundle).model_fields
        if name not in {"finding_bundle_id", "bundle_content_hash"}
    }


def finding_bundle_identity_matches(bundle: ShadowFindingBundleV1) -> bool:
    body = _finding_bundle_body(bundle)
    return bundle.bundle_content_hash == canonical_sha256(body) and bundle.finding_bundle_id == (
        stable_id(prefix="shbundle", namespace=_FINDING_BUNDLE_NAMESPACE, payload=body)
    )


class AdjudicationEntryInputV1(CorpusModel):
    """Sanitized human-supplied classification; contains no evidence or note text."""

    finding_id: Token
    finding_content_hash: ContentHash
    investigation_status: InvestigationStatusV1
    disposition: AdjudicationDispositionV1
    decision_impact: DecisionImpactV1
    researcher_review_seconds: NonNegativeInteger

    @model_validator(mode="after")
    def _check_state(self) -> AdjudicationEntryInputV1:
        if self.investigation_status == "not_started" and (
            self.disposition != "unresolved"
            or self.decision_impact != "not_assessed"
            or self.researcher_review_seconds != 0
        ):
            raise ValueError("a not-started review must remain unresolved and unmeasured")
        if (
            self.decision_impact == "customer_independently_confirmed"
            and self.disposition != "confirmed_issue"
        ):
            raise ValueError("decision impact can be confirmed only for a confirmed issue")
        return self


def _normalize_adjudication_inputs(
    value: tuple[AdjudicationEntryInputV1, ...],
) -> tuple[AdjudicationEntryInputV1, ...]:
    ids = [item.finding_id for item in value]
    if len(set(ids)) != len(ids):
        raise ValueError("adjudication finding identifiers must be unique")
    return tuple(sorted(value, key=lambda item: item.finding_id))


AdjudicationInputs = Annotated[
    tuple[AdjudicationEntryInputV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_adjudication_inputs),
]


class AdjudicationInputV1(CorpusModel):
    """Editable input template linked to one immutable finding bundle."""

    spec_version: Literal["quantcheck/shadow-adjudication-input/v1"] = (
        ADJUDICATION_INPUT_SPEC_VERSION
    )
    finding_bundle_id: FindingBundleId
    finding_bundle_hash: ContentHash
    entries: AdjudicationInputs


class AdjudicationEntryV1(AdjudicationEntryInputV1):
    """Final sanitized entry with the detector needed for aggregate reporting."""

    detector: DetectorKeyV2


def _normalize_adjudications(
    value: tuple[AdjudicationEntryV1, ...],
) -> tuple[AdjudicationEntryV1, ...]:
    ids = [item.finding_id for item in value]
    if len(set(ids)) != len(ids):
        raise ValueError("adjudication finding identifiers must be unique")
    return tuple(sorted(value, key=lambda item: item.finding_id))


Adjudications = Annotated[
    tuple[AdjudicationEntryV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_adjudications),
]


class AdjudicationExportV1(CorpusModel):
    """Privacy-minimized export used as the sole input to pilot outcomes."""

    adjudication_export_id: AdjudicationExportId
    export_content_hash: ContentHash
    spec_version: Literal["quantcheck/shadow-adjudication-export/v1"] = (
        ADJUDICATION_EXPORT_SPEC_VERSION
    )
    shadow_audit_id: ShadowAuditId
    finding_bundle_id: FindingBundleId
    finding_bundle_hash: ContentHash
    entries: Adjudications
    sanitized: Literal[True] = True
    finding_evidence_included: Literal[False] = False
    reviewer_notes_included: Literal[False] = False
    customer_record_ids_included: Literal[False] = False
    customer_values_included: Literal[False] = False


def _adjudication_export_body(export: AdjudicationExportV1) -> dict[str, object]:
    return {
        name: getattr(export, name)
        for name in type(export).model_fields
        if name not in {"adjudication_export_id", "export_content_hash"}
    }


def adjudication_export_identity_matches(export: AdjudicationExportV1) -> bool:
    body = _adjudication_export_body(export)
    return export.export_content_hash == canonical_sha256(body) and (
        export.adjudication_export_id
        == stable_id(prefix="shadj", namespace=_ADJUDICATION_EXPORT_NAMESPACE, payload=body)
    )


def _validate_note_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("reviewer note must be non-blank")
    if len(value) > 20_000:
        raise ValueError("reviewer note must be at most 20000 characters")
    if any(ord(character) < 0x20 and character not in {"\n", "\t"} for character in value):
        raise ValueError("reviewer note contains an unsupported control character")
    return value


ReviewerNoteText = Annotated[str, BeforeValidator(_validate_note_text)]


class ReviewerNoteInputV1(CorpusModel):
    """Private reviewer-authored note draft; never accepted by pilot reporting."""

    finding_id: Token
    note_revision: PositiveInteger
    reviewer_role: Token
    note: ReviewerNoteText


def _normalize_note_inputs(
    value: tuple[ReviewerNoteInputV1, ...],
) -> tuple[ReviewerNoteInputV1, ...]:
    keys = [(item.finding_id, item.note_revision) for item in value]
    if len(set(keys)) != len(keys):
        raise ValueError("reviewer note revisions must be unique per finding")
    return tuple(sorted(value, key=lambda item: (item.finding_id, item.note_revision)))


ReviewerNoteInputs = Annotated[
    tuple[ReviewerNoteInputV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_note_inputs),
]


class ReviewerNotesInputV1(CorpusModel):
    """Editable private note template stored apart from adjudication data."""

    spec_version: Literal["quantcheck/shadow-reviewer-notes-input/v1"] = (
        REVIEWER_NOTES_INPUT_SPEC_VERSION
    )
    finding_bundle_id: FindingBundleId
    finding_bundle_hash: ContentHash
    notes: ReviewerNoteInputs = ()
    private: Literal[True] = True


class ReviewerNoteV1(CorpusModel):
    reviewer_note_id: ReviewerNoteId
    finding_id: Token
    finding_content_hash: ContentHash
    note_revision: PositiveInteger
    reviewer_role: Token
    note: ReviewerNoteText

    @model_validator(mode="after")
    def _check_identity(self) -> ReviewerNoteV1:
        body = {
            name: getattr(self, name)
            for name in type(self).model_fields
            if name != "reviewer_note_id"
        }
        expected = stable_id(prefix="shnote", namespace=_REVIEWER_NOTE_NAMESPACE, payload=body)
        if self.reviewer_note_id != expected:
            raise ValueError("reviewer note identity mismatch")
        return self


def _normalize_notes(value: tuple[ReviewerNoteV1, ...]) -> tuple[ReviewerNoteV1, ...]:
    ids = [item.reviewer_note_id for item in value]
    keys = [(item.finding_id, item.note_revision) for item in value]
    if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
        raise ValueError("reviewer notes and revisions must be unique")
    return tuple(sorted(value, key=lambda item: (item.finding_id, item.note_revision)))


ReviewerNotes = Annotated[
    tuple[ReviewerNoteV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_notes),
]


class ReviewerNotesV1(CorpusModel):
    """Private note file linked by hashes, separate from findings and adjudication."""

    reviewer_notes_id: ReviewerNotesId
    notes_content_hash: ContentHash
    spec_version: Literal["quantcheck/shadow-reviewer-notes/v1"] = REVIEWER_NOTES_SPEC_VERSION
    finding_bundle_id: FindingBundleId
    finding_bundle_hash: ContentHash
    notes: ReviewerNotes
    private: Literal[True] = True
    included_in_pilot_metrics: Literal[False] = False


def _reviewer_notes_body(notes: ReviewerNotesV1) -> dict[str, object]:
    return {
        name: getattr(notes, name)
        for name in type(notes).model_fields
        if name not in {"reviewer_notes_id", "notes_content_hash"}
    }


def reviewer_notes_identity_matches(notes: ReviewerNotesV1) -> bool:
    body = _reviewer_notes_body(notes)
    return notes.notes_content_hash == canonical_sha256(body) and notes.reviewer_notes_id == (
        stable_id(prefix="shnotes", namespace=_REVIEWER_NOTES_NAMESPACE, payload=body)
    )


class FindingRerunComparisonV1(CorpusModel):
    """One exact comparison result; no similarity or correlation is inferred."""

    finding_key: ShadowFindingKey
    detector: DetectorKeyV2
    rule_id: Token
    status: Literal["unchanged", "changed", "added", "removed"]
    baseline_finding_id: Token | None
    baseline_finding_hash: ContentHash | None
    candidate_finding_id: Token | None
    candidate_finding_hash: ContentHash | None

    @model_validator(mode="after")
    def _check_sides(self) -> FindingRerunComparisonV1:
        baseline_present = self.baseline_finding_id is not None
        candidate_present = self.candidate_finding_id is not None
        if baseline_present != (self.baseline_finding_hash is not None):
            raise ValueError("baseline finding identity and hash must be paired")
        if candidate_present != (self.candidate_finding_hash is not None):
            raise ValueError("candidate finding identity and hash must be paired")
        if self.status in {"unchanged", "changed"} and not (baseline_present and candidate_present):
            raise ValueError("matched findings require both versions")
        if self.status == "added" and (baseline_present or not candidate_present):
            raise ValueError("added finding must exist only in the candidate")
        if self.status == "removed" and (not baseline_present or candidate_present):
            raise ValueError("removed finding must exist only in the baseline")
        if self.status == "unchanged" and self.baseline_finding_hash != self.candidate_finding_hash:
            raise ValueError("unchanged findings require identical canonical content")
        if self.status == "changed" and self.baseline_finding_hash == self.candidate_finding_hash:
            raise ValueError("changed findings require different canonical content")
        return self


def _normalize_comparisons(
    value: tuple[FindingRerunComparisonV1, ...],
) -> tuple[FindingRerunComparisonV1, ...]:
    keys = [item.finding_key for item in value]
    if len(set(keys)) != len(keys):
        raise ValueError("rerun comparison keys must be unique")
    return tuple(sorted(value, key=lambda item: item.finding_key))


FindingComparisons = Annotated[
    tuple[FindingRerunComparisonV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_comparisons),
]


class RerunComparisonV1(CorpusModel):
    """Exact cross-version comparison with explicit audit-context drift."""

    rerun_comparison_id: RerunComparisonId
    comparison_content_hash: ContentHash
    spec_version: Literal["quantcheck/shadow-rerun-comparison/v1"] = RERUN_COMPARISON_SPEC_VERSION
    baseline_finding_bundle_id: FindingBundleId
    baseline_finding_bundle_hash: ContentHash
    baseline_shadow_audit_id: ShadowAuditId
    baseline_quantcheck_version: Token
    baseline_code_revision: Token
    candidate_finding_bundle_id: FindingBundleId
    candidate_finding_bundle_hash: ContentHash
    candidate_shadow_audit_id: ShadowAuditId
    candidate_quantcheck_version: Token
    candidate_code_revision: Token
    baseline_audit_context_id: AuditContextId
    candidate_audit_context_id: AuditContextId
    audit_context_matches: bool
    comparisons: FindingComparisons
    unchanged_count: NonNegativeInteger
    changed_count: NonNegativeInteger
    added_count: NonNegativeInteger
    removed_count: NonNegativeInteger
    comparison_method: Literal["exact_evidence_key_no_fuzzy_matching"] = (
        "exact_evidence_key_no_fuzzy_matching"
    )
    original_evidence_modified: Literal[False] = False

    @model_validator(mode="after")
    def _check_counts(self) -> RerunComparisonV1:
        if (self.baseline_quantcheck_version, self.baseline_code_revision) == (
            self.candidate_quantcheck_version,
            self.candidate_code_revision,
        ):
            raise ValueError("rerun comparison requires a different version or code revision")
        if self.audit_context_matches != (
            self.baseline_audit_context_id == self.candidate_audit_context_id
        ):
            raise ValueError("audit_context_matches must reflect exact context identity")
        counts = tuple(
            sum(item.status == status for item in self.comparisons)
            for status in ("unchanged", "changed", "added", "removed")
        )
        if counts != (
            self.unchanged_count,
            self.changed_count,
            self.added_count,
            self.removed_count,
        ):
            raise ValueError("rerun status counts must equal comparison entries")
        return self


def _rerun_comparison_body(comparison: RerunComparisonV1) -> dict[str, object]:
    return {
        name: getattr(comparison, name)
        for name in type(comparison).model_fields
        if name not in {"rerun_comparison_id", "comparison_content_hash"}
    }


def rerun_comparison_identity_matches(comparison: RerunComparisonV1) -> bool:
    body = _rerun_comparison_body(comparison)
    return comparison.comparison_content_hash == canonical_sha256(body) and (
        comparison.rerun_comparison_id
        == stable_id(prefix="shcmp", namespace=_RERUN_COMPARISON_NAMESPACE, payload=body)
    )


class DetectorPilotMetricV1(CorpusModel):
    detector: DetectorKeyV2
    finding_count: NonNegativeInteger


def _normalize_detector_metrics(
    value: tuple[DetectorPilotMetricV1, ...],
) -> tuple[DetectorPilotMetricV1, ...]:
    detectors = [item.detector for item in value]
    if len(value) != len(ALL_V2_DETECTORS) or set(detectors) != set(ALL_V2_DETECTORS):
        raise ValueError("pilot metrics must report every detector exactly once")
    by_detector = {item.detector: item for item in value}
    return tuple(by_detector[detector] for detector in ALL_V2_DETECTORS)


DetectorPilotMetrics = Annotated[
    tuple[DetectorPilotMetricV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_detector_metrics),
]


class PilotArtifactReferenceV1(CorpusModel):
    """Hash-linked sources for one dataset, without dataset or finding details."""

    shadow_audit_id: ShadowAuditId
    finding_bundle_id: FindingBundleId
    finding_bundle_hash: ContentHash
    adjudication_export_id: AdjudicationExportId
    adjudication_export_hash: ContentHash


def _normalize_pilot_sources(
    value: tuple[PilotArtifactReferenceV1, ...],
) -> tuple[PilotArtifactReferenceV1, ...]:
    if not value:
        raise ValueError("a pilot report requires supplied data for at least one dataset")
    bundles = [item.finding_bundle_id for item in value]
    exports = [item.adjudication_export_id for item in value]
    if len(set(bundles)) != len(bundles) or len(set(exports)) != len(exports):
        raise ValueError("pilot source artifacts must be unique")
    return tuple(sorted(value, key=lambda item: item.finding_bundle_id))


PilotArtifactReferences = Annotated[
    tuple[PilotArtifactReferenceV1, ...],
    BeforeValidator(_to_tuple),
    AfterValidator(_normalize_pilot_sources),
]


class PilotReportV1(CorpusModel):
    """Privacy-minimized factual aggregate derived from supplied adjudications."""

    pilot_report_id: PilotReportId
    report_content_hash: ContentHash
    spec_version: Literal["quantcheck/shadow-pilot-report/v1"] = PILOT_REPORT_SPEC_VERSION
    pilot_key: Token
    source_artifacts: PilotArtifactReferences
    datasets_audited: PositiveInteger
    records_audited: NonNegativeInteger
    runtime_ns: PositiveInteger
    total_findings: NonNegativeInteger
    findings_by_detector: DetectorPilotMetrics
    findings_investigated: NonNegativeInteger
    confirmed_issues: NonNegativeInteger
    legitimate_data_conditions: NonNegativeInteger
    accepted_exceptions: NonNegativeInteger
    legitimate_exceptions: NonNegativeInteger
    duplicate_correlated_signals: NonNegativeInteger
    unresolved_investigated_alerts: NonNegativeInteger
    findings_not_investigated: NonNegativeInteger
    unexplained_or_noisy_alerts: NonNegativeInteger
    customer_confirmed_research_decision_issues: NonNegativeInteger
    researcher_review_seconds: NonNegativeInteger
    aggregate_only: Literal[True] = True
    customer_names_included: Literal[False] = False
    dataset_names_included: Literal[False] = False
    finding_evidence_included: Literal[False] = False
    reviewer_notes_included: Literal[False] = False
    customer_values_included: Literal[False] = False
    customer_decision_confirmation_required: Literal[True] = True
    manufactured_numbers: Literal[False] = False

    @model_validator(mode="after")
    def _check_derived_totals(self) -> PilotReportV1:
        if self.datasets_audited != len(self.source_artifacts):
            raise ValueError("datasets_audited must equal supplied bundle/export pairs")
        if self.total_findings != sum(item.finding_count for item in self.findings_by_detector):
            raise ValueError("detector counts must equal total findings")
        if self.legitimate_exceptions != (
            self.legitimate_data_conditions + self.accepted_exceptions
        ):
            raise ValueError("legitimate exceptions must preserve both source categories")
        if self.unexplained_or_noisy_alerts != (
            self.duplicate_correlated_signals + self.unresolved_investigated_alerts
        ):
            raise ValueError("unexplained/noisy alerts must preserve their source categories")
        if self.findings_investigated + self.findings_not_investigated != self.total_findings:
            raise ValueError("investigation counts must partition findings")
        return self


def _pilot_report_body(report: PilotReportV1) -> dict[str, object]:
    return {
        name: getattr(report, name)
        for name in type(report).model_fields
        if name not in {"pilot_report_id", "report_content_hash"}
    }


def pilot_report_identity_matches(report: PilotReportV1) -> bool:
    body = _pilot_report_body(report)
    return report.report_content_hash == canonical_sha256(body) and report.pilot_report_id == (
        stable_id(prefix="shpilot", namespace=_PILOT_REPORT_NAMESPACE, payload=body)
    )


def build_shadow_audit_id(payload: object) -> str:
    return stable_id(prefix="shaudit", namespace=_AUDIT_ID_NAMESPACE, payload=payload)


def build_audit_context_id(payload: object) -> str:
    return stable_id(prefix="shctx", namespace=_AUDIT_CONTEXT_NAMESPACE, payload=payload)


def build_finding_bundle_identity(payload: object) -> tuple[str, str]:
    return (
        stable_id(prefix="shbundle", namespace=_FINDING_BUNDLE_NAMESPACE, payload=payload),
        canonical_sha256(payload),
    )


def build_adjudication_export_identity(payload: object) -> tuple[str, str]:
    return (
        stable_id(prefix="shadj", namespace=_ADJUDICATION_EXPORT_NAMESPACE, payload=payload),
        canonical_sha256(payload),
    )


def build_reviewer_note_id(payload: object) -> str:
    return stable_id(prefix="shnote", namespace=_REVIEWER_NOTE_NAMESPACE, payload=payload)


def build_reviewer_notes_identity(payload: object) -> tuple[str, str]:
    return (
        stable_id(prefix="shnotes", namespace=_REVIEWER_NOTES_NAMESPACE, payload=payload),
        canonical_sha256(payload),
    )


def build_rerun_comparison_identity(payload: object) -> tuple[str, str]:
    return (
        stable_id(prefix="shcmp", namespace=_RERUN_COMPARISON_NAMESPACE, payload=payload),
        canonical_sha256(payload),
    )


def build_pilot_report_identity(payload: object) -> tuple[str, str]:
    return (
        stable_id(prefix="shpilot", namespace=_PILOT_REPORT_NAMESPACE, payload=payload),
        canonical_sha256(payload),
    )
