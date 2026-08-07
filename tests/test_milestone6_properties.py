"""Bounded properties and static safety checks for Duplicate Observations."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from types import ModuleType

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import quantcheck as q
import quantcheck.duplicate_fingerprint as duplicate_fingerprint_module
from quantcheck import (
    duplicate_contract,
    duplicate_detection,
    duplicate_injection,
    duplicate_manifest,
    duplicate_replay,
    duplicate_research,
    duplicate_scoring,
)
from tests.duplicate_support import duplicate_record, duplicate_snapshot, rebuild_duplicate_report

_SETTINGS = settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


def _distinct_singleton_snapshot(count: int = 6) -> q.DatasetSnapshot:
    records = tuple(duplicate_record(f"row-{i}", concept=f"Concept{i}") for i in range(count))
    return duplicate_snapshot(records)


@given(st.integers(min_value=0, max_value=10_000))
@_SETTINGS
def test_same_seed_is_byte_deterministic(seed: int) -> None:
    clean = _distinct_singleton_snapshot()
    config = q.DuplicateInjectionConfig(severity="medium", seed=seed)
    first = q.inject_duplicate_observations(clean, config)
    second = q.inject_duplicate_observations(clean, config)
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)


@given(st.integers(min_value=0, max_value=10_000))
@_SETTINGS
def test_input_order_never_changes_injection(seed: int) -> None:
    clean = _distinct_singleton_snapshot()
    reversed_clean = q.DatasetSnapshot(
        snapshot_id=clean.snapshot_id,
        dataset_name=clean.dataset_name,
        as_of_date=clean.as_of_date,
        records=tuple(reversed(clean.records)),
    )
    config = q.DuplicateInjectionConfig(severity="high", seed=seed)
    assert q.canonical_json_bytes(
        q.inject_duplicate_observations(clean, config)
    ) == q.canonical_json_bytes(q.inject_duplicate_observations(reversed_clean, config))


@given(
    st.integers(min_value=1, max_value=200),
    st.sampled_from([Decimal("0.01"), Decimal("0.05"), Decimal("0.15")]),
    st.integers(min_value=1, max_value=20),
)
@_SETTINGS
def test_target_count_is_positive_and_bounded(
    eligible_count: int, fraction: Decimal, cap: int
) -> None:
    count = q.duplicate_target_count(
        eligible_count=eligible_count, target_fraction=fraction, max_targets=cap
    )
    assert 1 <= count <= eligible_count
    assert count <= cap


@given(st.integers(min_value=0, max_value=1000))
@_SETTINGS
def test_injection_detection_replay_do_not_mutate_clean_input(seed: int) -> None:
    clean = _distinct_singleton_snapshot()
    before = q.canonical_json_bytes(clean)
    corrupted, manifest = q.inject_duplicate_observations(
        clean, q.DuplicateInjectionConfig(severity="medium", seed=seed)
    )
    report = q.detect_duplicate_observations(q.sanitize_for_audit(corrupted))
    q.score_duplicate_observations(report, manifest)
    q.manifest_assisted_exact_duplicate_replay(corrupted, manifest)
    assert q.canonical_json_bytes(clean) == before


@given(st.integers(min_value=0, max_value=1000))
@_SETTINGS
def test_manifest_and_public_artifacts_round_trip(seed: int) -> None:
    clean = _distinct_singleton_snapshot()
    corrupted, manifest = q.inject_duplicate_observations(
        clean, q.DuplicateInjectionConfig(severity="medium", seed=seed)
    )
    report = q.detect_duplicate_observations(q.sanitize_for_audit(corrupted))
    for model in (manifest, report):
        restored = type(model).model_validate(q.parse_canonical_json(q.canonical_json_bytes(model)))
        assert restored == model


@given(st.integers(min_value=0, max_value=1000))
@_SETTINGS
def test_created_record_id_is_always_distinct_from_every_original(seed: int) -> None:
    clean = _distinct_singleton_snapshot()
    corrupted, manifest = q.inject_duplicate_observations(
        clean, q.DuplicateInjectionConfig(severity="high", seed=seed)
    )
    original_ids = {record.record_id for record in clean.records}
    created_ids = {entry.created_record.record_id for entry in manifest.entries}
    assert created_ids.isdisjoint(original_ids)
    assert len(created_ids) == len(manifest.entries)


@given(st.integers(min_value=0, max_value=1000))
@_SETTINGS
def test_duplicate_findings_cannot_increase_recall(seed: int) -> None:
    clean = _distinct_singleton_snapshot()
    corrupted, manifest = q.inject_duplicate_observations(
        clean, q.DuplicateInjectionConfig(severity="high", seed=seed)
    )
    report = q.detect_duplicate_observations(q.sanitize_for_audit(corrupted))
    if not report.findings:
        return
    doubled = rebuild_duplicate_report(report, (*report.findings, report.findings[0]))
    baseline = q.score_duplicate_observations(report, manifest)
    inflated = q.score_duplicate_observations(doubled, manifest)
    assert inflated.metrics.true_positive_faults <= baseline.metrics.true_positive_faults + 0
    assert inflated.metrics.recall == baseline.metrics.recall


def test_new_modules_use_no_random_uuid_builtin_hash_id_or_float_conversion() -> None:
    modules: tuple[ModuleType, ...] = (
        duplicate_contract,
        duplicate_detection,
        duplicate_fingerprint_module,
        duplicate_injection,
        duplicate_manifest,
        duplicate_replay,
        duplicate_research,
        duplicate_scoring,
    )
    prohibited_calls = {"hash", "id", "float", "random", "uuid4"}
    for module in modules:
        source = inspect.getsource(module)
        tree = ast.parse(source)
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        )
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert {"random", "uuid"}.isdisjoint(imports)
        assert prohibited_calls.isdisjoint(calls)
