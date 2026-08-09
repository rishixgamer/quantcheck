"""Shared builders for the Recovery Phase 11 release-evidence tests.

Every helper here that needs a reserved final seed opens the authorization
itself and closes it again, so no test can leave the gate open for the next
one. ``assert_gate_closed`` makes that explicit where it matters.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import quantcheck as q

REPO_ROOT = Path(__file__).resolve().parent.parent


def assert_gate_closed() -> None:
    """Assert no final-seed authorization is active in this context."""
    assert q.active_final_seed_authorization() is None
    for seed in q.RESERVED_FINAL_SEEDS:
        assert not q.final_seed_authorized(seed)


def authorized_release_config() -> q.BenchmarkConfig:
    """Build the frozen release configuration and close the gate again."""
    config = q.build_authorized_release_config(release_candidate_id="test-candidate")
    assert_gate_closed()
    return config


def freeze_record(
    *,
    repo_root: Path | None = None,
    package_version: str = "0.1.0",
    python_requirement: str = ">=3.12,<3.13",
) -> q.ReleaseFreezeRecord:
    """Build a release freeze record against the real repository."""
    record = q.build_authorized_release_freeze(
        repo_root=repo_root or REPO_ROOT,
        package_version=package_version,
        python_requirement=python_requirement,
    )
    assert_gate_closed()
    return record


def repo_copy(destination: Path) -> Path:
    """Copy every frozen release input into a scratch repository root.

    Tamper tests need to modify a frozen input without touching the real
    working tree, so they operate on this copy.
    """
    for relative in q.FROZEN_SOURCE_FILES:
        source = REPO_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return destination


def written_freeze(destination_root: Path, record: q.ReleaseFreezeRecord) -> Path:
    """Persist a freeze record and return its path."""
    path = destination_root / q.RELEASE_FREEZE_RECORD_NAME
    q.write_release_freeze_record(record, destination=path)
    return path
