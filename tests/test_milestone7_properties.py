"""Bounded properties and static safety checks for Revision Overwrite."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from types import ModuleType

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import quantcheck as q
import quantcheck.revision_overwrite_contract as contract_module
import quantcheck.revision_overwrite_detection as detection_module
import quantcheck.revision_overwrite_injection as injection_module
import quantcheck.revision_overwrite_manifest as manifest_module
import quantcheck.revision_overwrite_replay as replay_module
import quantcheck.revision_overwrite_research as research_module
import quantcheck.revision_overwrite_scoring as scoring_module
import quantcheck.revision_overwrite_series as series_module
from tests.revision_overwrite_support import focused_history, focused_snapshot

_SETTINGS = settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


def _focused_clean() -> tuple[tuple[q.FinancialFact, ...], q.DatasetSnapshot]:
    records = focused_history()
    return records, focused_snapshot(records)


@given(st.integers(min_value=0, max_value=10_000))
@_SETTINGS
def test_same_seed_is_byte_deterministic(seed: int) -> None:
    records, clean = _focused_clean()
    config = q.RevisionOverwriteInjectionConfig(severity="high", seed=seed)
    assert q.canonical_json_bytes(q.inject_revision_overwrite(clean, records, config)) == (
        q.canonical_json_bytes(q.inject_revision_overwrite(clean, records, config))
    )


@given(st.integers(min_value=0, max_value=10_000))
@_SETTINGS
def test_source_order_never_changes_units_or_injection(seed: int) -> None:
    records, clean = _focused_clean()
    reversed_records = tuple(reversed(records))
    reversed_clean = focused_snapshot(reversed_records)
    config = q.RevisionOverwriteInjectionConfig(severity="high", seed=seed)
    units = q.build_revision_history_units(
        records,
        clean_snapshot=clean,
        minimum_relative_revision_size=Decimal("0.20"),
    )
    reversed_units = q.build_revision_history_units(
        reversed_records,
        clean_snapshot=reversed_clean,
        minimum_relative_revision_size=Decimal("0.20"),
    )
    assert units == reversed_units
    assert q.canonical_json_bytes(q.inject_revision_overwrite(clean, records, config)) == (
        q.canonical_json_bytes(
            q.inject_revision_overwrite(reversed_clean, reversed_records, config)
        )
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
    count = q.revision_overwrite_target_count(
        eligible_count=eligible_count,
        target_fraction=fraction,
        max_targets=cap,
    )
    assert 1 <= count <= eligible_count
    assert count <= cap


@given(st.integers(min_value=0, max_value=10_000))
@_SETTINGS
def test_injection_detection_scoring_and_replay_do_not_mutate_inputs(seed: int) -> None:
    records, clean = _focused_clean()
    source_before = q.canonical_json_bytes(records)
    clean_before = q.canonical_json_bytes(clean)
    corrupted, manifest = q.inject_revision_overwrite(
        clean,
        records,
        q.RevisionOverwriteInjectionConfig(severity="high", seed=seed),
    )
    report = q.detect_revision_overwrite(
        q.sanitize_for_audit(corrupted), q.RevisionOverwriteDetectorConfig()
    )
    q.score_revision_overwrite(report, manifest)
    q.manifest_assisted_exact_revision_overwrite_replay(corrupted, manifest)
    assert q.canonical_json_bytes(records) == source_before
    assert q.canonical_json_bytes(clean) == clean_before


@given(st.integers(min_value=0, max_value=10_000))
@_SETTINGS
def test_private_and_public_artifacts_round_trip_canonically(seed: int) -> None:
    records, clean = _focused_clean()
    corrupted, manifest = q.inject_revision_overwrite(
        clean,
        records,
        q.RevisionOverwriteInjectionConfig(severity="high", seed=seed),
    )
    audit_input = q.sanitize_for_audit(corrupted)
    report = q.detect_revision_overwrite(audit_input, q.RevisionOverwriteDetectorConfig())
    score = q.score_revision_overwrite(report, manifest)
    for artifact in (manifest, audit_input, report, score):
        restored = type(artifact).model_validate(
            q.parse_canonical_json(q.canonical_json_bytes(artifact))
        )
        assert restored == artifact


def test_new_modules_use_no_random_uuid_builtin_hash_id_or_float_conversion() -> None:
    modules: tuple[ModuleType, ...] = (
        contract_module,
        detection_module,
        injection_module,
        manifest_module,
        replay_module,
        research_module,
        scoring_module,
        series_module,
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
