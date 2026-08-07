"""Bounded properties and static safety checks for the SEC adapter."""

from __future__ import annotations

import ast
import inspect
from datetime import date
from pathlib import Path
from typing import Any, cast

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import quantcheck as q
from quantcheck import sec_adapter, sec_fixture

_SETTINGS = settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)


@given(st.integers(min_value=1, max_value=9_999_999_999))
@_SETTINGS
def test_every_supported_integer_cik_round_trips_to_ten_ascii_digits(cik: int) -> None:
    canonical = q.normalize_cik(cik)
    assert len(canonical) == 10
    assert canonical.isascii() and canonical.isdigit()
    assert int(canonical) == cik
    assert q.normalize_cik(canonical) == canonical


@given(st.permutations(list(range(5))))
@_SETTINGS
def test_asset_source_entry_permutations_preserve_normalized_logic(
    permutation: list[int],
) -> None:
    payload = cast(dict[str, Any], q.reviewed_sec_fixture_payload())
    entries = cast(
        list[dict[str, Any]],
        payload["facts"]["us-gaap"]["Assets"]["units"]["USD"],
    )
    payload["facts"]["us-gaap"]["Assets"]["units"]["USD"] = [
        entries[index] for index in permutation
    ]
    baseline = q.normalize_companyfacts(
        q.canonical_reviewed_sec_fixture_bytes(), q.reviewed_sec_normalization_config()
    )
    permuted = q.normalize_companyfacts(
        q.canonical_json_bytes(payload), q.reviewed_sec_normalization_config()
    )
    assert q.canonical_json_bytes(permuted.records) == q.canonical_json_bytes(baseline.records)
    assert permuted.exclusions == baseline.exclusions


@given(st.booleans())
@_SETTINGS
def test_exact_duplicate_multiplicity_uses_stable_non_position_ordinals(reverse: bool) -> None:
    payload = cast(dict[str, Any], q.reviewed_sec_fixture_payload())
    entries = cast(
        list[dict[str, Any]],
        payload["facts"]["us-gaap"]["Assets"]["units"]["USD"],
    )
    entries.append(dict(entries[0]))
    if reverse:
        entries.reverse()
    result = q.normalize_companyfacts(
        q.canonical_json_bytes(payload), q.reviewed_sec_normalization_config()
    )
    zero_assets = [
        record for record in result.records if record.concept == "Assets" and record.value == 0
    ]
    assert len(zero_assets) == 2
    assert len({record.record_id for record in zero_assets}) == 2


@given(st.sampled_from([date(2023, 11, 2), date(2023, 11, 3), date(2023, 11, 4)]))
@_SETTINGS
def test_sec_availability_uses_the_existing_inclusive_day_boundary(cutoff: date) -> None:
    result = q.normalize_companyfacts(
        q.canonical_reviewed_sec_fixture_bytes(), q.reviewed_sec_normalization_config()
    )
    snapshot = q.build_sec_snapshot(result, dataset_name="sec", as_of_date=cutoff)
    expected = {record.record_id for record in result.records if record.filed_on <= cutoff}
    assert {record.record_id for record in snapshot.records} == expected


def test_different_cache_directories_do_not_change_normalized_snapshot_or_audit_ids(
    tmp_path: Path,
) -> None:
    raw = q.canonical_reviewed_sec_fixture_bytes()
    outputs = []
    for name in ("one", "deep/two"):
        cache = q.SecRawCache(tmp_path / name)
        cache.accept(320193, url=q.companyfacts_url(320193), raw_bytes=raw)
        replayed = cache.load(320193)
        normalized = q.normalize_companyfacts(
            replayed.raw_bytes, q.reviewed_sec_normalization_config()
        )
        snapshot = q.build_sec_snapshot(
            normalized,
            dataset_name="sec-reviewed",
            as_of_date=date(2024, 12, 31),
        )
        outputs.append(
            (
                q.canonical_json_bytes(normalized.records),
                snapshot.snapshot_id,
                q.sanitize_for_audit(snapshot).audit_input_id,
            )
        )
    assert outputs[0] == outputs[1]


def test_sec_modules_have_no_random_uuid_builtin_hash_object_id_or_live_network_library() -> None:
    for module in (sec_adapter, sec_fixture):
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
        assert "random" not in imported
        assert "uuid" not in imported
        assert "requests" not in imported
        assert "urllib3" not in imported
        assert {"hash", "id", "uuid1", "uuid4", "getrandbits", "random"}.isdisjoint(called)


def test_sec_source_identity_has_no_path_clock_or_runtime_parameter() -> None:
    prohibited = {
        "path",
        "cache_dir",
        "retrieved_at",
        "generated_at",
        "cwd",
        "username",
        "hostname",
        "runtime",
    }
    assert prohibited.isdisjoint(inspect.signature(q.sec_source_row_id).parameters)
    source = inspect.getsource(q.sec_source_row_id)
    assert "time(" not in source
    assert "monotonic" not in source
