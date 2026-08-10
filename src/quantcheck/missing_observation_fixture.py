"""Deterministic development/validation/held-out Missing Observations cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from quantcheck.hashing import canonical_sha256, dataset_snapshot_id, source_record_id, stable_id
from quantcheck.missing_observation_contract import (
    MISSING_OBSERVATION_SPEC_VERSION,
    MissingnessMechanism,
    MissingObservationDetectorConfigV1,
    MissingObservationInjectionConfigV1,
    MissingObservationSeriesKeyV1,
    build_expected_observation,
    build_missing_observation_detector_config,
    expectation_context_for_mechanism,
)
from quantcheck.missing_observation_gate import (
    active_missing_observation_heldout_authorization,
)
from quantcheck.schemas import DatasetSnapshot, FinancialFact, SourceReference

__all__ = [
    "EVALUATION_MECHANISMS",
    "MISSING_OBSERVATION_EVALUATION_CONFIGURATION_HASH",
    "MISSING_OBSERVATION_EVALUATION_FREEZE_ID",
    "MissingObservationEvaluationCase",
    "build_missing_observation_evaluation_case",
    "evaluation_case_id",
    "evaluation_case_ids",
    "evaluation_case_seed",
]

EvaluationPartition = Literal["development", "validation", "heldout"]

EVALUATION_MECHANISMS: tuple[MissingnessMechanism, ...] = (
    "random_missingness",
    "periodic_reporting_gap",
    "entity_dependent_missingness",
    "concept_dependent_missingness",
    "survivorship_like_filtering",
    "source_feed_outage",
)
_PARTITION_CODES: dict[EvaluationPartition, str] = {
    "development": "a17",
    "validation": "b29",
    "heldout": "c43",
}
_PARTITION_SEED_BASES: dict[EvaluationPartition, int] = {
    "development": 10,
    "validation": 110,
    "heldout": 2010,
}
_PERIOD_ENDS = (
    date(2023, 3, 31),
    date(2023, 6, 30),
    date(2023, 9, 30),
    date(2023, 12, 31),
)
_SNAPSHOT_AS_OF = date(2024, 3, 31)
_GENERATOR_VERSION = "quantcheck/missing-observation-evaluation-fixture/v1"


def evaluation_case_seed(partition: EvaluationPartition, mechanism: MissingnessMechanism) -> int:
    return _PARTITION_SEED_BASES[partition] + EVALUATION_MECHANISMS.index(mechanism)


def evaluation_case_id(partition: EvaluationPartition, mechanism: MissingnessMechanism) -> str:
    return stable_id(
        prefix="mcase",
        namespace="quantcheck/missing-observation-evaluation-case/v1",
        payload={
            "generator_version": _GENERATOR_VERSION,
            "partition": partition,
            "mechanism": mechanism,
            "seed": evaluation_case_seed(partition, mechanism),
            "severity": "medium",
        },
    )


def evaluation_case_ids(partition: EvaluationPartition) -> tuple[str, ...]:
    return tuple(
        sorted(evaluation_case_id(partition, mechanism) for mechanism in EVALUATION_MECHANISMS)
    )


def _configuration_body() -> dict[str, object]:
    partitions: tuple[EvaluationPartition, ...] = (
        "development",
        "validation",
        "heldout",
    )
    return {
        "spec_version": "quantcheck/missing-observation-evaluation/v1",
        "generator_version": _GENERATOR_VERSION,
        "mechanisms": EVALUATION_MECHANISMS,
        "partitions": tuple(
            {
                "partition": partition,
                "case_ids": evaluation_case_ids(partition),
                "seeds": tuple(
                    evaluation_case_seed(partition, mechanism)
                    for mechanism in EVALUATION_MECHANISMS
                ),
            }
            for partition in partitions
        ),
        "severity": "medium",
        "entity_count": 2,
        "concept_count": 2,
        "period_count": len(_PERIOD_ENDS),
        "snapshot_as_of": _SNAPSHOT_AS_OF,
    }


MISSING_OBSERVATION_EVALUATION_CONFIGURATION_HASH = canonical_sha256(_configuration_body())
MISSING_OBSERVATION_EVALUATION_FREEZE_ID = stable_id(
    prefix="mefreeze",
    namespace="quantcheck/missing-observation-evaluation-freeze/v1",
    payload=_configuration_body(),
)


@dataclass(frozen=True, slots=True)
class MissingObservationEvaluationCase:
    case_id: str
    partition: EvaluationPartition
    mechanism: MissingnessMechanism
    clean_snapshot: DatasetSnapshot
    detector_config: MissingObservationDetectorConfigV1
    injection_config: MissingObservationInjectionConfigV1


def _require_heldout_authorized(case_id: str) -> None:
    authorization = active_missing_observation_heldout_authorization()
    if (
        authorization is None
        or authorization.freeze_id != MISSING_OBSERVATION_EVALUATION_FREEZE_ID
        or authorization.case_ids != evaluation_case_ids("heldout")
        or not authorization.permits(case_id)
    ):
        raise PermissionError(
            "held-out Missing Observations records require the frozen complete-case authorization"
        )


def build_missing_observation_evaluation_case(
    partition: EvaluationPartition,
    mechanism: MissingnessMechanism,
) -> MissingObservationEvaluationCase:
    """Materialize one deterministic case, guarding held-out records at execution."""
    case_id = evaluation_case_id(partition, mechanism)
    if partition == "heldout":
        _require_heldout_authorized(case_id)
    code = _PARTITION_CODES[partition]
    context = expectation_context_for_mechanism(mechanism)
    source_name = f"synthetic-missing-feed-{code}"
    source_locator = f"synthetic://missing-evaluation/{code}"
    dataset_name = f"missing-evaluation-{code}-{EVALUATION_MECHANISMS.index(mechanism)}"
    records: list[FinancialFact] = []
    expectations = []
    entity_ids = (f"ME{code.upper()}01", f"ME{code.upper()}02")
    concepts = ("Revenue", "OperatingIncome")
    for entity_index, entity_id in enumerate(entity_ids):
        for concept_index, concept in enumerate(concepts):
            series = MissingObservationSeriesKeyV1(
                entity_id=entity_id,
                concept_namespace="synthetic-gaap",
                concept=concept,
                unit="USD",
                dimensions=(),
                period_type="instant",
                source_name=source_name,
                source_locator=source_locator,
            )
            for period_index, period_end in enumerate(_PERIOD_ENDS):
                expected_by = period_end + timedelta(days=45)
                row_key = f"{entity_id}:{concept}:{period_end.isoformat()}"
                source = SourceReference(
                    source_name=source_name,
                    source_locator=source_locator,
                    source_row_key=row_key,
                )
                records.append(
                    FinancialFact(
                        record_id=source_record_id(
                            source_name=source_name,
                            source_locator=source_locator,
                            source_row_key=row_key,
                        ),
                        entity_id=entity_id,
                        entity_name=f"Synthetic entity {entity_index + 1}",
                        concept_namespace="synthetic-gaap",
                        concept=concept,
                        value=Decimal(
                            (entity_index + 1) * 1000 + (concept_index + 1) * 100 + period_index + 1
                        ),
                        unit="USD",
                        dimensions=(),
                        period_type="instant",
                        period_start=None,
                        period_end=period_end,
                        filed_on=expected_by,
                        available_on=expected_by,
                        form="SYN",
                        accession_number=f"{code}-{entity_index}-{concept_index}-{period_index}",
                        source=source,
                    )
                )
                expectations.append(
                    build_expected_observation(
                        context=context,
                        series=series,
                        period_start=None,
                        period_end=period_end,
                        expected_by=expected_by,
                        evidence_reference=(f"contract://missing-evaluation/{code}/{context}"),
                    )
                )
    clean_snapshot = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name=dataset_name,
            as_of_date=_SNAPSHOT_AS_OF,
            records=records,
        ),
        dataset_name=dataset_name,
        as_of_date=_SNAPSHOT_AS_OF,
        records=tuple(records),
    )
    detector_config = build_missing_observation_detector_config(tuple(expectations))
    injection_fields: dict[str, object] = {
        "spec_version": MISSING_OBSERVATION_SPEC_VERSION,
        "mechanism": mechanism,
        "severity": "medium",
        "seed": evaluation_case_seed(partition, mechanism),
        "max_targets": 100,
        "survivorship_entity_ids": (),
        "outage_period_start": None,
        "outage_period_end": None,
    }
    if mechanism == "survivorship_like_filtering":
        injection_fields["survivorship_entity_ids"] = (entity_ids[0],)
    if mechanism == "source_feed_outage":
        injection_fields["outage_period_start"] = _PERIOD_ENDS[1]
        injection_fields["outage_period_end"] = _PERIOD_ENDS[2]
    injection_config = MissingObservationInjectionConfigV1.model_validate(injection_fields)
    return MissingObservationEvaluationCase(
        case_id=case_id,
        partition=partition,
        mechanism=mechanism,
        clean_snapshot=clean_snapshot,
        detector_config=detector_config,
        injection_config=injection_config,
    )
