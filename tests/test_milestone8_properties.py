"""Property-based and static invariants for the Milestone 8 benchmark layer."""

from __future__ import annotations

import inspect
from decimal import Decimal, localcontext

from hypothesis import given
from hypothesis import strategies as st

import quantcheck as q
from tests.benchmark_support import (
    duplicate_profile,
    lookahead_profile,
    revision_overwrite_profile,
    single_profile_config,
    unit_drift_profile,
)

_ORDINARY_SEEDS = st.sampled_from([*q.DEVELOPMENT_SEED_RANGE, *q.VALIDATION_SEED_RANGE])


@given(seed=_ORDINARY_SEEDS)
def test_every_ordinary_seed_classifies_into_exactly_one_partition(seed: int) -> None:
    seed_class = q.classify_benchmark_seed(seed)
    assert seed_class in q.SEED_CLASSES
    assert (seed_class == "development") == (seed in q.DEVELOPMENT_SEED_RANGE)
    assert (seed_class == "validation") == (seed in q.VALIDATION_SEED_RANGE)
    assert not q.is_final_seed(seed)


@given(seed=st.sampled_from(list(q.FINAL_SEED_RANGE)))
def test_no_final_seed_ever_classifies(seed: int) -> None:
    assert q.is_final_seed(seed)
    try:
        q.classify_benchmark_seed(seed)
    except q.BenchmarkSeedClassError:
        return
    raise AssertionError(f"final seed {seed} was accepted")


@given(
    severities=st.lists(
        st.sampled_from(["low", "medium", "high"]), min_size=1, max_size=3, unique=True
    ),
    seeds=st.lists(_ORDINARY_SEEDS, min_size=1, max_size=4, unique=True),
)
def test_normalization_makes_list_order_irrelevant_to_identity(
    severities: list[str], seeds: list[int]
) -> None:
    forward = single_profile_config(
        duplicate_profile(severities=tuple(severities), seeds=tuple(seeds))
    )
    backward = single_profile_config(
        duplicate_profile(severities=tuple(reversed(severities)), seeds=tuple(reversed(seeds)))
    )
    assert forward.benchmark_id == backward.benchmark_id
    assert q.canonical_json_bytes(forward) == q.canonical_json_bytes(backward)


@given(
    severities=st.lists(
        st.sampled_from(["low", "medium", "high"]), min_size=1, max_size=3, unique=True
    ),
    seeds=st.lists(_ORDINARY_SEEDS, min_size=1, max_size=4, unique=True),
)
def test_expansion_size_is_exactly_the_configured_cross_product(
    severities: list[str], seeds: list[int]
) -> None:
    config = single_profile_config(
        duplicate_profile(severities=tuple(severities), seeds=tuple(seeds))
    )
    matrix = q.expand_benchmark_cases(config)
    assert matrix.case_count == len(severities) * len(seeds)
    identifiers = [case.benchmark_case_id for case in matrix.cases]
    assert len(set(identifiers)) == len(identifiers)
    assert identifiers == sorted(identifiers)


@given(
    seeds=st.lists(_ORDINARY_SEEDS, min_size=1, max_size=4, unique=True),
)
def test_every_expanded_case_verifies_its_own_identity(seeds: list[int]) -> None:
    config = single_profile_config(lookahead_profile(seeds=tuple(seeds)))
    for case in q.expand_benchmark_cases(config).cases:
        assert q.benchmark_case_identity_matches(case)


@given(
    true_positives=st.integers(min_value=0, max_value=50),
    extra_false_positives=st.integers(min_value=0, max_value=50),
    denominator=st.integers(min_value=0, max_value=200),
)
def test_group_metrics_follow_the_null_conventions_for_any_counts(
    true_positives: int, extra_false_positives: int, denominator: int
) -> None:
    findings = true_positives + extra_false_positives
    group = q.BenchmarkAggregateGroup(
        grouping="overall",
        key="overall",
        configured_case_count=1,
        successful_case_count=1,
        failed_case_count=0,
        incomplete_case_count=0,
        injected_faults=true_positives,
        findings=findings,
        true_positive_faults=true_positives,
        false_negative_faults=0,
        true_positive_findings=true_positives,
        false_positive_findings=extra_false_positives,
        eligible_clean_denominator=denominator,
        precision=_expected_precision(true_positives, findings),
        recall=_expected_recall(true_positives, true_positives),
        f1=_expected_f1(
            _expected_precision(true_positives, findings),
            _expected_recall(true_positives, true_positives),
        ),
        false_positive_rate=_expected_rate(extra_false_positives, denominator),
        research_summary_count=0,
        research_changed_count=0,
        replay_restored_count=0,
    )
    assert (group.recall is None) == (group.injected_faults == 0)
    assert (group.false_positive_rate is None) == (group.eligible_clean_denominator == 0)
    assert (group.f1 is None) == (group.precision is None or group.recall is None)
    if group.precision is not None:
        assert 0 <= group.precision <= 1


def _expected_precision(true_positives: int, findings: int) -> Decimal | None:
    if findings:
        with localcontext() as context:
            context.prec = 50
            return Decimal(true_positives) / Decimal(findings)
    return Decimal(1) if true_positives == 0 else None


