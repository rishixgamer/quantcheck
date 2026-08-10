"""Large-file, malformed-container, and raw-byte integrity gates."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

import quantcheck.external_dataset_ingestion as ingestion
from quantcheck.external_dataset_contract import (
    CsvInputOptionsV1,
    ExternalDatasetFileInputV1,
)
from quantcheck.external_dataset_ingestion import (
    ExternalDatasetValidationError,
    load_external_file,
    normalize_external_file,
    profile_external_file,
)
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import (
    mapping,
    pinned_file_input,
    row,
    write_arrow,
    write_csv,
)


def _large_rows(count: int) -> list[dict[str, object]]:
    return [
        row(
            f"large-row-{index:06d}",
            amount=Decimal(index),
            entity=f"ENTITY-{index % 97:03d}",
        )
        for index in range(count)
    ]


def test_large_csv_stream_validates_and_normalizes(tmp_path: Path) -> None:
    path = tmp_path / "large.csv"
    write_csv(path, _large_rows(10_000))
    profile, dataset = load_external_file(path, mapping(), pinned_file_input(path, "csv"))
    assert profile.valid is True
    assert profile.row_count == profile.valid_record_count == 10_000
    assert dataset.record_count == 10_000


def test_large_parquet_crosses_arrow_batch_boundary(tmp_path: Path) -> None:
    path = tmp_path / "large.parquet"
    write_arrow(path, _large_rows(66_000), "parquet")
    profile = profile_external_file(path, mapping(), pinned_file_input(path, "parquet"))
    assert profile.valid is True
    assert profile.row_count == profile.valid_record_count == 66_000


def test_production_normalization_requires_an_expected_digest(tmp_path: Path) -> None:
    path = tmp_path / "facts.csv"
    write_csv(path, [row("row-1")])
    file_input = ExternalDatasetFileInputV1(
        input_format="csv",
        csv=CsvInputOptionsV1(null_tokens=("",)),
    )
    with pytest.raises(ExternalDatasetValidationError) as caught:
        normalize_external_file(path, mapping(), file_input)
    assert caught.value.profile.diagnostics[0].code == "integrity.sha256_required"


def test_dry_run_may_discover_digest_before_production_pin(tmp_path: Path) -> None:
    path = tmp_path / "facts.csv"
    write_csv(path, [row("row-1")])
    profile = profile_external_file(
        path,
        mapping(),
        ExternalDatasetFileInputV1(
            input_format="csv",
            csv=CsvInputOptionsV1(null_tokens=("",)),
        ),
    )
    assert profile.valid is True
    assert profile.source_sha256 == sha256_hex_of_bytes(path.read_bytes())


def test_sha256_mismatch_is_rejected_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "not-even-csv.csv"
    path.write_bytes(b"CUSTOMER_VALUE_SHOULD_NEVER_BE_PARSED")
    profile = profile_external_file(
        path,
        mapping(),
        ExternalDatasetFileInputV1(
            input_format="csv",
            expected_sha256="0" * 64,
            csv=CsvInputOptionsV1(),
        ),
    )
    assert profile.diagnostics[0].code == "integrity.sha256_mismatch"
    assert b"CUSTOMER_VALUE" not in canonical_json_bytes(profile)


def test_size_mismatch_is_machine_readable(tmp_path: Path) -> None:
    path = tmp_path / "facts.csv"
    write_csv(path, [row("row-1")])
    valid = pinned_file_input(path, "csv")
    profile = profile_external_file(
        path,
        mapping(),
        ExternalDatasetFileInputV1(
            input_format="csv",
            expected_sha256=valid.expected_sha256,
            expected_size_bytes=path.stat().st_size + 1,
            csv=valid.csv,
        ),
    )
    assert profile.diagnostics[0].code == "integrity.size_mismatch"


@pytest.mark.parametrize("input_format", ["parquet", "arrow_file", "arrow_stream"])
def test_truncated_arrow_container_is_rejected(
    tmp_path: Path,
    input_format: str,
) -> None:
    path = tmp_path / f"truncated.{input_format}"
    write_arrow(path, [row("row-1")], input_format)
    raw = path.read_bytes()
    path.write_bytes(raw[: max(1, len(raw) // 3)])
    profile = profile_external_file(
        path,
        mapping(),
        pinned_file_input(path, input_format),
    )
    assert profile.valid is False
    assert profile.diagnostics[0].code == "input.malformed"


def test_malformed_csv_quoting_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "malformed.csv"
    path.write_bytes(b'entity,amount\n"unterminated,100\n')
    profile = profile_external_file(path, mapping(), pinned_file_input(path, "csv"))
    assert profile.valid is False
    assert profile.diagnostics[0].code in {"input.malformed", "schema.missing_column"}


def test_invalid_utf8_csv_is_rejected_without_quoting_bytes(tmp_path: Path) -> None:
    path = tmp_path / "invalid.csv"
    path.write_bytes(b"entity,amount\n\xff,100\n")
    profile = profile_external_file(path, mapping(), pinned_file_input(path, "csv"))
    assert profile.valid is False
    assert profile.diagnostics[0].code in {"input.invalid_utf8", "schema.missing_column"}
    assert b"\xff" not in canonical_json_bytes(profile)


def test_missing_file_diagnostic_contains_no_path(tmp_path: Path) -> None:
    path = tmp_path / "PRIVATE_CUSTOMER_FILENAME.csv"
    profile = profile_external_file(
        path,
        mapping(),
        ExternalDatasetFileInputV1(
            input_format="csv",
            csv=CsvInputOptionsV1(),
        ),
    )
    serialized = canonical_json_bytes(profile)
    assert profile.diagnostics[0].code == "input.file_missing"
    assert b"PRIVATE_CUSTOMER_FILENAME" not in serialized
    assert str(tmp_path).encode() not in serialized


def test_symlink_input_is_rejected_at_integrity_boundary(tmp_path: Path) -> None:
    target = tmp_path / "target.csv"
    link = tmp_path / "link.csv"
    write_csv(target, [row("row-1")])
    link.symlink_to(target)
    profile = profile_external_file(
        link,
        mapping(),
        ExternalDatasetFileInputV1(
            input_format="csv",
            csv=CsvInputOptionsV1(null_tokens=("",)),
        ),
    )
    assert profile.diagnostics[0].code == "input.symlink_rejected"


def test_missing_pyarrow_is_a_fixed_diagnostic_not_import_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "facts.parquet"
    write_arrow(path, [row("row-1")], "parquet")

    def unavailable() -> object:
        raise ModuleNotFoundError("private dependency detail")

    monkeypatch.setattr(ingestion, "_pyarrow", unavailable)
    profile = profile_external_file(path, mapping(), pinned_file_input(path, "parquet"))
    assert profile.diagnostics[0].code == "input.pyarrow_unavailable"
    assert b"private dependency detail" not in canonical_json_bytes(profile)
