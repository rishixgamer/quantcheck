"""The v0.2 public contract documents versioning and non-migration semantics."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_contract_documents_every_version_and_finding_category() -> None:
    text = (REPO_ROOT / "docs" / "BENCHMARK_V0_2.md").read_text()
    for token in (
        "quantcheck/benchmark/v2",
        "quantcheck/detector-execution/v2",
        "quantcheck/finding-evaluation/v2",
        "primary_matched",
        "secondary_corroborating",
        "independent_background",
        "unmatched",
    ):
        assert token in text


def test_contract_documents_the_three_researcher_questions() -> None:
    text = (REPO_ROOT / "docs" / "BENCHMARK_V0_2.md").read_text()
    assert "Did the primary injected failure get detected?" in text
    assert "What other valid rules did the same record violate?" in text
    assert "Which findings remain genuinely unexplained?" in text


def test_migration_contract_forbids_rewriting_v01_evidence() -> None:
    text = (REPO_ROOT / "docs" / "BENCHMARK_V0_2.md").read_text()
    assert "no in-place migration" in text
    assert "never retroactively" in text
    assert "consumers dispatch on `spec_version`" in text
    assert "CHECKSUMS.md` is intentionally unchanged" in text


def test_v2_decisions_record_dual_views_and_explicit_migration() -> None:
    text = (REPO_ROOT / "docs" / "DECISIONS_V0_2.md").read_text()
    assert "ADR-V2-010 — Selected execution and evaluation use two explicit views" in text
    assert "ADR-V2-011 — v0.2 envelopes are additive" in text
