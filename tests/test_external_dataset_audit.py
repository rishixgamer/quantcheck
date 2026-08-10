"""Production workflow: normalize -> snapshot -> sanitize -> selected detectors."""

from __future__ import annotations

import inspect
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path

from quantcheck.external_dataset_audit import (
    audit_external_file,
    audit_external_rows,
    audit_normalized_dataset,
    external_audit_report_identity_matches,
)
from quantcheck.external_dataset_ingestion import load_external_rows
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import (
    explicit_revision_rows,
    mapping,
    pinned_file_input,
    policy,
    row,
    write_csv,
)


def test_end_to_end_duplicate_audit_uses_no_manifest_or_injection() -> None:
    first = row("duplicate-source-a", accession="same-accession")
    second = row("duplicate-source-b", accession="same-accession")
    artifacts = audit_external_rows(
        [first, second],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(enabled_detectors=("duplicate_observation",)),
    )
    report = artifacts.public_report
    assert report.finding_count == 1
    assert tuple(run.detector for run in report.detector_runs) == ("duplicate_observation",)
    assert report.manifest_used is False
    assert report.fault_injection_used is False
    assert report.benchmark_claim is False
    assert report.network_used is False
    assert report.policy_id == artifacts.policy.policy_id
    assert report.policy_content_hash == artifacts.policy.policy_content_hash
    assert external_audit_report_identity_matches(report)


def test_lookahead_audit_runs_on_sanitized_point_in_time_input() -> None:
    supplied = row(
        "lookahead-source",
        filed_date="2024-04-30",
        available_date="2024-03-31",
    )
    artifacts = audit_external_rows(
        [supplied],
        mapping=mapping(),
        as_of_date=date(2024, 4, 15),
        policy=policy(enabled_detectors=("lookahead_timestamp",)),
    )
    assert artifacts.public_report.finding_count == 1
    assert artifacts.audit_input.records[0].available_on == date(2024, 3, 31)
    assert artifacts.audit_input.records[0].filed_on == date(2024, 4, 30)


def test_revision_selection_occurs_before_sanitization_and_audit() -> None:
    artifacts = audit_external_rows(
        explicit_revision_rows(),
        mapping=mapping(),
        as_of_date=date(2024, 5, 15),
        policy=policy(enabled_detectors=("duplicate_observation",)),
    )
    assert artifacts.normalized_dataset.record_count == 2
    assert len(artifacts.snapshot.records) == 1
    assert len(artifacts.audit_input.records) == 1
    assert artifacts.public_report.source_record_count == 2
    assert artifacts.public_report.snapshot_record_count == 1


def test_selected_detector_order_is_normalized_and_explicit() -> None:
    artifacts = audit_external_rows(
        [row("row-1")],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(enabled_detectors=("unit_drift", "duplicate_observation")),
    )
    assert tuple(run.detector for run in artifacts.public_report.detector_runs) == (
        "duplicate_observation",
        "unit_drift",
    )


def test_public_report_omits_private_source_row_and_entity_name() -> None:
    source_secret = "PRIVATE_SOURCE_ROW_102938"
    entity_secret = "PRIVATE_ENTITY_NAME_564738"
    artifacts = audit_external_rows(
        [row(source_secret, entity_name=entity_secret)],
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(enabled_detectors=("duplicate_observation",)),
    )
    public_bytes = canonical_json_bytes(artifacts.public_report)
    assert source_secret.encode() not in public_bytes
    assert entity_secret.encode() not in public_bytes
    assert b"source_row_key" not in public_bytes
    assert b"revision_lineage" not in public_bytes
    assert b"manifest" in public_bytes  # explicit false boundary declaration


def test_public_report_is_deterministic_under_input_reordering() -> None:
    supplied = [
        row("row-a", amount=Decimal("100")),
        row(
            "row-b",
            amount=Decimal("120"),
            period_start="2024-04-01",
            period_end="2024-06-30",
            filed_date="2024-07-30",
            available_date="2024-07-31",
        ),
    ]
    audit_policy = policy(enabled_detectors=("duplicate_observation", "lookahead_timestamp"))
    first = audit_external_rows(
        supplied,
        mapping=mapping(),
        as_of_date=date(2024, 8, 31),
        policy=audit_policy,
    )
    second = audit_external_rows(
        list(reversed(supplied)),
        mapping=mapping(),
        as_of_date=date(2024, 8, 31),
        policy=audit_policy,
    )
    assert canonical_json_bytes(first.public_report) == canonical_json_bytes(second.public_report)


def test_customer_file_is_byte_and_metadata_unchanged_by_audit(tmp_path: Path) -> None:
    path = tmp_path / "customer.csv"
    write_csv(path, [row("row-1")])
    before_bytes = path.read_bytes()
    before_stat = path.stat()
    audit_external_file(
        path,
        mapping=mapping(),
        file_input=pinned_file_input(path, "csv"),
        as_of_date=date(2024, 6, 30),
        policy=policy(enabled_detectors=("duplicate_observation",)),
    )
    after_stat = path.stat()
    assert path.read_bytes() == before_bytes
    assert after_stat.st_mtime_ns == before_stat.st_mtime_ns
    assert after_stat.st_size == before_stat.st_size


def test_python_inputs_are_unchanged_by_complete_audit() -> None:
    supplied = [row("row-1")]
    before = deepcopy(supplied)
    audit_external_rows(
        supplied,
        mapping=mapping(),
        as_of_date=date(2024, 6, 30),
        policy=policy(enabled_detectors=("duplicate_observation",)),
    )
    assert supplied == before


def test_audit_normalized_dataset_rejects_an_unrelated_mapping() -> None:
    profile, normalized = load_external_rows([row("row-1")], mapping())
    other_document = mapping().model_dump(mode="python")
    other_document["dataset_name"] = "different-customer-dataset"
    other_mapping = type(mapping()).model_validate(other_document)
    try:
        audit_normalized_dataset(
            normalized,
            mapping=other_mapping,
            validation_profile=profile,
            as_of_date=date(2024, 6, 30),
            policy=policy(enabled_detectors=("duplicate_observation",)),
        )
    except ValueError as exc:
        assert "mapping identity mismatch" in str(exc)
    else:  # pragma: no cover - integrity regression guard
        raise AssertionError("unrelated mapping was accepted")


def test_audit_api_has_no_manifest_seed_severity_or_injector_parameter() -> None:
    for function in (audit_external_file, audit_external_rows, audit_normalized_dataset):
        parameters = set(inspect.signature(function).parameters)
        assert not parameters & {"manifest", "seed", "severity", "injector", "fault_profile"}
        assert "policy" in parameters
        assert "detector_config" not in parameters
