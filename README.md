# QuantCheck

QuantCheck is a deterministic Python framework for testing whether
point-in-time financial research data can manufacture misleading results
through timestamp leakage, unit corruption, duplicate observations, or
revision-history failure. See `PROJECT_SCOPE.md` for the full problem
statement and `MVP_ACCEPTANCE_CRITERIA.md` for the target release criteria.

## Current implementation status

**Milestone 0 (repository bootstrap) and Milestone 1 (canonical contract
layer) are complete.** The repository has a typed `quantcheck` package, a
`uv`-managed toolchain (Ruff, MyPy, pytest, Hypothesis), an installed
`quantcheck` CLI entry point that supports only `--help`/`--version`, and a CI
workflow that runs the baseline quality gates.

Milestone 1 provides the deterministic layer everything else will depend on:

- strict JSON-domain value types and exact `Decimal`/`date`/UTC-timestamp encodings;
- immutable, strictly validated Pydantic v2 schemas (`FinancialFact`,
  `SourceReference`, `Dimension`, `DatasetSnapshot`, `AuditInputRecord`,
  `AuditInputSnapshot`, `CaseConfig`, `RuntimeMetadata`, `ArtifactIdentity`);
- one canonical serialization path producing deterministic UTF-8 bytes;
- SHA-256 content hashes and prefixed, row-order-independent stable identifiers.

The rules are documented in [`docs/SERIALIZATION_AND_HASHING.md`](docs/SERIALIZATION_AND_HASHING.md)
and frozen by static golden vectors in `tests/`.

**Not implemented yet:** fixtures, point-in-time snapshot selection, revision
ordering, sanitized audit-input conversion, the SEC adapter, fault injectors,
detectors, manifests, scoring, benchmark artifacts, and the dashboard/HTML
presentation layer. No benchmark metrics, hashes, or test counts from any prior
implementation apply to this repository; the original serialization contract did
not survive, so no historical digest is reproduced or claimed. `IMPLEMENT.md` is
the authoritative record of current status and the next task.

## Development setup

Requires [`uv`](https://docs.astral.sh/uv/) and Python `>=3.12,<3.13` (uv can
install the interpreter for you).

```bash
uv python install 3.12
uv sync --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
uv run quantcheck --help
```

## Repository layout

- `src/quantcheck/` — the package.
- `tests/` — unit and smoke tests.
- `docs/` — current architecture and process documents, starting with
  `docs/AUTHORITY_AND_READING_ORDER.md`.
- `reference/` — historical documents describing the project concept and a
  prior 0.1.0 implementation. They are specifications and historical
  evidence only; they do not describe the current state of this repository.
- `AGENTS.md`, `PROJECT_SCOPE.md`, `MVP_ACCEPTANCE_CRITERIA.md`,
  `IMPLEMENT.md` — governing instructions, scope, acceptance criteria, and
  the operational implementation log for agents working in this repository.
