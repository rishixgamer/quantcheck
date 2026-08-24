"""No ordinary interface can **execute** a reserved final seed.

Milestone 11 added an authorization path. This module proves it changed
nothing for anyone who does not open it.

The boundary is deliberately drawn at *execution*, not at *representation*,
and the distinction is load-bearing:

* **Executing** a reserved seed without an authorization is refused everywhere
  — configuration building, expansion, the dispatcher, ``run_benchmark``, all
  three saved-stage functions, and every CLI command.
* **Representing** one is allowed, because released held-out artifacts have to
  stay readable. The public reader, presentation model, HTML summary, and
  dashboard all deserialize saved cases and execute nothing. An earlier draft
  refused representation too, which made the public evidence package
  unreadable by the very surfaces built to present it — see
  ``test_a_released_case_config_stays_readable_with_the_gate_closed``, the
  regression test for exactly that defect.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import quantcheck as q
from tests.benchmark_support import (
    FIXED_RUNTIME,
    lookahead_profile,
    single_profile_config,
)
from tests.cli_helpers import invoke
from tests.release_support import assert_gate_closed

RESERVED = q.RESERVED_FINAL_SEEDS
#: Seeds just outside every partition, which must stay rejected with *or*
#: without an authorization: authorization widens nothing.
NEAR_MISS = (10, 99, 110, 999, 1010, 1100, 10_000)


@pytest.fixture(autouse=True)
def _gate_is_closed() -> None:
    assert_gate_closed()


def _released_case() -> q.BenchmarkCaseConfig:
    """One real expanded release case, built under a scoped authorization."""
    with q.reserved_final_seeds(release_candidate_id="c", seeds=RESERVED):
        config = q.release_benchmark_config()
        return q.expand_benchmark_cases(config).cases[0]


# --------------------------------------------------------------------------
# Configuration building and expansion refuse to execute a reserved seed
# --------------------------------------------------------------------------


@pytest.mark.parametrize("seed", RESERVED)
def test_building_a_benchmark_config_refuses_every_reserved_final_seed(seed: int) -> None:
    with pytest.raises(q.BenchmarkSeedClassError, match="not authorized"):
        single_profile_config(lookahead_profile(seeds=(seed,)))


@pytest.mark.parametrize("seed", RESERVED)
def test_a_clean_control_at_a_reserved_seed_cannot_reach_a_benchmark(seed: int) -> None:
    """Two independent rules block it, so both are asserted.

    A control pinned to a reserved seed inside an otherwise ordinary profile is
    refused by the pre-existing Milestone 8 coherence rule that a control must
    use one of its own profile's configured seeds. Making the profile
    consistent by listing the reserved seed then hits the execution guard.
    """
    control = q.BenchmarkCleanControl(severity="medium", seed=seed)
    with pytest.raises(ValidationError, match="configured seeds"):
        single_profile_config(lookahead_profile(seeds=(0,), control=control))

    with pytest.raises(q.BenchmarkSeedClassError, match="not authorized"):
        single_profile_config(lookahead_profile(seeds=(seed,), control=control))


@pytest.mark.parametrize("seed", NEAR_MISS)
def test_a_seed_outside_every_partition_is_rejected(seed: int) -> None:
    with pytest.raises(ValidationError, match="unclassified"):
        lookahead_profile(seeds=(seed,))


@pytest.mark.parametrize("seed", NEAR_MISS)
def test_a_near_miss_seed_stays_rejected_even_under_authorization(seed: int) -> None:
    """Authorization permits the reserved partition and widens nothing else."""
    with (
        q.reserved_final_seeds(release_candidate_id="c", seeds=RESERVED),
        pytest.raises(ValidationError, match="unclassified"),
    ):
        lookahead_profile(seeds=(seed,))


def test_a_profile_may_not_mix_final_seeds_with_ordinary_seeds() -> None:
    """Silently mixing partitions would contaminate held-out evidence."""
    with pytest.raises(ValidationError, match="must not mix"):
        lookahead_profile(seeds=(0, 1000))
    with pytest.raises(ValidationError, match="must not mix"):
        lookahead_profile(seeds=(100, *RESERVED))


def test_expansion_refuses_a_reserved_seed_configuration() -> None:
    """A saved release config can be read, but never expanded unauthorized."""
    with q.reserved_final_seeds(release_candidate_id="c", seeds=RESERVED):
        config = q.release_benchmark_config()
        payload = q.canonical_json_bytes(config)

    assert_gate_closed()
    reloaded = q.BenchmarkConfig.model_validate(json.loads(payload))
    assert reloaded.benchmark_id == config.benchmark_id
    with pytest.raises(q.BenchmarkSeedClassError, match="not authorized"):
        q.expand_benchmark_cases(reloaded)


# --------------------------------------------------------------------------
# Released evidence stays readable — the regression for the found defect
# --------------------------------------------------------------------------


def test_a_released_case_config_stays_readable_with_the_gate_closed() -> None:
    """Regression: released held-out artifacts must deserialize unauthorized.

    An earlier draft refused to *represent* a reserved seed at all. That made
    ``public/benchmark_config.json`` and every released ``case_config.json``
    unreadable by the strict public reader, so the public evidence package
    could not be loaded, aggregated, presented, or rendered. Reading is not
    running; this test pins the distinction.
    """
    case = _released_case()
    payload = q.canonical_json_bytes(case)

    assert_gate_closed()
    reloaded = q.BenchmarkCaseConfig.model_validate(json.loads(payload))
    assert reloaded == case
    assert reloaded.seed in RESERVED
    assert reloaded.seed_class == "final"


def test_the_released_public_evidence_loads_with_the_gate_closed(tmp_path: Path) -> None:
    """The whole public tree, not just one artifact, must load unauthorized."""
    saved = Path("release_evidence/public_only")
    case_statuses = saved / "public/cases"
    if (
        not saved.is_dir()
        or len(list(case_statuses.glob("*/status.json"))) < q.RELEASE_TOTAL_CASE_COUNT
    ):
        pytest.skip("complete released public evidence tree is not checked in")
    assert_gate_closed()
    artifacts = q.read_public_benchmark(saved)
    assert artifacts.aggregate.overall.configured_case_count == q.RELEASE_TOTAL_CASE_COUNT
    assert {case.case.seed_class for case in artifacts.cases} == {"final"}
    presentation = q.build_presentation(artifacts)
    assert q.render_html_summary(presentation)


def test_a_case_config_must_still_declare_a_consistent_seed_class() -> None:
    """Representation is permitted; mislabelling is not."""
    case = _released_case()
    document = json.loads(q.canonical_json_bytes(case))
    document["seed_class"] = "development"
    with pytest.raises(ValidationError, match="seed_class must match"):
        q.BenchmarkCaseConfig.model_validate(document)


# --------------------------------------------------------------------------
# Execution entry points
# --------------------------------------------------------------------------


def test_the_dispatcher_refuses_a_released_case() -> None:
    case = _released_case()
    with pytest.raises(q.BenchmarkSeedClassError, match="not authorized"):
        q.dispatch_benchmark_case(case)


def test_run_benchmark_refuses_a_released_configuration(tmp_path: Path) -> None:
    with q.reserved_final_seeds(release_candidate_id="c", seeds=RESERVED):
        config = q.release_benchmark_config()

    assert_gate_closed()
    with pytest.raises(q.BenchmarkSeedClassError, match="not authorized"):
        q.run_benchmark(config, output_root=tmp_path / "out", runtime=FIXED_RUNTIME)
    assert not (tmp_path / "out" / "public" / "case_matrix.json").exists()


@pytest.mark.parametrize("stage", ("inject_case", "audit_case", "evaluate_case"))
def test_every_saved_stage_function_refuses_a_released_case(tmp_path: Path, stage: str) -> None:
    case = _released_case()
    public = q.AtomicArtifactStore(tmp_path / "public")
    private = q.AtomicArtifactStore(tmp_path / "private")
    function = getattr(q, stage)
    with pytest.raises(q.BenchmarkSeedClassError, match="not authorized"):
        function(case, public=public, private=private)
    assert not any((tmp_path / "private").rglob("manifest.json"))


def test_an_ordinary_benchmark_run_is_unaffected(tmp_path: Path) -> None:
    result = q.run_benchmark(
        single_profile_config(lookahead_profile(seeds=(0,))),
        output_root=tmp_path,
        runtime=FIXED_RUNTIME,
    )
    assert result.aggregate.overall.configured_case_count == 1
    assert result.aggregate.overall.successful_case_count == 1


# --------------------------------------------------------------------------
# Classifier
# --------------------------------------------------------------------------


@pytest.mark.parametrize("seed", RESERVED)
def test_classify_benchmark_seed_rejects_a_reserved_seed(seed: int) -> None:
    with pytest.raises(q.BenchmarkSeedClassError, match="reserved"):
        q.classify_benchmark_seed(seed)


@pytest.mark.parametrize("seed", RESERVED)
def test_require_seed_execution_authorized_refuses_a_reserved_seed(seed: int) -> None:
    with pytest.raises(q.BenchmarkSeedClassError, match="not authorized"):
        q.require_seed_execution_authorized(seed)


@pytest.mark.parametrize("seed", (0, 9, 100, 109))
def test_require_seed_execution_authorized_permits_an_ordinary_seed(seed: int) -> None:
    q.require_seed_execution_authorized(seed)


@pytest.mark.parametrize("seed", RESERVED)
def test_is_final_seed_still_reports_the_reserved_partition(seed: int) -> None:
    assert q.is_final_seed(seed)
    assert not q.is_final_seed(seed - 1000)


def test_the_ordinary_seed_classes_do_not_include_final() -> None:
    assert q.SEED_CLASSES == ("development", "validation")
    assert "final" in q.ALL_SEED_CLASSES


def test_the_smoke_configuration_uses_no_reserved_seed() -> None:
    config = q.smoke_benchmark_config()
    for profile in config.profiles:
        assert not set(profile.seeds) & set(RESERVED)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _config_with_seed(seed: int) -> dict[str, object]:
    """A benchmark configuration document naming one seed, built by hand.

    Built as raw JSON rather than through the builder precisely because the
    builder refuses it — this is what a user attempting to smuggle a final
    seed through the CLI would actually write.
    """
    return {
        "benchmark_id": "bench_" + "0" * 16,
        "spec_version": "quantcheck/benchmark/v1",
        "benchmark_name": "attempt",
        "detector_configs": {},
        "profiles": [
            {
                "fault_profile": "lookahead_timestamp",
                "injector_spec_version": "quantcheck/lookahead-period-end/v1",
                "fixture": {
                    "fixture_id": "quantcheck/reviewed-fixture/v1",
                    "dataset_name": "reviewed",
                    "as_of_date": "2024-04-30",
                },
                "severities": ["medium"],
                "seeds": [seed],
                "research": {
                    "method": "availability_count_v0_1",
                    "research_as_of_date": "2024-04-14",
                },
            }
        ],
    }


@pytest.mark.parametrize("seed", (1000, 1005, 1009))
def test_benchmark_run_rejects_a_final_seed_configuration(tmp_path: Path, seed: int) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(_config_with_seed(seed)))
    result = invoke(
        ["benchmark", "run", "--config", str(config_path), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 2, result.stdout + result.stderr
    assert not (tmp_path / "out" / "public" / "case_matrix.json").exists()


def test_benchmark_smoke_never_touches_a_reserved_seed(tmp_path: Path) -> None:
    result = invoke(["benchmark", "smoke", "--output", str(tmp_path / "out")])
    assert result.exit_code == 0, result.stdout + result.stderr
    matrix = json.loads((tmp_path / "out" / "public" / "case_matrix.json").read_text())
    seeds = {case["seed"] for case in matrix["cases"]}
    assert not seeds & set(RESERVED)
    assert {case["seed_class"] for case in matrix["cases"]} <= {"development", "validation"}


@pytest.mark.parametrize("command", ("inject", "audit", "evaluate"))
def test_the_saved_stage_commands_reject_a_released_case(tmp_path: Path, command: str) -> None:
    case_path = tmp_path / "case.json"
    case_path.write_bytes(q.canonical_json_bytes(_released_case()))
    result = invoke([command, "--case", str(case_path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2, result.stdout + result.stderr
    assert not any((tmp_path / "out").rglob("manifest.json"))


def test_the_saved_stage_commands_reject_a_handwritten_final_seed_case(tmp_path: Path) -> None:
    """Not only a genuine released case: a hand-written one is refused too."""
    case_path = tmp_path / "case.json"
    case_path.write_text(
        json.dumps(
            {
                "benchmark_case_id": "bcase_" + "0" * 16,
                "benchmark_id": "bench_" + "0" * 16,
                "spec_version": "quantcheck/benchmark/v1",
                "case_kind": "fault",
                "fault_profile": "lookahead_timestamp",
                "injector_spec_version": "quantcheck/lookahead-period-end/v1",
                "fixture": {
                    "fixture_id": "quantcheck/reviewed-fixture/v1",
                    "dataset_name": "reviewed",
                    "as_of_date": "2024-04-30",
                },
                "detector_configs": {},
                "severity": "medium",
                "seed": 1000,
                "seed_class": "final",
                "max_targets": 8,
                "research": {
                    "method": "availability_count_v0_1",
                    "research_as_of_date": "2024-04-14",
                },
            }
        )
    )
    result = invoke(["inject", "--case", str(case_path), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2, result.stdout + result.stderr


def test_no_root_command_was_added_for_the_release() -> None:
    """The command surface is still exactly the six Milestone 9 roots.

    Typer leaves ``name`` unset when a command is registered by decorating a
    function, so the callback's name is the authoritative one.
    """
    from quantcheck.cli import app

    groups: set[str | None] = set()
    for group in app.registered_groups:
        instance = group.typer_instance
        assert instance is not None
        groups.add(group.name or instance.info.name)
    commands = {
        command.name or (command.callback.__name__ if command.callback else None)
        for command in app.registered_commands
    }
    assert groups == {"ingest", "benchmark"}
    assert commands == {"inject", "audit", "evaluate", "explain"}
