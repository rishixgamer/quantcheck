"""Bounded properties and static safety checks for Unit Drift."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from types import ModuleType

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import quantcheck as q
from quantcheck import (
    unit_drift_contract,
    unit_drift_detection,
    unit_drift_injection,
    unit_drift_manifest,
    unit_drift_math,
    unit_drift_replay,
    unit_drift_research,
    unit_drift_scoring,
    unit_drift_series,
)
from tests.unit_drift_support import unit_drift_records, unit_drift_snapshot

_SETTINGS = settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@given(st.integers(min_value=0, max_value=10_000))
@_SETTINGS
def test_same_seed_is_byte_deterministic(seed: int) -> None:
    clean = unit_drift_snapshot(unit_drift_records())
    config = q.UnitDriftInjectionConfig(severity="medium", seed=seed)
    first = q.inject_unit_drift(clean, config)
    second = q.inject_unit_drift(clean, config)
    assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)


@given(st.integers(min_value=0, max_value=10_000))
@_SETTINGS
def test_input_order_never_changes_injection(seed: int) -> None:
    clean = unit_drift_snapshot(unit_drift_records())
    reversed_clean = q.DatasetSnapshot(
        snapshot_id=clean.snapshot_id,
        dataset_name=clean.dataset_name,
        as_of_date=clean.as_of_date,
        records=tuple(reversed(clean.records)),
    )
    config = q.UnitDriftInjectionConfig(severity="high", seed=seed)
    assert q.canonical_json_bytes(q.inject_unit_drift(clean, config)) == q.canonical_json_bytes(
        q.inject_unit_drift(reversed_clean, config)
    )


@given(
    st.integers(min_value=1, max_value=200),
    st.sampled_from([Decimal("0.02"), Decimal("0.05"), Decimal("0.10")]),
    st.integers(min_value=1, max_value=20),
)
@_SETTINGS
def test_target_count_is_positive_and_bounded(
    eligible_count: int,
    fraction: Decimal,
    cap: int,
) -> None:
    count = q.unit_drift_target_count(
        eligible_count=eligible_count,
        target_fraction=fraction,
        max_targets=cap,
    )
    assert 1 <= count <= eligible_count
    assert count <= cap


@given(
    st.integers(min_value=-(10**12), max_value=10**12).filter(lambda value: value != 0),
    st.sampled_from(["low", "medium", "high"]),
)
@_SETTINGS
def test_scale_arithmetic_is_exact_decimal(value: int, severity: q.UnitDriftSeverity) -> None:
    profile = q.unit_drift_severity_profile(severity)
    mutation = q.UnitDriftMutation(
        original_value=Decimal(value),
        corrupted_value=Decimal(value) * profile.scale_factor,
        scale_factor=profile.scale_factor,
    )
    assert mutation.corrupted_value / mutation.scale_factor == mutation.original_value
    assert isinstance(mutation.corrupted_value, Decimal)


@given(st.integers(min_value=0, max_value=1000))
@_SETTINGS
def test_injection_detection_replay_do_not_mutate_clean_input(seed: int) -> None:
    clean = unit_drift_snapshot(unit_drift_records())
    before = q.canonical_json_bytes(clean)
    corrupted, manifest = q.inject_unit_drift(
        clean, q.UnitDriftInjectionConfig(severity="medium", seed=seed)
    )
    report = q.detect_unit_drift(q.sanitize_for_audit(corrupted), q.UnitDriftDetectorConfig())
    q.score_unit_drift(report, manifest)
    q.manifest_assisted_exact_unit_drift_replay(corrupted, manifest)
    assert q.canonical_json_bytes(clean) == before


@given(st.integers(min_value=0, max_value=1000))
@_SETTINGS
def test_manifest_and_public_artifacts_round_trip(seed: int) -> None:
    clean = unit_drift_snapshot(unit_drift_records())
    corrupted, manifest = q.inject_unit_drift(
        clean, q.UnitDriftInjectionConfig(severity="medium", seed=seed)
    )
    report = q.detect_unit_drift(q.sanitize_for_audit(corrupted), q.UnitDriftDetectorConfig())
    for model in (manifest, report):
        restored = type(model).model_validate(q.parse_canonical_json(q.canonical_json_bytes(model)))
        assert restored == model


def test_new_modules_use_no_random_uuid_builtin_hash_id_or_float_conversion() -> None:
    modules: tuple[ModuleType, ...] = (
        unit_drift_contract,
        unit_drift_detection,
        unit_drift_injection,
        unit_drift_manifest,
        unit_drift_math,
        unit_drift_replay,
        unit_drift_research,
        unit_drift_scoring,
        unit_drift_series,
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