def _expected_recall(true_positives: int, injected: int) -> Decimal | None:
    if not injected:
        return None
    with localcontext() as context:
        context.prec = 50
        return Decimal(true_positives) / Decimal(injected)


def _expected_rate(numerator: int, denominator: int) -> Decimal | None:
    if not denominator:
        return None
    with localcontext() as context:
        context.prec = 50
        return Decimal(numerator) / Decimal(denominator)


def _expected_f1(precision: Decimal | None, recall: Decimal | None) -> Decimal | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0:
        return Decimal(0)
    with localcontext() as context:
        context.prec = 50
        return (Decimal(2) * precision * recall) / (precision + recall)


@given(path=st.text(min_size=1, max_size=40))
def test_a_public_path_never_admits_a_private_or_escaping_reference(path: str) -> None:
    from pydantic import ValidationError

    try:
        reference = q.BenchmarkArtifactReference(
            kind="artifact", relative_path=path, content_hash="0" * 64
        )
    except ValidationError:
        return
    segments = reference.relative_path.split("/")
    assert ".." not in segments
    assert "." not in segments
    assert "private" not in segments
    assert not reference.relative_path.startswith("/")
    assert "\\" not in reference.relative_path
    assert "~" not in reference.relative_path


def test_the_benchmark_layer_adds_no_manifest_parameter_to_any_detector_path() -> None:
    """Static check: nothing in the dispatch path can hand a detector truth."""
    forbidden = {"manifest", "clean_snapshot", "corrupted_snapshot", "seed", "severity"}
    for name, function in inspect.getmembers(q.benchmark_dispatch, inspect.isfunction):
        if function.__module__ != q.benchmark_dispatch.__name__:
            continue
        if not name.startswith(("run_all", "combined")):
            continue
        assert not forbidden & set(inspect.signature(function).parameters), name


def test_no_benchmark_module_imports_a_heavy_or_networked_dependency() -> None:
    """Checked in a fresh subprocess: within this same pytest process,
    ``sys.modules`` is shared across every collected test file, so another
    module's legitimate ``quantcheck.cli`` import (which does need Typer)
    would otherwise make this check fail for a reason unrelated to the
    benchmark layer itself.
    """
    import subprocess
    import sys

    script = (
        "import quantcheck.benchmark_contract, quantcheck.benchmark_fixtures, "
        "quantcheck.benchmark_expansion, quantcheck.benchmark_dispatch, "
        "quantcheck.benchmark_store, quantcheck.benchmark_runner, "
        "quantcheck.benchmark_aggregate, quantcheck.benchmark_smoke\n"
        "import sys\n"
        "forbidden = {'pandas', 'numpy', 'streamlit', 'pyarrow', 'typer'}\n"
        "assert forbidden.isdisjoint(sys.modules), sorted(forbidden & set(sys.modules))\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


def test_no_benchmark_module_reads_the_clock_or_a_random_source() -> None:
    """Determinism is structural: the library never calls a nondeterministic API."""
    import pathlib

    package = pathlib.Path(q.__file__).parent
    for path in sorted(package.glob("benchmark_*.py")):
        source = path.read_text()
        for forbidden in (
            "datetime.now(",
            "datetime.utcnow(",
            "time.time(",
            "random.",
            "uuid4",
            "os.urandom",
        ):
            assert forbidden not in source, f"{path.name} uses {forbidden}"


def test_the_benchmark_fixture_registry_is_closed_and_deterministic() -> None:
    assert set(q.BENCHMARK_FIXTURE_IDS) == {
        q.REVIEWED_FIXTURE_ID,
        q.UNIT_DRIFT_SERIES_FIXTURE_ID,
    }
    for fixture_id in q.BENCHMARK_FIXTURE_IDS:
        first = q.benchmark_fixture_records(fixture_id)
        second = q.benchmark_fixture_records(fixture_id)
        assert q.canonical_json_bytes(first) == q.canonical_json_bytes(second)


def test_the_unit_drift_series_fixture_is_a_clean_source_with_no_baked_fault() -> None:
    records = q.unit_drift_series_records()
    assert len(records) == q.UNIT_DRIFT_SERIES_RECORD_COUNT
    snapshot = q.build_dataset_snapshot(
        records, dataset_name="benchmark-unit-drift-series", as_of_date=records[-1].period_end
    )
    report = q.detect_unit_drift(q.sanitize_for_audit(snapshot), q.UnitDriftDetectorConfig())
    assert report.findings == ()


def test_the_reviewed_fixture_is_unchanged_by_milestone_eight() -> None:
    """The benchmark added a fixture; it did not touch the reviewed one."""
    assert q.benchmark_fixture_records(q.REVIEWED_FIXTURE_ID) == q.generate_reviewed_fixture()
    assert len(q.generate_reviewed_fixture()) == q.EXPECTED_FIXTURE_RECORD_COUNT


def test_every_supported_profile_and_fixture_pairing_actually_dispatches() -> None:
    builders = (
        lookahead_profile,
        unit_drift_profile,
        duplicate_profile,
        revision_overwrite_profile,
    )
    for builder in builders:
        config = single_profile_config(builder())
        for case in q.expand_benchmark_cases(config).cases:
            artifacts = q.dispatch_benchmark_case(case)
            assert artifacts.score.metrics.injected_faults >= 1
