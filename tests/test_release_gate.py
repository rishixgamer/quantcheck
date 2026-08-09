"""The final-seed authorization boundary.

These tests exist to prove one property from as many directions as possible:
**reserved final seeds `1000-1009` are unreachable except through the explicit
release path.** A single hole here would mean the held-out evidence was never
held out.
"""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

import quantcheck as q
from tests.release_support import assert_gate_closed

_SOURCE = Path(q.__file__).resolve().parent

#: Modules allowed to reference the gate at all. Everything else in the
#: package must be unable to authorize a final seed even by accident.
#:
#: ``__init__.py`` is here because it re-exports the gate's public names, which
#: is visibility rather than permission — re-exporting a context manager does
#: not open it. ``test_only_the_release_path_opens_an_authorization`` below is
#: the control that actually matters.
_GATE_AWARE_MODULES = frozenset(
    {
        "__init__.py",
        "release_gate.py",
        "release_run.py",
        "release_contract.py",
        "schemas.py",
        "benchmark_contract.py",
    }
)

#: Modules allowed to *open* an authorization. Only the release execution path.
_AUTHORIZING_MODULES = frozenset({"release_gate.py", "release_run.py"})


# --------------------------------------------------------------------------
# The gate is closed by default
# --------------------------------------------------------------------------


def test_no_authorization_is_active_by_default() -> None:
    assert_gate_closed()


def test_an_ordinary_seed_is_never_reported_as_authorized() -> None:
    """``final_seed_authorized`` answers about reserved seeds, not all seeds."""
    with q.reserved_final_seeds(release_candidate_id="c", seeds=q.RESERVED_FINAL_SEEDS):
        assert not q.final_seed_authorized(0)
        assert not q.final_seed_authorized(100)
        assert not q.final_seed_authorized(999)
        assert not q.final_seed_authorized(1010)


def test_the_authorization_is_removed_when_the_block_raises() -> None:
    with (
        pytest.raises(RuntimeError, match="deliberate"),
        q.reserved_final_seeds(release_candidate_id="c", seeds=q.RESERVED_FINAL_SEEDS),
    ):
        assert q.final_seed_authorized(1000)
        raise RuntimeError("deliberate")
    assert_gate_closed()


def test_the_authorization_is_removed_on_a_normal_exit() -> None:
    with q.reserved_final_seeds(release_candidate_id="c", seeds=q.RESERVED_FINAL_SEEDS):
        assert q.final_seed_authorized(1009)
    assert_gate_closed()


# --------------------------------------------------------------------------
# Only the exact complete reserved partition is accepted
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seeds", "reason"),
    [
        ((), "missing"),
        ((1000,), "missing"),
        (tuple(range(1000, 1009)), "missing"),
        (tuple(range(1000, 1011)), "refused"),
        ((999, *range(1000, 1010)), "refused"),
        ((*range(1000, 1010), 0), "refused"),
        ((*range(1000, 1010), 100), "refused"),
        ((*range(1000, 1010), 1000), "duplicates"),
        ((0, 1, 2), "refused"),
        ((100, 101), "refused"),
    ],
)
def test_only_the_complete_reserved_partition_is_authorized(
    seeds: tuple[int, ...], reason: str
) -> None:
    with (
        pytest.raises(q.FinalSeedAuthorizationError, match=reason),
        q.reserved_final_seeds(release_candidate_id="c", seeds=seeds),
    ):
        pass  # pragma: no cover - the context manager must not open
    assert_gate_closed()


def test_a_non_integer_seed_is_refused() -> None:
    with (
        pytest.raises(q.FinalSeedAuthorizationError, match="integers"),
        q.reserved_final_seeds(release_candidate_id="c", seeds=("1000",)),  # type: ignore[arg-type]
    ):
        pass  # pragma: no cover


def test_a_boolean_seed_is_refused_rather_than_treated_as_an_integer() -> None:
    with (
        pytest.raises(q.FinalSeedAuthorizationError, match="integers"),
        q.reserved_final_seeds(release_candidate_id="c", seeds=(True,)),
    ):
        pass  # pragma: no cover


def test_a_string_is_not_accepted_as_a_seed_sequence() -> None:
    with (
        pytest.raises(q.FinalSeedAuthorizationError, match="sequence"),
        q.reserved_final_seeds(release_candidate_id="c", seeds="1000"),  # type: ignore[arg-type]
    ):
        pass  # pragma: no cover


def test_an_anonymous_authorization_is_refused() -> None:
    for candidate in ("", None):
        with (
            pytest.raises(q.FinalSeedAuthorizationError, match="candidate"),
            q.reserved_final_seeds(
                release_candidate_id=candidate,  # type: ignore[arg-type]
                seeds=q.RESERVED_FINAL_SEEDS,
            ),
        ):
            pass  # pragma: no cover


