# QuantCheck visual source register

Every public figure uses the restrained forensic research palette defined for the repository: charcoal `#17212B`, audit blue `#175CD3`, controlled-corruption rust `#B42318`, caution ochre `#A15C00`, private slate `#667085`, and paper `#FCFCFA`. Color is always paired with labels, line styles, patterns, or shapes.

| Asset | Purpose | Evidence / source | Claim boundary |
| --- | --- | --- | --- |
| `quantcheck-hero-timeline.svg` | Signature "future arrives early" explanation | `docs/faults/LOOK_AHEAD.md`; `docs/METHODOLOGY.md` | Conceptual method illustration; dates are illustrative, not benchmark measurements. |
| `quantcheck-architecture.svg` | Manifest-blind detector path and private scoring lane | `docs/METHODOLOGY.md`; `docs/ARTIFACTS_AND_PRIVACY.md`; public evidence ledger A-07 to A-10 | Architecture diagram; no performance claim. There is intentionally no manifest-to-detector connector. |
| `quantcheck-benchmark-v01.svg` | Frozen v0.1 case and finding accounting | `evidence/v0_1_release/aggregate_report.json`, aggregate `agg_571aae0b7c60a4a5`; `docs/FINAL_BENCHMARK_RESULTS.md` | Controlled synthetic fixture; not a production precision or recall estimate. |
| `quantcheck-failure-analysis.svg` | Exact matches, strict false positives, misses, and no-target cells kept separate | Same aggregate plus `evidence/v0_1_release/case_matrix.json` | Structural no-target is not a miss. The zero false-negative count covers successful scored cases only. |
| `quantcheck-real-source-evidence.svg` | Detector-specific observational SEC applicability | `evidence/real_data_study/applicability.json`; `docs/research/REAL_DATA_RESULTS.md`; `docs/research/REAL_DATA_ADJUDICATION.md` | Real-source pipeline execution; not natural-error validation or data certification. |
| `demo-dashboard.svg` | Static preview of the local public-only review surface | `evidence/v0_1_release/aggregate_report.json`; `docs/DASHBOARD_AND_HTML.md` | Interface preview; the actual local surfaces read saved public artifacts only. |

## Evidence sets intentionally not pooled

- Frozen v0.1: 124 configured synthetic cases and aggregate `agg_571aae0b7c60a4a5`.
- Observational SEC run: 472 selected observations from five issuers; detector-specific applicability; zero emitted findings.
- Adversarial SEC-derived substrate: 120 injected faults across nine cases, 120 exact matches, four retained Unit Drift false positives; not natural SEC defects.
- Synthetic v0.2 development/validation: separate engineering evidence; not held-out, customer, or production validation. It is not visualized on the landing page.

`README.md` currently uses three of these figures: `quantcheck-hero-timeline.svg`, `quantcheck-architecture.svg`, and `quantcheck-benchmark-v01.svg`. The remaining superseded SVGs in this directory are unreferenced and are kept only to avoid deleting prior user-authored assets. Public README review should use the five `quantcheck-*` figures listed above.

No visual should be changed to improve a headline number. If a source artifact changes, revise the figure and this register in the same review.
