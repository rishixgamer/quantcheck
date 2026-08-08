# QuantCheck

QuantCheck is a deterministic Python framework for testing whether
point-in-time financial research data can manufacture misleading results
through timestamp leakage, unit corruption, duplicate observations, or
revision-history failure. See `PROJECT_SCOPE.md` for the full problem
statement and `MVP_ACCEPTANCE_CRITERIA.md` for the target release criteria.

## Current implementation status

**Recovery Phases 0–10 are complete.** The repository has a typed `quantcheck`
package, a `uv`-managed toolchain (Ruff, MyPy, pytest, Hypothesis), a
deterministic benchmark layer over the four completed fault families, an
installed `quantcheck` CLI (Typer) exposing `ingest sec`, `inject`, `audit`,
`evaluate`, `benchmark run`, `benchmark smoke`, and `explain`, a public-only
presentation layer (strict reader, one shared immutable model, a read-only
Streamlit dashboard, and a deterministic self-contained HTML summary), and a CI
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

A deterministic benchmark layer (strict configuration/expansion, an
all-four-detector dispatcher, public/private atomic artifact persistence,
structured failures, safe resume, and public-only aggregation) and a saved-stage
`inject`/`audit`/`evaluate` CLI workflow over it are documented in
`docs/DECISIONS.md` (ADR-006, ADR-007) and `docs/CLI_CONTRACT.md`.

A public-only presentation layer reads those saved artifacts and nothing else:
a strict reader with a role allowlist, path security, schema validation, and
SHA-256 verification; one immutable model shared by both surfaces; a read-only
Streamlit forensic dashboard; and a deterministic self-contained HTML summary.
Both surfaces work with the entire `private/` tree deleted and execute no
scientific logic. See [`docs/DASHBOARD_AND_HTML.md`](docs/DASHBOARD_AND_HTML.md)
and ADR-008.

**Not implemented yet:** release evidence (Recovery Phase 11). The reserved
final seeds `1000–1009` remain prohibited, and no final held-out benchmark has
been run. No benchmark metrics, hashes, or test counts from any prior
implementation apply to this repository; no historical digest is reproduced
or claimed. `IMPLEMENT.md` is the authoritative operational record and
next-task handoff.

## CLI usage

```bash
# Run the deterministic offline smoke benchmark.
uv run quantcheck benchmark smoke --output /tmp/qc-smoke --json

# Inject, audit, and evaluate one saved, fully expanded benchmark case.
uv run quantcheck inject --case case.json --output /tmp/qc-case
uv run quantcheck audit --dir /tmp/qc-case
uv run quantcheck evaluate --dir /tmp/qc-case

# Explain one saved public finding.
uv run quantcheck explain --dir /tmp/qc-case --finding <finding_id>
```

See [`docs/CLI_CONTRACT.md`](docs/CLI_CONTRACT.md) for the full command
surface, exit-code taxonomy, and privacy rules.

## Reviewing saved results

Both presentation surfaces read saved **public** artifacts only. Neither is a
`quantcheck` CLI command — the root command surface stays exactly six.

```bash
# 1. Produce artifacts with the existing offline smoke benchmark.
uv run quantcheck benchmark smoke --output artifacts/smoke

# 2. Launch the local read-only forensic dashboard.
uv run --group dashboard streamlit run dashboard/app.py -- --artifacts artifacts/smoke

# 3. Render the deterministic self-contained HTML summary.
uv run python scripts/render_html_summary.py artifacts/smoke \
  --output artifacts/smoke/summary.html
```

The `--` separator is required so the arguments reach the app rather than
Streamlit. Both surfaces work against a copy of `public/` alone, with the entire
`private/` tree deleted, and neither runs injection, detection, scoring, replay,
or private research logic. Streamlit lives in the optional `dashboard`
dependency group, so an ordinary `import quantcheck` never imports it.

[`docs/DASHBOARD_AND_HTML.md`](docs/DASHBOARD_AND_HTML.md) documents the reader
trust boundary, path-security rules, privacy and determinism guarantees, the
null-metric display policy, and how failed and incomplete cases are handled.

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
- `dashboard/` — the standalone read-only Streamlit app (not distributed).
- `scripts/` — repository development tools (not distributed).
- `tests/` — unit and smoke tests.
- `docs/` — current architecture and process documents, starting with
  `docs/AUTHORITY_AND_READING_ORDER.md`.
- `reference/` — historical documents describing the project concept and a
  prior 0.1.0 implementation. They are specifications and historical
  evidence only; they do not describe the current state of this repository.
- `AGENTS.md`, `PROJECT_SCOPE.md`, `MVP_ACCEPTANCE_CRITERIA.md`,
  `IMPLEMENT.md` — governing instructions, scope, acceptance criteria, and
  the operational implementation log for agents working in this repository.
