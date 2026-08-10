"""Detector selection, trust boundary, provenance, and pairwise coverage."""

from __future__ import annotations

import inspect
from itertools import combinations

import pytest
from pydantic import ValidationError

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.benchmark_v2_contract import ALL_V2_DETECTORS, DetectorKeyV2
from quantcheck.benchmark_v2_execution import (
    detector_execution_findings,
    detector_execution_v2_identity_matches,
    run_selected_detectors_v2,
)
from quantcheck.benchmark_v2_schemas import DetectorExecutionConfigV2
from quantcheck.corpus_eligibility import unit_snapshot
from quantcheck.corpus_registry import corpus_unit_records, corpus_unit_spec
from quantcheck.schemas import AuditInputSnapshot
from quantcheck.serialization import canonical_json_bytes
from tests.benchmark_v2_support import unit_named


@pytest.fixture(scope="module")
def unusual_clean_input() -> AuditInputSnapshot:
    frozen = unit_named("development-stress")
    records = corpus_unit_records(frozen.corpus_unit_id)
    live = corpus_unit_spec(frozen.corpus_unit_id)
    return sanitize_for_audit(unit_snapshot(live, records))


def test_default_selection_is_all_supported_detectors() -> None:
    assert DetectorExecutionConfigV2().selected_detectors == ALL_V2_DETECTORS


@pytest.mark.parametrize("detector", ALL_V2_DETECTORS)
def test_each_detector_can_run_alone(
    unusual_clean_input: AuditInputSnapshot,
    detector: DetectorKeyV2,
) -> None:
    execution = run_selected_detectors_v2(
        unusual_clean_input,
        DetectorExecutionConfigV2(selected_detectors=(detector,)),
    )
    assert tuple(run.detector for run in execution.runs) == (detector,)
    assert detector_execution_v2_identity_matches(execution)


PAIRWISE_SELECTIONS = tuple(combinations(ALL_V2_DETECTORS, 2))


@pytest.mark.parametrize("selection", PAIRWISE_SELECTIONS)
def test_every_pairwise_cross_detector_combination_runs_exactly_once(
    unusual_clean_input: AuditInputSnapshot,
    selection: tuple[DetectorKeyV2, DetectorKeyV2],
) -> None:
    execution = run_selected_detectors_v2(
        unusual_clean_input,
        DetectorExecutionConfigV2(selected_detectors=selection),
    )
    assert len(execution.runs) == 2
    assert set(run.detector for run in execution.runs) == set(selection)
    assert execution.finding_count == sum(len(run.report.findings) for run in execution.runs)
    assert detector_execution_v2_identity_matches(execution)


def test_detector_selection_normalizes_to_contract_order() -> None:
    forward = DetectorExecutionConfigV2(
        selected_detectors=("lookahead_timestamp", "duplicate_observation")
    )
    reverse = DetectorExecutionConfigV2(
        selected_detectors=("duplicate_observation", "lookahead_timestamp")
    )
    assert forward == reverse


def test_empty_and_duplicate_selections_are_rejected() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        DetectorExecutionConfigV2(selected_detectors=())
    with pytest.raises(ValidationError, match="duplicates"):
        DetectorExecutionConfigV2(selected_detectors=("lookahead_timestamp", "lookahead_timestamp"))


def test_all_selected_findings_keep_their_exact_detector_provenance(
    unusual_clean_input: AuditInputSnapshot,
) -> None:
    execution = run_selected_detectors_v2(unusual_clean_input)
    for run in execution.runs:
        for finding in run.report.findings:
            assert finding.detector_id == run.report.detector_id
            assert finding.detector_version == run.report.detector_version
    ids = [finding.finding_id for finding in detector_execution_findings(execution)]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_execution_does_not_modify_the_caller_owned_audit_input(
    unusual_clean_input: AuditInputSnapshot,
) -> None:
    before = canonical_json_bytes(unusual_clean_input)
    run_selected_detectors_v2(unusual_clean_input)
    assert canonical_json_bytes(unusual_clean_input) == before


def test_execution_function_has_no_manifest_or_injector_channel() -> None:
    assert tuple(inspect.signature(run_selected_detectors_v2).parameters) == (
        "audit_input",
        "config",
    )
    module = inspect.getmodule(run_selected_detectors_v2)
    assert module is not None
    source = inspect.getsource(module)
    # The prose may describe the boundary as "manifest-blind".  What matters
    # mechanically is that no private type, injector, or answer-key field is
    # imported or accepted by this execution module.
    for forbidden in (
        "ManifestV1",
        "_manifest import",
        "_injection import",
        "inject_",
        "clean_snapshot",
        "target_rank",
    ):
        assert forbidden not in source


def test_the_only_scientific_input_is_audit_input_snapshot(
    unusual_clean_input: AuditInputSnapshot,
) -> None:
    assert unusual_clean_input.__class__.__name__ == "AuditInputSnapshot"
    execution = run_selected_detectors_v2(unusual_clean_input)
    assert execution.audit_input == unusual_clean_input
