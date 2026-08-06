# QuantCheck

**Adversarial tests for point-in-time financial research.**

QuantCheck is a Python 3.12 framework for testing whether financial research data can manufacture misleading results through information available too early, scale corruption, duplicate observations, or later revisions substituted into an earlier historical state.

It produces reproducible evidence: deterministic fault injection, manifest-blind audit inputs, exact scoring, controlled research-impact comparisons, public/private artifacts, and a public-only forensic dashboard and HTML report.

## What 0.1.0 proves

The frozen final benchmark ran 120 fault cases plus 12 clean controls on a reviewed synthetic fixture. All 132 cases completed, with zero failed or incomplete cases.

| Metric | Exact saved value |
|---|---:|
| Injected fault units | 170 |
| Findings | 247 |
| True-positive faults | 165 |
| False-negative faults | 5 |
| False-positive findings | 82 |
| Eligible clean units | 2035 |
| Precision | `0.6680161943319838056680161943` |
| Recall | `0.9705882352941176470588235294` |
| F1 | `0.7913669064748201438848920862` |
| False-positive rate | `0.04029484029484029484029484029` |
| Fault cases that changed controlled research output | 107 / 120 |
| Exact replay restorations | 120 / 120 |
| Clean-control findings | 0 / 12 controls |

The benchmark is intentionally honest. Unit Drift missed five injected faults because immediate-neighbor comparisons can be directionally ambiguous or mutually masked. Look-Ahead and Revision Overwrite each reached recall `1` but precision `0.5` under strict primary-label scoring because the same corrupted records violated both temporal contracts; the correlated cross-detector findings remain visible.

See [the final technical report](docs/FINAL_BENCHMARK_RESULTS.md) for exact per-fault, per-severity, and per-seed results and limitations.

## Install

Install the exact development and runtime environment:

```bash
uv sync --frozen --all-groups
uv run quantcheck --help
```

Build distributable packages:

```bash
uv build --offline
```

The package is MIT licensed. Version `0.1.0` supports Python `>=3.12,<3.13`.

## Five-minute quick start

Run the exact 12-case offline smoke matrix:

```bash
uv run quantcheck benchmark smoke \
  --config configs/smoke.json \
  --output artifacts/benchmark-smoke \
  --json
```

The expected smoke benchmark ID is `247ecdbf581f6437fb04d0ff4337165cfe07a116f7f374690e13798dc6b39203`, with 12 successful cases and zero failed/incomplete cases.

Verify public evidence and render the deterministic HTML:

```bash
uv run python scripts/verify_release_evidence.py artifacts/benchmark-smoke

uv run python scripts/render_html_summary.py \
  artifacts/benchmark-smoke \
  --output artifacts/benchmark-smoke/summary.html
```

Launch the local read-only dashboard:

```bash
uv run streamlit run dashboard/app.py -- \
  --artifacts artifacts/benchmark-smoke
```

The dashboard and HTML use indexed public artifacts only. They do not execute injection, detection, scoring, repair, or private research logic.

## Reproduce the final release benchmark

Reserved final seeds cannot run through the ordinary Python API, saved-case workflow, or CLI. The release-only path accepts exactly seeds `1000`–`1009` and first verifies the candidate freeze byte for byte:

```bash
uv run python scripts/freeze_release_candidate.py \
  configs/release.json --check release/freeze.json

uv run python scripts/run_release_benchmark.py \
  configs/release.json release/freeze.json \
  --output artifacts/reproduced-release

uv run python scripts/verify_release_evidence.py \
  artifacts/reproduced-release
```

Expected identities:

- release candidate: `2f1bbc3d8a4e80715ac378691df90805c6c78f5cd32c3be49a0a49b537d439fb`
- benchmark: `e5a1770a7599c76d628769fbc8d534f7e3807f455241d8a5306299100ae811bc`
- aggregate report: `6606132b146a24300dc55ce67e6ef8cb5995c2628b2c371c7c30e4d4fa6225b9`
- final HTML SHA-256: `78422911eef3f0e6fed32416ba1eed36046b363ed805a154bb4aeeaad64c80ee`

