"""Shared helpers for Recovery Phase 9 CLI tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from typer.testing import CliRunner, Result

import quantcheck as q
from quantcheck.cli import app
from quantcheck.sec_adapter import SecRawCache, companyfacts_url
from quantcheck.sec_fixture import (
    REVIEWED_SEC_CIK,
    canonical_reviewed_sec_fixture_bytes,
    reviewed_sec_normalization_config,
)
from tests.benchmark_support import (
    case_of as _case_of,
)
from tests.benchmark_support import (
    duplicate_profile,
    lookahead_profile,
    revision_overwrite_profile,
    single_profile_config,
    unit_drift_profile,
)

runner = CliRunner()

#: A stable, non-placeholder, contact-bearing user agent for hermetic SEC tests.
TEST_SEC_USER_AGENT = "QuantCheck-CLI-Test research@quantcheck-recovery-harness.dev"

_PROFILE_BUILDERS: dict[str, Callable[..., q.BenchmarkProfile]] = {
    "lookahead_timestamp": lookahead_profile,
    "unit_drift": unit_drift_profile,
    "duplicate_observation": duplicate_profile,
    "revision_overwrite": revision_overwrite_profile,
}


def invoke(args: list[str]) -> Result:
    """Invoke the Typer app exactly as the console script would."""
    return runner.invoke(app, args)


def write_case_config(path: Path, case: q.BenchmarkCaseConfig) -> None:
    path.write_bytes(q.canonical_json_bytes(case))


def fault_case(profile_name: str) -> q.BenchmarkCaseConfig:
    builder = _PROFILE_BUILDERS[profile_name]
    config = single_profile_config(builder())
    return _case_of(config, profile_name, kind="fault")


def clean_control_case(profile_name: str) -> q.BenchmarkCaseConfig:
    builder = _PROFILE_BUILDERS[profile_name]
    severity = "low" if profile_name == "revision_overwrite" else "medium"
    config = single_profile_config(
        builder(control=q.BenchmarkCleanControl(severity=severity, seed=0))
    )
    return _case_of(config, profile_name, kind="clean_control")


def seed_sec_cache(cache_dir: Path) -> None:
    """Populate an offline SEC raw cache with the reviewed curated fixture.

    No test using this helper ever touches the network: the cache already
    holds an accepted response before the adapter is invoked.
    """
    cache = SecRawCache(cache_dir)
    cache.accept(
        REVIEWED_SEC_CIK,
        url=companyfacts_url(REVIEWED_SEC_CIK),
        raw_bytes=canonical_reviewed_sec_fixture_bytes(),
    )


def write_sec_normalization_config(path: Path) -> None:
    """Write the exact reviewed SEC normalization allowlist as CLI-input JSON.

    Reusing ``reviewed_sec_normalization_config()`` (rather than hand-rolling
    a second allowlist) keeps this fixture's expected normalized/excluded
    counts consistent with the rest of the Milestone 4 test suite.
    """
    normalization = reviewed_sec_normalization_config()
    config = {
        "cik": normalization.cik,
        "concepts": [
            {
                "taxonomy": item.taxonomy,
                "concept": item.concept,
                "unit": item.unit,
                "period_type": item.period_type,
            }
            for item in normalization.concepts
        ],
        "forms": list(normalization.forms),
        "filed_from": normalization.filed_from.isoformat(),
        "filed_through": normalization.filed_through.isoformat(),
    }
    path.write_text(json.dumps(config))


def all_json_bytes_under(root: Path) -> bytes:
    """Concatenate every JSON file under a directory, for privacy scans."""
    chunks = [path.read_bytes() for path in sorted(root.rglob("*.json")) if path.is_file()]
    return b"\n".join(chunks)
