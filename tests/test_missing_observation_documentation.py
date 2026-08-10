"""Documentation honesty and frozen-v0.1 isolation for Milestone H."""

from __future__ import annotations

from pathlib import Path

import quantcheck as q

REPO_ROOT = Path(__file__).resolve().parents[1]


def _normalized(path: str) -> str:
    return " ".join((REPO_ROOT / path).read_text().split())


def test_fault_contract_records_the_evidence_tie_and_fallback() -> None:
    text = _normalized("docs/faults/MISSING_OBSERVATIONS.md")
    assert "available evidence therefore does not distinguish them" in text
    assert "implemented first only by the milestone's explicit tie-break rule" in text
    assert "not evidence that customers reported more missingness pain" in text
    assert "customer_evidence=false" in text


def test_fault_contract_names_all_mechanisms_and_expectation_boundary() -> None:
    text = _normalized("docs/faults/MISSING_OBSERVATIONS.md")
    for phrase in (
        "random missingness",
        "periodic/reporting gaps",
        "entity-dependent missingness",
        "concept-dependent missingness",
        "survivorship-like filtering",
        "source-feed outage",
        "gap without an expectation is outside detector authority",
        "future expectation is explicitly not evaluated",
        "manifest-assisted",
        "held-out",
    ):
        assert phrase in text


def test_adr_records_selection_and_rejected_trust_boundary_weakening() -> None:
    text = _normalized("docs/DECISIONS_V0_2.md")
    assert "ADR-V2-018" in text
    assert "The evidence cannot distinguish them" in text
    assert "Require an identity-bearing public detector configuration" in text
    assert "passing deleted records, manifests, seeds" in text
    assert "presenting synthetic held-out evidence as a design-partner pilot" in text


def test_frozen_v01_package_surface_does_not_import_new_family() -> None:
    freeze = q.read_release_freeze_record(REPO_ROOT / "release_freeze.json")
    for entry in freeze.frozen_files:
        if not entry.path.startswith("src/quantcheck/") or not entry.path.endswith(".py"):
            continue
        assert "quantcheck.missing_observation" not in (REPO_ROOT / entry.path).read_text()
    assert "missing_observation" not in (REPO_ROOT / "src/quantcheck/__init__.py").read_text()


def test_only_the_repository_evaluation_script_opens_the_heldout_gate() -> None:
    callers = []
    for root in (REPO_ROOT / "src", REPO_ROOT / "scripts"):
        for path in root.rglob("*.py"):
            if path.name == "missing_observation_gate.py":
                continue
            if "heldout_missing_observation_cases" in path.read_text():
                callers.append(path.relative_to(REPO_ROOT).as_posix())
    assert callers == ["scripts/missing_observation_evaluation.py"]