def test_nesting_is_refused_so_two_candidates_cannot_be_open_at_once() -> None:
    with q.reserved_final_seeds(release_candidate_id="outer", seeds=q.RESERVED_FINAL_SEEDS):
        with (
            pytest.raises(q.FinalSeedAuthorizationError, match="already active"),
            q.reserved_final_seeds(release_candidate_id="inner", seeds=q.RESERVED_FINAL_SEEDS),
        ):
            pass  # pragma: no cover
        # The outer authorization survives the refused inner one.
        assert q.active_final_seed_authorization() is not None
        assert q.active_final_seed_authorization().release_candidate_id == "outer"  # type: ignore[union-attr]
    assert_gate_closed()


def test_the_authorization_records_the_exact_partition_it_permitted() -> None:
    descending = tuple(reversed(q.RESERVED_FINAL_SEEDS))
    with q.reserved_final_seeds(release_candidate_id="c", seeds=descending):
        active = q.active_final_seed_authorization()
        assert active is not None
        assert active.seeds == q.RESERVED_FINAL_SEEDS
        assert active.release_candidate_id == "c"


# --------------------------------------------------------------------------
# The gate cannot be reached from ordinary code
# --------------------------------------------------------------------------


def _modules_referencing_gate() -> set[str]:
    referencing: set[str] = set()
    for path in sorted(_SOURCE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "quantcheck.release_gate":
                referencing.add(path.name)
            if isinstance(node, ast.Import) and any(
                alias.name == "quantcheck.release_gate" for alias in node.names
            ):
                referencing.add(path.name)
    return referencing


def test_only_gate_aware_modules_import_the_release_gate() -> None:
    """A module that cannot import the gate cannot open it."""
    referencing = _modules_referencing_gate()
    unexpected = sorted(referencing - _GATE_AWARE_MODULES)
    assert unexpected == [], unexpected


def _modules_calling_reserved_final_seeds() -> set[str]:
    calling: set[str] = set()
    for path in sorted(_SOURCE.glob("*.py")):
        if "reserved_final_seeds" in path.read_text(encoding="utf-8"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    name = getattr(func, "id", None) or getattr(func, "attr", None)
                    if name == "reserved_final_seeds":
                        calling.add(path.name)
    return calling


def test_only_the_release_path_opens_an_authorization() -> None:
    calling = _modules_calling_reserved_final_seeds()
    unexpected = sorted(calling - _AUTHORIZING_MODULES)
    assert unexpected == [], unexpected


def test_the_cli_module_never_mentions_the_gate_or_a_final_seed() -> None:
    """The contracted CLI surface must have no route to held-out execution."""
    source = (_SOURCE / "cli.py").read_text(encoding="utf-8")
    for forbidden in (
        "release_gate",
        "reserved_final_seeds",
        "release_benchmark_config",
        "run_release_benchmark",
        "final_seed_authorized",
    ):
        assert forbidden not in source, forbidden


def test_no_cli_command_exposes_a_release_or_held_out_flag() -> None:
    from quantcheck.cli import app

    rendered = repr(app.registered_commands) + repr(app.registered_groups)
    for forbidden in ("held-out", "held_out", "--release", "--final", "allow-final", "force-seed"):
        assert forbidden not in rendered, forbidden


def test_the_gate_imports_nothing_from_quantcheck() -> None:
    """A gate that depends on the package could be influenced by the package."""
    tree = ast.parse((_SOURCE / "release_gate.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module is None or not node.module.startswith("quantcheck"), node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("quantcheck"), alias.name


def test_classify_benchmark_seed_takes_no_authorization_parameter() -> None:
    """The escape hatch must not exist as a parameter, only as ambient scope."""
    signature = inspect.signature(q.classify_benchmark_seed)
    assert list(signature.parameters) == ["seed"]


def test_run_benchmark_takes_no_authorization_parameter() -> None:
    forbidden = {"allow_final", "held_out", "release", "force", "authorization", "seeds"}
    assert not forbidden & set(inspect.signature(q.run_benchmark).parameters)


_SUBPROCESS_PROBE = """
import quantcheck as q

# A fresh process: nothing has ever opened the gate here.
assert q.active_final_seed_authorization() is None
for seed in q.RESERVED_FINAL_SEEDS:
    assert not q.final_seed_authorized(seed)
try:
    q.require_seed_execution_authorized(1000)
except q.BenchmarkSeedClassError:
    print("closed")
else:
    print("OPEN")
"""


def test_a_fresh_process_starts_with_the_gate_closed() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_PROBE],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "closed"
