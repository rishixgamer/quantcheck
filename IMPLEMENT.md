# Implementation status

This is the operational handoff between Claude Code sessions. Keep it concise, factual, and current.

## Current phase

**Recovery Milestone 0 — Repository bootstrap not started**

The original source repository was lost. Historical 0.1.0 documentation survives under `reference/`, but no historical implementation claim is considered current until rebuilt and verified.

## Immediate next task

Complete repository bootstrap only:

- initialize the Python 3.12 package and `src/` layout;
- configure `uv`, Hatchling, Ruff, MyPy, pytest, and Hypothesis;
- add the installed `quantcheck` CLI entry point with help-only placeholder behavior;
- add GitHub Actions for the baseline quality gates;
- add minimal package and smoke tests;
- make all baseline commands pass from a clean checkout.

Do not implement financial schemas, injectors, detectors, benchmarks, SEC access, dashboard logic, or historical release metrics in Milestone 0.

## Fixed implementation choices

- Python: 3.12
- Package: `quantcheck`
- Dependency manager: `uv`
- Build backend: Hatchling
- Public schemas: Pydantic v2, introduced in the schemas milestone
- Lint and format: Ruff
- Type checking: MyPy
- Tests: pytest and Hypothesis
- CLI: Typer, introduced at the contracted milestone unless a minimal entry-point dependency is deliberately deferred
- HTTP: HTTPX, introduced with the SEC adapter
- Tabular processing: pandas and PyArrow, introduced only when required
- Dashboard: Streamlit, introduced only after benchmark and CLI stability

## Historical target

The prior release documentation describes a 0.1.0 implementation with four fault families, a 132-case frozen benchmark, a strict CLI, public/private artifacts, and read-only presentation. Those documents are design and acceptance references, not current status.

## Required handoff update after each task

Record:

- milestone and task completed;
- files changed;
- commands run and exact outcomes;
- decisions added or revised;
- known limitations;
- exact next task.

## Last updated

2026-08-06
