# QuantCheck

QuantCheck is a deterministic Python framework for testing whether
point-in-time financial research data can manufacture misleading results
through timestamp leakage, unit corruption, duplicate observations, or
revision-history failure. See `PROJECT_SCOPE.md` for the full problem
statement and `MVP_ACCEPTANCE_CRITERIA.md` for the target release criteria.

## Current implementation status

**Recovery Phases 0–11 are complete.** The immutable `v0.1.0` tag remains the
historical release. The current worktree is version `0.2.0.dev0`, a
design-partner beta-closure candidate rather than a production release. It has
a typed `quantcheck` package, a `uv`-managed toolchain (Ruff, MyPy, pytest,
Hypothesis), a
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

A release-evidence layer executes the held-out benchmark. Reserved final seeds
`1000–1009` are rejected by every ordinary interface and are executable only
through an explicit release path, guarded by a byte-verified frozen release
candidate. See [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) and ADR-009/ADR-010.

No benchmark metric, hash, identifier, or test count from any prior
implementation applies to this repository; every number below was measured by
this code. `IMPLEMENT.md` is the authoritative operational record and next-task
handoff.

## Final held-out benchmark result

Release candidate `relc_2c6e945a71b85b39`, benchmark `bench_403a85e506ff66ea`,
aggregate `agg_571aae0b7c60a4a5`. 4 fault profiles × 3 severities × 10 reserved
final seeds = 120 held-out fault cases, plus 4 clean controls = **124 cases**.

| Metric | Exact saved value |
| --- | --- |
| Successful / failed / incomplete | 94 / 30 / 0 |
| Injected faults / findings | 130 / 208 |
| True positives / false negatives | 130 / 0 |
| False-positive findings | 78 |
| Eligible clean denominator | 1070 |
| **Precision** | `0.625` |
| **Recall** | `1` |
| **F1** | `0.76923076923076923076923076923076923076923076923077` |
| **False-positive rate** | `0.072897196261682242990654205607476635514018691588785` |
| Research output changed | 90 / 90 |
| Exact replay restored | 90 / 90 |

Read honestly: **30 cases failed** with `no_eligible_targets` because three
profile/severity cells have no eligible target on the reviewed fixture
(Look-Ahead at `high`, Revision Overwrite at `medium` and `high`). They were
kept in the matrix rather than configured away. **All 78 false positives are
cross-detector findings** under strict primary-label scoring, dominated by the
reviewed fixture's documented natural duplicate pair — retained detector
behaviour, not a defect, and not tuned. Recall of `1` is a measurement on a
26-record synthetic fixture, not a general sensitivity claim.

Every number traces to `release_evidence/final/public/aggregate_report.json`.
Full breakdown, per-seed metrics, and failure analysis:
[`docs/FINAL_BENCHMARK_RESULTS.md`](docs/FINAL_BENCHMARK_RESULTS.md).

**QuantCheck claims no** production readiness, completed design-partner pilot,
customer validation, financial-data certification,
automated remediation, loss prevention, trading alpha, universal SEC coverage,
statement reconstruction, universal restatement detection, or vendor-wide
reliability. See [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

## Installation and five-minute quick start

```bash
# 1. Install (Python 3.12).
uv sync --all-groups          # from a checkout
# or: pip install dist/quantcheck-0.2.0.dev0-py3-none-any.whl

# 2. Confirm the CLI works.
uv run quantcheck --help

# 3. Run the deterministic offline smoke benchmark (12 cases, no network).
uv run quantcheck benchmark smoke --output /tmp/qc-smoke

# 4. Render the self-contained HTML summary from public artifacts only.
uv run python scripts/render_html_summary.py /tmp/qc-smoke \
    --output /tmp/qc-smoke/summary.html

# 5. Browse the same artifacts in the local read-only dashboard.
uv run --group dashboard streamlit run dashboard/app.py -- --artifacts /tmp/qc-smoke
```

## Reproducing the final benchmark

The commands below reproduce the historical v0.1 held-out evidence. They are
not the v0.2 development/validation evidence path.

```bash
uv run python scripts/release_freeze.py --check          # must pass first
uv run python scripts/run_release_benchmark.py --output release_evidence/final
uv run python scripts/verify_release_evidence.py \
    --source release_evidence/final \
    --public-only release_evidence/public_only \
    --html release_evidence/public_only/summary.html
uv run python scripts/release_checksums.py --check
```

Reserved seeds execute only through `scripts/run_release_benchmark.py`, and only
after the frozen candidate verifies byte for byte against the working tree.
See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md).

## Reproducing the v0.2 beta-candidate evidence

The v0.2 runner preregisters separate 390-case development and validation
matrices. It completes development first, writes a validation freeze over both
matrices plus the development aggregate and science-source hashes, and only
then unseals validation. Every case has a paired clean control. Failed and
incomplete cases remain visible, and aggregates rebuild byte-for-byte from the
public tree without the private manifests or snapshots.

```bash
uv run python scripts/run_benchmark_v2_evidence.py \
  --partition all --output benchmark_evidence_v0_2

uv build --offline
uv run python scripts/build_beta_evidence.py \
  --benchmark-evidence benchmark_evidence_v0_2 \
  --output evidence/design_partner_beta
```

`design_partner_beta_freeze.json` binds the current package, source-tree hash,
corpus identities, development/validation aggregate identities, distributions,
SBOM, provenance statement, OCI state, and attestation state. Generated bulky
case evidence lives in the gitignored `benchmark_evidence_v0_2/` directory;
compact aggregates and supply-chain records persist under
`evidence/design_partner_beta/`. This is synthetic engineering evidence, not a
design-partner result; held-out v0.2 execution remains separately gated.

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
  `docs/AUTHORITY_AND_READING_ORDER.md`. Release documents:
  `METHODOLOGY.md`, `ARTIFACTS_AND_PRIVACY.md`, `THREAT_MODEL.md`,
  `REPRODUCIBILITY.md`, `FINAL_BENCHMARK_RESULTS.md`, `LIMITATIONS.md`,
  `RELEASE_CHECKLIST.md`, `RELEASE_NOTES_0.1.0.md`.
- `CHANGELOG.md`, `CONTRIBUTING.md`, `CHECKSUMS.md`, `LICENSE`,
  `release_freeze.json` — immutable v0.1 release surface.
- `design_partner_beta_freeze.json` — current v0.2 beta-candidate identity and
  references to generated engineering evidence.
- `reference/` — historical documents describing the project concept and a
  prior 0.1.0 implementation. They are specifications and historical
  evidence only; they do not describe the current state of this repository.
- `AGENTS.md`, `PROJECT_SCOPE.md`, `MVP_ACCEPTANCE_CRITERIA.md`,
  `IMPLEMENT.md` — governing instructions, scope, acceptance criteria, and
  the operational implementation log for agents working in this repository.
