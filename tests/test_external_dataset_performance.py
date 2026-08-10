"""Reproducible performance-suite contracts and required measurements."""

from __future__ import annotations

from pathlib import Path

from quantcheck.external_dataset_performance import (
    ExternalAuditPerformanceReportV1,
    PerformanceEnvelopeV1,
    run_performance_benchmark,
)
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json


def test_micro_performance_suite_records_every_required_measurement(tmp_path: Path) -> None:
    envelopes = (
        PerformanceEnvelopeV1(
            label="small",
            record_count=40,
            partition_count=2,
            maximum_records_per_partition=20,
        ),
        PerformanceEnvelopeV1(
            label="medium",
            record_count=80,
            partition_count=2,
            maximum_records_per_partition=40,
        ),
        PerformanceEnvelopeV1(
            label="large",
            record_count=120,
            partition_count=3,
            maximum_records_per_partition=40,
        ),
    )
    report = run_performance_benchmark(tmp_path, envelopes=envelopes)
    assert tuple(item.label for item in report.cases) == ("small", "medium", "large")
    for item in report.cases:
        assert item.input_record_count > 0
        assert len(item.detector_runtimes) == 4
        assert item.total_runtime_ns > 0
        assert item.peak_memory_bytes > 0
        assert item.normalized_input_size_bytes > 0
        assert item.public_artifact_size_bytes > 0
        assert item.private_artifact_size_bytes >= item.normalized_input_size_bytes
        assert item.unchanged_rerun_runtime_ns > 0
        assert item.changed_partition_rerun_runtime_ns > 0
        assert item.changed_partition_executed_count == 1
        assert item.changed_partition_reused_count == item.partition_count - 1
    assert tuple(item.worker_count for item in report.large_parallel_measurements) == (1, 2, 4)
    assert len({item.logical_artifact_hash for item in report.large_parallel_measurements}) == 1
    assert b'scientific_metrics_claim":false' in canonical_json_bytes(report)


def test_performance_script_has_a_reproducible_output_contract() -> None:
    script = Path("scripts/run_performance_benchmarks.py").read_text()
    assert "--output" in script
    assert "run_performance_benchmark" in script
    assert "canonical_json_bytes" in script


def test_checked_in_baseline_and_documented_envelopes_are_current() -> None:
    path = Path("performance_baseline_v1.json")
    payload = path.read_bytes()
    report = ExternalAuditPerformanceReportV1.model_validate(parse_canonical_json(payload))
    assert canonical_json_bytes(report) == payload
    assert sha256_hex_of_bytes(payload) == (
        "0ed3fe5cb5e3b2c466208503ab2abe5c25c8e14f7a8d75614ddaa70235ebf70e"
    )
    assert tuple(item.input_record_count for item in report.cases) == (1_000, 10_000, 50_000)
    assert len({item.logical_artifact_hash for item in report.large_parallel_measurements}) == 1
    document = Path("docs/PERFORMANCE_AND_EXECUTION.md").read_text()
    for phrase in (
        "Profile first",
        "Documented envelopes",
        "complete_entity_histories_disjoint",
        "Atomic",
        "Interruption",
        "50,000",
    ):
        assert phrase.lower() in document.lower()
