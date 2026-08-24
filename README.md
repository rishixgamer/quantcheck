# QuantCheck

[![CI](https://github.com/rishixgamer/quantcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/rishixgamer/quantcheck/actions/workflows/ci.yml)
[![Security](https://github.com/rishixgamer/quantcheck/actions/workflows/security.yml/badge.svg)](https://github.com/rishixgamer/quantcheck/actions/workflows/security.yml)
[![Release v0.1.0](https://img.shields.io/github/v/release/rishixgamer/quantcheck?display_name=tag&sort=semver)](https://github.com/rishixgamer/quantcheck/releases/tag/v0.1.0)

**Adversarial testing for point-in-time financial research data.** QuantCheck is a
deterministic Python framework for testing whether timestamp leakage, unit drift,
duplicate observations, or revision overwrites can manufacture a misleading
research result. It is a research-integrity tool, not a trading system.

[Demo](#demo) · [Quick start](#quick-start) · [Benchmark](docs/FINAL_BENCHMARK_RESULTS.md) · [Evidence archive](evidence/) · [Research](#research)

## Why this matters

A filing can become public on May 10 even though its quarter ended on March 31.
If a dataset labels the value as available on March 31, a mathematically correct
calculation can still use an impossible historical state. QuantCheck keeps period,
filing, availability, research as-of, and runtime dates distinct. Its v0.1
visibility contract is deliberately narrow and day-level:

```text
visible ⇔ available_on <= as_of_date
```

## How it works

1. Build a clean point-in-time snapshot.
2. Inject one deterministic, configured fault and keep its truth private.
3. Sanitize the corrupted snapshot into an `AuditInputSnapshot`.
4. Run detectors without the manifest, clean values, target IDs, seed, or injector metadata.
5. Finalize findings, then score them against the private manifest.
6. Compare one controlled research output across clean, corrupted, and replayed states.

The public presentation layer reads public artifacts only. It does not rerun
scientific logic or require the private artifact tree.

## Controlled fault families

The frozen v0.1 benchmark covers one narrow subtype per family:

| Family | Subtype | Detector question |
| --- | --- | --- |
| Look-Ahead Timestamp | `period_end_substitution` | Did a period-end date make a fact visible before filing? |
| Unit Drift | `value_scaled_unit_unchanged` | Is there a scale discontinuity in an exact comparable series? |
| Duplicate Observations | `exact_occurrence_copy` | Does one exact public fingerprint occur more than once? |
| Revision Overwrite | `later_vintage_in_earlier_state` | Does an earlier state contain a later declared revision? |

These are controlled contracts, not universal timestamp, anomaly, deduplication,
entity-resolution, or restatement detection.

## Evidence at a glance

The immutable v0.1 controlled benchmark has **124 configured cases**: 94
successful, 30 structural no-target, and 0 incomplete. Among successful scored
cases it recorded 130 injected faults, 130 exact matches, 78 strict
cross-detector false-positive findings, precision **0.625**, recall **1.000**,
and F1 **0.769**. This is synthetic fixture evidence, not production
performance. See the [canonical aggregate report](release_evidence/final/public/aggregate_report.json)
and the [human-readable benchmark summary](docs/FINAL_BENCHMARK_RESULTS.md).

The separate observational SEC study processed **472 selected observations from
five issuers** and emitted no findings. Only Exact Duplicate had applicable
opportunities; the run demonstrates bounded public-source pipeline execution,
not natural-error discovery or broad detector validation. The SEC-derived
adversarial study manufactured 120 faults and is likewise not evidence of 120
natural SEC defects.

## Quick start

Requires Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --frozen --all-groups
uv run quantcheck benchmark smoke --output /tmp/qc-smoke
uv run python scripts/render_html_summary.py /tmp/qc-smoke \
  --output /tmp/qc-smoke/summary.html
```

The smoke path runs 12 deterministic offline cases. For the read-only dashboard:

```bash
uv run --group dashboard streamlit run dashboard/app.py -- --artifacts /tmp/qc-smoke
```

No ordinary test or quick-start command makes a live network request.

## Reproduce the frozen baseline

Use the immutable [`v0.1.0` release](https://github.com/rishixgamer/quantcheck/releases/tag/v0.1.0)
for the held-out baseline. The complete procedure is in
[Reproducibility](docs/REPRODUCIBILITY.md); the current worktree is
`0.2.0.dev0`, not a claim of a new production release.

```bash
uv sync --frozen --all-groups
uv run python scripts/release_freeze.py --check
uv run python scripts/run_release_benchmark.py --output release_evidence/final
uv run python scripts/verify_release_evidence.py \
  --source release_evidence/final \
  --public-only release_evidence/public_only \
  --html release_evidence/public_only/summary.html
```

## Demo

Review the [production notes](video/PRODUCTION_PACKAGE.md). The immutable
release-hosted narrated demo is available as the
[QuantCheck_demo.mp4 release asset](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/QuantCheck_demo.mp4).
The accompanying [real-data evidence archive](https://github.com/rishixgamer/quantcheck/releases/download/portfolio-evidence-2026-08-24/quantcheck-real-data-evidence-2026-08-13.tar.gz)
contains the raw study payloads that are intentionally absent from this tip.

## My role

Rishi Haldar owned the problem framing, scientific contracts, evidence boundaries,
verification gates, and final publication decisions. Implementation used
**AI-assisted development** under explicit acceptance criteria, tests, and review;
this is not a claim that every line was manually authored. The repository's
contribution is the contract-and-verification design, with inconvenient outcomes
and limitations retained in the evidence record.

## Limitations

The primary benchmark is synthetic and fixture-bounded. The observational SEC run
has no ground truth and only one detector with a nonzero opportunity denominator.
The adversarial SEC-derived study uses manufactured faults on a reused substrate.
The current worktree has no customer pilot, customer adjudication, production
deployment, published candidate image, trusted candidate attestation, or held-out
v0.2 result. QuantCheck does not claim alpha, returns, prevented losses, natural
SEC defect prevalence, vendor-scale coverage, or automatic remediation.

See the [current status](docs/STATUS.md)
and [authoritative limitations](docs/LIMITATIONS.md).

## Research

The research archive is retained in the current tree:

- [Research paper](docs/research/QUANTCHECK_RESEARCH_PAPER.md)
- [Public evidence ledger](docs/research/QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md)
- [Observational SEC results](docs/research/REAL_DATA_RESULTS.md)
- [SEC-derived adversarial results](docs/research/REAL_DATA_SUBSTRATE_ADVERSARIAL_RESULTS.md)
- [Adversarial adjudication](docs/research/REAL_DATA_SUBSTRATE_ADVERSARIAL_ADJUDICATION.md)
- [Real-data limitations](docs/research/REAL_DATA_LIMITATIONS.md)

For implementation semantics, start with [Methodology](docs/METHODOLOGY.md).
The [evidence archive](evidence/) contains the saved public and study-scoped
artifacts; private truth is not a public performance claim.
