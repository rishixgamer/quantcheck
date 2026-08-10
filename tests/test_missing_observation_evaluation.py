"""Clean controls, complete mechanism coverage, and the held-out gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.missing_observation_evaluation import (
    MissingObservationEvaluationEvidenceV1,
    evaluate_missing_observation_partition,
    missing_observation_evaluation_identity_matches,
    run_missing_observation_evaluation,
)
from quantcheck.missing_observation_fixture import (
    EVALUATION_MECHANISMS,
    MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
    build_missing_observation_evaluation_case,
    evaluation_case_ids,
)
from quantcheck.missing_observation_gate import (
    MissingObservationHeldoutAuthorizationError,
    active_missing_observation_heldout_authorization,
    heldout_missing_observation_cases,
)
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_development_and_validation_run_before_holdout() -> None:
    development = evaluate_missing_observation_partition("development")
    validation = evaluate_missing_observation_partition("validation")
    for result, partition in (
        (development, "development"),
        (validation, "validation"),
    ):
        assert result.partition == partition
        assert result.case_count == len(EVALUATION_MECHANISMS)
        assert result.injected_faults == 26
        assert result.findings == 26
        assert result.true_positive_faults == 26
        assert result.false_positive_findings == 0
        assert result.false_negative_faults == 0
        assert result.clean_control_findings == 0
        assert result.research_changed_cases == 6
        assert result.exact_restoration_cases == 6
        assert result.precision == result.recall == result.f1 == 1


def test_heldout_partition_is_closed_without_authorization() -> None:
    with pytest.raises(PermissionError, match="complete frozen case set"):
        evaluate_missing_observation_partition("heldout")


def test_partial_heldout_authorization_cannot_execute() -> None:
    case_ids = evaluation_case_ids("heldout")
    with (
        heldout_missing_observation_cases(
            freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
            case_ids=case_ids[:-1],
        ),
        pytest.raises(PermissionError, match="complete frozen case set"),
    ):
        evaluate_missing_observation_partition("heldout")


def test_partial_authorization_cannot_materialize_one_heldout_case() -> None:
    case_ids = evaluation_case_ids("heldout")
    with (
        heldout_missing_observation_cases(
            freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
            case_ids=(case_ids[0],),
        ),
        pytest.raises(PermissionError, match="complete-case authorization"),
    ):
        build_missing_observation_evaluation_case("heldout", "random_missingness")


def test_complete_authorized_heldout_evaluation_and_public_evidence() -> None:
    case_ids = evaluation_case_ids("heldout")
    with heldout_missing_observation_cases(
        freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
        case_ids=case_ids,
    ):
        evidence = run_missing_observation_evaluation()
        assert active_missing_observation_heldout_authorization() is not None
    assert active_missing_observation_heldout_authorization() is None

    assert evidence.heldout.case_count == 6
    assert evidence.heldout.injected_faults == 26
    assert evidence.heldout.true_positive_faults == 26
    assert evidence.heldout.false_positive_findings == 0
    assert evidence.heldout.false_negative_faults == 0
    assert evidence.heldout.clean_control_findings == 0
    assert evidence.heldout.research_changed_cases == 6
    assert evidence.heldout.exact_restoration_cases == 6
    assert evidence.heldout.precision == evidence.heldout.recall == evidence.heldout.f1 == 1
    assert evidence.synthetic_contract_evidence is True
    assert evidence.customer_evidence is False
    assert missing_observation_evaluation_identity_matches(evidence)

    public_bytes = canonical_json_bytes(evidence)
    for prohibited in (
        b"deleted_record",
        b"original_record",
        b"source_row_key",
        b"selection_digest",
        b"target_rank",
        b"aggregate_value",
        b"cohort_mean",
    ):
        assert prohibited not in public_bytes


def test_evaluation_evidence_round_trips_and_is_reproducible() -> None:
    case_ids = evaluation_case_ids("heldout")
    with heldout_missing_observation_cases(
        freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
        case_ids=case_ids,
    ):
        first = run_missing_observation_evaluation()
    with heldout_missing_observation_cases(
        freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
        case_ids=case_ids,
    ):
        second = run_missing_observation_evaluation()
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    parsed = MissingObservationEvaluationEvidenceV1.model_validate(
        parse_canonical_json(canonical_json_bytes(first))
    )
    assert parsed == first


def test_checked_in_evaluation_evidence_is_current_and_public_only() -> None:
    data = (REPO_ROOT / "missing_observation_evaluation_v1.json").read_bytes()
    evidence = MissingObservationEvaluationEvidenceV1.model_validate(parse_canonical_json(data))
    assert evidence.evaluation_id == "meval_51a9d73ee7d716a7"
    assert sha256_hex_of_bytes(data) == (
        "bae2d0bb65a007ba0d1c1b2e3b549e23dbf5ff123ff69bb403cf09d0cdba064a"
    )
    assert missing_observation_evaluation_identity_matches(evidence)
    assert evidence.heldout.true_positive_faults == 26
    assert evidence.heldout.false_positive_findings == 0
    assert evidence.heldout.false_negative_faults == 0


def test_gate_rejects_duplicate_cases_and_nesting() -> None:
    case_ids = evaluation_case_ids("heldout")
    with (
        pytest.raises(MissingObservationHeldoutAuthorizationError, match="duplicates"),
        heldout_missing_observation_cases(
            freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
            case_ids=case_ids + (case_ids[0],),
        ),
    ):
        pass
    with (
        heldout_missing_observation_cases(
            freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
            case_ids=case_ids,
        ),
        pytest.raises(MissingObservationHeldoutAuthorizationError, match="already active"),
        heldout_missing_observation_cases(
            freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
            case_ids=case_ids,
        ),
    ):
        pass
