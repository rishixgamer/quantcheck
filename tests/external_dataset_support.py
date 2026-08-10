"""Shared deterministic inputs for the external-dataset production path."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from quantcheck.duplicate_contract import DUPLICATE_RULE_ID
from quantcheck.external_dataset_contract import (
    AvailabilityColumnMappingV1,
    CsvInputOptionsV1,
    DatasetMappingV1,
    DateColumnMappingV1,
    ExternalDatasetFileInputV1,
    MappedTextColumnV1,
    MappedTextConstantV1,
    PeriodTypeColumnMappingV1,
    RevisionColumnsMappingV1,
    ValueColumnMappingV1,
)
from quantcheck.external_dataset_policy_contract import (
    AuditPolicyContentV1,
    AuditPolicyV1,
    ConceptUnitExpectationV1,
    DatasetPolicyExceptionV1,
    DetectorPolicyRuleV1,
    PublicationLagExpectationV1,
    ReportingFrequencyExpectationV1,
    UnitDriftThresholdPolicyV1,
    build_audit_policy,
)
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.lookahead_contract import LOOKAHEAD_RULE_ID
from quantcheck.revision_overwrite_contract import REVISION_OVERWRITE_RULE_ID
from quantcheck.unit_drift_contract import UNIT_DRIFT_RULE_ID

COLUMNS = (
    "entity",
    "entity_name",
    "concept",
    "amount",
    "unit",
    "period_kind",
    "period_start",
    "period_end",
    "filed_date",
    "available_date",
    "form",
    "accession",
    "source_row",
    "revision_lineage",
    "revision_sequence",
)


def policy(
    *,
    enabled_detectors: tuple[str, ...] = (
        "duplicate_observation",
        "lookahead_timestamp",
        "revision_overwrite",
        "unit_drift",
    ),
    detector_action: str = "warning",
    unit_drift_threshold: Decimal = Decimal("50"),
    concept_unit_expectations: tuple[ConceptUnitExpectationV1, ...] = (),
    publication_lag_expectations: tuple[PublicationLagExpectationV1, ...] = (),
    reporting_frequency_expectations: tuple[ReportingFrequencyExpectationV1, ...] = (),
    dataset_exceptions: tuple[DatasetPolicyExceptionV1, ...] = (),
    policy_name: str = "test-external-audit-policy",
    policy_version: str = "1.0.0",
) -> AuditPolicyV1:
    rule_ids = {
        "duplicate_observation": DUPLICATE_RULE_ID,
        "lookahead_timestamp": LOOKAHEAD_RULE_ID,
        "revision_overwrite": REVISION_OVERWRITE_RULE_ID,
        "unit_drift": UNIT_DRIFT_RULE_ID,
    }
    detector_rules = tuple(
        DetectorPolicyRuleV1(
            detector=detector,  # type: ignore[arg-type]
            rule_id=rule_id,
            enabled=detector in enabled_detectors,
            action=detector_action,  # type: ignore[arg-type]
            disabled_reason=(
                None
                if detector in enabled_detectors
                else "disabled explicitly for this focused test policy"
            ),
            threshold=(
                UnitDriftThresholdPolicyV1(ratio_threshold=unit_drift_threshold)
                if detector == "unit_drift"
                else None
            ),
        )
        for detector, rule_id in rule_ids.items()
    )
    return build_audit_policy(
        AuditPolicyContentV1(
            policy_name=policy_name,
            policy_version=policy_version,
            detector_rules=detector_rules,
            concept_unit_expectations=concept_unit_expectations,
            publication_lag_expectations=publication_lag_expectations,
            reporting_frequency_expectations=reporting_frequency_expectations,
            dataset_exceptions=dataset_exceptions,
        )
    )


def mapping(*, unmapped_columns: str = "reject") -> DatasetMappingV1:
    return DatasetMappingV1(
        dataset_name="customer-financial-facts-v1",
        unmapped_columns=unmapped_columns,  # type: ignore[arg-type]
        entity_id=MappedTextColumnV1(column="entity"),
        entity_name=MappedTextColumnV1(column="entity_name"),
        concept_namespace=MappedTextConstantV1(value="us-gaap"),
        concept=MappedTextColumnV1(column="concept"),
        value=ValueColumnMappingV1(column="amount"),
        unit=MappedTextColumnV1(column="unit"),
        dimensions=(),
        period_type=PeriodTypeColumnMappingV1(
            column="period_kind",
            instant_value="I",
            duration_value="D",
        ),
        period_start=DateColumnMappingV1(column="period_start"),
        period_end=DateColumnMappingV1(column="period_end"),
        filed_on=DateColumnMappingV1(column="filed_date"),
        available_on=AvailabilityColumnMappingV1(
            column="available_date",
            evidence_reference="customer-data-dictionary-section-7",
        ),
        form=MappedTextColumnV1(column="form"),
        accession_or_equivalent=MappedTextColumnV1(column="accession"),
        source_name=MappedTextConstantV1(value="customer-warehouse"),
        source_locator=MappedTextConstantV1(value="customer://financial-facts/v1"),
        source_row_id=MappedTextColumnV1(column="source_row"),
        source_provenance_visibility="public_audit_evidence",
        revision_lineage=RevisionColumnsMappingV1(
            lineage_column="revision_lineage",
            sequence_column="revision_sequence",
        ),
    )


def dimension_free_mapping() -> DatasetMappingV1:
    return mapping()


def independent_mapping() -> DatasetMappingV1:
    document = mapping().model_dump(mode="python")
    document["revision_lineage"] = {
        "kind": "independent",
        "declaration": "source_does_not_provide_revision_lineage",
    }
    document["entity_name"] = {
        "kind": "absent",
        "reason": "source has no issuer display name",
    }
    return DatasetMappingV1.model_validate(document)


def row(
    source_row: str,
    *,
    amount: object = Decimal("100.25"),
    entity: str = "ENTITY-001",
    entity_name: str | None = "Example Customer Issuer",
    concept: str = "RevenueFromContractWithCustomerExcludingAssessedTax",
    unit: str = "USD",
    period_kind: str = "D",
    period_start: object = "2024-01-01",
    period_end: object = "2024-03-31",
    filed_date: object = "2024-04-30",
    available_date: object = "2024-05-02",
    form: str | None = "10-Q",
    accession: str | None = "0000000000-24-000001",
    revision_lineage: str | None = None,
    revision_sequence: object = None,
) -> dict[str, object]:
    return {
        "entity": entity,
        "entity_name": entity_name,
        "concept": concept,
        "amount": amount,
        "unit": unit,
        "period_kind": period_kind,
        "period_start": period_start,
        "period_end": period_end,
        "filed_date": filed_date,
        "available_date": available_date,
        "form": form,
        "accession": accession,
        "source_row": source_row,
        "revision_lineage": revision_lineage,
        "revision_sequence": revision_sequence,
    }


def reviewed_rows() -> list[dict[str, object]]:
    return [
        row("row-1"),
        row(
            "row-2",
            amount=Decimal("120.00"),
            period_start="2024-04-01",
            period_end="2024-06-30",
            filed_date="2024-07-30",
            available_date="2024-07-31",
            accession="0000000000-24-000002",
        ),
        row(
            "row-3",
            amount=Decimal("130"),
            period_start="2024-07-01",
            period_end="2024-09-30",
            filed_date="2024-10-30",
            available_date="2024-10-31",
            accession="0000000000-24-000003",
        ),
    ]


def explicit_revision_rows() -> list[dict[str, object]]:
    return [
        row(
            "revision-source-a",
            amount=Decimal("100"),
            available_date="2024-04-30",
            revision_lineage="vendor-history-9",
            revision_sequence=1,
        ),
        row(
            "revision-source-b",
            amount=Decimal("102"),
            filed_date="2024-06-01",
            available_date="2024-06-01",
            accession="0000000000-24-000009",
            revision_lineage="vendor-history-9",
            revision_sequence=2,
        ),
    ]


def csv_options() -> CsvInputOptionsV1:
    return CsvInputOptionsV1(null_tokens=("",))


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for supplied in rows:
            writer.writerow(
                {key: "" if value is None else str(value) for key, value in supplied.items()}
            )


def pinned_file_input(path: Path, input_format: str) -> ExternalDatasetFileInputV1:
    raw = path.read_bytes()
    return ExternalDatasetFileInputV1(
        input_format=input_format,  # type: ignore[arg-type]
        expected_sha256=sha256_hex_of_bytes(raw),
        expected_size_bytes=len(raw),
        csv=csv_options() if input_format == "csv" else None,
    )


def arrow_table(rows: Sequence[dict[str, object]]) -> Any:
    import pyarrow as pa

    schema = pa.schema(
        [
            pa.field("entity", pa.string(), nullable=False),
            pa.field("entity_name", pa.string()),
            pa.field("concept", pa.string(), nullable=False),
            pa.field("amount", pa.decimal128(38, 6), nullable=False),
            pa.field("unit", pa.string(), nullable=False),
            pa.field("period_kind", pa.string(), nullable=False),
            pa.field("period_start", pa.string()),
            pa.field("period_end", pa.string(), nullable=False),
            pa.field("filed_date", pa.string(), nullable=False),
            pa.field("available_date", pa.string(), nullable=False),
            pa.field("form", pa.string()),
            pa.field("accession", pa.string()),
            pa.field("source_row", pa.string(), nullable=False),
            pa.field("revision_lineage", pa.string()),
            pa.field("revision_sequence", pa.int64()),
        ]
    )
    return pa.Table.from_pylist(list(rows), schema=schema)


def write_arrow(path: Path, rows: Sequence[dict[str, object]], input_format: str) -> None:
    import pyarrow.ipc as ipc
    import pyarrow.parquet as parquet

    table = arrow_table(rows)
    if input_format == "parquet":
        parquet.write_table(table, path)  # type: ignore[no-untyped-call]
        return
    with path.open("wb") as handle:
        if input_format == "arrow_file":
            with ipc.new_file(handle, table.schema) as writer:  # type: ignore[no-untyped-call]
                writer.write_table(table)
        elif input_format == "arrow_stream":
            with ipc.new_stream(handle, table.schema) as writer:  # type: ignore[no-untyped-call]
                writer.write_table(table)
        else:  # pragma: no cover - support call-site guard
            raise ValueError(input_format)
