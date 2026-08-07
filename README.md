# QuantCheck

QuantCheck is a deterministic Python framework for testing whether
point-in-time financial research data can manufacture misleading results
through timestamp leakage, unit corruption, duplicate observations, or
revision-history failure. See `PROJECT_SCOPE.md` for the full problem
statement and `MVP_ACCEPTANCE_CRITERIA.md` for the target release criteria.

## Current implementation status

**Recovery Phases 0–7 are complete.** The repository has a typed `quantcheck`
package, a `uv`-managed toolchain (Ruff, MyPy, pytest, Hypothesis), an installed
`quantcheck` CLI entry point that supports only `--help`/`--version`, and a CI
workflow that runs the baseline quality gates.

The implemented deterministic foundation includes:

- strict JSON-domain value types and exact `Decimal`/`date`/UTC-timestamp encodings;
- immutable, strictly validated Pydantic v2 schemas (`FinancialFact`,
  `SourceReference`, `Dimension`, `DatasetSnapshot`, `AuditInputRecord`,
  `AuditInputSnapshot`, `CaseConfig`, `RuntimeMetadata`, `ArtifactIdentity`,
  and the narrow Look-Ahead, Unit Drift, Duplicate Observations, and Revision
  Overwrite evidence artifacts);
- one canonical serialization path producing deterministic UTF-8 bytes;
- SHA-256 content hashes and prefixed, row-order-independent stable identifiers.
- a deterministic, reviewed 26-record synthetic fixture, explicit revision
  lineages, end-of-day point-in-time snapshots, and `sanitize_for_audit`;
- the complete `lookahead_timestamp` / `period_end_substitution` slice:
  deterministic injection, private manifest, manifest-blind detection, exact
  matching/scoring, controlled `availability_count_v0_1`, and private
  manifest-assisted exact replay;
- the complete `unit_drift` / `value_scaled_unit_unchanged` slice: exact
  comparable-series grouping, deterministic value scaling with unchanged unit,
  manifest-blind immediate-neighbor ratio detection, exact matching/scoring,
  controlled `aggregate_value_v0_1`, and private manifest-assisted exact replay;
- the complete `duplicate_observation` / `exact_occurrence_copy` slice: an
  exact fingerprint shared by injection eligibility and detection, one
  appended created copy per selected source (never a replacement), exact
  fingerprint-group matching/scoring with a fixed `medium` finding severity,
  controlled `record_count_v0_1` plus reuse of the existing
  `aggregate_value_v0_1` for a double-counting demonstration, and private
  manifest-assisted exact replay that removes only the injected copies;
- the complete `revision_overwrite` / `later_vintage_in_earlier_state` slice:
  explicit source-supported adjacent revision histories, deterministic
  later-vintage substitution retaining historical availability, manifest-blind
  temporal-contradiction detection, exact matching/scoring, private
  manifest-assisted exact replay, and a controlled frozen-vintage
  `growth_ranking_v0_1` sensitivity comparison;
- a narrow synchronous SEC Company Facts adapter: one CIK at a time, explicit
  contact-bearing user-agent, HTTPX-only requests, cache-first exact-byte
  persistence, integrity-checked offline replay, and explicit
  taxonomy/concept/unit/form/date/period-shape allowlists. Supported SEC facts
  use the day-level rule `available_on == filed_on` and flow through the
  existing point-in-time and audit-boundary code. Ordinary tests use HTTPX
  mock transports and never call the live SEC service.

The rules are documented in [`docs/SERIALIZATION_AND_HASHING.md`](docs/SERIALIZATION_AND_HASHING.md),
[`docs/faults/LOOK_AHEAD.md`](docs/faults/LOOK_AHEAD.md),
[`docs/faults/UNIT_DRIFT.md`](docs/faults/UNIT_DRIFT.md),
[`docs/faults/DUPLICATE_OBSERVATIONS.md`](docs/faults/DUPLICATE_OBSERVATIONS.md), and
[`docs/faults/REVISION_OVERWRITE.md`](docs/faults/REVISION_OVERWRITE.md); they are frozen by
static golden vectors and focused tests.

The SEC adapter does not reconstruct statements, harmonize concepts, convert
currencies or scale, infer segments/amendments/revisions/duplicates, look up
tickers, download multiple CIKs, expire caches, or make intraday availability
claims.

**Not implemented yet:** full benchmark artifacts, contracted Typer CLI, or
the dashboard/HTML presentation layer. No benchmark metrics, hashes, or test
counts from any prior implementation apply to this repository; no historical
digest is reproduced or claimed. `IMPLEMENT.md` is the authoritative
operational record and next-task handoff.

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
