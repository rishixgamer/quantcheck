"""Dual-view v0.2 evaluation after both audit executions are finalized.

The strict view delegates unchanged to the primary family's frozen v0.1
one-to-one scorer.  The production view never changes recall: it interprets
the same immutable findings using the paired clean control and a narrow,
explicit relationship to one injected fault unit.
"""

from __future__ import annotations

from dataclasses import dataclass

from quantcheck.benchmark_dispatch import combined_audit_report
from quantcheck.benchmark_v2_contract import (
    ALL_V2_DETECTORS,
    DETECTOR_IDENTITY_BY_KEY,
    EVALUATION_V2_NAMESPACE,
    FINDING_INTERPRETATION_V2_NAMESPACE,
    DetectorKeyV2,
)
from quantcheck.benchmark_v2_execution import (
    detector_execution_findings,
    detector_execution_v2_identity_matches,
)
from quantcheck.benchmark_v2_schemas import (
    BenchmarkV2Evaluation,
    DetectorExecutionV2,
    FaultUnitOutcomeV2,
    FindingInterpretationV2,
    ProductionFindingInterpretationV2,
)
from quantcheck.duplicate_scoring import score_duplicate_observations
from quantcheck.hashing import canonical_sha256, stable_id
from quantcheck.json_types import JsonValue
from quantcheck.lookahead_scoring import score_lookahead
from quantcheck.revision_overwrite_scoring import score_revision_overwrite
from quantcheck.schemas import (
    AuditReport,
    DuplicateManifest,
    FaultManifest,
    Finding,
    RevisionOverwriteManifest,
    ScoreReport,
    UnitDriftEvidence,
    UnitDriftManifest,
)
from quantcheck.serialization import to_canonical_json
from quantcheck.unit_drift_scoring import score_unit_drift

__all__ = ["BenchmarkV2EvaluationError", "evaluate_detector_execution_v2"]

ManifestV1 = FaultManifest | UnitDriftManifest | DuplicateManifest | RevisionOverwriteManifest


class BenchmarkV2EvaluationError(ValueError):
    """Raised when finalized execution and private truth cannot be evaluated."""


@dataclass(frozen=True, slots=True)
class _FaultRelation:
    fault_id: str
    causal_record_ids: frozenset[str]


def _manifest_relations(
    manifest: ManifestV1,
) -> tuple[tuple[_FaultRelation, ...], dict[str, str]]:
    relations: list[_FaultRelation] = []
    corrupted_to_clean: dict[str, str] = {}
    if isinstance(manifest, FaultManifest | UnitDriftManifest):
        for replacement_entry in manifest.entries:
            corrupted = replacement_entry.corrupted_record.record_id
            original = replacement_entry.original_record.record_id
            relations.append(_FaultRelation(replacement_entry.fault_id, frozenset({corrupted})))
            corrupted_to_clean[corrupted] = original
    elif isinstance(manifest, DuplicateManifest):
        for duplicate_entry in manifest.entries:
            original = duplicate_entry.original_record.record_id
            created = duplicate_entry.created_record.record_id
            relations.append(
                _FaultRelation(duplicate_entry.fault_id, frozenset({original, created}))
            )
            # A created copy has no clean counterpart. Mapping it to its source
            # is only for clean-control equivalence and cannot create a clean
            # duplicate finding because group_size remains part of the key.
            corrupted_to_clean[created] = original
    else:
        units = {unit.eligibility_unit_id: unit for unit in manifest.eligible_units}
        for revision_entry in manifest.entries:
            unit = units[revision_entry.eligibility_unit_id]
            corrupted = revision_entry.corrupted_record.record_id
            historical = unit.historical_record.record_id
            relations.append(_FaultRelation(revision_entry.fault_id, frozenset({corrupted})))
            corrupted_to_clean[corrupted] = historical
    return tuple(sorted(relations, key=lambda relation: relation.fault_id)), corrupted_to_clean


def _finding_record_references(finding: Finding) -> frozenset[str]:
    references = set(finding.affected_record_ids)
    if isinstance(finding.evidence, UnitDriftEvidence):
        references.update(neighbor.record_id for neighbor in finding.evidence.neighbors)
    return frozenset(references)


def _replace_record_ids(value: JsonValue, record_map: dict[str, str]) -> JsonValue:
    if isinstance(value, str):
        return record_map.get(value, value)
    if isinstance(value, list):
        return [_replace_record_ids(item, record_map) for item in value]
    if isinstance(value, dict):
        return {key: _replace_record_ids(item, record_map) for key, item in value.items()}
    return value


