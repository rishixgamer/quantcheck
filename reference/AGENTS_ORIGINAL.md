# Repository instructions for Codex

## Mission

Build **QuantCheck**, a Python framework that tests whether point-in-time financial research data can manufacture misleading results through timestamp leakage, unit corruption, duplicates, or revision-history failure.

The project must produce reproducible evidence, not a polished but unverifiable demonstration.

## Required first action

Before editing any file:

1. Read `IMPLEMENT.md`.
2. Read `docs/AUTHORITY_AND_READING_ORDER.md`.
3. Read only the task-specific documents required by the reading matrix.
4. Inspect the current repository state.
5. Restate the applicable invariants and acceptance criteria.
6. Propose the smallest viable diff and tests.

Do not begin implementation until the task is coherent.

## Fixed decisions

Do not reopen these decisions unless the user explicitly requests a design revision:

- Python 3.12
- package name `quantcheck`
- `uv`
- Pydantic v2
- Ruff
- MyPy
- pytest
- Hypothesis
- Typer
- HTTPX
- pandas
- PyArrow
- Streamlit only after benchmark and CLI stability
- daily financial availability semantics for v0.1
- end-of-day research decisions for v0.1
- JSON string serialization for `Decimal`
- SHA-256 canonical hashes

## Version 0.1 scope

Version 0.1 includes:

- canonical financial fact and dataset schemas;
- synthetic fixtures;
- one small SEC Company Facts adapter;
- four fault classes;
- one independent detector for each fault class;
- hidden fault manifests;
- exact scoring rules;
- controlled research-impact scenarios;
- a local CLI;
- one thin Streamlit forensic dashboard;
- at least 120 seeded fault cases plus clean controls.

## Non-goals

Do not add:

- authentication, accounts, teams, or billing;
- a hosted multi-tenant SaaS;
- real-money trading;
- order execution;
- portfolio optimization as a core product;
- a general-purpose backtesting engine;
- machine learning without a demonstrated need;
- intraday availability claims;
- streaming infrastructure;
- React or a second frontend;
- microservices, Kubernetes, or distributed workers;
- unsupported claims about alpha, loss prevention, compliance, or certification.

## Hard invariants

1. **Manifest isolation:** detectors and audit orchestration never receive the manifest, pre-corruption values, injected-row flags, or injector-only metadata.
2. **Sanitized audit boundary:** detectors receive `AuditInputSnapshot`, not unrestricted canonical records.
3. **Determinism:** the same clean snapshot, configuration, seed, and code version produce the same corruption and artifacts.
4. **Non-mutation:** caller-owned inputs are never modified in place.
5. **Temporal honesty:** period dates, filing dates, availability dates, and artifact timestamps are distinct concepts.
6. **Day-level finance semantics:** v0.1 uses `date` for financial availability and end-of-day as-of selection.
7. **Precision:** financial values use `Decimal`; public JSON encodes them as canonical strings.
8. **Stable artifacts:** identifiers and hashes follow `docs/SERIALIZATION_AND_HASHING.md`.
9. **Traceability:** every record is traceable to a stable source row or synthetic fixture row.
10. **Evidence-backed findings:** findings include rule ID, affected records, evidence, explanation, and confidence classification.
11. **Clean controls:** every detector is evaluated on uncorrupted data.
12. **No staged benchmark:** scoring can read the manifest only after the audit report is finalized.
13. **No guessed semantics:** unsupported or ambiguous source cases are rejected or explicitly recorded.
14. **No live-network unit tests:** ordinary tests use checked-in fixtures.
15. **Honest results:** synthetic and measured results are clearly distinguished.

## Engineering standards

- Use type hints for all public APIs.
- Keep public schemas independent of pandas and network libraries.
- Prefer immutable models and tuples at public boundaries.
- Prefer explicit domain functions over generic frameworks.
- Avoid hidden global state.
- Avoid broad exception handling that discards context.
- Preserve exception causes when wrapping.
- Add no dependency without a concrete requirement and decision-log entry.
- Do not generate placeholder benchmark results.
- Do not leave `pass`, fake implementations, or unowned TODOs in completed milestones.
- Keep diffs scoped to the task.

## Development sequence

For each task:

1. Inspect specifications and code.
2. State assumptions and risks.
3. Identify tests before implementation.
4. Implement one cohesive behavior.
5. Run targeted checks.
6. Run all applicable quality gates.
7. Review the complete diff.
8. Update `IMPLEMENT.md`.
9. Update contracts or decisions only when behavior truly changed.
10. Report limitations and commands run.

## Completion rule

A task is complete only when:

- acceptance criteria are met;
- positive, negative, edge, and regression tests pass;
- applicable quality gates pass;
- serialized artifacts match their contracts;
- financial semantics were reviewed;
- the diff contains no accidental scope expansion;
- `IMPLEMENT.md` is current.

Passing tests is insufficient when the tests encode the wrong semantics.
