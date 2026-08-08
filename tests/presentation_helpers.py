"""Shared saved-benchmark fixtures for the Recovery Phase 10 presentation tests.

Three trees are built once per session and reused, because running a benchmark
is the expensive part of these tests and none of them mutates a shared tree
in place:

* a complete 12-case smoke run (successes and clean controls);
* a mixed run containing one genuinely **failed** case; and
* a run with one **incomplete** case.

Nothing here fabricates a metric. Every number the presentation tests assert on
comes from a real run of the existing benchmark, at ordinary development and
validation seeds only.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import quantcheck as q
from tests.benchmark_support import (
    FIXED_RUNTIME,
    duplicate_profile,
    lookahead_profile,
    public_root,
)

__all__ = [
    "build_failed_benchmark",
    "build_incomplete_benchmark",
    "build_smoke_benchmark",
    "case_pre_injection_record_ids",
    "copy_public_only",
    "manifest_answer_key_strings",
    "rebuild_derived_public_artifacts",
]


def build_smoke_benchmark(root: Path) -> q.BenchmarkRunResult:
    """Run the committed 12-case offline smoke benchmark into ``root``."""
    return q.run_benchmark(q.smoke_benchmark_config(), output_root=root, runtime=FIXED_RUNTIME)


def _ineligible_unit_drift_profile() -> q.BenchmarkUnitDriftProfile:
    """A Unit Drift profile whose horizon leaves no comparable series at all.

    Only the first observation of the benchmark series is visible, so the
    frozen three-observation comparability prerequisite cannot be met. The
    resulting failure is a real eligibility failure, not a simulated one.
    """
    return q.BenchmarkUnitDriftProfile(
        fixture=q.BenchmarkFixtureConfig(
            fixture_id=q.UNIT_DRIFT_SERIES_FIXTURE_ID,
            dataset_name="benchmark-unit-drift-series",
            as_of_date=date(2024, 2, 1),
        ),
        severities=("medium",),
        seeds=(0,),
        research=q.BenchmarkUnitDriftResearch(research_as_of_date=date(2024, 2, 1)),
    )


def build_failed_benchmark(root: Path) -> q.BenchmarkRunResult:
    """Run a benchmark containing one genuinely failed case and two successes."""
    config = q.build_benchmark_config(
        benchmark_name="presentation-mixed",
        profiles=(_ineligible_unit_drift_profile(), lookahead_profile(), duplicate_profile()),
    )
    return q.run_benchmark(config, output_root=root, runtime=FIXED_RUNTIME)


def rebuild_derived_public_artifacts(output_root: Path) -> None:
    """Rebuild the two derived per-run public artifacts from what is on disk.

    ``aggregate_report.json`` and ``index.json`` are explicitly *derived*
    per-run artifacts (see ``benchmark_store``): every run rebuilds them from
    the immutable case evidence. Rebuilding them here is that same sanctioned
    operation, so a tree with a removed status ends up in the state a real
    re-aggregated run would leave, rather than in an artificially inconsistent
    one.
    """
    public = q.AtomicArtifactStore(public_root(output_root))
    aggregate = q.aggregate_from_public_artifacts(public)
    aggregate_payload = public.write_run_artifact(q.BENCHMARK_AGGREGATE_PATH, aggregate)

    entries: list[q.BenchmarkArtifactReference] = []
    for role, relative in (
        ("benchmark_config", q.BENCHMARK_CONFIG_PATH),
        ("case_matrix", q.BENCHMARK_MATRIX_PATH),
        ("runtime_metadata", q.BENCHMARK_RUNTIME_PATH),
    ):
        if public.exists(relative):
            entries.append(
                q.BenchmarkArtifactReference(
                    kind=role,
                    relative_path=relative,
                    content_hash=q.sha256_hex_of_bytes(public.read_bytes(relative)),
                )
            )
    entries.append(
        q.BenchmarkArtifactReference(
            kind="aggregate_report",
            relative_path=q.BENCHMARK_AGGREGATE_PATH,
            content_hash=q.sha256_hex_of_bytes(aggregate_payload),
        )
    )

    matrix = q.BenchmarkCaseMatrix.model_validate(public.read_canonical(q.BENCHMARK_MATRIX_PATH))
    for case in matrix.cases:
        status_path = f"{q.public_case_directory(case.benchmark_case_id)}/status.json"
        if not public.exists(status_path):
            continue
        status = q.BenchmarkCaseStatus.model_validate(public.read_canonical(status_path))
        entries.extend(status.artifacts)
        entries.append(
            q.BenchmarkArtifactReference(
                kind="status",
                relative_path=status_path,
                content_hash=q.sha256_hex_of_bytes(public.read_bytes(status_path)),
            )
        )

    public.write_run_artifact(
        q.BENCHMARK_INDEX_PATH,
        q.BenchmarkPublicIndex(
            benchmark_id=aggregate.benchmark_id,
            spec_version=q.BENCHMARK_SPEC_VERSION,
            entries=tuple(entries),
        ),
    )


def build_incomplete_benchmark(root: Path) -> str:
    """Produce a tree with one legitimately incomplete case; return its id.

    This reproduces a run interrupted before one case's terminal status was
    written, which is then re-aggregated: the case's own immutable evidence is
    untouched, but nothing on disk claims it finished, so it must be reported
    as incomplete and never inferred to have succeeded.
    """
    config = q.build_benchmark_config(
        benchmark_name="presentation-partial",
        profiles=(lookahead_profile(), duplicate_profile()),
    )
    result = q.run_benchmark(config, output_root=root, runtime=FIXED_RUNTIME)
    case_id = min(status.benchmark_case_id for status in result.statuses)
    (public_root(root) / "cases" / case_id / "status.json").unlink()
    rebuild_derived_public_artifacts(root)
    return case_id


def copy_public_only(source_root: Path, destination_root: Path) -> Path:
    """Copy only ``public/`` elsewhere, leaving no private artifact behind."""
    destination = Path(destination_root)
    shutil.copytree(public_root(source_root), destination / q.PUBLIC_ROOT_NAME)
    assert not (destination / q.PRIVATE_ROOT_NAME).exists()
    return destination


#: Fault families whose injector *replaces* the targeted record with a freshly
#: minted identity. For these, the pre-injection ``record_id`` has no legitimate
#: public reason to appear anywhere in its own case.
#:
#: ``duplicate_observation`` is deliberately absent, for the reason already
#: documented in ``tests/test_cli_privacy.py``: its injector *adds* a copy
#: rather than replacing the original, so the original record's own identity
#: legitimately remains visible as one half of the real duplicate pair in
#: public detector evidence.
_REPLACING_FAMILIES = frozenset({"lookahead_timestamp", "unit_drift", "revision_overwrite"})


def _manifest_bodies(output_root: Path) -> list[tuple[str, dict[str, object]]]:
    bodies: list[tuple[str, dict[str, object]]] = []
    private = Path(output_root) / q.PRIVATE_ROOT_NAME
    for manifest_path in sorted(private.rglob("manifest.json")):
        body = q.parse_canonical_json(manifest_path.read_bytes())
        assert isinstance(body, dict)
        bodies.append((manifest_path.parent.name, body))
    return bodies


def manifest_answer_key_strings(output_root: Path) -> set[str]:
    """Collect answer-key strings that must never appear in *any* public surface.

    These are unconditionally private: manifest identifiers, fault identifiers,
    and injector selection digests exist only inside the manifest and have no
    public counterpart in any case.

    Pre-injection record identities are *not* collected here, because they are
    private only relative to their own case: the same clean record is ordinary
    public data in a clean control and in another seed's case, where it was
    never targeted. Those are checked per case by
    :func:`case_pre_injection_record_ids` instead.

    Raw numeric *values* are also not collected, for the reason documented in
    ``tests/test_cli_privacy.py``: several detectors legitimately publish a
    reconstructed corrected value as their own public evidence, and that value
    can coincide with a private original.
    """
    secrets: set[str] = set()
    for _case_id, body in _manifest_bodies(output_root):
        manifest_id = body.get("manifest_id")
        if isinstance(manifest_id, str):
            secrets.add(manifest_id)
        entries = body.get("entries")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for key in ("fault_id", "selection_digest"):
                value = entry.get(key)
                if isinstance(value, str):
                    secrets.add(value)
    return secrets


def case_pre_injection_record_ids(output_root: Path) -> dict[str, set[str]]:
    """Map each case to the record identities its own injector hid.

    Only the replacing families are included (see ``_REPLACING_FAMILIES``). The
    resulting identity must not appear anywhere in *that case's* public
    evidence; it may legitimately appear in other cases, where the same clean
    record was never a target.
    """
    hidden: dict[str, set[str]] = {}
    for case_id, body in _manifest_bodies(output_root):
        if body.get("fault_type") not in _REPLACING_FAMILIES:
            continue
        entries = body.get("entries")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            original = entry.get("original_record")
            if isinstance(original, dict) and isinstance(original.get("record_id"), str):
                hidden.setdefault(case_id, set()).add(original["record_id"])
            mutation = entry.get("mutation")
            if isinstance(mutation, dict):
                for key in ("historical_record_id", "later_record_id"):
                    value = mutation.get(key)
                    if isinstance(value, str):
                        hidden.setdefault(case_id, set()).add(value)
    return hidden


#: Manifest and injector field names that must never appear in a public
#: presentation surface, mirroring the CLI privacy contract's marker list.
PRIVATE_FIELD_MARKERS: tuple[str, ...] = (
    "original_record",
    "corrupted_record",
    "created_record",
    "historical_record",
    "later_record",
    "manifest_id",
    "target_rank",
    "selection_digest",
    "eligibility_unit_id",
    "exception_message",
    "exception_class",
)
