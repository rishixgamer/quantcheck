"""The presentation layer's isolation from private benchmark truth.

These tests exist to prove a *structural* property, not a stylistic one: the
presentation code cannot become a second way into the answer key, even by
accident, because it does not import the modules that hold it and cannot
address the tree that stores it.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

import quantcheck as q
from quantcheck.presentation import build_presentation
from quantcheck.public_artifact_reader import read_public_benchmark
from tests.presentation_helpers import (
    PRIVATE_FIELD_MARKERS,
    build_smoke_benchmark,
    case_pre_injection_record_ids,
    copy_public_only,
    manifest_answer_key_strings,
)

_REPOSITORY = Path(__file__).resolve().parent.parent
_SOURCE = _REPOSITORY / "src" / "quantcheck"

#: The Recovery Phase 10 presentation surface, in full.
_PRESENTATION_MODULES = (
    _SOURCE / "public_artifact_reader.py",
    _SOURCE / "presentation.py",
    _SOURCE / "html_summary.py",
    _REPOSITORY / "dashboard" / "app.py",
)

#: Modules that hold, produce, or repair private truth. Presentation importing
#: any of them would mean the answer key is one attribute access away.
_FORBIDDEN_IMPORT_SUFFIXES = (
    "_manifest",
    "_injection",
    "_scoring",
    "_replay",
    "_research",
    "_detection",
)

_FORBIDDEN_MODULES = frozenset(
    {
        "quantcheck.benchmark_dispatch",
        "quantcheck.benchmark_runner",
        "quantcheck.saved_case_workflow",
        "quantcheck.point_in_time",
        "quantcheck.audit_boundary",
        "quantcheck.sec_adapter",
        "quantcheck.fixtures",
        "quantcheck.benchmark_fixtures",
    }
)


@pytest.fixture(scope="module")
def smoke_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("isolation-smoke")
    build_smoke_benchmark(root)
    return root


def _imported_modules(source_path: Path) -> set[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


@pytest.mark.parametrize("source_path", _PRESENTATION_MODULES, ids=lambda path: path.name)
def test_presentation_source_imports_no_private_truth_module(source_path: Path) -> None:
    imported = _imported_modules(source_path)
    forbidden = sorted(
        name
        for name in imported
        if name in _FORBIDDEN_MODULES
        or (name.startswith("quantcheck.") and name.endswith(_FORBIDDEN_IMPORT_SUFFIXES))
    )
    assert not forbidden, (source_path.name, forbidden)


@pytest.mark.parametrize("source_path", _PRESENTATION_MODULES, ids=lambda path: path.name)
def test_presentation_source_names_no_manifest_or_injector_type(source_path: Path) -> None:
    """No manifest/injector symbol is even referenced by name in the source."""
    text = source_path.read_text(encoding="utf-8")
    for symbol in ("FaultManifest", "UnitDriftManifest", "DuplicateManifest", "inject_"):
        assert symbol not in text, (source_path.name, symbol)


def _transitive_quantcheck_imports(source_path: Path) -> set[str]:
    """Every ``quantcheck.*`` module reachable from one file's own imports.

    This deliberately walks the module graph rather than ``sys.modules``: an
    ordinary ``import quantcheck.presentation`` also executes the package
    ``__init__``, which re-exports the whole public API and therefore loads
    every module regardless of what the presentation code needs. The property
    that matters is what presentation code can *reach on its own*.
    """
    seen: set[str] = set()
    pending = [source_path]
    while pending:
        current = pending.pop()
        for name in _imported_modules(current):
            if not name.startswith("quantcheck.") or name in seen:
                continue
            seen.add(name)
            candidate = _SOURCE / f"{name.removeprefix('quantcheck.')}.py"
            if candidate.is_file():
                pending.append(candidate)
    return seen


@pytest.mark.parametrize("source_path", _PRESENTATION_MODULES, ids=lambda path: path.name)
def test_no_private_truth_module_is_reachable_from_presentation_code(
    source_path: Path,
) -> None:
    reachable = _transitive_quantcheck_imports(source_path)
    forbidden = sorted(
        name
        for name in reachable
        if name in _FORBIDDEN_MODULES or name.endswith(_FORBIDDEN_IMPORT_SUFFIXES)
    )
    assert not forbidden, (source_path.name, forbidden)


def test_the_reachable_presentation_dependencies_are_the_expected_small_set() -> None:
    """Pin the closure, so a future import cannot widen it unnoticed.

    ``unit_drift_math`` is in the set because ``schemas`` itself imports it: it
    is a leaf pure-``Decimal`` helper with no fault, manifest, or injector
    knowledge, not a private-truth module.
    """
    reachable = _transitive_quantcheck_imports(_SOURCE / "public_artifact_reader.py")
    assert reachable == {
        "quantcheck.benchmark_contract",
        "quantcheck.benchmark_store",
        "quantcheck.hashing",
        "quantcheck.json_types",
        "quantcheck.schemas",
        "quantcheck.serialization",
        "quantcheck.unit_drift_math",
    }


_STREAMLIT_PROBE = """
import sys
import quantcheck
sys.stdout.write("streamlit" if "streamlit" in sys.modules else "clean")
"""


def test_an_ordinary_import_quantcheck_does_not_import_streamlit() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", _STREAMLIT_PROBE],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPOSITORY,
    )
    assert completed.stdout.strip() == "clean"


def test_the_core_package_is_usable_without_importing_dashboard_code() -> None:
    probe = (
        "import sys, quantcheck; "
        "assert not [m for m in sys.modules if m.startswith('dashboard')]; "
        "print(quantcheck.__version__)"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPOSITORY,
    )
    assert completed.stdout.strip()


# --------------------------------------------------------------------------
# Runtime isolation
# --------------------------------------------------------------------------


def test_the_whole_pipeline_runs_with_the_private_tree_physically_absent(
    smoke_root: Path, tmp_path: Path
) -> None:
    copied = copy_public_only(smoke_root, tmp_path / "public-only")
    assert not (copied / q.PRIVATE_ROOT_NAME).exists()
    assert not list(copied.rglob("manifest.json"))

    artifacts = read_public_benchmark(copied)
    model = build_presentation(artifacts)
    destination = tmp_path / "summary.html"
    q.write_html_summary(model, destination)
    assert destination.is_file()
    assert model.configured_case_count == q.SMOKE_CASE_COUNT


def test_the_reader_result_carries_no_filesystem_path(smoke_root: Path) -> None:
    """A path that is never carried cannot later be rendered."""
    artifacts = read_public_benchmark(smoke_root)
    fields = set(type(artifacts).__slots__)
    assert fields == {"config", "matrix", "aggregate", "index", "runtime", "cases"}
    assert not any(isinstance(getattr(artifacts, name), Path) for name in fields)


def test_the_serialized_model_contains_no_manifest_or_injector_field_name(
    smoke_root: Path,
) -> None:
    serialized = q.canonical_json_bytes(
        build_presentation(read_public_benchmark(smoke_root))
    ).decode("utf-8")
    leaked = sorted(marker for marker in PRIVATE_FIELD_MARKERS if marker in serialized)
    assert not leaked, leaked


def test_the_serialized_model_contains_no_global_answer_key_value(smoke_root: Path) -> None:
    serialized = q.canonical_json_bytes(
        build_presentation(read_public_benchmark(smoke_root))
    ).decode("utf-8")
    secrets = manifest_answer_key_strings(smoke_root)
    assert secrets
    leaked = sorted(secret for secret in secrets if secret in serialized)
    assert not leaked, leaked


def test_no_case_in_the_model_reveals_its_own_hidden_record_identity(
    smoke_root: Path,
) -> None:
    model = build_presentation(read_public_benchmark(smoke_root))
    by_id = {case.benchmark_case_id: case for case in model.cases}
    hidden = case_pre_injection_record_ids(smoke_root)
    assert hidden
    for case_id, secrets in hidden.items():
        serialized = q.canonical_json_bytes(by_id[case_id]).decode("utf-8")
        leaked = sorted(secret for secret in secrets if secret in serialized)
        assert not leaked, (case_id, leaked)


def test_private_failure_diagnostics_never_reach_the_model(tmp_path: Path) -> None:
    """Private diagnostics keep the exception text; the model must not have it."""
    from tests.presentation_helpers import build_failed_benchmark

    build_failed_benchmark(tmp_path)
    diagnostics = sorted((tmp_path / q.PRIVATE_ROOT_NAME).rglob("diagnostics.json"))
    assert diagnostics, "the failed case should have produced private diagnostics"
    body = q.parse_canonical_json(diagnostics[0].read_bytes())
    assert isinstance(body, dict)
    message = body["exception_message"]
    assert isinstance(message, str) and message

    serialized = q.canonical_json_bytes(build_presentation(read_public_benchmark(tmp_path))).decode(
        "utf-8"
    )
    assert message not in serialized
    assert body["exception_class"] not in serialized


def test_the_model_cannot_be_pointed_at_the_private_tree(smoke_root: Path) -> None:
    with pytest.raises(q.PublicArtifactError):
        read_public_benchmark(smoke_root / q.PRIVATE_ROOT_NAME)


def test_presentation_writes_nothing_into_the_artifact_tree(smoke_root: Path) -> None:
    before = {path: path.read_bytes() for path in sorted(smoke_root.rglob("*.json"))}
    build_presentation(read_public_benchmark(smoke_root))
    after = {path: path.read_bytes() for path in sorted(smoke_root.rglob("*.json"))}
    assert before == after
