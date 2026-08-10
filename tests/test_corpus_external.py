"""The externally supplied private/vendor boundary.

The property under test is that an external dataset is never *required* and its
content never *quoted*. Every test here builds a fake external root under
``tmp_path``: no licensed data exists in this repository, and none is needed.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from quantcheck.corpus_external import (
    EXTERNAL_CORPUS_MANIFEST_NAME,
    EXTERNAL_CORPUS_ROOT_ENV,
    ExternalCorpusError,
    external_corpus_root,
    external_unit_records,
    external_unit_spec,
    read_external_declarations,
    redacted_external_summary,
)
from quantcheck.corpus_registry import corpus_unit_ids
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.schemas import Dimension, FinancialFact, SourceReference
from quantcheck.serialization import canonical_json_bytes

_UNIT_ID = "cunit_0123456789abcdef"


def _record(row_key: str = "vendor-row-1") -> FinancialFact:
    return FinancialFact(
        record_id="rec_00112233445566aa",
        entity_id="CIK0009999999",
        entity_name="Confidential Vendor Issuer",
        concept_namespace="us-gaap",
        concept="Revenues",
        value=Decimal("123456.78"),
        unit="USD",
        dimensions=(Dimension(axis="Segment", member="Total"),),
        period_type="duration",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 3, 31),
        filed_on=date(2024, 5, 2),
        available_on=date(2024, 5, 2),
        form="10-Q",
        accession_number="0009999999-24-000001",
        source=SourceReference(
            source_name="vendor-feed",
            source_locator="vendor://point-in-time",
            source_row_key=row_key,
        ),
    )


def _declaration(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "corpus_unit_id": _UNIT_ID,
        "unit_name": "vendor-pit-extract",
        "partition": "development",
        "audit_dataset_name": "vendorset01",
        "source_name": "vendor-feed",
        "source_locator": "vendor://point-in-time",
        "snapshot_as_of_date": "2024-06-30",
        "research_as_of_date": "2024-05-15",
        "records_file": "records.json",
        "records_sha256": "0" * 64,
        "record_count": 1,
        "supported_fault_profiles": ["duplicate_observation"],
        "inclusion_rule_ids": ["IR-01", "IR-08"],
        "publisher": "Example Data Vendor",
        "notes": "Licensed extract; not redistributable.",
    }
    fields.update(overrides)
    return fields


def _write_root(tmp_path: Path, **overrides: object) -> Path:
    records = (_record(),)
    payload = canonical_json_bytes(records)
    (tmp_path / "records.json").write_bytes(payload)
    fields: dict[str, object] = {"records_sha256": sha256_hex_of_bytes(payload)}
    fields.update(overrides)
    declaration = _declaration(**fields)
    (tmp_path / EXTERNAL_CORPUS_MANIFEST_NAME).write_text(
        json.dumps({"units": [declaration]}), encoding="utf-8"
    )
    return tmp_path


class TestExternalDataIsNeverRequired:
    def test_the_committed_corpus_declares_no_external_unit(self) -> None:
        # Every unit the registry knows about is committed and in-repository.
        assert len(corpus_unit_ids()) == 12

    def test_an_unset_root_is_the_default_and_not_an_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(EXTERNAL_CORPUS_ROOT_ENV, raising=False)
        assert external_corpus_root() is None

    def test_the_root_may_be_supplied_by_environment_or_argument(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv(EXTERNAL_CORPUS_ROOT_ENV, str(tmp_path))
        assert external_corpus_root() == tmp_path
        # An explicit argument always wins, so a test can never be steered by
        # an environment variable it did not set.
        other = tmp_path / "other"
        assert external_corpus_root(other) == other

    def test_no_repository_file_points_at_an_external_dataset(self) -> None:
        source = Path(__file__).resolve().parent.parent / "src" / "quantcheck"
        for path in source.glob("corpus_*.py"):
            text = path.read_text()
            assert "vendor://" not in text
            assert "/Users/" not in text


class TestDeclarationsAreValidatedNotTrusted:
    def test_a_valid_root_reads_back(self, tmp_path: Path) -> None:
        declarations = read_external_declarations(_write_root(tmp_path))
        assert len(declarations) == 1
        assert declarations[0].corpus_unit_id == _UNIT_ID

    def test_a_missing_manifest_is_an_explicit_error(self, tmp_path: Path) -> None:
        with pytest.raises(ExternalCorpusError, match=EXTERNAL_CORPUS_MANIFEST_NAME):
            read_external_declarations(tmp_path)

    def test_a_malformed_unit_id_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ExternalCorpusError, match="malformed external corpus unit id"):
            read_external_declarations(_write_root(tmp_path, corpus_unit_id="not-a-unit"))

    def test_an_unsupported_declaration_field_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ExternalCorpusError, match="unsupported fields"):
            read_external_declarations(_write_root(tmp_path, secret_api_key="hunter2"))

    def test_a_traversing_records_file_name_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ExternalCorpusError, match="plain file name"):
            read_external_declarations(_write_root(tmp_path, records_file="../escape.json"))

    def test_a_malformed_digest_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ExternalCorpusError, match="lowercase SHA-256 digest"):
            read_external_declarations(_write_root(tmp_path, records_sha256="ZZ"))

    def test_a_nonpositive_record_count_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ExternalCorpusError, match="positive integer"):
            read_external_declarations(_write_root(tmp_path, record_count=0))


class TestRecordsAreVerifiedBeforeUse:
    def test_records_load_when_the_digest_matches(self, tmp_path: Path) -> None:
        root = _write_root(tmp_path)
        declaration = read_external_declarations(root)[0]
        records = external_unit_records(root, declaration)
        assert len(records) == 1
        assert records[0].concept == "Revenues"

    def test_drifted_bytes_are_refused_rather_than_admitted(self, tmp_path: Path) -> None:
        root = _write_root(tmp_path)
        declaration = read_external_declarations(root)[0]
        (root / "records.json").write_bytes(canonical_json_bytes((_record("changed"),)))
        with pytest.raises(ExternalCorpusError, match="declared digest"):
            external_unit_records(root, declaration)

    def test_a_missing_records_file_is_an_explicit_error(self, tmp_path: Path) -> None:
        root = _write_root(tmp_path)
        declaration = read_external_declarations(root)[0]
        (root / "records.json").unlink()
        with pytest.raises(ExternalCorpusError, match="records file is missing"):
            external_unit_records(root, declaration)

    def test_a_record_count_disagreement_is_refused(self, tmp_path: Path) -> None:
        records = (_record("a"), _record("b"))
        payload = canonical_json_bytes(records)
        (tmp_path / "records.json").write_bytes(payload)
        declaration_fields = _declaration(
            records_sha256=sha256_hex_of_bytes(payload), record_count=5
        )
        (tmp_path / EXTERNAL_CORPUS_MANIFEST_NAME).write_text(
            json.dumps({"units": [declaration_fields]}), encoding="utf-8"
        )
        declaration = read_external_declarations(tmp_path)[0]
        with pytest.raises(ExternalCorpusError, match="declared"):
            external_unit_records(tmp_path, declaration)


class TestNothingLicensedReachesARepositoryArtifact:
    def test_an_external_unit_spec_carries_no_record_derived_content(self, tmp_path: Path) -> None:
        declaration = read_external_declarations(_write_root(tmp_path))[0]
        spec = external_unit_spec(declaration)
        assert spec.provenance.source_class == "external_private"
        assert spec.provenance.in_repository is False
        assert spec.provenance.redistributable is False
        assert spec.diversity is None
        assert spec.content_hash is None

    def test_the_spec_serializes_without_any_issuer_or_value(self, tmp_path: Path) -> None:
        declaration = read_external_declarations(_write_root(tmp_path))[0]
        payload = canonical_json_bytes(external_unit_spec(declaration)).decode()
        record = _record()
        assert record.entity_id not in payload
        assert record.entity_name is not None
        assert record.entity_name not in payload
        assert "123456.78" not in payload
        assert record.record_id not in payload
        assert record.accession_number is not None
        assert record.accession_number not in payload

    def test_the_redacted_summary_is_identity_and_a_count(self, tmp_path: Path) -> None:
        declaration = read_external_declarations(_write_root(tmp_path))[0]
        summary = redacted_external_summary(declaration)
        assert set(summary) == {
            "corpus_unit_id",
            "partition",
            "source_class",
            "license_tier",
            "in_repository",
            "record_count",
        }
        assert summary["record_count"] == 1

    def test_the_schema_refuses_an_external_unit_that_publishes_content(
        self, tmp_path: Path
    ) -> None:
        declaration = read_external_declarations(_write_root(tmp_path))[0]
        spec = external_unit_spec(declaration)
        with pytest.raises(ValidationError, match="must not publish record-derived content"):
            type(spec).model_validate({**spec.model_dump(), "content_hash": "a" * 64})
