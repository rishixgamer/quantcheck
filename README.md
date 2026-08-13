# QuantCheck

**Adversarial testing for point-in-time financial research data**

> QuantCheck tests whether future information was made visible too early—and whether that changes a research result.

[![A timeline shows quarter end on March 31, a research decision on April 15, and a later filing on May 10. A dashed rust path moves the filing value's apparent availability back to March 31, making it visible at the decision date. QuantCheck identifies the temporal violation.](docs/assets/quantcheck-hero-timeline.svg)](docs/assets/quantcheck-hero-timeline.svg)

*Figure 1. A controlled look-ahead mutation moves a value's apparent availability before the research decision, even though the filing became public later. QuantCheck detects the detector-visible temporal contradiction. This is a conceptual illustration, not measured benchmark evidence.*

[Demo](#demo) · [Research paper](QUANTCHECK_RESEARCH_PAPER.md) · [Reproduce](#reproduce) · [Methodology](docs/METHODOLOGY.md) · [Evidence ledger](QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md)

- **Frozen v0.1 controlled benchmark:** 124 configured · 94 successful · 30 structural no-target · 0 incomplete. Synthetic fixture evidence, not production performance.
- **Manifest-blind evaluation:** detectors see sanitized audit input; private truth enters only after findings are final.
- **Real-source exposure:** 472 selected observations · 5 issuers · 0 emitted findings; only Exact Duplicate had opportunities. Pipeline execution, not natural-error validation.

## The problem

**What if your backtest's data knew something the researcher did not?**

A company can finish a quarter on March 31, a researcher can make a decision on April 15, and the filing can become public on May 10. If a dataset labels the filing value as available on March 31, the calculation may be mathematically correct while its historical state is impossible.

QuantCheck tests the data state before making any claim about prediction. It separates five concepts that research systems often blur: reporting period, filing date, availability date, research cutoff, and runtime.

For v0.1, visibility is explicit and narrow:

```text
visible ⇔ available_on <= as_of_date
```

The contract is day-level and end-of-day. It makes no intraday availability claim.

## The temporal contradiction

The signature Look-Ahead test changes one controlled field: an eligible fact's apparent `available_on` date becomes its `period_end`. Its filing date, value, unit, dimensions, and provenance remain unchanged.

At the April 15 research decision in Figure 1, the clean history excludes the May 10 filing. The corrupted history includes it. The detector does not need the hidden original value to prove the visible contradiction `available_on == period_end < filed_on`.

## How QuantCheck works

[![A two-lane architecture diagram shows the primary public audit path from private clean data through deterministic fault injection, sanitized audit input, a detector, finalized findings, hidden-manifest scoring, and research-impact comparison. A separate hatched private lane carries the fault manifest from injection to scoring only after audit finalization. There is no connector from the manifest to the detector.](docs/assets/quantcheck-architecture.svg)](docs/assets/quantcheck-architecture.svg)

*Figure 2. QuantCheck separates controlled corruption from manifest-blind detection. Private truth is used only after findings are finalized for exact scoring and controlled impact comparison.*

1. Build a clean point-in-time snapshot.
2. Inject a deterministic, configured fault and retain its truth privately.
3. Sanitize the corrupted snapshot into the detector's audit input.
4. Run all detectors without the manifest, clean values, targets, seed, or injector metadata.
5. Finalize every finding, including cross-detector warnings.
6. Score exact one-to-one matches against the hidden manifest.
7. Compare one narrow research output across clean, corrupted, and privately replayed states.

Clean controls use the same detector and scoring contracts. Public artifacts cannot address the private artifact tree.

## Fault families

The frozen v0.1 benchmark tests one deliberately narrow subtype in each family:

| Family | Controlled subtype | Detector question | Deliberate boundary |
| --- | --- | --- | --- |
| **Look-Ahead Timestamp** | `period_end_substitution` | Did a period-end date make a fact visible before filing? | Not arbitrary timestamp or intraday detection |
| **Unit Drift** | `value_scaled_unit_unchanged` | Does an exact comparable series contain a scale discontinuity? | Not currency conversion or general anomaly detection |
| **Duplicate Observations** | `exact_occurrence_copy` | Does one exact public fingerprint occur more than once? | Not fuzzy deduplication or entity resolution |
| **Revision Overwrite** | `later_vintage_in_earlier_state` | Does an earlier state contain a later declared revision? | Requires source-declared lineage; not universal restatement detection |

Missing Observations exists as separate post-MVP work. It is not part of the frozen four-family v0.1 result, and Entity Identity remains unimplemented.

## Frozen v0.1 held-out benchmark

[![A benchmark accounting diagram starts with 124 configured cases and separates 94 successful cases, 30 structural no-target cases, and zero incomplete cases. It then shows 130 injected faults, 130 exact matches, 78 strict false-positive findings, and zero false-negative faults among successful scored cases. Metrics are precision 0.625, recall 1.000, F1 0.769, and eligible-clean denominator 1,070.](docs/assets/quantcheck-benchmark-v01.svg)](docs/assets/quantcheck-benchmark-v01.svg)

*Figure 3. Frozen v0.1 case and finding accounting. Strict primary-family scoring on a controlled synthetic fixture. Evidence: aggregate `agg_571aae0b7c60a4a5`, [canonical aggregate](release_evidence/final/public/aggregate_report.json). Not a production precision or recall estimate.*

| Accounting | Exact saved value |
| --- | ---: |
| Configured / successful / structural no-target / incomplete | 124 / 94 / 30 / 0 |
| Injected faults / exact matches | 130 / 130 |
| Strict false-positive findings | 78 |
| False-negative faults among successful scored cases | 0 |
| Eligible-clean denominator | 1,070 |
| Strict micro precision / recall / F1 | 0.625 / 1.000 / 0.769 |
| Controlled output changed / manifest-assisted replay restored | 90 / 90 |

The displayed F1 is rounded from the canonical Decimal value. The complete exact values, denominators, and profile breakdown are in [Final benchmark results](docs/FINAL_BENCHMARK_RESULTS.md).

## What QuantCheck gets wrong

[![A failure-analysis diagram keeps four categories separate: 130 exact matches, 78 strict cross-detector false-positive findings, zero false-negative faults among successful scored cases, and 30 structural no-target cases. It lists the three no-target cells and explains that structural no-target is not a miss.](docs/assets/quantcheck-failure-analysis.svg)](docs/assets/quantcheck-failure-analysis.svg)

*Figure 4. Exact matches, strict false positives, misses, and structural no-target cases remain separate because they have different meanings. Evidence: aggregate `agg_571aae0b7c60a4a5` and the frozen case matrix.*

The benchmark keeps inconvenient outcomes visible:

- **78 strict false-positive findings.** All are cross-detector findings under the predeclared primary-family score. A mechanically valid alert from another family still counts against strict precision.
- **0 false-negative faults among successful scored cases.** This is fixture-bounded recall, not a general sensitivity claim.
- **30 structural no-target cases.** No fault was injected, so these cells are not detector misses: Look-Ahead / high has no 30-day natural filing lag; Revision Overwrite / medium and high require 5% and 20% changes, while the declared history changes by 2%.
- **A thin denominator.** Revision Overwrite has an eligible-clean denominator of 11. Its rates should not be compared casually with larger profiles.

## Real-source evidence

The real-source work answers a different question from the synthetic benchmark: can the same bounded pipeline run on selected public SEC Company Facts histories, and which detector rules have an opportunity to apply?

[![An observational evidence table states 472 selected observations, five issuers, and zero emitted findings. Exact Duplicate has 472 singleton fingerprint groups and an applicable null result. Look-Ahead and Revision Overwrite each show N/A with zero opportunities, and Unit Drift shows N/A with zero comparable observations. The footer says no findings were available to adjudicate and this does not certify the data as correct.](docs/assets/quantcheck-real-source-evidence.svg)](docs/assets/quantcheck-real-source-evidence.svg)

*Figure 5. Detector-specific applicability in the observational SEC run. Evidence: [applicability artifact](evidence/real_data_study/applicability.json) and [observational results](REAL_DATA_RESULTS.md). Real-source pipeline execution—not natural-error validation.*

QuantCheck processed **472 selected observations from five issuers** and emitted **zero observational findings**. Only Exact Duplicate had applicable opportunities: all 472 fingerprint groups were singletons. The other families were `NOT_APPLICABLE`, not zero-valued performance tests. There were no findings to adjudicate, and the result does not certify the selected data as correct.

### Controlled adversarial test on an SEC-derived substrate

This is separate from the observational run. QuantCheck introduced **120 manufactured faults** across nine seeded cases on preserved SEC-derived observations: 12 Look-Ahead, 72 Duplicate, and 36 Unit Drift. All 120 had exact matches; four additional Unit Drift warnings remain strict false positives. Revision Overwrite was not applicable because the adapter declared no revision lineage.

**120 injected faults—not 120 natural SEC defects.** The cases reuse one narrow substrate and do not estimate natural-error prevalence or general real-world accuracy.

Read the [observational results](REAL_DATA_RESULTS.md), [adversarial results](REAL_DATA_SUBSTRATE_ADVERSARIAL_RESULTS.md), [warning adjudication](REAL_DATA_SUBSTRATE_ADVERSARIAL_ADJUDICATION.md), and [real-source limitations](REAL_DATA_LIMITATIONS.md).

## Reproducibility

Logical artifacts use canonical JSON, exact `Decimal` serialization, and SHA-256 identities. With the same clean snapshot, configuration, seed, and code version, logical artifact bytes are designed to reproduce across output roots, reordered inputs, and tested `PYTHONHASHSEED` values. Runtime metadata and the index are intentionally environment-specific.

### Reproduce the offline smoke path

Requires Python 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --frozen --all-groups
uv run quantcheck benchmark smoke --output /tmp/qc-smoke
uv run python scripts/render_html_summary.py /tmp/qc-smoke \
  --output /tmp/qc-smoke/summary.html
```

This produces 12 offline smoke cases. It does not reproduce the frozen held-out result.

### Reproduce the frozen v0.1 evidence

From the matching `v0.1.0` release checkout:

```bash
uv sync --frozen --all-groups
uv run python scripts/release_freeze.py --check
uv run python scripts/run_release_benchmark.py --output release_evidence/final
uv run python scripts/verify_release_evidence.py \
  --source release_evidence/final \
  --public-only release_evidence/public_only \
  --html release_evidence/public_only/summary.html
uv run python scripts/release_checksums.py --check
```

See the full [reproducibility guide](docs/REPRODUCIBILITY.md) before interpreting byte-level comparisons.

## Demo

[**Watch the 2:56 narrated project demo**](video/QuantCheck_demo.mp4) or review its [captions, evidence qualifiers, and production notes](video/PRODUCTION_PACKAGE.md).

The demo uses saved public evidence and keeps synthetic, observational, and adversarial claims separate. The local review surfaces can also be generated without reading private artifacts:

```bash
uv run quantcheck benchmark smoke --output /tmp/qc-demo
uv run python scripts/render_html_summary.py /tmp/qc-demo \
  --output /tmp/qc-demo/summary.html
uv run --group dashboard streamlit run dashboard/app.py -- \
  --artifacts /tmp/qc-demo
```

## Research paper and methodology

[**QuantCheck: Adversarial Testing of Point-in-Time Financial Research Data**](QUANTCHECK_RESEARCH_PAPER.md) develops the threat model, manifest-blind evaluation design, benchmark, real-source evidence taxonomy, failure analysis, and limitations.

For claim review, the [public evidence ledger](QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md) is the factual source of truth. For implementation semantics, begin with [Methodology](docs/METHODOLOGY.md), then follow the individual fault contracts.

## Limitations

QuantCheck's primary v0.1 evidence is synthetic and fixture-bounded. The observational SEC study is narrow and has applicable opportunities for only one detector. The SEC-derived adversarial experiment uses manufactured faults, three deterministic seeds, and a reused substrate. The current `0.2.0.dev0` worktree has no completed customer pilot, customer adjudication, production deployment, published candidate image, trusted candidate attestation, or held-out v0.2 result.

QuantCheck does not claim investment returns, alpha, financial losses prevented, automatic detector-only remediation, natural SEC defect discovery, vendor-scale coverage, universal restatement detection, or production accuracy. Read the [authoritative limitations](docs/LIMITATIONS.md).

## Documentation

| Question | Start here |
| --- | --- |
| What can be claimed publicly? | [Public evidence ledger](QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md) |
| How is private truth isolated? | [Methodology](docs/METHODOLOGY.md) · [Threat model](docs/THREAT_MODEL.md) · [Artifacts and privacy](docs/ARTIFACTS_AND_PRIVACY.md) |
| What exactly did v0.1 measure? | [Final benchmark results](docs/FINAL_BENCHMARK_RESULTS.md) |
| What does each detector prove? | [Look-Ahead](docs/faults/LOOK_AHEAD.md) · [Unit Drift](docs/faults/UNIT_DRIFT.md) · [Duplicates](docs/faults/DUPLICATE_OBSERVATIONS.md) · [Revision Overwrite](docs/faults/REVISION_OVERWRITE.md) |
| How do I reproduce it? | [Reproducibility](docs/REPRODUCIBILITY.md) · [CLI contract](docs/CLI_CONTRACT.md) |
| What happened on public SEC histories? | [Observational protocol](REAL_DATA_STUDY_PROTOCOL.md) · [Results](REAL_DATA_RESULTS.md) · [Adversarial protocol](REAL_DATA_SUBSTRATE_ADVERSARIAL_PROTOCOL.md) |
| What is implemented now? | [Implementation status](IMPLEMENT.md) · [Project scope](PROJECT_SCOPE.md) |
| How were the figures sourced? | [Visual source register](docs/assets/VISUAL_SOURCES.md) |
| How can I contribute? | [Contributing guide](CONTRIBUTING.md) |

The repository's `reference/` directory is historical evidence from the lost implementation. It does not override current contracts or saved artifacts.
