# Visual source register

Every visual in this directory is explanatory or evidence-labeled. The SVGs do not introduce new measurements; displayed numbers are copied from the listed source artifacts and remain qualified in their captions.

| Asset | Purpose | Source of wording/numbers | Required caveat |
| --- | --- | --- | --- |
| `quantcheck-hero.svg` | First-screen method and trust boundary | `docs/METHODOLOGY.md`, `QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md` A-07–A-10 | Method diagram; no performance claim. |
| `lookahead-timeline.svg` | Concrete point-in-time example | `reference/QUANT_DATA_CHAOS_LAB_CONCEPT.txt`, `docs/faults/LOOK_AHEAD.md` | Controlled illustration; not an observed SEC defect. |
| `evidence-layers.svg` | Separate synthetic, observational, and real-substrate evidence | `QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md` C, G-14, G-15 | Evidence classes must not be merged. |
| `benchmark-results.svg` | v0.1 benchmark summary | `release_evidence/final/public/aggregate_report.json`, `docs/FINAL_BENCHMARK_RESULTS.md` | Small reviewed synthetic fixture; retained failures and false positives are part of the result. |
| `real-substrate-results.svg` | Real-data adversarial summary | `REAL_DATA_SUBSTRATE_ADVERSARIAL_RESULTS.md`, `evidence/real_data_substrate_adversarial/study_run.json` | Manufactured faults on preserved SEC observations; not natural SEC defects. |

No visual should be changed to improve a headline number. If a source artifact changes, regenerate or revise the asset and update this register in the same review.