def _clean_equivalence_key(finding: Finding, record_map: dict[str, str]) -> str:
    document = to_canonical_json(finding)
    assert isinstance(document, dict)
    # Identity and prose intentionally do not determine equivalence. Every
    # detector/rule/evidence field still does, including dates, values,
    # neighbors, confidence, and severity.
    body = {
        key: value for key, value in document.items() if key not in {"finding_id", "explanation"}
    }
    return canonical_sha256(_replace_record_ids(body, record_map))


def _score_primary(
    primary: DetectorKeyV2,
    report: AuditReport,
    manifest: ManifestV1,
) -> ScoreReport:
    if primary == "lookahead_timestamp" and isinstance(manifest, FaultManifest):
        return score_lookahead(report, manifest)
    if primary == "unit_drift" and isinstance(manifest, UnitDriftManifest):
        return score_unit_drift(report, manifest)
    if primary == "duplicate_observation" and isinstance(manifest, DuplicateManifest):
        return score_duplicate_observations(report, manifest)
    if primary == "revision_overwrite" and isinstance(manifest, RevisionOverwriteManifest):
        return score_revision_overwrite(report, manifest)
    raise BenchmarkV2EvaluationError("primary fault profile and manifest type disagree")


def _manifest_fault_type(manifest: ManifestV1) -> str:
    return manifest.fault_type


