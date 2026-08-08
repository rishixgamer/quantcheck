"""CLI ``ingest sec`` — hermetic offline behavior over the Milestone 4 adapter.

Every test here pre-seeds the raw cache before invoking the CLI, so none of
them can make a live network request. ``--replay-only`` is additionally
exercised to prove the offline path never even attempts one.
"""

from __future__ import annotations

import json
from pathlib import Path

from quantcheck.sec_fixture import (
    EXPECTED_SEC_EXCLUSION_COUNT,
    EXPECTED_SEC_NORMALIZED_RECORD_COUNT,
    REVIEWED_SEC_CIK,
)
from tests.cli_helpers import (
    TEST_SEC_USER_AGENT,
    invoke,
    seed_sec_cache,
    write_sec_normalization_config,
)


def test_ingest_sec_replay_only_never_touches_the_network(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    seed_sec_cache(cache_dir)
    config_path = tmp_path / "normalization.json"
    write_sec_normalization_config(config_path)
    output = tmp_path / "out"

    result = invoke(
        [
            "ingest",
            "sec",
            "--cik",
            REVIEWED_SEC_CIK,
            "--config",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--user-agent",
            TEST_SEC_USER_AGENT,
            "--output",
            str(output),
            "--dataset-name",
            "reviewed-sec",
            "--as-of-date",
            "2024-12-31",
            "--replay-only",
            "--json",
        ]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["canonical_cik"] == REVIEWED_SEC_CIK
    assert payload["from_cache"] is True
    assert payload["normalized_record_count"] == EXPECTED_SEC_NORMALIZED_RECORD_COUNT
    assert payload["excluded_record_count"] == EXPECTED_SEC_EXCLUSION_COUNT
    assert (output / "snapshot.json").exists()


def test_ingest_sec_fetch_uses_the_warm_cache(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    seed_sec_cache(cache_dir)
    config_path = tmp_path / "normalization.json"
    write_sec_normalization_config(config_path)
    output = tmp_path / "out"

    result = invoke(
        [
            "ingest",
            "sec",
            "--cik",
            REVIEWED_SEC_CIK,
            "--config",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--user-agent",
            TEST_SEC_USER_AGENT,
            "--output",
            str(output),
            "--dataset-name",
            "reviewed-sec",
            "--as-of-date",
            "2024-12-31",
            "--json",
        ]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["from_cache"] is True


def test_ingest_sec_replay_only_without_a_cache_is_a_sec_error(tmp_path: Path) -> None:
    cache_dir = tmp_path / "empty-cache"
    config_path = tmp_path / "normalization.json"
    write_sec_normalization_config(config_path)
    output = tmp_path / "out"

    result = invoke(
        [
            "ingest",
            "sec",
            "--cik",
            REVIEWED_SEC_CIK,
            "--config",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--user-agent",
            TEST_SEC_USER_AGENT,
            "--output",
            str(output),
            "--dataset-name",
            "reviewed-sec",
            "--as-of-date",
            "2024-12-31",
            "--replay-only",
            "--json",
        ]
    )
    assert result.exit_code == 4
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"


def test_ingest_sec_rejects_a_placeholder_user_agent(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    seed_sec_cache(cache_dir)
    config_path = tmp_path / "normalization.json"
    write_sec_normalization_config(config_path)
    output = tmp_path / "out"

    result = invoke(
        [
            "ingest",
            "sec",
            "--cik",
            REVIEWED_SEC_CIK,
            "--config",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--user-agent",
            "MyApp (change-me@example.com)",
            "--output",
            str(output),
            "--dataset-name",
            "reviewed-sec",
            "--as-of-date",
            "2024-12-31",
            "--replay-only",
            "--json",
        ]
    )
    assert result.exit_code == 4


def test_ingest_sec_rejects_refresh_combined_with_replay_only(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    seed_sec_cache(cache_dir)
    config_path = tmp_path / "normalization.json"
    write_sec_normalization_config(config_path)
    output = tmp_path / "out"

    result = invoke(
        [
            "ingest",
            "sec",
            "--cik",
            REVIEWED_SEC_CIK,
            "--config",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--user-agent",
            TEST_SEC_USER_AGENT,
            "--output",
            str(output),
            "--dataset-name",
            "reviewed-sec",
            "--as-of-date",
            "2024-12-31",
            "--refresh",
            "--replay-only",
            "--json",
        ]
    )
    assert result.exit_code == 2


def test_ingest_sec_output_never_contains_the_cache_directory_path(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    seed_sec_cache(cache_dir)
    config_path = tmp_path / "normalization.json"
    write_sec_normalization_config(config_path)
    output = tmp_path / "out"

    result = invoke(
        [
            "ingest",
            "sec",
            "--cik",
            REVIEWED_SEC_CIK,
            "--config",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--user-agent",
            TEST_SEC_USER_AGENT,
            "--output",
            str(output),
            "--dataset-name",
            "reviewed-sec",
            "--as-of-date",
            "2024-12-31",
            "--replay-only",
            "--json",
        ]
    )
    assert str(cache_dir) not in result.stdout
    assert str(tmp_path) not in result.stdout


def test_ingest_sec_malformed_config_is_a_user_error(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    seed_sec_cache(cache_dir)
    config_path = tmp_path / "normalization.json"
    config_path.write_text(json.dumps({"cik": REVIEWED_SEC_CIK}))
    output = tmp_path / "out"

    result = invoke(
        [
            "ingest",
            "sec",
            "--cik",
            REVIEWED_SEC_CIK,
            "--config",
            str(config_path),
            "--cache-dir",
            str(cache_dir),
            "--user-agent",
            TEST_SEC_USER_AGENT,
            "--output",
            str(output),
            "--dataset-name",
            "reviewed-sec",
            "--as-of-date",
            "2024-12-31",
            "--replay-only",
            "--json",
        ]
    )
    assert result.exit_code == 2
