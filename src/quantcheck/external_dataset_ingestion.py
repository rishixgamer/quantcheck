"""Read-only validation and normalization of externally supplied datasets.

CSV is parsed as text, while Parquet and Arrow use a lazily imported PyArrow
runtime.  No financial value is ever converted through ``float``.  All
diagnostics come from a fixed data-free catalogue: source values, exception
messages, paths, and row identifiers are never copied into them.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import importlib
import io
import os
import re
import stat
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from quantcheck.external_dataset_contract import (
    DATASET_MAPPING_V1_NAMESPACE,
    EXTERNAL_REVISION_LINEAGE_V1_NAMESPACE,
    EXTERNAL_SOURCE_ROW_V1_NAMESPACE,
    NORMALIZED_DATASET_V1_NAMESPACE,
    VALIDATION_PROFILE_V1_NAMESPACE,
    AvailabilityColumnMappingV1,
    CsvInputOptionsV1,
    DatasetMappingV1,
    DateColumnMappingV1,
    DateConstantMappingV1,
    DiagnosticV1,
    DimensionColumnMappingV1,
    ExternalDatasetFileInputV1,
    ExternalDatasetValidationProfileV1,
    ExternalInputFormatV1,
    IndependentRevisionMappingV1,
    MappedTextColumnV1,
    MappedTextConstantV1,
    NormalizedDatasetV1,
    NormalizedRowProvenanceV1,
    OptionalDateAbsentMappingV1,
    OptionalTextAbsentMappingV1,
    PeriodTypeColumnMappingV1,
    PeriodTypeConstantMappingV1,
    RevisionColumnsMappingV1,
)
from quantcheck.hashing import source_record_id, stable_id
from quantcheck.json_types import (
    CanonicalizationError,
    canonical_decimal_string,
    parse_canonical_date,
    parse_canonical_decimal,
)
from quantcheck.point_in_time import AmbiguousRevisionHistoryError, build_dataset_snapshot
from quantcheck.schemas import Dimension, FinancialFact, SourceReference

__all__ = [
    "ExternalDatasetValidationError",
    "dataset_mapping_id",
    "load_external_file",
    "load_external_rows",
    "normalize_external_file",
    "normalize_external_rows",
    "normalized_dataset_identity_matches",
    "profile_external_file",
    "profile_external_rows",
    "validation_profile_identity_matches",
]

_CHUNK_SIZE = 1024 * 1024
_ARROW_BATCH_SIZE = 65_536
_LOCAL_PATH_PATTERN = re.compile(r"^(?:/|~|[A-Za-z]:[\\/])")
_SEQUENCE_PATTERN = re.compile(r"^[1-9][0-9]*$")

_MESSAGES: dict[str, str] = {
    "input.file_missing": "the configured input is not a readable regular file",
    "input.symlink_rejected": "symbolic-link inputs are rejected at the integrity boundary",
    "input.pyarrow_unavailable": "PyArrow is required for this declared input format",
    "input.malformed": "the input container is malformed, truncated, or not in the declared format",
    "input.invalid_utf8": "CSV input must be valid UTF-8",
    "input.csv_header": "CSV input must have one nonempty unique header row",
    "input.csv_row_width": "a CSV row does not match the declared header width",
    "integrity.sha256_required": "a production normalization requires expected_sha256",
    "integrity.sha256_mismatch": "input bytes do not match expected_sha256",
    "integrity.size_mismatch": "input bytes do not match expected_size_bytes",
    "integrity.changed_during_read": "the input changed while it was being validated",
    "schema.missing_column": "a column required by the mapping is absent",
    "schema.unmapped_column": "the input has a column not admitted by the mapping policy",
    "schema.duplicate_column": "input column names must be unique",
    "schema.float_value_column": "the financial value column must not use binary floating point",
    "schema.unsupported_value_type": "the financial value column must be decimal, integer, or text",
    "normalization.row_not_mapping": "a Python input row must be a string-keyed mapping",
    "normalization.missing_value": "a required mapped value is absent or null",
    "normalization.invalid_text": "a mapped text value violates the canonical token contract",
    "normalization.invalid_decimal": "a financial value is not an exact supported decimal input",
    "normalization.invalid_date": "a mapped date is not an exact day-level calendar date",
    "normalization.invalid_period_type": "a period label is not explicitly mapped",
    "normalization.invalid_period_shape": "period type, start, and end do not form a valid fact",
    "normalization.invalid_dimension": "a mapped dimension member is absent or invalid",
    "normalization.invalid_source_locator": "public source provenance must not be a local path",
    "normalization.invalid_revision": "revision lineage and sequence are incomplete or invalid",
    "normalization.duplicate_source_identity": (
        "two rows resolve to the same deterministic source identity"
    ),
    "normalization.canonical_contract": (
        "a row does not satisfy the canonical FinancialFact contract"
    ),
    "revision.ambiguous_history": "source-declared revision history is contradictory or ambiguous",
}


class ExternalDatasetValidationError(ValueError):
    """Raised with a data-free message and an attached machine-readable profile."""

    def __init__(self, profile: ExternalDatasetValidationProfileV1) -> None:
        super().__init__("external dataset validation failed")
        self.profile = profile


@dataclass(frozen=True, slots=True)
class _RowError(Exception):
    code: str
    field: str | None = None


@dataclass(frozen=True, slots=True)
class _NormalizedRow:
    fact: FinancialFact
    provenance: NormalizedRowProvenanceV1


@dataclass(frozen=True, slots=True)
class _InputMetadata:
    input_format: ExternalInputFormatV1
    source_sha256: str | None
    source_size_bytes: int | None


@dataclass(frozen=True, slots=True)
class _ReadResult:
    rows: tuple[_NormalizedRow, ...]
    row_count: int
    valid_record_count: int
    metadata: _InputMetadata


class _Diagnostics:
    def __init__(self, maximum: int) -> None:
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
            raise ValueError("max_diagnostics must be a positive integer")
        self.maximum = maximum
        self.items: list[DiagnosticV1] = []
        self.error_count = 0
        self.warning_count = 0

    def add(
        self,
        code: str,
        *,
        stage: str,
        field: str | None = None,
        row_number: int | None = None,
        severity: str = "error",
    ) -> None:
        if severity == "error":
            self.error_count += 1
        elif severity == "warning":
            self.warning_count += 1
        else:  # pragma: no cover - internal call-site guard
            raise ValueError("diagnostic severity must be error or warning")
        if len(self.items) >= self.maximum:
            return
        self.items.append(
            DiagnosticV1(
                code=code,
                severity=cast(Any, severity),
                stage=cast(Any, stage),
                field=field,
                row_number=row_number,
                message=_MESSAGES[code],
            )
        )

    @property
    def omitted_count(self) -> int:
        return self.error_count + self.warning_count - len(self.items)


def dataset_mapping_id(mapping: DatasetMappingV1) -> str:
    """Return the stable identity of the complete versioned mapping contract."""
    return stable_id(prefix="dmap", namespace=DATASET_MAPPING_V1_NAMESPACE, payload=mapping)


def _mapped_column(mapping: object) -> str | None:
    return mapping.column if isinstance(mapping, MappedTextColumnV1 | DateColumnMappingV1) else None


def _required_columns(mapping: DatasetMappingV1) -> tuple[str, ...]:
    columns: set[str] = {mapping.value.column, mapping.source_row_id.column}
    for item in (
        mapping.entity_id,
        mapping.entity_name,
        mapping.concept_namespace,
        mapping.concept,
        mapping.unit,
        mapping.period_start,
        mapping.period_end,
        mapping.filed_on,
        mapping.form,
        mapping.accession_or_equivalent,
        mapping.source_name,
        mapping.source_locator,
    ):
        column = _mapped_column(item)
        if column is not None:
            columns.add(column)
    if isinstance(mapping.period_type, PeriodTypeColumnMappingV1):
        columns.add(mapping.period_type.column)
    if isinstance(mapping.available_on, AvailabilityColumnMappingV1):
        columns.add(mapping.available_on.column)
    for dimension in mapping.dimensions:
        columns.add(dimension.member_column)
    if isinstance(mapping.revision_lineage, RevisionColumnsMappingV1):
        columns.add(mapping.revision_lineage.lineage_column)
        columns.add(mapping.revision_lineage.sequence_column)
    return tuple(sorted(columns))


def _validate_columns(
    columns: Sequence[str],
    mapping: DatasetMappingV1,
    diagnostics: _Diagnostics,
) -> bool:
    if len(set(columns)) != len(columns):
        diagnostics.add("schema.duplicate_column", stage="schema")
        return False
    present = set(columns)
    required = set(_required_columns(mapping))
    for column in sorted(required - present):
        diagnostics.add("schema.missing_column", stage="schema", field=column)
    if mapping.unmapped_columns == "reject":
        for column in sorted(present - required):
            diagnostics.add("schema.unmapped_column", stage="schema", field=column)
    return diagnostics.error_count == 0


def _require(row: Mapping[str, object], column: str, field: str) -> object:
    if column not in row or row[column] is None:
        raise _RowError("normalization.missing_value", field)
    return row[column]


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise _RowError("normalization.invalid_text", field)
    try:
        # Source/canonical token validation is applied by a tiny strict model.
        return MappedTextConstantV1(value=value).value
    except ValidationError as exc:
        raise _RowError("normalization.invalid_text", field) from exc


def _mapped_text(mapping: object, row: Mapping[str, object], field: str) -> str | None:
    if isinstance(mapping, MappedTextColumnV1):
        return _text(_require(row, mapping.column, field), field)
    if isinstance(mapping, MappedTextConstantV1):
        return mapping.value
    if isinstance(mapping, OptionalTextAbsentMappingV1):
        return None
    raise AssertionError(f"unexpected text mapping: {type(mapping).__name__}")


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool | float):
        raise _RowError("normalization.invalid_decimal", "value")
    try:
        if isinstance(value, Decimal):
            canonical_decimal_string(value)
            return value
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, str):
            return parse_canonical_decimal(value)
    except CanonicalizationError as exc:
        raise _RowError("normalization.invalid_decimal", "value") from exc
    raise _RowError("normalization.invalid_decimal", "value")


def _date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        raise _RowError("normalization.invalid_date", field)
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return parse_canonical_date(value)
        except CanonicalizationError as exc:
            raise _RowError("normalization.invalid_date", field) from exc
    raise _RowError("normalization.invalid_date", field)


def _mapped_date(mapping: object, row: Mapping[str, object], field: str) -> date | None:
    if isinstance(mapping, DateColumnMappingV1):
        return _date(_require(row, mapping.column, field), field)
    if isinstance(mapping, DateConstantMappingV1):
        return mapping.value
    if isinstance(mapping, OptionalDateAbsentMappingV1):
        return None
    raise AssertionError(f"unexpected date mapping: {type(mapping).__name__}")


def _period_type(mapping: object, row: Mapping[str, object]) -> str:
    if isinstance(mapping, PeriodTypeConstantMappingV1):
        return mapping.value
    if isinstance(mapping, PeriodTypeColumnMappingV1):
        value = _text(_require(row, mapping.column, "period_type"), "period_type")
        if value == mapping.instant_value:
            return "instant"
        if value == mapping.duration_value:
            return "duration"
    raise _RowError("normalization.invalid_period_type", "period_type")


def _sequence(value: object) -> int:
    if isinstance(value, bool):
        raise _RowError("normalization.invalid_revision", "revision_lineage")
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and _SEQUENCE_PATTERN.fullmatch(value) is not None:
        return int(value)
    raise _RowError("normalization.invalid_revision", "revision_lineage")


def _source_coordinate(
    mapping: DatasetMappingV1,
    row: Mapping[str, object],
    *,
    source_name: str,
    source_locator: str,
    source_row_id: str,
) -> tuple[str, str | None, int | None]:
    revision = mapping.revision_lineage
    if isinstance(revision, IndependentRevisionMappingV1):
        key = stable_id(
            prefix="xrow",
            namespace=EXTERNAL_SOURCE_ROW_V1_NAMESPACE,
            payload={
                "source_name": source_name,
                "source_locator": source_locator,
                "source_row_id": source_row_id,
            },
        )
        return key, None, None

    lineage_raw = row.get(revision.lineage_column)
    sequence_raw = row.get(revision.sequence_column)
    if lineage_raw is None and sequence_raw is None:
        key = stable_id(
            prefix="xrow",
            namespace=EXTERNAL_SOURCE_ROW_V1_NAMESPACE,
            payload={
                "source_name": source_name,
                "source_locator": source_locator,
                "source_row_id": source_row_id,
            },
        )
        return key, None, None
    if lineage_raw is None or sequence_raw is None:
        raise _RowError("normalization.invalid_revision", "revision_lineage")
    lineage = _text(lineage_raw, "revision_lineage")
    sequence = _sequence(sequence_raw)
    opaque_lineage = stable_id(
        prefix="xline",
        namespace=EXTERNAL_REVISION_LINEAGE_V1_NAMESPACE,
        payload={
            "source_name": source_name,
            "source_locator": source_locator,
            "source_lineage": lineage,
        },
    )
    return f"{opaque_lineage}#r{sequence}", lineage, sequence


def _dimensions(
    mappings: Sequence[DimensionColumnMappingV1],
    row: Mapping[str, object],
) -> tuple[Dimension, ...]:
    result: list[Dimension] = []
    for mapping in mappings:
        try:
            member = _text(
                _require(row, mapping.member_column, "dimensions"),
                "dimensions",
            )
            result.append(Dimension(axis=mapping.axis, member=member))
        except (ValidationError, _RowError) as exc:
            raise _RowError("normalization.invalid_dimension", "dimensions") from exc
    return tuple(result)


def _normalize_row(mapping: DatasetMappingV1, row: Mapping[str, object]) -> _NormalizedRow:
    entity_id = cast(str, _mapped_text(mapping.entity_id, row, "entity_id"))
    entity_name = _mapped_text(mapping.entity_name, row, "entity_name")
    concept_namespace = cast(str, _mapped_text(mapping.concept_namespace, row, "concept_namespace"))
    concept = cast(str, _mapped_text(mapping.concept, row, "concept"))
    value = _decimal(_require(row, mapping.value.column, "value"))
    unit = cast(str, _mapped_text(mapping.unit, row, "unit"))
    period_type = _period_type(mapping.period_type, row)
    period_start = _mapped_date(mapping.period_start, row, "period_start")
    period_end = cast(date, _mapped_date(mapping.period_end, row, "period_end"))
    filed_on = cast(date, _mapped_date(mapping.filed_on, row, "filed_on"))
    if isinstance(mapping.available_on, AvailabilityColumnMappingV1):
        available_on = _date(
            _require(row, mapping.available_on.column, "available_on"),
            "available_on",
        )
    else:
        available_on = filed_on
    form = _mapped_text(mapping.form, row, "form")
    accession = _mapped_text(
        mapping.accession_or_equivalent,
        row,
        "accession_or_equivalent",
    )
    source_name = cast(str, _mapped_text(mapping.source_name, row, "source_name"))
    source_locator = cast(str, _mapped_text(mapping.source_locator, row, "source_locator"))
    if _LOCAL_PATH_PATTERN.match(source_locator) is not None:
        raise _RowError("normalization.invalid_source_locator", "source_locator")
    source_row_id = cast(str, _mapped_text(mapping.source_row_id, row, "source_row_id"))
    source_row_key, revision_lineage, revision_sequence = _source_coordinate(
        mapping,
        row,
        source_name=source_name,
        source_locator=source_locator,
        source_row_id=source_row_id,
    )
    record_id = source_record_id(
        source_name=source_name,
        source_locator=source_locator,
        source_row_key=source_row_key,
    )
    try:
        fact = FinancialFact(
            record_id=record_id,
            entity_id=entity_id,
            entity_name=entity_name,
            concept_namespace=concept_namespace,
            concept=concept,
            value=value,
            unit=unit,
            dimensions=_dimensions(mapping.dimensions, row),
            period_type=cast(Any, period_type),
            period_start=period_start,
            period_end=period_end,
            filed_on=filed_on,
            available_on=available_on,
            form=form,
            accession_number=accession,
            source=SourceReference(
                source_name=source_name,
                source_locator=source_locator,
                source_row_key=source_row_key,
            ),
        )
    except ValidationError as exc:
        code = (
            "normalization.invalid_period_shape"
            if period_type in {"instant", "duration"}
            else "normalization.canonical_contract"
        )
        raise _RowError(code) from exc
    return _NormalizedRow(
        fact=fact,
        provenance=NormalizedRowProvenanceV1(
            record_id=record_id,
            source_row_id=source_row_id,
            source_name=source_name,
            source_locator=source_locator,
            revision_lineage=revision_lineage,
            revision_sequence=revision_sequence,
        ),
    )


def _normalize_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    mapping: DatasetMappingV1,
    diagnostics: _Diagnostics,
    validate_each_row_columns: bool,
) -> tuple[tuple[_NormalizedRow, ...], int, int]:
    normalized: list[_NormalizedRow] = []
    seen: set[str] = set()
    seen_revisions: set[tuple[str, str, str, int]] = set()
    row_count = 0
    valid_count = 0
    required = set(_required_columns(mapping))
    for row_count, supplied in enumerate(rows, start=1):
        if not isinstance(supplied, Mapping) or not all(isinstance(key, str) for key in supplied):
            diagnostics.add(
                "normalization.row_not_mapping",
                stage="normalization",
                row_number=row_count,
            )
            continue
        row = dict(supplied)
        if validate_each_row_columns:
            missing = sorted(required - set(row))
            extra = sorted(set(row) - required) if mapping.unmapped_columns == "reject" else []
            for column in missing:
                diagnostics.add(
                    "schema.missing_column",
                    stage="schema",
                    field=column,
                    row_number=row_count,
                )
            for column in extra:
                diagnostics.add(
                    "schema.unmapped_column",
                    stage="schema",
                    field=column,
                    row_number=row_count,
                )
            if missing or extra:
                continue
        try:
            item = _normalize_row(mapping, row)
        except _RowError as exc:
            diagnostics.add(
                exc.code,
                stage="normalization",
                field=exc.field,
                row_number=row_count,
            )
            continue
        provenance = item.provenance
        if provenance.revision_lineage is not None and provenance.revision_sequence is not None:
            revision_coordinate = (
                provenance.source_name,
                provenance.source_locator,
                provenance.revision_lineage,
                provenance.revision_sequence,
            )
            if revision_coordinate in seen_revisions:
                diagnostics.add(
                    "revision.ambiguous_history",
                    stage="revision",
                    row_number=row_count,
                )
                continue
            seen_revisions.add(revision_coordinate)
        if item.fact.record_id in seen:
            diagnostics.add(
                "normalization.duplicate_source_identity",
                stage="normalization",
                field="source_row_id",
                row_number=row_count,
            )
            continue
        seen.add(item.fact.record_id)
        normalized.append(item)
        valid_count += 1

    if normalized:
        try:
            build_dataset_snapshot(
                tuple(item.fact for item in normalized),
                dataset_name=mapping.dataset_name,
                as_of_date=date.max,
            )
        except AmbiguousRevisionHistoryError:
            diagnostics.add("revision.ambiguous_history", stage="revision")
    return tuple(normalized), row_count, valid_count


def _profile(
    *,
    mapping: DatasetMappingV1,
    metadata: _InputMetadata,
    row_count: int,
    valid_record_count: int,
    diagnostics: _Diagnostics,
) -> ExternalDatasetValidationProfileV1:
    body: dict[str, object] = {
        "spec_version": "quantcheck/dataset-validation-profile/v1",
        "mapping_id": dataset_mapping_id(mapping),
        "input_format": metadata.input_format,
        "source_sha256": metadata.source_sha256,
        "source_size_bytes": metadata.source_size_bytes,
        "row_count": row_count,
        "valid_record_count": valid_record_count,
        "error_count": diagnostics.error_count,
        "warning_count": diagnostics.warning_count,
        "diagnostics": tuple(diagnostics.items),
        "omitted_diagnostic_count": diagnostics.omitted_count,
        "valid": diagnostics.error_count == 0,
        "audit_claim": False,
        "benchmark_claim": False,
        "network_used": False,
        "manifest_used": False,
    }
    return ExternalDatasetValidationProfileV1.model_validate(
        {
            "validation_profile_id": stable_id(
                prefix="dprof",
                namespace=VALIDATION_PROFILE_V1_NAMESPACE,
                payload=body,
            ),
            **body,
        }
    )


def _normalized_dataset(
    mapping: DatasetMappingV1,
    rows: Sequence[_NormalizedRow],
) -> NormalizedDatasetV1:
    ordered = tuple(sorted(rows, key=lambda item: item.fact.record_id))
    body: dict[str, object] = {
        "spec_version": "quantcheck/normalized-dataset/v1",
        "mapping_id": dataset_mapping_id(mapping),
        "dataset_name": mapping.dataset_name,
        "record_count": len(ordered),
        "records": tuple(item.fact for item in ordered),
        "provenance": tuple(item.provenance for item in ordered),
    }
    return NormalizedDatasetV1.model_validate(
        {
            "normalized_dataset_id": stable_id(
                prefix="ndset",
                namespace=NORMALIZED_DATASET_V1_NAMESPACE,
                payload=body,
            ),
            **body,
        }
    )


def _hash_open_file(handle: io.BufferedReader) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        block = handle.read(_CHUNK_SIZE)
        if not block:
            break
        digest.update(block)
        size += len(block)
    handle.seek(0)
    return digest.hexdigest(), size


def _integrity_ok(
    file_input: ExternalDatasetFileInputV1,
    *,
    actual_sha256: str,
    actual_size: int,
    require_integrity: bool,
    diagnostics: _Diagnostics,
) -> bool:
    if require_integrity and file_input.expected_sha256 is None:
        diagnostics.add("integrity.sha256_required", stage="integrity")
    if file_input.expected_sha256 is not None and file_input.expected_sha256 != actual_sha256:
        diagnostics.add("integrity.sha256_mismatch", stage="integrity")
    if file_input.expected_size_bytes is not None and file_input.expected_size_bytes != actual_size:
        diagnostics.add("integrity.size_mismatch", stage="integrity")
    return diagnostics.error_count == 0


def _pyarrow() -> Any:
    return importlib.import_module("pyarrow")


def _arrow_value_type_ok(pa: Any, value_type: Any, diagnostics: _Diagnostics) -> bool:
    if pa.types.is_floating(value_type):
        diagnostics.add("schema.float_value_column", stage="schema", field="value")
        return False
    if any(
        predicate(value_type)
        for predicate in (
            pa.types.is_decimal,
            pa.types.is_integer,
            pa.types.is_string,
            pa.types.is_large_string,
        )
    ):
        return True
    diagnostics.add("schema.unsupported_value_type", stage="schema", field="value")
    return False


def _arrow_rows(
    handle: io.BufferedReader,
    *,
    file_input: ExternalDatasetFileInputV1,
    mapping: DatasetMappingV1,
    diagnostics: _Diagnostics,
) -> tuple[Iterator[Mapping[str, object]], tuple[str, ...]]:
    pa = _pyarrow()
    if file_input.input_format == "parquet":
        parquet = importlib.import_module("pyarrow.parquet")
        reader = parquet.ParquetFile(handle)
        schema = reader.schema_arrow
        columns = tuple(schema.names)
        if _validate_columns(columns, mapping, diagnostics):
            value_type = schema.field(mapping.value.column).type
            _arrow_value_type_ok(pa, value_type, diagnostics)

        def batches() -> Iterator[Mapping[str, object]]:
            for batch in reader.iter_batches(batch_size=_ARROW_BATCH_SIZE):
                yield from cast(list[dict[str, object]], batch.to_pylist())

        return batches(), columns

    ipc = importlib.import_module("pyarrow.ipc")
    reader = (
        ipc.open_file(handle)
        if file_input.input_format == "arrow_file"
        else ipc.open_stream(handle)
    )
    schema = reader.schema
    columns = tuple(schema.names)
    if _validate_columns(columns, mapping, diagnostics):
        value_type = schema.field(mapping.value.column).type
        _arrow_value_type_ok(pa, value_type, diagnostics)

    def arrow_batches() -> Iterator[Mapping[str, object]]:
        if file_input.input_format == "arrow_file":
            for index in range(reader.num_record_batches):
                batch = reader.get_batch(index)
                for row in cast(list[dict[str, object]], batch.to_pylist()):
                    yield row
        else:
            for batch in reader:
                for row in cast(list[dict[str, object]], batch.to_pylist()):
                    yield row

    return arrow_batches(), columns


def _csv_rows(
    handle: io.BufferedReader,
    *,
    options: CsvInputOptionsV1,
    mapping: DatasetMappingV1,
    diagnostics: _Diagnostics,
) -> tuple[Iterator[Mapping[str, object]], tuple[str, ...], io.TextIOWrapper]:
    text = io.TextIOWrapper(handle, encoding=options.encoding, newline="")
    reader = csv.reader(
        text,
        delimiter=options.delimiter,
        quotechar=options.quote_character,
        strict=True,
    )
    try:
        header = next(reader)
    except StopIteration:
        header = []
    if not header or any(not column for column in header) or len(set(header)) != len(header):
        diagnostics.add("input.csv_header", stage="input")
        return iter(()), tuple(header), text
    columns = tuple(header)
    if not _validate_columns(columns, mapping, diagnostics):
        return iter(()), columns, text
    null_tokens = set(options.null_tokens)

    def rows() -> Iterator[Mapping[str, object]]:
        for values in reader:
            if len(values) != len(columns):
                raise _RowError("input.csv_row_width")
            yield {
                column: (None if value in null_tokens else value)
                for column, value in zip(columns, values, strict=True)
            }

    return rows(), columns, text


def _read_file(
    path: Path,
    *,
    mapping: DatasetMappingV1,
    file_input: ExternalDatasetFileInputV1,
    diagnostics: _Diagnostics,
    require_integrity: bool,
) -> _ReadResult:
    metadata = _InputMetadata(file_input.input_format, None, None)
    try:
        if path.is_symlink():
            diagnostics.add("input.symlink_rejected", stage="input")
            return _ReadResult((), 0, 0, metadata)
        path_stat = path.stat()
        if not stat.S_ISREG(path_stat.st_mode):
            diagnostics.add("input.file_missing", stage="input")
            return _ReadResult((), 0, 0, metadata)
        with path.open("rb") as handle:
            opened_stat = os.fstat(handle.fileno())
            digest, size = _hash_open_file(handle)
            metadata = _InputMetadata(file_input.input_format, digest, size)
            if not _integrity_ok(
                file_input,
                actual_sha256=digest,
                actual_size=size,
                require_integrity=require_integrity,
                diagnostics=diagnostics,
            ):
                return _ReadResult((), 0, 0, metadata)

            text_wrapper: io.TextIOWrapper | None = None
            try:
                if file_input.input_format == "csv":
                    assert file_input.csv is not None
                    rows, _, text_wrapper = _csv_rows(
                        handle,
                        options=file_input.csv,
                        mapping=mapping,
                        diagnostics=diagnostics,
                    )
                else:
                    try:
                        rows, _ = _arrow_rows(
                            handle,
                            file_input=file_input,
                            mapping=mapping,
                            diagnostics=diagnostics,
                        )
                    except ModuleNotFoundError:
                        diagnostics.add("input.pyarrow_unavailable", stage="input")
                        return _ReadResult((), 0, 0, metadata)
                if diagnostics.error_count:
                    return _ReadResult((), 0, 0, metadata)
                try:
                    normalized, row_count, valid_count = _normalize_rows(
                        rows,
                        mapping=mapping,
                        diagnostics=diagnostics,
                        validate_each_row_columns=False,
                    )
                except _RowError as exc:
                    diagnostics.add(exc.code, stage="input")
                    normalized, row_count, valid_count = (), 0, 0
            finally:
                if text_wrapper is not None:
                    with contextlib.suppress(ValueError, OSError):
                        text_wrapper.detach()
            final_stat = os.fstat(handle.fileno())
            if (
                opened_stat.st_dev,
                opened_stat.st_ino,
                opened_stat.st_size,
                opened_stat.st_mtime_ns,
            ) != (
                final_stat.st_dev,
                final_stat.st_ino,
                final_stat.st_size,
                final_stat.st_mtime_ns,
            ):
                diagnostics.add("integrity.changed_during_read", stage="integrity")
            return _ReadResult(tuple(normalized), row_count, valid_count, metadata)
    except FileNotFoundError:
        diagnostics.add("input.file_missing", stage="input")
    except UnicodeDecodeError:
        diagnostics.add("input.invalid_utf8", stage="input")
    except (csv.Error, OSError, ValueError, TypeError):
        diagnostics.add("input.malformed", stage="input")
    return _ReadResult((), 0, 0, metadata)


def _load_file(
    path: Path,
    mapping: DatasetMappingV1,
    file_input: ExternalDatasetFileInputV1,
    *,
    max_diagnostics: int,
    require_integrity: bool,
) -> tuple[ExternalDatasetValidationProfileV1, NormalizedDatasetV1 | None]:
    diagnostics = _Diagnostics(max_diagnostics)
    result = _read_file(
        path,
        mapping=mapping,
        file_input=file_input,
        diagnostics=diagnostics,
        require_integrity=require_integrity,
    )
    profile = _profile(
        mapping=mapping,
        metadata=result.metadata,
        row_count=result.row_count,
        valid_record_count=result.valid_record_count,
        diagnostics=diagnostics,
    )
    dataset = _normalized_dataset(mapping, result.rows) if profile.valid else None
    return profile, dataset


def load_external_file(
    path: Path,
    mapping: DatasetMappingV1,
    file_input: ExternalDatasetFileInputV1,
    *,
    max_diagnostics: int = 100,
) -> tuple[ExternalDatasetValidationProfileV1, NormalizedDatasetV1]:
    """Validate and normalize one integrity-pinned file without modifying it."""
    profile, dataset = _load_file(
        path,
        mapping,
        file_input,
        max_diagnostics=max_diagnostics,
        require_integrity=True,
    )
    if dataset is None:
        raise ExternalDatasetValidationError(profile)
    return profile, dataset


def profile_external_file(
    path: Path,
    mapping: DatasetMappingV1,
    file_input: ExternalDatasetFileInputV1,
    *,
    max_diagnostics: int = 100,
) -> ExternalDatasetValidationProfileV1:
    """Dry-run a file with no audit, benchmark, network, or manifest claim."""
    profile, _ = _load_file(
        path,
        mapping,
        file_input,
        max_diagnostics=max_diagnostics,
        require_integrity=False,
    )
    return profile


def normalize_external_file(
    path: Path,
    mapping: DatasetMappingV1,
    file_input: ExternalDatasetFileInputV1,
    *,
    max_diagnostics: int = 100,
) -> NormalizedDatasetV1:
    """Return deterministic canonical facts from one integrity-pinned file."""
    return load_external_file(
        path,
        mapping,
        file_input,
        max_diagnostics=max_diagnostics,
    )[1]


def _load_rows(
    rows: Iterable[Mapping[str, object]],
    mapping: DatasetMappingV1,
    *,
    max_diagnostics: int,
) -> tuple[ExternalDatasetValidationProfileV1, NormalizedDatasetV1 | None]:
    diagnostics = _Diagnostics(max_diagnostics)
    normalized, row_count, valid_count = _normalize_rows(
        rows,
        mapping=mapping,
        diagnostics=diagnostics,
        validate_each_row_columns=True,
    )
    profile = _profile(
        mapping=mapping,
        metadata=_InputMetadata("python", None, None),
        row_count=row_count,
        valid_record_count=valid_count,
        diagnostics=diagnostics,
    )
    dataset = _normalized_dataset(mapping, normalized) if profile.valid else None
    return profile, dataset


def load_external_rows(
    rows: Iterable[Mapping[str, object]],
    mapping: DatasetMappingV1,
    *,
    max_diagnostics: int = 100,
) -> tuple[ExternalDatasetValidationProfileV1, NormalizedDatasetV1]:
    """Validate and normalize caller-owned Python mappings without mutation."""
    profile, dataset = _load_rows(rows, mapping, max_diagnostics=max_diagnostics)
    if dataset is None:
        raise ExternalDatasetValidationError(profile)
    return profile, dataset


def profile_external_rows(
    rows: Iterable[Mapping[str, object]],
    mapping: DatasetMappingV1,
    *,
    max_diagnostics: int = 100,
) -> ExternalDatasetValidationProfileV1:
    """Dry-run Python mappings and discard normalized records afterward."""
    profile, _ = _load_rows(rows, mapping, max_diagnostics=max_diagnostics)
    return profile


def normalize_external_rows(
    rows: Iterable[Mapping[str, object]],
    mapping: DatasetMappingV1,
    *,
    max_diagnostics: int = 100,
) -> NormalizedDatasetV1:
    """Return deterministic canonical facts from caller-owned Python mappings."""
    return load_external_rows(rows, mapping, max_diagnostics=max_diagnostics)[1]


def normalized_dataset_identity_matches(dataset: NormalizedDatasetV1) -> bool:
    body = {
        name: getattr(dataset, name)
        for name in type(dataset).model_fields
        if name != "normalized_dataset_id"
    }
    return dataset.normalized_dataset_id == stable_id(
        prefix="ndset",
        namespace=NORMALIZED_DATASET_V1_NAMESPACE,
        payload=body,
    )


def validation_profile_identity_matches(
    profile: ExternalDatasetValidationProfileV1,
) -> bool:
    body = {
        name: getattr(profile, name)
        for name in type(profile).model_fields
        if name != "validation_profile_id"
    }
    return profile.validation_profile_id == stable_id(
        prefix="dprof",
        namespace=VALIDATION_PROFILE_V1_NAMESPACE,
        payload=body,
    )
