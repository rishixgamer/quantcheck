# Repository instructions for Claude Code

## Mission

Rebuild **QuantCheck**, a Python framework that tests whether point-in-time financial research data can manufacture misleading results through timestamp leakage, unit corruption, duplicate observations, or revision-history failure.

The repository currently starts from source-code loss. Historical documents under `reference/` describe the intended behavior but are not current implementation status.

## Required first action

Before editing any file:

1. Read `IMPLEMENT.md`.
2. Read `docs/AUTHORITY_AND_READING_ORDER.md`.
3. Read `PROJECT_SCOPE.md` and `MVP_ACCEPTANCE_CRITERIA.md`.
4. Read only the task-specific historical references required for the current milestone.
5. Inspect the actual repository tree and Git status.
6. Restate the applicable invariants and acceptance criteria.
7. Propose the smallest viable diff and tests.

Do not claim that historical release behavior exists unless it is present in the new code and verified locally.

## Fixed technical choices

- Python 3.12
- package name `quantcheck`
- `uv`
- Hatchling
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
- day-level financial availability semantics for v0.1
- end-of-day research decisions for v0.1
- JSON string serialization for `Decimal`
- SHA-256 canonical hashes

## Hard invariants

1. Detectors never receive manifests, pre-corruption values, injected-row flags, or injector-only metadata.
2. Detectors receive a sanitized `AuditInputSnapshot`, not unrestricted canonical records.
3. The same clean snapshot, configuration, seed, and code version produce the same logical corruption and artifacts.
4. Caller-owned inputs are never modified in place.
5. Period, filing, availability, as-of, and runtime dates are distinct concepts.
6. Financial values use `Decimal`; public JSON encodes them as canonical strings.
7. IDs and hashes must not depend on DataFrame row position or Python hash randomization.
8. Findings contain a rule ID, affected records, evidence, explanation, and confidence classification.
9. Every detector is evaluated against clean controls.
10. Scoring can read the private manifest only after the audit report is finalized.
11. Ordinary tests make no live network requests.
12. Unsupported source semantics are rejected or explicitly recorded rather than guessed.
13. Synthetic, controlled, and real-data claims remain clearly distinguished.
14. Historical metrics and hashes are not copied into new output unless reproduced from the rebuilt implementation.

## Scope discipline

Do not add authentication, SaaS infrastructure, real-money trading, a generic backtester, machine learning, intraday claims, React, microservices, Kubernetes, or new fault families during the v0.1 rebuild.

## Completion rule

A task is complete only when its acceptance criteria, positive/negative/edge/regression tests, applicable quality gates, serialization contracts, and financial semantics all pass; the diff is scoped; and `IMPLEMENT.md` is current.