Detailed commands and the logical/runtime identity distinction are in [the reproducibility guide](docs/REPRODUCIBILITY.md).

## How it works

```text
clean snapshot
   ├── controlled clean research output
   └── deterministic injector ──> corrupted snapshot + private manifest
                                  │
                                  └── sanitize_for_audit
                                         │
                                         v
                                  AuditInputSnapshot
                                         │
                                  manifest-blind detectors
                                         │
                                         v
                                    AuditReport
                                         │
                       finalized report + private manifest
                                         │
                                  exact scoring/replay
                                         │
                            public evidence + private truth
```

Detectors receive `AuditInputSnapshot`, never unrestricted canonical records or manifests. The manifest becomes visible only after the audit report is finalized. Public presentation follows indexed paths under `public/`; hidden manifests and value-bearing replay artifacts remain under `private/`.

See:

- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Point-in-time and research methodology](docs/RESEARCH_METHODOLOGY.md)
- [Scoring and benchmark rules](docs/BENCHMARK_SPEC.md)
- [Public/private artifact contracts](docs/ARTIFACT_CONTRACTS.md)
- [Threat model and adversarial review](docs/THREAT_MODEL.md)
- [Fault catalog](docs/faults/)

## Fault catalog

- **Look-Ahead Timestamp:** makes a record available before its preserved filing date.
- **Unit Drift:** scales a value while leaving its unit metadata unchanged.
- **Duplicate Observations:** copies an exact semantic occurrence and tests double counting.
- **Revision Overwrite:** substitutes a later revision vintage into an earlier research state.

Each family has a frozen spec for eligibility, severity, injection, detection, matching, false-positive denominator, replay, and research impact under `docs/faults/`.

## CLI

The six root commands are:

```text
ingest  inject  audit  evaluate  benchmark  explain
```

Use `--json` for one canonical machine-readable result. Saved-stage workflows consume fully expanded case configurations so seeds, detector settings, and research semantics are not reinterpreted at the interface. There is no force-overwrite, unrestricted held-out, dashboard, or live-test root command. See [the CLI contract](docs/CLI_CONTRACT.md).

## Scope and limitations

QuantCheck 0.1.0 is evidence for a narrow, reviewed methodology—not general production readiness.

- One reviewed synthetic benchmark fixture; no vendor-scale validation.
- Four fault families only; no missing-observation or entity-swap support.
- Daily financial availability and end-of-day decisions; no intraday claims.
- Controlled availability-count, aggregate-value, and growth-ranking comparisons; not a trading backtest and no alpha, Sharpe, or loss-prevention claim.
- Manifest-assisted exact replay; not detector-only or automatic remediation.
- Immediate-neighbor Unit Drift limitations and exact-copy-only Duplicate scope.
- Narrow source-supported Revision Overwrite histories; no universal restatement detection.
- One-CIK-at-a-time synchronous SEC adapter; no live SEC attestation in this environment and no statement reconstruction.
- Local sequential execution; no database, cloud system, parallel scheduler, accounts, or hosted platform.
- Local read-only Streamlit; public presentation cannot browse manifests or private values.
- Remote CI, Git commit/tag verification, registry publication, and human browser/video review remain external gates in this checkout.

## Development

```bash
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
MYPYPATH=src uv run mypy --explicit-package-bases dashboard scripts
uv run pytest
uv lock --check
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) before changing contracts or scientific behavior. Repository authority and task reading order are defined in `AGENTS.md` and `docs/AUTHORITY_AND_READING_ORDER.md`.

## Résumé-ready description

Built QuantCheck, a Python 3.12 adversarial-testing framework for point-in-time financial research data. Designed deterministic fault injection and manifest-blind detection for timestamp leakage, unit drift, duplicates, and revision overwrites; implemented canonical SHA-256 evidence artifacts, exact scoring, controlled research-impact replay, a strict CLI, and public-only Streamlit/HTML forensics. Released a frozen 132-case benchmark with reproducible public evidence, explicit privacy boundaries, and honest failure analysis.

## License

MIT. See [LICENSE](LICENSE).
