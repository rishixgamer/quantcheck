# QuantCheck 0.1.0 release notes

**Status: release candidate, prepared locally. Not published.** No Git tag,
GitHub release, PyPI upload, hosted dashboard, or CI run exists. See
[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) for the external gates.

## What this is

QuantCheck is a deterministic Python framework that tests whether point-in-time
financial research data can manufacture misleading results. It builds a
point-in-time snapshot, injects one controlled defect, hides the truth in a
private manifest, sanitises the data, runs manifest-blind detectors, and scores
the findings exactly against the manifest only after the audit is finalised.

## Highlights

* **Four fault families**, each a complete vertical slice from deterministic
  injection through manifest-blind detection, exact scoring, controlled research
  impact, and manifest-assisted exact replay: Look-Ahead Timestamp, Unit Drift,
  Duplicate Observations, Revision Overwrite.
* **A held-out benchmark.** 120 fault cases across 4 profiles × 3 severities ×
  10 reserved final seeds, plus 4 clean controls. The reserved seeds are
  executable only through an explicit release path guarded by a frozen release
  candidate.
* **An enforceable public/private boundary.** Detectors never receive the
  manifest; public artifacts cannot address private storage; the whole
  presentation layer works with `private/` deleted.
* **Deterministic evidence.** Identical logical bytes across output roots,
  working directories, and `PYTHONHASHSEED` values.
* **Read-only presentation.** A strict public artifact reader, one immutable
  shared model, a deterministic self-contained HTML summary, and a local
  Streamlit dashboard — none of which executes any scientific logic.
* **A six-command Typer CLI** with stable exit codes and a saved-stage
  `inject` → `audit` → `evaluate` workflow that is byte-equivalent to a direct
  dispatch.

## Final held-out result

| Metric | Value |
| --- | --- |
| Configured cases | 124 (120 fault + 4 control) |
| Successful / failed / incomplete | 94 / 30 / 0 |
| Injected faults / findings | 130 / 208 |
| True positives / false negatives | 130 / 0 |
| False-positive findings | 78 |
| Precision | `0.625` |
| Recall | `1` |
| F1 | `0.76923076923076923076923076923076923076923076923077` |
| False-positive rate | `0.072897196261682242990654205607476635514018691588785` |
| Research output changed | 90 / 90 |
| Exact replay restored | 90 / 90 |

Read these honestly:

* **30 cases failed** with `no_eligible_targets`. Three profile/severity cells
  have no eligible target on the reviewed fixture. They were kept in the matrix
  rather than configured away.
* **All 78 false positives are cross-detector findings** under strict
  primary-label scoring, dominated by the reviewed fixture's documented natural
  duplicate pair. This is retained detector behaviour, not a defect, and it was
  not tuned.
* **Recall of `1`** is a measurement on a 26-record synthetic fixture, not a
  general sensitivity claim.

Full breakdown and failure analysis:
[FINAL_BENCHMARK_RESULTS.md](FINAL_BENCHMARK_RESULTS.md).

## Release identities

| Artifact | Identity |
| --- | --- |
| Release candidate | `relc_2c6e945a71b85b39` |
| Freeze record SHA-256 | `7584be72c2fa3882c3a61c0ba47354cd3e45f53cd1f4d0bb70f9a012e59f42eb` |
| Benchmark | `bench_403a85e506ff66ea` |
| Aggregate report | `agg_571aae0b7c60a4a5` |
| Release config SHA-256 | `a29c131b83d85323b379436e674efbadff7e382f5e0ca09c7dd3e3bef46e6f3c` |
| Case matrix SHA-256 | `2a1ffbc7d2ff32a0965ccfea3076ac17f46a20d2de6c0d9fc6590799e629cc13` |
| Summary HTML SHA-256 | `2ba3c7746e18df90699a99ddd4ce0e0dc100bb6fa2b0ead7f88e4887e52ac795` |

Package checksums are in [`../CHECKSUMS.md`](../CHECKSUMS.md).

## An invalidated candidate is preserved

An earlier candidate, `relc_a573d64b0345a5b5`, completed the full 124-case
matrix first and was then invalidated by a **release-plumbing defect, not by its
detector performance**: reserved seeds could not be deserialized at all, so the
released public evidence package was unreadable by the reader, aggregator, and
presentation surfaces. The fix moved the boundary from representation to
execution. Both runs are preserved, and 593 of 594 indexed artifacts are
byte-identical between them — the only differences are runtime metadata and the
index that embeds its hash. The correction provably changed no science.

## Known limitations

Four narrow fault subtypes, synthetic reviewed fixtures, controlled research
comparisons rather than backtests, manifest-assisted replay rather than
automatic repair, a one-CIK SEC adapter with no live attestation, and a local
single-user read-only dashboard. Full list:
[LIMITATIONS.md](LIMITATIONS.md).

QuantCheck makes **no claim** of production readiness, financial-data
certification, automated remediation, loss prevention, trading alpha, universal
SEC coverage, statement reconstruction, universal restatement detection, or
vendor-wide reliability.

## Installation

```bash
pip install dist/quantcheck-0.1.0-py3-none-any.whl
quantcheck --help
```

Requires Python 3.12. The dashboard needs the optional `dashboard` dependency
group and the repository checkout; it does not ship in the distribution.

## Project summary

> **QuantCheck** — a deterministic Python framework for measuring whether
> point-in-time financial data defects can manufacture misleading research
> results. Injects four families of controlled corruption (look-ahead
> timestamps, unit drift, duplicate observations, revision overwrites) into
> point-in-time snapshots, runs manifest-blind detectors across an enforced
> public/private trust boundary, and scores findings exactly against a hidden
> answer key. Ships a 124-case held-out benchmark behind a cryptographically
> frozen release candidate, byte-reproducible artifacts across hash seeds and
> output roots, and a public-only evidence package that renders with all
> private truth deleted. Python 3.12, Pydantic v2, Typer, ~1,600 tests.