def evaluate_detector_execution_v2(
    *,
    primary_fault_profile: DetectorKeyV2,
    corrupted_execution: DetectorExecutionV2,
    clean_control_execution: DetectorExecutionV2,
    manifest: ManifestV1,
) -> BenchmarkV2Evaluation:
    """Evaluate selected findings only after corrupted and clean audits finish.

    The private manifest is accepted here, never by detector execution. A
    secondary finding attaches to an injected fault only when its public
    evidence references exactly one fault unit and no equivalent finding was
    present in the paired clean control. Multiple candidates remain unmatched.
    """
    if not detector_execution_v2_identity_matches(corrupted_execution):
        raise BenchmarkV2EvaluationError("corrupted execution identity is invalid")
    if not detector_execution_v2_identity_matches(clean_control_execution):
        raise BenchmarkV2EvaluationError("clean-control execution identity is invalid")
    if corrupted_execution.config != clean_control_execution.config:
        raise BenchmarkV2EvaluationError("paired executions must use one detector configuration")
    if (
        corrupted_execution.dataset_name != clean_control_execution.dataset_name
        or corrupted_execution.as_of_date != clean_control_execution.as_of_date
    ):
        raise BenchmarkV2EvaluationError("paired executions must share dataset and as-of context")
    selection = corrupted_execution.config.selected_detectors
    if primary_fault_profile not in selection:
        raise BenchmarkV2EvaluationError("the primary detector was not selected")
    if _manifest_fault_type(manifest) != primary_fault_profile:
        raise BenchmarkV2EvaluationError("primary fault profile and manifest disagree")

    corrupted_findings = detector_execution_findings(corrupted_execution)
    strict_report = combined_audit_report(
        audit_input=corrupted_execution.audit_input,
        findings=corrupted_findings,
        fault_profile=primary_fault_profile,
    )
    strict_score = _score_primary(primary_fault_profile, strict_report, manifest)

    matches_by_finding = {match.finding_id: match.fault_id for match in strict_score.matches}
    relations, corrupted_to_clean = _manifest_relations(manifest)
    clean_by_key: dict[str, list[str]] = {}
    for finding in detector_execution_findings(clean_control_execution):
        clean_by_key.setdefault(_clean_equivalence_key(finding, {}), []).append(finding.finding_id)

    primary_detector_id = DETECTOR_IDENTITY_BY_KEY[primary_fault_profile][0]
    interpreted: list[FindingInterpretationV2] = []
    for finding in corrupted_findings:
        matched_fault_id = matches_by_finding.get(finding.finding_id)
        if matched_fault_id is not None:
            interpreted.append(
                FindingInterpretationV2(
                    finding=finding,
                    category="primary_matched",
                    matched_fault_id=matched_fault_id,
                    rationale_code="exact_primary_one_to_one",
                )
            )
            continue

        clean_matches = tuple(
            sorted(
                clean_by_key.get(
                    _clean_equivalence_key(finding, corrupted_to_clean),
                    (),
                )
            )
        )
        if clean_matches:
            interpreted.append(
                FindingInterpretationV2(
                    finding=finding,
                    category="independent_background",
                    clean_control_finding_ids=clean_matches,
                    rationale_code="present_in_paired_clean_control",
                )
            )
            continue

        references = _finding_record_references(finding)
        candidates = tuple(
            relation.fault_id for relation in relations if references & relation.causal_record_ids
        )
        if len(candidates) == 1 and finding.detector_id != primary_detector_id:
            interpreted.append(
                FindingInterpretationV2(
                    finding=finding,
                    category="secondary_corroborating",
                    related_fault_id=candidates[0],
                    rationale_code="unique_corruption_related_rule",
                )
            )
        else:
            interpreted.append(
                FindingInterpretationV2(
                    finding=finding,
                    category="unmatched",
                    rationale_code="no_unique_supported_relationship",
                )
            )

    interpreted_tuple = tuple(interpreted)
    by_id = {item.finding.finding_id: item for item in interpreted_tuple}
    primary_by_fault = {match.fault_id: match.finding_id for match in strict_score.matches}
    fault_units = []
    for relation in relations:
        secondary = tuple(
            sorted(
                item.finding.finding_id
                for item in interpreted_tuple
                if item.related_fault_id == relation.fault_id
            )
        )
        primary_finding = primary_by_fault.get(relation.fault_id)
        finding_ids = ((primary_finding,) if primary_finding is not None else ()) + secondary
        fault_units.append(
            FaultUnitOutcomeV2(
                fault_id=relation.fault_id,
                primary_finding_id=primary_finding,
                secondary_finding_ids=secondary,
                violated_rule_ids=tuple(
                    sorted({by_id[finding_id].finding.rule_id for finding_id in finding_ids})
                ),
            )
        )

    category_counts = {
        category: sum(1 for item in interpreted_tuple if item.category == category)
        for category in (
            "primary_matched",
            "secondary_corroborating",
            "independent_background",
            "unmatched",
        )
    }
    interpretation_body: dict[str, object] = {
        "spec_version": "quantcheck/finding-evaluation/v2",
        "corrupted_execution_id": corrupted_execution.detector_execution_id,
        "clean_control_execution_id": clean_control_execution.detector_execution_id,
        "findings": interpreted_tuple,
        "fault_units": tuple(fault_units),
        "primary_matched_count": category_counts["primary_matched"],
        "secondary_corroborating_count": category_counts["secondary_corroborating"],
        "independent_background_count": category_counts["independent_background"],
        "unmatched_count": category_counts["unmatched"],
        "genuinely_unexplained_finding_ids": tuple(
            sorted(
                item.finding.finding_id
                for item in interpreted_tuple
                if item.category == "unmatched"
            )
        ),
    }
    interpretation = ProductionFindingInterpretationV2.model_validate(
        {
            "finding_interpretation_id": stable_id(
                prefix="fint2",
                namespace=FINDING_INTERPRETATION_V2_NAMESPACE,
                payload=interpretation_body,
            ),
            **interpretation_body,
        }
    )
    evaluation_body: dict[str, object] = {
        "spec_version": "quantcheck/finding-evaluation/v2",
        "primary_fault_profile": primary_fault_profile,
        "manifest_id": manifest.manifest_id,
        "detector_selection": selection,
        "corrupted_execution_id": corrupted_execution.detector_execution_id,
        "clean_control_execution_id": clean_control_execution.detector_execution_id,
        "strict_primary_audit_report": strict_report,
        "strict_primary_score": strict_score,
        "v0_1_all_detector_comparable": selection == ALL_V2_DETECTORS,
        "injected_fault_count": strict_score.metrics.injected_faults,
        "primary_matched_fault_count": strict_score.metrics.true_positive_faults,
        "primary_missed_fault_count": strict_score.metrics.false_negative_faults,
        "all_primary_faults_detected": strict_score.metrics.false_negative_faults == 0,
        "production_interpretation": interpretation,
    }
    return BenchmarkV2Evaluation.model_validate(
        {
            "evaluation_id": stable_id(
                prefix="eval2",
                namespace=EVALUATION_V2_NAMESPACE,
                payload=evaluation_body,
            ),
            **evaluation_body,
        }
    )
