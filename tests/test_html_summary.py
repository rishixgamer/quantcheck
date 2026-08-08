"""The deterministic self-contained HTML summary.

Determinism and escaping are the whole contract here: the same logical public
artifacts must produce the same bytes anywhere, in any process, under any hash
seed, and no artifact-derived string may ever reach the page unescaped.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from decimal import Decimal
from html import escape
from pathlib import Path

import pytest

import quantcheck as q
from quantcheck.benchmark_store import ArtifactIntegrityError
from quantcheck.html_summary import (
    HtmlSummaryError,
    render_html_summary,
    write_html_summary,
)
from quantcheck.presentation import build_presentation
from quantcheck.public_artifact_reader import read_public_benchmark
from tests.presentation_helpers import (
    build_failed_benchmark,
    build_incomplete_benchmark,
    build_smoke_benchmark,
    copy_public_only,
)


@pytest.fixture(scope="module")
def smoke_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("html-smoke")
    build_smoke_benchmark(root)
    return root


@pytest.fixture(scope="module")
def presentation(smoke_root: Path) -> q.BenchmarkPresentation:
    return build_presentation(read_public_benchmark(smoke_root))


@pytest.fixture(scope="module")
def rendered(presentation: q.BenchmarkPresentation) -> str:
    return render_html_summary(presentation)


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


def test_identical_input_renders_identical_bytes(
    presentation: q.BenchmarkPresentation,
) -> None:
    assert render_html_summary(presentation) == render_html_summary(presentation)


def test_two_different_destinations_receive_identical_bytes(
    presentation: q.BenchmarkPresentation, tmp_path: Path
) -> None:
    first = tmp_path / "a" / "summary.html"
    second = tmp_path / "b" / "summary.html"
    assert write_html_summary(presentation, first) == write_html_summary(presentation, second)
    assert first.read_bytes() == second.read_bytes()


def test_the_output_root_never_reaches_the_rendered_bytes(
    smoke_root: Path, tmp_path: Path, rendered: str
) -> None:
    """Re-run the same benchmark into a different root; the HTML is unchanged."""
    other = tmp_path / "elsewhere"
    build_smoke_benchmark(other)
    from_other = render_html_summary(build_presentation(read_public_benchmark(other)))
    assert from_other == rendered


def test_a_public_only_copy_renders_identical_bytes(
    smoke_root: Path, tmp_path: Path, rendered: str
) -> None:
    copied = copy_public_only(smoke_root, tmp_path / "public-only")
    assert render_html_summary(build_presentation(read_public_benchmark(copied))) == rendered


_SUBPROCESS_RENDER = """
import hashlib, sys
import quantcheck as q
artifacts = q.read_public_benchmark(sys.argv[1])
payload = q.render_html_summary(q.build_presentation(artifacts)).encode("utf-8")
sys.stdout.write(hashlib.sha256(payload).hexdigest())
"""


@pytest.mark.parametrize("hash_seed", ["0", "1", "987654"])
def test_a_fresh_subprocess_renders_identical_bytes_under_any_hash_seed(
    smoke_root: Path, rendered: str, hash_seed: str
) -> None:
    environment = dict(os.environ, PYTHONHASHSEED=hash_seed)
    completed = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_RENDER, str(smoke_root)],
        capture_output=True,
        text=True,
        check=True,
        env=environment,
    )
    expected = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    assert completed.stdout.strip() == expected


def test_rendering_is_unaffected_by_the_working_directory(
    smoke_root: Path, tmp_path: Path, rendered: str
) -> None:
    previous = Path.cwd()
    os.chdir(tmp_path)
    try:
        model = build_presentation(read_public_benchmark(smoke_root))
        assert render_html_summary(model) == rendered
    finally:
        os.chdir(previous)


# --------------------------------------------------------------------------
# Self-containment and privacy
# --------------------------------------------------------------------------


def test_the_page_is_utf8_and_declares_it(rendered: str) -> None:
    assert rendered.startswith("<!DOCTYPE html>")
    assert '<meta charset="utf-8">' in rendered
    rendered.encode("utf-8").decode("utf-8")


def test_the_page_contains_no_javascript(rendered: str) -> None:
    lowered = rendered.lower()
    assert "<script" not in lowered
    assert "javascript:" not in lowered
    assert not re.search(r"\son[a-z]+\s*=", lowered)


def test_the_page_loads_no_remote_resource(rendered: str) -> None:
    lowered = rendered.lower()
    for marker in ("http://", "https://", "//cdn", "<link", "<img", "@import", "src="):
        assert marker not in lowered, marker


def test_the_page_carries_no_render_timestamp_or_random_identifier(rendered: str) -> None:
    assert not re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", rendered)
    assert "generated_at" not in rendered
    assert "Generated on" not in rendered


def test_the_page_contains_no_local_filesystem_path(rendered: str, smoke_root: Path) -> None:
    assert str(smoke_root) not in rendered
    assert str(Path.home()) not in rendered
    for marker in ("/Users/", "/home/", "/var/folders", "/private/var", "C:\\"):
        assert marker not in rendered, marker


def test_the_page_contains_no_private_answer_key_value(rendered: str, smoke_root: Path) -> None:
    """Manifest, fault, and selection-digest identities are private everywhere."""
    from tests.presentation_helpers import manifest_answer_key_strings

    secrets = manifest_answer_key_strings(smoke_root)
    assert secrets, "the smoke run should have produced private manifests to check against"
    leaked = sorted(secret for secret in secrets if secret in rendered)
    assert not leaked, leaked


def test_no_case_section_reveals_its_own_pre_injection_record_identity(
    smoke_root: Path, presentation: q.BenchmarkPresentation
) -> None:
    """A hidden identity is private *relative to its own case*.

    The same clean record legitimately appears in a clean control and in another
    seed's case, where it was never a target, so a page-wide scan would be both
    wrong and weaker. This checks the identity that actually matters: the record
    each case's own injector replaced must not appear in that case's own output.
    """
    from tests.presentation_helpers import case_pre_injection_record_ids

    hidden = case_pre_injection_record_ids(smoke_root)
    assert hidden, "the smoke run should include replacing-family fault cases"
    by_id = {case.benchmark_case_id: case for case in presentation.cases}
    for case_id, secrets in hidden.items():
        serialized = q.canonical_json_bytes(by_id[case_id]).decode("utf-8")
        leaked = sorted(secret for secret in secrets if secret in serialized)
        assert not leaked, (case_id, leaked)


def test_the_page_contains_no_manifest_or_injector_field_name(rendered: str) -> None:
    from tests.presentation_helpers import PRIVATE_FIELD_MARKERS

    leaked = sorted(marker for marker in PRIVATE_FIELD_MARKERS if marker in rendered)
    assert not leaked, leaked


# --------------------------------------------------------------------------
# Escaping
# --------------------------------------------------------------------------


def _hostile_presentation() -> q.BenchmarkPresentation:
    """A model whose artifact-derived strings are all markup-shaped.

    Escaping is checked against a model built by hand rather than a real run,
    because the reviewed fixtures contain no hostile text — and "our data
    happens to be safe" is not the property under test.
    """
    hostile = '<script>alert("x")&\'</script>'
    metrics = q.PresentationMetrics(
        injected_faults=1,
        findings=1,
        true_positive_faults=1,
        false_negative_faults=0,
        true_positive_findings=1,
        false_positive_findings=0,
        eligible_clean_denominator=0,
        precision=Decimal(1),
        recall=Decimal(1),
        f1=Decimal(1),
        false_positive_rate=None,
    )
    finding = q.PresentationFinding(
        finding_id=hostile,
        rule_id=hostile,
        detector_id=hostile,
        detector_version=hostile,
        fault_type=hostile,
        fault_subtype=hostile,
        severity=hostile,
        confidence=hostile,
        explanation=hostile,
        affected_record_ids=(hostile,),
        evidence=(q.PresentationEvidenceItem(label=hostile, value=hostile),),
    )
    case = q.PresentationCase(
        benchmark_case_id=hostile,
        case_kind=hostile,
        fault_profile=hostile,
        severity=hostile,
        seed=0,
        seed_class=hostile,
        fixture_id=hostile,
        dataset_name=hostile,
        as_of_date=hostile,
        terminal_status=hostile,
        audit_input_record_count=1,
        metrics=metrics,
        research=q.PresentationResearch(method=hostile, changed=True, exact_restoration=False),
        findings=(finding,),
        failure=q.PresentationFailure(
            stage=hostile, category=hostile, error_code=hostile, message=hostile
        ),
    )
    return q.BenchmarkPresentation(
        benchmark_id=hostile,
        benchmark_name=hostile,
        spec_version=hostile,
        aggregate_report_id=hostile,
        configured_case_count=1,
        successful_case_count=1,
        failed_case_count=0,
        incomplete_case_count=0,
        clean_control_count=0,
        fault_case_count=1,
        overall=metrics,
        by_fault_profile=(
            q.PresentationGroup(
                grouping=hostile,
                key=hostile,
                configured_case_count=1,
                successful_case_count=1,
                failed_case_count=0,
                incomplete_case_count=0,
                metrics=metrics,
                research_summary_count=1,
                research_changed_count=1,
                replay_restored_count=1,
            ),
        ),
        by_severity=(),
        by_seed_class=(),
        by_seed=(),
        cases=(case,),
    )


def test_artifact_derived_markup_is_escaped_everywhere() -> None:
    page = render_html_summary(_hostile_presentation())
    assert "<script>alert" not in page
    assert "&lt;script&gt;alert(&quot;x&quot;)&amp;&#x27;&lt;/script&gt;" in page
    assert page.lower().count("<script") == 0


@pytest.mark.parametrize("character", ["<", ">", "&", '"', "'"])
def test_every_dangerous_character_is_escaped(character: str) -> None:
    page = render_html_summary(_hostile_presentation())
    # The hostile string contains all five; none may survive unescaped inside
    # the rendered text nodes, so the raw hostile substring must be absent.
    assert '<script>alert("x")&\'</script>' not in page
    assert character in "<>&\"'"


# --------------------------------------------------------------------------
# Failed, incomplete, and null-metric content
# --------------------------------------------------------------------------


def test_a_failed_case_is_rendered_with_its_redacted_failure(tmp_path: Path) -> None:
    build_failed_benchmark(tmp_path)
    page = render_html_summary(build_presentation(read_public_benchmark(tmp_path)))
    assert "no_eligible_targets" in page
    # The fixed public sentence contains an apostrophe, which the renderer
    # correctly escapes; comparing against the escaped form proves both that
    # the message is present and that it went through escaping.
    assert escape(q.redacted_failure_message("no_eligible_targets"), quote=True) in page
    assert "status-failed" in page


def test_an_incomplete_case_is_rendered_as_incomplete(tmp_path: Path) -> None:
    case_id = build_incomplete_benchmark(tmp_path)
    page = render_html_summary(build_presentation(read_public_benchmark(tmp_path)))
    assert case_id in page
    assert "status-incomplete" in page
    assert "reported as incomplete rather than assumed successful" in page


def test_a_null_metric_is_rendered_as_undefined_not_zero(tmp_path: Path) -> None:
    build_failed_benchmark(tmp_path)
    page = render_html_summary(build_presentation(read_public_benchmark(tmp_path)))
    assert '<span class="null">n/a</span>' in page


def test_clean_controls_are_rendered(smoke_root: Path, rendered: str) -> None:
    model = build_presentation(read_public_benchmark(smoke_root))
    controls = [case for case in model.cases if case.case_kind == "clean_control"]
    assert controls
    for control in controls:
        assert control.benchmark_case_id in rendered


# --------------------------------------------------------------------------
# Output behaviour
# --------------------------------------------------------------------------


def test_an_identical_existing_output_is_reused_untouched(
    presentation: q.BenchmarkPresentation, tmp_path: Path
) -> None:
    destination = tmp_path / "summary.html"
    write_html_summary(presentation, destination)
    before = destination.stat().st_mtime_ns
    payload = write_html_summary(presentation, destination)
    assert destination.read_bytes() == payload
    assert destination.stat().st_mtime_ns == before


def test_a_conflicting_existing_output_is_rejected_rather_than_overwritten(
    presentation: q.BenchmarkPresentation, tmp_path: Path
) -> None:
    destination = tmp_path / "summary.html"
    destination.write_bytes(b"<html>someone else's report</html>")
    with pytest.raises(ArtifactIntegrityError, match="different content"):
        write_html_summary(presentation, destination)
    assert destination.read_bytes() == b"<html>someone else's report</html>"


@pytest.mark.parametrize("name", ["summary.json", "summary", "summary.htm", "summary.HTML"])
def test_a_non_html_destination_is_rejected(
    presentation: q.BenchmarkPresentation, tmp_path: Path, name: str
) -> None:
    with pytest.raises(HtmlSummaryError, match="must end in"):
        write_html_summary(presentation, tmp_path / name)


def test_a_directory_in_place_of_the_output_file_is_rejected(
    presentation: q.BenchmarkPresentation, tmp_path: Path
) -> None:
    destination = tmp_path / "summary.html"
    destination.mkdir()
    with pytest.raises(HtmlSummaryError, match="is a directory"):
        write_html_summary(presentation, destination)


def test_an_impossible_destination_leaves_no_partial_output(
    presentation: q.BenchmarkPresentation, tmp_path: Path
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"not a directory")
    destination = blocker / "nested" / "summary.html"
    with pytest.raises(HtmlSummaryError):
        write_html_summary(presentation, destination)
    assert not destination.exists()
    assert blocker.read_bytes() == b"not a directory"


def test_a_failed_write_leaves_no_temporary_file_behind(
    presentation: q.BenchmarkPresentation, tmp_path: Path
) -> None:
    directory = tmp_path / "readonly"
    directory.mkdir()
    destination = directory / "summary.html"
    directory.chmod(0o500)
    try:
        with pytest.raises(HtmlSummaryError):
            write_html_summary(presentation, destination)
        assert list(directory.iterdir()) == []
    finally:
        directory.chmod(0o700)


def test_the_script_entry_point_renders_the_same_bytes(
    smoke_root: Path, tmp_path: Path, rendered: str
) -> None:
    destination = tmp_path / "from-script.html"
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent.parent / "scripts" / "render_html_summary.py"),
            str(smoke_root),
            "--output",
            str(destination),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.returncode == 0
    assert destination.read_text(encoding="utf-8") == rendered
