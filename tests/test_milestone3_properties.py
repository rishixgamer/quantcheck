"""Bounded properties and static safety checks for Recovery Phase 3."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from types import ModuleType

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import quantcheck as q
from quantcheck import (
    lookahead_contract,
    lookahead_detection,
    lookahead_injection,
    lookahead_manifest,
    lookahead_replay,
    lookahead_research,
    lookahead_scoring,
)
from tests.lookahead_support import reviewed_lookahead_case

_SETTINGS = settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@given(
    st.integers(min_value=1, max_value=500),
    st.sampled_from([Decimal("0.02"), Decimal("0.05"), Decimal("0.10")]),
    st.integers(min_value=1, max_value=50),
)
@_SETTINGS
def test_target_count_is_always_positive_bounded_and_uses_ceiling(
    eligible: int, fraction: Decimal, cap: int
) -> None:
    count = q.lookahead_target_count(
        eligible_count=eligible,
        target_fraction=fraction,
        max_targets=cap,
    )
    assert 1 <= count <= min(eligible, cap)
    if count < min(eligible, cap):
        assert Decimal(count) >= Decimal(eligible) * fraction


@given(st.integers(min_value=0, max_value=10_000))
@_SETTINGS
def test_same_seed_always_produces_identical_selected_truth(seed: int) -> None:
    first = reviewed_lookahead_case(seed=seed)
    second = reviewed_lookahead_case(seed=seed)
    assert q.canonical_json_bytes(first.manifest) == q.canonical_json_bytes(second.manifest)
    assert q.canonical_json_bytes(first.audit_report) == q.canonical_json_bytes(second.audit_report)


@given(st.permutations(list(range(13))))
@settings(max_examples=20, deadline=None)
def test_full_pipeline_is_independent_of_clean_record_permutation(
    permutation: list[int],
) -> None:
    baseline = reviewed_lookahead_case()
    records = tuple(baseline.clean.records[index] for index in permutation)
    permuted = q.DatasetSnapshot(
        snapshot_id=baseline.clean.snapshot_id,
        dataset_name=baseline.clean.dataset_name,
        as_of_date=baseline.clean.as_of_date,
        records=records,
    )
    corrupted, manifest = q.inject_lookahead(permuted, baseline.config)
    report = q.detect_lookahead(q.sanitize_for_audit(corrupted))
    score = q.score_lookahead(report, manifest)
    repaired = q.manifest_assisted_exact_replay(corrupted, manifest)
    assert q.canonical_json_bytes(corrupted) == q.canonical_json_bytes(baseline.corrupted)
    assert q.canonical_json_bytes(manifest) == q.canonical_json_bytes(baseline.manifest)
    assert q.canonical_json_bytes(report) == q.canonical_json_bytes(baseline.audit_report)
    assert q.canonical_json_bytes(score) == q.canonical_json_bytes(baseline.score)
    assert q.canonical_json_bytes(repaired) == q.canonical_json_bytes(baseline.clean)


def test_mapping_insertion_order_does_not_change_new_artifact_identifiers() -> None:
    forward = {"alpha": 1, "beta": {"x": 2, "y": 3}}
    backward = {"beta": {"y": 3, "x": 2}, "alpha": 1}
    assert q.lookahead_finding_id(finding_body=forward) == q.lookahead_finding_id(
        finding_body=backward
    )
    assert q.fault_manifest_id(manifest_body=forward) == q.fault_manifest_id(manifest_body=backward)


def test_new_namespaces_collision_separate_an_identical_payload() -> None:
    payload = {"same": "payload"}
    identifiers = {
        q.lookahead_finding_id(finding_body=payload),
        q.fault_manifest_id(manifest_body=payload),
        q.lookahead_audit_report_id(report_body=payload),
        q.lookahead_score_report_id(score_body=payload),
        q.lookahead_research_result_id(result_body=payload),
        q.lookahead_impact_id(impact_body=payload),
    }
    assert len(identifiers) == 6


@pytest.mark.parametrize(
    "module",
    [
        lookahead_contract,
        lookahead_detection,
        lookahead_injection,
        lookahead_manifest,
        lookahead_replay,
        lookahead_research,
        lookahead_scoring,
    ],
)
def test_no_milestone3_module_calls_uuid_builtin_hash_id_or_random(module: ModuleType) -> None:
    source = inspect.getsource(module)
    tree = ast.parse(source)
    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)
    assert "uuid" not in imported
    assert "random" not in imported
    assert {"hash", "id", "uuid1", "uuid4", "getrandbits", "random"}.isdisjoint(called)
