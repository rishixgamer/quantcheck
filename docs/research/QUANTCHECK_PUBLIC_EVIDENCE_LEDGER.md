# QUANTCHECK_PUBLIC_EVIDENCE_LEDGER

Evidence ledger for any future public presentation of QuantCheck. This is an
evidence register, not marketing copy. It records what can be said, under which
version and artifact boundary, and what must remain qualified or unpublished.

Review date: 2026-08-13
Reviewed worktree: /Users/rishihaldar/Downloads/quantcheck-recovery-harness
Reviewed commit: 4bc3c2598b913a2b757b51082035ffa2a9ece4b1
Current package version: 0.2.0.dev0
Immutable v0.1 tag: v0.1.0 at 46c5a989045099d2cbe66eb873969a4e32b5fc69

The only pre-existing Git worktree change observed before this ledger was an
untracked .claude-flow/ directory. It was not inspected, changed, staged, or
removed. No code, test, configuration, release, or external resource was
modified for this ledger.

## Reading and publication rules

The repository's authority order is: AGENTS.md, current docs/STATUS.md, current
contracts and acceptance criteria, current ADRs, schemas and implementation,
tests, then the research archive. Historical documents describe the lost implementation
or prior intent; they do not establish current behavior.

Evidence classes used below:

- Directly measured — a saved artifact or command/test result records the value directly.
- Design/implementation fact — a current contract, source boundary, or implemented surface; not a performance result.
- Interpretation — a conclusion derived from measured evidence.
- Limitation — an explicit boundary, weakness, or non-claim.
- Historical/outdated — retained for provenance or discrepancy analysis, but unsafe as a current public claim.

Publication confidence means safe to publish only with the stated version and
caveats. “High” does not mean broad or production-grade; it means the wording
is faithfully supported by the cited artifact. “Do not publish” means the
wording is contradicted, stale, or unsupported.

Audience labels: quant recruiter; technical interviewer; transfer admissions
reader; professor/research reviewer.

## Source-of-truth hierarchy for claims

| Claim area | Primary source of truth | Secondary reading aid | Do not substitute |
| --- | --- | --- | --- |
| Current implementation and status | docs/STATUS.md, current source, current contracts | README.md | archived release prose |
| v0.1 held-out numbers | release_evidence/final/public/aggregate_report.json | docs/FINAL_BENCHMARK_RESULTS.md | historical 132-case metrics |
| v0.1 release identity and freeze | release_freeze.json, CHECKSUMS.md, Git tag v0.1.0 | docs/REPRODUCIBILITY.md, docs/RELEASE_CHECKLIST.md | mutable current worktree as if it were the tag |
| v0.2 corpus and development/validation evidence | corpus_freeze_v0_2.json, design_partner_beta_freeze.json, evidence/design_partner_beta/development_aggregate.json, evidence/design_partner_beta/validation_aggregate.json, evidence/design_partner_beta/validation_freeze.json | docs/CORPUS_V0_2.md, docs/BENCHMARK_V0_2.md | treating synthetic evidence as customer or production evidence |
| Missing Observations evidence | missing_observation_evaluation_v1.json | docs/faults/MISSING_OBSERVATIONS.md | claiming customer demand or real-feed performance |
| Performance | performance_baseline_v1.json | docs/PERFORMANCE_AND_EXECUTION.md | converting one-machine timings into a universal SLA |
| Scientific method and boundaries | docs/METHODOLOGY.md, docs/faults/*.md, docs/LIMITATIONS.md | README.md | broad fault-family or financial-performance wording |
| Product surfaces | docs/CLI_CONTRACT.md, docs/DASHBOARD_AND_HTML.md, source/tests | README.md | implying hosted SaaS or public web availability |
| External audit path | docs/EXTERNAL_DATASETS.md, docs/PRODUCTION_AUDIT_POLICIES.md | docs/STATUS.md | calling manifest-free audit output benchmark precision/recall |
| Supply chain and deployment | design_partner_beta_freeze.json, evidence/design_partner_beta/*, docs/SUPPLY_CHAIN_SECURITY.md, docs/SELF_HOSTED_DEPLOYMENT.md | docs/STATUS.md | treating configured workflows as completed gates |

## Claim register

### A. Identity, purpose, and scientific contract

| ID | Claim | Exact value or wording | Supporting source/artifact | Class | Audience | Publish confidence | Important caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A-01 | QuantCheck's purpose | “A deterministic Python framework for testing whether point-in-time financial research data can manufacture misleading results through timestamp leakage, unit corruption, duplicate observations, or revision-history failure.” | PROJECT_SCOPE.md; README.md | Design/implementation fact | All four | High | “Deterministic” describes the specified logical pipeline, not universal reproducibility of every runtime metadata file or OCI build. |
| A-02 | Current status | Current worktree is 0.2.0.dev0, described as a design-partner beta-closure candidate rather than a production release. | README.md current implementation status; docs/STATUS.md; design_partner_beta_freeze.json | Design/implementation fact plus limitation | All four | High | There is no exact current beta release commit/tag, published image, customer pilot, or production deployment. |
| A-03 | Immutable v0.1 baseline | Annotated tag v0.1.0; release candidate relc_2c6e945a71b85b39; package version 0.1.0; benchmark bench_403a85e506ff66ea. | Git tag; release_freeze.json; docs/FINAL_BENCHMARK_RESULTS.md | Directly measured / design fact | All four | High | The tag is the historical release baseline, not the version of the current 0.2.0.dev0 worktree. |
| A-04 | Point-in-time semantics | Visibility is available_on <= as_of_date, at day-level end-of-day semantics; period_end, filed_on, available_on, as_of_date, and runtime dates are distinct. | docs/METHODOLOGY.md; src/quantcheck/point_in_time.py; tests | Design/implementation fact | Technical interviewer; professor/research reviewer | High | This is a day-level contract, not an intraday availability claim. |
| A-05 | Exact financial values | Financial arithmetic and public Decimal serialization use exact Decimal; public JSON encodes Decimal values as canonical strings; binary floats are rejected in the relevant contracts. | docs/SERIALIZATION_AND_HASHING.md; fault contracts; docs/EXTERNAL_DATASETS.md; tests | Design/implementation fact | Technical interviewer; professor/research reviewer | High | Exact arithmetic does not validate the economic meaning of a source value or mapping. |
| A-06 | Deterministic identity model | Canonical JSON, SHA-256 hashes, and stable IDs are designed to be independent of row position and Python hash randomization. | docs/SERIALIZATION_AND_HASHING.md; docs/REPRODUCIBILITY.md; determinism tests | Design/implementation fact plus directly measured tests | Technical interviewer; professor/research reviewer | High | Runtime metadata and the index are deliberately runtime-specific; see F-03. |
| A-07 | Public/private architecture | Clean and corrupted snapshots, manifests, repaired snapshots, and value-bearing research impacts are private; sanitized audit input, finalized findings, score, and redacted research summary are public. | docs/METHODOLOGY.md; docs/ARTIFACTS_AND_PRIVACY.md | Design/implementation fact | Technical interviewer; professor/research reviewer | High | Public evidence still exposes the public finding evidence defined by each detector; privacy minimization is not anonymization. |
| A-08 | Scoring order | Detectors run on sanitized input; scoring reads the private manifest only after the audit report is finalized. | docs/METHODOLOGY.md; docs/THREAT_MODEL.md; benchmark dispatch tests | Design/implementation fact | Technical interviewer; professor/research reviewer | High | This proves a trust-boundary design and test result, not that every possible future detector will preserve it. |
| A-09 | Clean controls | Clean controls are run through the same detector/scoring contracts and remain visible in benchmark totals. | MVP_ACCEPTANCE_CRITERIA.md; docs/METHODOLOGY.md; saved aggregate artifacts | Design/implementation fact plus directly measured | Technical interviewer; professor/research reviewer | High | v0.1 uses four controls, one per fault profile; historical documents describe a different control policy. |
| A-10 | Exact matching | Finding/fault matching is exact and one-to-one; wrong-class findings remain false positives, misses remain false negatives, and duplicate findings cannot increase recall. | docs/METHODOLOGY.md; all four current fault contracts | Design/implementation fact | Technical interviewer; professor/research reviewer | High | The metric result depends on the documented primary-family scoring convention. |

### B. Supported fault families

The v0.1 scientific claim is four families, but only one narrow subtype of each
family is implemented. The table below is the safe wording.

| ID | Claim | Exact supported subtype and rule | Supporting source | Class | Audience | Publish confidence | Important caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B-01 | Look-Ahead Timestamp is supported | lookahead_timestamp / period_end_substitution; rule temporal.period_end_available_before_filing; target mutation sets available_on = period_end. | docs/faults/LOOK_AHEAD.md; src/quantcheck/lookahead_*.py | Design/implementation fact | All four | High | Only records with supported available_on == filed_on semantics and the narrow public contradiction are eligible. |
| B-02 | Unit Drift is supported | unit_drift / value_scaled_unit_unchanged; rule value.scale_discontinuity; exact approved factors are 100, 1000, 1000000; default ratio threshold is 50. | docs/faults/UNIT_DRIFT.md; src/quantcheck/unit_drift_*.py | Design/implementation fact | All four | High | Immediate-neighbor Decimal ratios can miss simultaneous corruption or attribute an endpoint discontinuity ambiguously. |
| B-03 | Duplicate Observations are supported | duplicate_observation / exact_occurrence_copy; rule occurrence.exact_duplicate; one appended exact copy per selected source; public finding severity is fixed at medium. | docs/faults/DUPLICATE_OBSERVATIONS.md; src/quantcheck/duplicate_*.py | Design/implementation fact | All four | High | This is exact-copy detection, not fuzzy deduplication, entity resolution, amended-filing interpretation, or arbitrary cleanup. |
| B-04 | Revision Overwrite is supported | revision_overwrite / later_vintage_in_earlier_state; rule revision.later_vintage_in_earlier_state; later value/provenance is substituted while historical availability is retained. | docs/faults/REVISION_OVERWRITE.md; src/quantcheck/revision_overwrite_*.py | Design/implementation fact | All four | Requires an explicit source-declared lineage marker and adjacent eligible history; it is not universal restatement detection. |
| B-05 | Missing Observations exists only as additive post-MVP work | quantcheck/missing-observation/v1; six mechanisms: random, periodic, entity-dependent, concept-dependent, survivorship-like, and source-feed outage. | docs/faults/MISSING_OBSERVATIONS.md; missing_observation_evaluation_v1.json; docs/STATUS.md | Design/implementation fact plus limitation | Technical interviewer; professor/research reviewer | Medium | It is not part of the frozen v0.1 four-family benchmark and was selected by an evidence-tie fallback, not customer-pain evidence. |
| B-06 | Entity Identity is not implemented | The remaining historical candidate is explicitly left unimplemented. | docs/faults/MISSING_OBSERVATIONS.md; docs/STATUS.md; docs/LIMITATIONS.md | Limitation | All four | High | Do not imply that the supported family list includes entity swaps or identity resolution. |
| B-07 | Severity profiles are fixed, version-scoped contracts | Look-Ahead: 2%/5%/10% target fractions with 7/14/30 day lags; Unit Drift: 100/1000/1000000 factors with 2%/5%/10% fractions; Duplicate: 1%/5%/15%; Revision: 1%/5%/20% minimum relative revision with 2%/5%/10% fractions. | docs/METHODOLOGY.md; four fault contracts; release_freeze.json | Design/implementation fact | Technical interviewer; professor/research reviewer | High | These are not tuned thresholds, and they should not be changed to improve a headline metric without a new ADR and evidence package. |

### C. v0.1 final held-out benchmark evidence

All values in this section are read from
release_evidence/final/public/aggregate_report.json, whose saved identity is
agg_571aae0b7c60a4a5. They are the current source of truth for the v0.1
numbers.

| ID | Claim | Exact measured value | Supporting source/artifact | Class | Audience | Publish confidence | Important caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C-01 | v0.1 benchmark size | 124 configured cases = 120 fault cases + 4 clean controls. | release_freeze.json; release_evidence/final/public/aggregate_report.json; docs/FINAL_BENCHMARK_RESULTS.md | Directly measured | All four | High | This is not the historical 132-case target described in archived release material; see X-01. |
| C-02 | v0.1 final seeds | Reserved final seeds 1000 through 1009; all ten seed values executed through the release-only path. | release_freeze.json; docs/REPRODUCIBILITY.md; docs/FINAL_BENCHMARK_RESULTS.md | Directly measured / design fact | Technical interviewer; professor/research reviewer | High | Reserved seeds are release evidence for this frozen candidate, not a general user-facing execution mode. |
| C-03 | v0.1 status totals | 94 successful, 30 failed, 0 incomplete. | release_evidence/final/public/aggregate_report.json | Directly measured | All four | High | The 30 failures are retained structural ineligibility cases, not successful benchmark cases. |
| C-04 | v0.1 injected fault count | 130 injected fault units. | release_evidence/final/public/aggregate_report.json | Directly measured | All four | High | This is the pooled count among successful injected cases; 30 cases injected no target because they failed at injection. |
| C-05 | v0.1 findings | 208 total findings: 130 true-positive findings and 78 false-positive findings under strict primary-family scoring. | release_evidence/final/public/aggregate_report.json | Directly measured | All four | High | “False positive” here means false relative to the case’s primary family, not necessarily an invalid detector observation. |
| C-06 | v0.1 false negatives | 0 false-negative faults among the injected faults in the successful scored cases. | release_evidence/final/public/aggregate_report.json | Directly measured | All four | High | This does not measure the 30 failed no-target cells and is not general sensitivity. |
| C-07 | v0.1 precision | 0.625. | release_evidence/final/public/aggregate_report.json | Directly measured | All four | High | Micro-pooled strict primary-label precision; not a per-detector production precision estimate. |
| C-08 | v0.1 recall | 1. | release_evidence/final/public/aggregate_report.json | Directly measured | All four | High | Measured on a 26-record reviewed synthetic fixture plus a five-observation Unit Drift series and successful injected cases only. |
| C-09 | v0.1 F1 | 0.76923076923076923076923076923076923076923076923077. | release_evidence/final/public/aggregate_report.json | Directly measured | Technical interviewer; professor/research reviewer | High | Exact Decimal F1 under the same strict micro-pooled convention as C-07 and C-08. |
| C-10 | v0.1 false-positive rate | 0.072897196261682242990654205607476635514018691588785, with eligible-clean denominator 1070. | release_evidence/final/public/aggregate_report.json | Directly measured | Technical interviewer; professor/research reviewer | High | The denominator is a contract-specific eligible-clean denominator, not total rows or total findings. |
| C-11 | v0.1 research-output change | 90 / 90 successful fault cases changed the configured controlled research output. | release_evidence/final/public/aggregate_report.json; docs/FINAL_BENCHMARK_RESULTS.md | Directly measured | All four | High | The outputs are narrow sensitivity demonstrations, not returns, alpha, Sharpe, portfolio results, or loss estimates. |
| C-12 | v0.1 replay restoration | 90 / 90 successful fault cases had exact manifest-assisted replay restoration. | release_evidence/final/public/aggregate_report.json; docs/FINAL_BENCHMARK_RESULTS.md | Directly measured | All four | High | Replay uses private answer-key truth; it is not detector-only or automatic remediation. |
| C-13 | v0.1 failure cause | All 30 failures are stage=injection, category=no_eligible_targets, in three cells: Look-Ahead high (30 day lag), Revision Overwrite medium (5% revision), and Revision Overwrite high (20% revision). | docs/FINAL_BENCHMARK_RESULTS.md; release_evidence/final/public/case_matrix.json; docs/STATUS.md | Directly measured plus interpretation | All four | High | The cells were retained rather than configured away; they were not measured for recall because no target existed. |
| C-14 | v0.1 false-positive behavior | All 78 false positives are cross-detector findings under strict primary-label scoring. The dominant source is the documented natural exact-duplicate pair; a Revision Overwrite corruption also creates a valid Duplicate signal. | docs/FINAL_BENCHMARK_RESULTS.md; docs/METHODOLOGY.md; docs/faults/DUPLICATE_OBSERVATIONS.md | Directly measured plus interpretation | Technical interviewer; professor/research reviewer | High | This explains the metric; it does not prove that every cross-detector finding is useful in production. |

#### v0.1 by-fault-profile breakdown

| Profile | Configured / successful / failed | Injected faults | Findings | TP / FP | Eligible-clean denominator | Precision | Recall | F1 | False-positive rate | Research changed / replay restored |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| duplicate_observation | 31 / 31 / 0 | 70 | 101 | 70 / 31 | 651 | 0.69306930693069306930693069306930693069306930693069 | 1 | 0.8187134502923976608187134502923976608187134502924 | 0.047619047619047619047619047619047619047619047619048 | 30 / 30 |
| lookahead_timestamp | 31 / 21 / 10 | 20 | 41 | 20 / 21 | 253 | 0.4878048780487804878048780487804878048780487804878 | 1 | 0.65573770491803278688524590163934426229508196721311 | 0.08300395256916996047430830039525691699604743083004 | 20 / 20 |
| revision_overwrite | 31 / 11 / 20 | 10 | 21 | 10 / 11 | 11 | 0.47619047619047619047619047619047619047619047619048 | 1 | 0.64516129032258064516129032258064516129032258064516 | 1 | 10 / 10 |
| unit_drift | 31 / 31 / 0 | 30 | 45 | 30 / 15 | 155 | 0.66666666666666666666666666666666666666666666666667 | 1 | 0.79999999999999999999999999999999999999999999999996 | 0.096774193548387096774193548387096774193548387096774 | 30 / 30 |

Source: release_evidence/final/public/aggregate_report.json and
docs/FINAL_BENCHMARK_RESULTS.md. The Revision Overwrite rate of 1 is
arithmetically correct but has denominator 11, so it is statistically thin.

#### v0.1 by-severity breakdown

| Severity | Configured / successful / failed | Injected faults | Findings | TP / FP | Denominator | Precision | Recall | F1 | False-positive rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| low | 41 / 41 / 0 | 40 | 76 | 40 / 36 | 391 | 0.52631578947368421052631578947368421052631578947368 | 1 | 0.68965517241379310344827586206896551724137931034484 | 0.092071611253196930946291560102301790281329923273657 |
| medium | 43 / 33 / 10 | 40 | 67 | 40 / 27 | 419 | 0.59701492537313432835820895522388059701492537313433 | 1 | 0.74766355140186915887850467289719626168224299065425 | 0.064439140811455847255369928400954653937947494033413 |
| high | 40 / 20 / 20 | 50 | 65 | 50 / 15 | 260 | 0.76923076923076923076923076923076923076923076923077 | 1 | 0.86956521739130434782608695652173913043478260869562 | 0.057692307692307692307692307692307692307692307692308 |

Source: release_evidence/final/public/aggregate_report.json.

### D. v0.2 corpus and development/validation evidence

These claims are current additive engineering evidence, not a replacement for
the frozen v0.1 result and not customer evidence.

| ID | Claim | Exact value | Supporting source/artifact | Class | Audience | Publish confidence | Important caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V2-01 | v0.2 corpus size | 12 corpus units and 4,320 records; 3 partitions with 1,440 records each. | corpus_freeze_v0_2.json; docs/CORPUS_V0_2.md | Directly measured | All four | High | This is corpus substrate evidence, not benchmark-result evidence by itself. |
| V2-02 | v0.2 source composition | 9 synthetic-adversarial units / 4,104 records; 3 curated-public units / 216 records; 0 external-private units. | corpus_freeze_v0_2.json; docs/CORPUS_V0_2.md | Directly measured | All four | High | The curated-public units are placeholders with purpose-built values and verbatim_source=false; no live SEC response is reproduced. |
| V2-03 | v0.2 partition design | Development, validation, and separately frozen held-out partitions use disjoint synthetic issuer identities and the same declared cohort construction. | docs/CORPUS_V0_2.md; corpus_freeze_v0_2.json | Design/implementation fact | Technical interviewer; professor/research reviewer | High | Same-generator disjoint partitions are not independent samples of the real world. |
| V2-04 | v0.2 all cells eligible | The corpus census reports all 36 detector/severity cells eligible; Look-Ahead high has 40 best-unit / 86 total eligible units per partition, Revision Overwrite medium 42 / 42, high 28 / 28. | docs/CORPUS_V0_2.md; corpus_freeze_v0_2.json | Directly measured | Technical interviewer; professor/research reviewer | High | Eligibility is a substrate adequacy result, not detector performance. |
| V2-05 | v0.2 persisted development matrix | 390 development fault cases; all 390 succeeded, 0 failed, 0 incomplete; every fault case has paired_clean_control=true. | benchmark_evidence_v0_2/public/development_matrix.json; evidence/design_partner_beta/development_aggregate.json; design_partner_beta_freeze.json | Directly measured | All four | High | The aggregate configured_case_count=390 is the fault-case matrix count; clean-control findings are reported separately. |
| V2-06 | v0.2 persisted validation matrix | 390 validation fault cases; all 390 succeeded, 0 failed, 0 incomplete; every fault case has paired_clean_control=true. | benchmark_evidence_v0_2/public/validation_matrix.json; evidence/design_partner_beta/validation_aggregate.json; design_partner_beta_freeze.json | Directly measured | All four | High | This is synthetic validation evidence, not customer or production validation. |
| V2-07 | v0.2 development aggregate | 4,210 injected faults, 4,815 findings, 3,992 primary matched/true-positive faults, 218 false-negative faults, 823 false-positive findings; precision 0.82907580477673935617860851505711318795430944963655, recall 0.9482185273159144893111638954869358669833729216152, F1 0.8846537396121883656509695290858725761772853185595, false-positive rate 0.012999526141209919444005686305480966671931764334228. | evidence/design_partner_beta/development_aggregate.json | Directly measured | Technical interviewer; professor/research reviewer | High | Copy exact Decimal strings from the JSON; these are synthetic v0.2 production-interpretation aggregates, not customer metrics. |
| V2-08 | v0.2 validation aggregate | 4,210 injected faults, 4,943 findings, 4,046 primary matched/true-positive faults, 164 false-negative faults, 897 false-positive findings; precision 0.81853125632207161642727088812462067570301436374671, recall 0.96104513064133016627078384798099762470308788598575, F1 0.88408172183983393422921446520266579263629411122034, false-positive rate 0.014168377823408624229979466119096509240246406570842. | evidence/design_partner_beta/validation_aggregate.json | Directly measured | Technical interviewer; professor/research reviewer | High | Copy exact Decimal strings from the JSON; these are synthetic v0.2 production-interpretation aggregates, not customer metrics. |
| V2-09 | v0.2 production-interpretation counts | Development: 329 independent-background, 0 secondary-corroborating, 494 unmatched; validation: 344 independent-background, 0 secondary-corroborating, 553 unmatched. | evidence/design_partner_beta/development_aggregate.json; evidence/design_partner_beta/validation_aggregate.json | Directly measured | Technical interviewer; professor/research reviewer | High | These are interpretation categories, not revised precision/recall or additional recall credit. |
| V2-10 | v0.2 clean-control behavior | Development and validation each report 90 clean-control cases with findings and 360 clean-control findings. | Same v0.2 aggregate artifacts | Directly measured | Technical interviewer; professor/research reviewer | High | 90 is the count with findings, not the total number of paired controls. |
| V2-11 | v0.2 held-out benchmark status | No complete v0.2 held-out benchmark result is authorized or claimed in the current beta freeze. | design_partner_beta_freeze.json claims; docs/BENCHMARK_V0_2.md; docs/STATUS.md | Limitation | All four | High | The corpus held-out partition exists and is separately sealed, but its presence is not a result. |
| V2-12 | v0.2 metric interpretation | Development/validation aggregates are synthetic conditional evidence under a versioned corpus and paired-control contract. | docs/BENCHMARK_V0_2.md; design_partner_beta_freeze.json claims synthetic_evidence_only=true, customer_validation_claimed=false, production_validation_claimed=false | Interpretation plus limitation | All four | High | Never label these numbers “customer validation,” “production performance,” or “real-world sensitivity.” |

### E. Missing Observations evidence

| ID | Claim | Exact value | Supporting source/artifact | Class | Audience | Publish confidence | Important caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E-01 | Missing Observations contract exists | Six deterministic mechanisms are implemented under quantcheck/missing-observation/v1. | docs/faults/MISSING_OBSERVATIONS.md; docs/STATUS.md | Design/implementation fact | Technical interviewer; professor/research reviewer | High | This is additive post-MVP functionality, not one of the four frozen v0.1 families. |
| E-02 | Missing Observations development result | 6 cases, 26 injected faults, 26 findings, 0 false positives, 0 false negatives, precision/recall/F1 all 1, 6 research changes, 6 exact restorations. | missing_observation_evaluation_v1.json development section | Directly measured | Technical interviewer; professor/research reviewer | Medium | Explicit expectations were correct by construction; this is synthetic contract evidence. |
| E-03 | Missing Observations validation result | Same exact result as development: 6 cases, 26 faults/findings, 0/0 FP/FN, precision/recall/F1 1, 6 changes, 6 restorations. | missing_observation_evaluation_v1.json validation section | Directly measured | Technical interviewer; professor/research reviewer | Medium | Synthetic validation is not real-feed precision or customer evidence. |
| E-04 | Missing Observations held-out result | Same exact result as development and validation for the gated synthetic six-case set. | missing_observation_evaluation_v1.json heldout section; evaluation ID meval_51a9d73ee7d716a7; freeze ID mefreeze_7b192c639c93010f | Directly measured | Technical interviewer; professor/research reviewer | Medium | The result demonstrates the explicit expectation contract, not that the expectations are economically or operationally correct. |
| E-05 | Missingness authority boundary | A missing cell is evaluated only when an identity-verified expected observation, expected-by date, and evidence reference are supplied; no expectation means no finding. | docs/faults/MISSING_OBSERVATIONS.md | Design/implementation fact | Professor/research reviewer | High | It does not infer calendars, endpoints, taxonomy equivalence, issuer lifecycle, outage cause, or missing values. |

### F. Reproducibility, tests, and package evidence

| ID | Claim | Exact value or wording | Supporting source/artifact | Class | Audience | Publish confidence | Important caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F-01 | v0.1 public-only reconstruction | Public-only aggregate reconstruction is byte-identical to the saved aggregate; the presentation model, HTML, and public artifacts were verified without the private tree. | docs/REPRODUCIBILITY.md; docs/ARTIFACTS_AND_PRIVACY.md; docs/FINAL_BENCHMARK_RESULTS.md | Directly measured | Technical interviewer; professor/research reviewer | High | This proves artifact/presentation reproducibility, not scientific validity or production deployment. |
| F-02 | v0.1 HTML reproducibility | Rendered HTML SHA-256: 2ba3c7746e18df90699a99ddd4ce0e0dc100bb6fa2b0ead7f88e4887e52ac795; presentation model SHA-256: 2c2788ca2673f67f807c89760ddbc030ddde13b8395b65be9300af6566ef7f68. | docs/REPRODUCIBILITY.md; docs/FINAL_BENCHMARK_RESULTS.md | Directly measured | Technical interviewer; professor/research reviewer | High | Hashes identify this saved artifact set and must not be reused for a changed tree. |
| F-03 | Reproducibility across environments | Fresh subprocesses under PYTHONHASHSEED=0, 1, and 987654, changed working/output/temp/user state, and reordered inputs preserve the tested logical artifacts. | docs/REPRODUCIBILITY.md; docs/STATUS.md; determinism tests | Directly measured | Technical interviewer; professor/research reviewer | High | runtime_metadata.json records wall clock/platform/interpreter and differs; index.json differs because it hashes runtime metadata. |
| F-04 | Current test-count status | Direct collection on 2026-08-13 collected 2,257 tests. The attempted full run was interrupted before completion. The last full-suite pass recorded for the Missing Observations milestone is 2,245 tests in 67.82s. | uv run pytest --collect-only -q output; interrupted uv run pytest -q; archived run notes | Directly measured status | Technical interviewer; professor/research reviewer | High if phrased exactly | Do not claim “2,257 tests passed.” The current full-suite result was not completed in this review. |
| F-05 | Earlier recorded full suites | Archived implementation notes record milestone-specific totals including 1,595 at v0.1 release, 2,021 at v0.2 detector execution, 2,140 after policy work, 2,157 after performance work, 2,245 after Missing Observations. | archived run notes | Historical/current milestone evidence | Technical interviewer; professor/research reviewer | Medium | Every number is tied to a different repository state and command; no generic “total tests” claim is safe without a commit and command. |
| F-06 | Package build and clean installation | Offline wheel/sdist builds and clean Python 3.12 installs are repeatedly recorded as passing; the beta closure records 38 focused package/format/integrity tests after PyArrow became a direct dependency. | docs/STATUS.md; design_partner_beta_freeze.json; evidence/design_partner_beta/* | Directly measured, version-scoped | Technical interviewer; professor/research reviewer | Medium | The exact current full build/test evidence must be rerun for a new release; do not infer it from archived run notes. |
| F-07 | Public artifact privacy | Release evidence scans report no manifest/private-only keys, local paths, secrets, tracebacks, or traversable private references in public artifacts. | docs/ARTIFACTS_AND_PRIVACY.md; docs/THREAT_MODEL.md; release_evidence/final/public/ | Directly measured tests | Technical interviewer; professor/research reviewer | High | Privacy minimization is not anonymization; stable hashes can remain linkable and customer/operator retention controls remain outside the application. |
| F-08 | v0.1 release reproducibility identity | Freeze record SHA-256 7584be72c2fa3882c3a61c0ba47354cd3e45f53cd1f4d0bb70f9a012e59f42eb; release config SHA-256 a29c131b83d85323b379436e674efbadff7e382f5e0ca09c7dd3e3bef46e6f3c; case matrix SHA-256 2a1ffbc7d2ff32a0965ccfea3076ac17f46a20d2de6c0d9fc6590799e629cc13. | docs/FINAL_BENCHMARK_RESULTS.md; release_freeze.json | Directly measured | Technical interviewer; professor/research reviewer | High | These authenticate the frozen v0.1 evidence package, not the mutable current worktree. |

### G. SEC, external data, CLI, dashboard, and performance surfaces

| ID | Claim | Exact value or wording | Supporting source/artifact | Class | Audience | Publish confidence | Important caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G-01 | SEC adapter scope | One CIK at a time, one exact Company Facts endpoint, explicit contact-bearing User-Agent, HTTPX requests, cache-first exact-byte persistence, offline replay, and explicit taxonomy/concept/unit/form/date/period allowlists. | README.md; docs/EXTERNAL_DATASETS.md; src/quantcheck/sec_adapter.py | Design/implementation fact | All four | High | It does not reconstruct statements, harmonize concepts, convert currencies/scales, infer revisions/amendments/segments, download multiple CIKs, or make intraday claims. |
| G-02 | SEC live-data evidence status | Ordinary tests still use HTTPX mock transports, but a separate local study preserved five exact SEC Company Facts response hashes and processed 472 selected records. | docs/research/REAL_DATA_RESULTS.md; evidence/real_data_study/study_run.json; docs/CORPUS_V0_2.md | Directly measured, study-scoped | All four | High if study scope remains attached | The observational run demonstrates real-source pipeline execution and an exact-duplicate null result; it is not broad detector validation. Per-fetch live-versus-cache status was not retained. |
| G-03 | Current external input formats | Current 0.2.0.dev0 path accepts declared Parquet, Arrow IPC file/stream, CSV, and Python mappings; mapping, source identity, availability, revision semantics, and integrity pins are explicit. | docs/EXTERNAL_DATASETS.md; docs/PRODUCTION_AUDIT_POLICIES.md | Design/implementation fact | Technical interviewer; professor/research reviewer | Medium | No real customer/vendor file or approved customer policy has been exercised. |
| G-04 | External audit evidence boundary | The external audit path emits manifest-free public audit reports and explicitly does not produce benchmark precision/recall without controlled private truth. | docs/EXTERNAL_DATASETS.md; docs/PRODUCTION_AUDIT_POLICIES.md | Design/implementation fact plus limitation | Technical interviewer; professor/research reviewer | High | A production audit report is not a benchmark score and does not prove source correctness. |
| G-05 | CLI surface | Six root command groups: ingest, inject, audit, evaluate, explain, benchmark; concrete nested workflows include ingest sec, benchmark run, and benchmark smoke. | docs/CLI_CONTRACT.md; src/quantcheck/cli.py | Design/implementation fact | All four | High | Avoid calling this simply “six commands” without saying root groups; the concrete invocation list contains nested subcommands. See X-05. |
| G-06 | Saved-stage CLI equivalence | For expanded cases, inject -> audit -> evaluate produces artifacts byte-identical to direct dispatch for the four v0.1 fault families. | docs/CLI_CONTRACT.md; docs/STATUS.md; CLI equivalence tests | Directly measured | Technical interviewer; professor/research reviewer | High | This is offline contract equivalence, not a usability or production-operations study. |
| G-07 | Presentation surfaces | A strict public artifact reader, one shared immutable presentation model, deterministic self-contained offline HTML, and a local read-only Streamlit dashboard exist. | docs/DASHBOARD_AND_HTML.md; README.md | Design/implementation fact | All four | High | Dashboard is local, single-user, unauthenticated, and not a hosted public URL; dashboard/scripts are outside the wheel/sdist. |
| G-08 | Dashboard/HTML privacy behavior | Presentation reads public artifacts only, does not run injection/detection/scoring/replay/research, and renders with the private tree deleted. | docs/DASHBOARD_AND_HTML.md; presentation isolation tests | Directly measured tests | Technical interviewer; professor/research reviewer | High | It presents saved evidence; it does not independently validate scientific truth. |
| G-09 | Measured local performance envelope | On the checked-in deterministic corpus: 1,000 records total runtime 0.349605250s; 10,000 3.434787625s; 50,000 17.915681750s with one worker. The 50,000-record run was 9.725262708s at two workers and 6.436192375s at four workers; traced largest-partition Python allocation 36,325,079 bytes. | performance_baseline_v1.json; docs/PERFORMANCE_AND_EXECUTION.md | Directly measured | Technical interviewer; professor/research reviewer | Medium | macOS arm64, Python 3.12.13, one deterministic synthetic corpus; peak measure excludes native PyArrow memory and aggregate worker RSS. |
| G-10 | Performance logical determinism | The 50,000-record 1/2/4-worker runs share logical artifact hash 42f05328cdcda08e0882415197f8dde62bc71c591412e31e37abb6387c76203e. | performance_baseline_v1.json | Directly measured | Technical interviewer; professor/research reviewer | High | This proves the recorded local worker-count comparison, not a universal throughput guarantee. |
| G-11 | Self-hosted distribution status | A digest-pinned non-root container, bounded mounts, no-network configuration, security workflows, SBOM/provenance path, and reproducibility script are implemented. | Dockerfile; docs/SELF_HOSTED_DEPLOYMENT.md; docs/SUPPLY_CHAIN_SECURITY.md; docs/STATUS.md | Design/implementation fact | Technical interviewer; professor/research reviewer | Medium | The current candidate has no verified OCI digest, published image, registry push, trusted attestation, pulled-image smoke, or exact two-build OCI proof. |
| G-12 | Local security scan status | Candidate-local Trivy 0.73.0 reports 0 fixable high/critical locked-dependency findings and 0 scanned repository secrets; Syft 1.50.0 emitted an SPDX 2.3 package SBOM. | design_partner_beta_freeze.json; evidence/design_partner_beta/trivy-*.json; evidence/design_partner_beta/quantcheck-wheel.syft.spdx.json | Directly measured | Technical interviewer; professor/research reviewer | Medium | These are local/package-scope results; they do not include a candidate container image and do not establish certification or security. |
| G-13 | Current OCI and trusted-attestation status | OCI archive/config/layer digests are null/not verified for the candidate; candidate source Security run is not_run; trusted attestation is not_created. | design_partner_beta_freeze.json fields oci, security_workflow, supply_chain | Directly measured limitation | All four | High | Never convert configured workflow files or historical run 31368451109 into current candidate completion evidence. |
| G-14 | Observational SEC result | QuantCheck accepted 472 selected records: 180 Assets and 292 NetIncomeLoss. Exact Duplicate had 472 singleton fingerprint groups and zero findings; Look-Ahead, Revision Overwrite, and Unit Drift had zero eligible opportunities. | docs/research/REAL_DATA_RESULTS.md; evidence/real_data_study/applicability.json | Directly measured, retrospective applicability correction | All four | High if detector-specific denominators remain attached | The protocol was not independently timestamped or committed before execution; do not call it preregistered. |
| G-15 | Real-data-substrate adversarial result | Under a protocol committed before outcomes, nine seeded cases contained 120 injected fault instances. All 120 were exactly matched; Unit Drift also emitted four strict false-positive warnings. | docs/research/REAL_DATA_SUBSTRATE_ADVERSARIAL_PROTOCOL.md; docs/research/REAL_DATA_SUBSTRATE_ADVERSARIAL_RESULTS.md; evidence/real_data_substrate_adversarial/study_run.json | Directly measured controlled evidence on real SEC substrate | All four | High if the injected-fault boundary remains attached | These are manufactured faults on preserved real observations, not natural SEC defects or population performance. Revision Overwrite was not applicable. |

## Important discrepancies and required resolutions

| ID | Discrepancy | Artifacts showing each side | Resolution before publication |
| --- | --- | --- | --- |
| X-01 | Archived release materials describe 120 fault cases + 12 controls = 132 cases, while the rebuilt v0.1 release artifact is 120 + 4 = 124. | Archived release material; current: release_freeze.json, release_evidence/final/public/aggregate_report.json, docs/FINAL_BENCHMARK_RESULTS.md | Use 124 for the rebuilt v0.1 evidence. Mention 132 only as an archived target/discrepancy, never as the measured current result. |
| X-02 | Archived metric set conflicts with rebuilt v0.1 artifact: historical precision 0.668..., recall 0.970..., F1 0.791..., 170 injected faults, 5 false negatives, 82 false positives; current artifact is 0.625, 1, 0.769..., 130, 0, 78. | Archived release material; current release_evidence/final/public/aggregate_report.json | Use only the current saved artifact for rebuilt v0.1 claims. Label archived values as historical/outdated and unsafe as current metrics. |
| X-03 | docs/RELEASE_NOTES_0.1.0.md says the release was not published and had no tag, GitHub release, or CI run; docs/RELEASE_CHECKLIST.md records GitHub Actions run 31293937904, tag v0.1.0, and a GitHub release. | docs/RELEASE_NOTES_0.1.0.md; docs/RELEASE_CHECKLIST.md; Git tag | Treat the release notes as stale historical prose. For release-status claims, use the checklist, Git tag, and exact release artifacts. |
| X-04 | docs/DASHBOARD_AND_HTML.md contains a stale limitation saying no final held-out benchmark, release evidence, or CHECKSUMS.md exists, while those artifacts exist and are used by the current release evidence. | docs/DASHBOARD_AND_HTML.md; release_evidence/final/; release_freeze.json; CHECKSUMS.md | Do not quote that stale sentence. Resolve the document before any portfolio publication or use the artifact-backed current status. |
| X-05 | README/release prose calls the interface a “six-command CLI” while the concrete list includes ingest sec, inject, audit, evaluate, benchmark run, benchmark smoke, and explain. | README.md; docs/CLI_CONTRACT.md | Use the precise wording “six root command groups; nested invocations include …” until the prose is harmonized. |
| X-06 | Test counts vary by milestone and repository state: current collection 2,257; interrupted current full run; last recorded full pass 2,245; v0.1 milestone record 1,595; stale release prose says approximately 1,600. | uv run pytest --collect-only -q; interrupted uv run pytest -q; archived run notes | Publish a test count only with a named commit/state and exact command. Do not use “2,257 tests passed” or “approximately 1,600 tests” as a timeless claim. |
| X-07 | Current 0.2.0.dev0 docs scope PyArrow differently by version: immutable v0.1 wheel metadata did not declare it, while current 0.2.0.dev0 metadata declares pyarrow>=24,<25, locked at 24.0.0. | docs/LIMITATIONS.md; docs/EXTERNAL_DATASETS.md; pyproject.toml | Always version the statement: v0.1 wheel versus current 0.2.0.dev0 distribution. |
| X-08 | The current beta freeze claims synthetic evidence only and no customer/production validation, while “design-partner beta” wording could be read as completed pilot evidence. | design_partner_beta_freeze.json; README.md; docs/STATUS.md; docs/DESIGN_PARTNER_SHADOW_MODE.md | Use “beta engineering candidate” or “synthetic engineering evidence”; do not use “design-partner result,” “pilot,” or “customer validation.” |
| X-09 | Long Decimal values in v0.2 aggregates are easy to mis-transcribe when copied from prose. | evidence/design_partner_beta/development_aggregate.json; evidence/design_partner_beta/validation_aggregate.json | Re-read JSON and copy exact strings; never round silently or use an unverified prose transcription. |

## A. Ten strongest defensible public claims

These are the strongest claims currently supportable, provided the version and
caveats remain attached.

1. QuantCheck implements four narrow, deterministic fault-injection and
   manifest-blind auditing slices: Look-Ahead Timestamp, Unit Drift, Duplicate
   Observations, and Revision Overwrite.
2. The v0.1 audit boundary is structural: detectors receive sanitized
   AuditInputSnapshot data and no manifest, clean snapshot, seed, severity, or
   injector target channel.
3. The v0.1 release evidence contains a saved 124-case matrix: 120 fault cases
   and four clean controls.
4. In that matrix, 94 cases succeeded, 30 remained visible as structural
   no_eligible_targets failures, and zero cases were incomplete.
5. Across the successful scored v0.1 cases, the saved results are 130 injected
   faults, 208 findings, precision 0.625, recall 1, F1
   0.76923076923076923076923076923076923076923076923077, and false-positive
   rate 0.072897196261682242990654205607476635514018691588785.
6. All 78 v0.1 false-positive findings are retained cross-detector findings
   under strict primary-family scoring; they were not hidden to improve the
   headline metric.
7. The 90 successful v0.1 fault cases that changed the controlled research
   output also had exact manifest-assisted replay restoration in 90 / 90
   cases.
8. v0.2 adds a frozen 12-unit, 4,320-record corpus substrate and persisted
   synthetic development/validation evidence with 390 successful fault cases in
   each partition; it does not claim customer validation.
9. QuantCheck’s current product surfaces include an offline CLI workflow, a
   public-only artifact reader, deterministic HTML rendering, a local read-only
   dashboard, and a narrow SEC Company Facts adapter.
10. The current 0.2.0.dev0 candidate has local package/security evidence but
    remains not ready to claim a published OCI image, trusted attestation,
    production deployment, or completed design-partner pilot.

## B. Ten claims that must NOT be made

1. “QuantCheck has production-ready v1.0 software” or “the current candidate is
   ready for production deployment.”
2. “QuantCheck was validated by a design partner,” “a customer pilot found,” or
   “customers reported missing-observation pain.”
3. “QuantCheck has 132 measured v0.1 benchmark cases.” The rebuilt artifact is
   124 cases; 132 is historical target evidence.
4. “QuantCheck achieves 100% recall in general” or “the detectors are perfectly
   sensitive.” Recall 1 is fixture- and matrix-specific, and v0.2 Unit Drift
   has false negatives in both development and validation aggregates.
5. “QuantCheck has 0% false positives.” The v0.1 saved result has 78 strict
   primary-label false-positive findings and the v0.2 aggregates also record
   false positives and unmatched findings.
6. “Replay automatically repairs customer data.” Replay is private,
   manifest-assisted answer-key restoration, not detector-only remediation.
7. “QuantCheck reconstructs financial statements, detects all restatements,
   harmonizes taxonomies, converts currencies, or covers all SEC data.” Those
   capabilities are explicitly outside the supported scope.
8. “All four detectors were validated on naturally occurring SEC defects.” The
   observational study had applicable opportunities only for Exact Duplicate;
   the stronger follow-up used manufactured faults on real SEC substrate and
   excluded Revision Overwrite as not applicable.
9. “QuantCheck is certified secure,” “SOC 2/SLSA/NIST/ISO compliant,” or “the
   scans prove the software is secure.” No certification, independent audit, or
   candidate-image scan/attestation is present.
10. “A published container/image/digest or trusted provenance attestation
    exists” for the current beta candidate. The freeze records these candidate
    fields as not verified/not created.

## C. Five weaknesses to disclose proactively

1. **The headline v0.1 result is small and synthetic.** It uses a 26-record
   reviewed synthetic fixture plus a five-observation Unit Drift series. It does
   not establish performance on vendor or customer feeds.
2. **Thirty v0.1 matrix cells never injected a fault.** Look-Ahead high and
   Revision Overwrite medium/high had no eligible target under frozen rules, so
   their recall was not measured. This is a measurement limitation, not a
   hidden success.
3. **Precision is affected by correlated detector findings.** All 78 v0.1
   false positives are cross-detector findings under the strict single-primary
   score, including a legitimate natural duplicate pair.
4. **Some denominators are thin.** Revision Overwrite’s pooled eligible-clean
   denominator is only 11, producing a false-positive rate of exactly 1; it
   must not be compared with large-denominator profiles without the denominator.
5. **External and operational evidence is incomplete.** No real customer/vendor
   file, approved customer policy, adjudicated pilot, candidate OCI proof,
   published image digest, trusted attestation, or third-party security audit is
   present.

## D. Exact source-of-truth artifacts for future portfolio work

Use these artifacts directly, preserving their version labels and caveats.

### Frozen v0.1 benchmark

- release_freeze.json
- release_evidence/final/public/aggregate_report.json
- release_evidence/final/public/case_matrix.json
- release_evidence/final/public/index.json
- docs/FINAL_BENCHMARK_RESULTS.md
- docs/METHODOLOGY.md
- docs/REPRODUCIBILITY.md
- docs/ARTIFACTS_AND_PRIVACY.md
- docs/THREAT_MODEL.md
- docs/LIMITATIONS.md
- CHECKSUMS.md
- Git tag v0.1.0

### Current v0.2 synthetic engineering evidence

- design_partner_beta_freeze.json
- evidence/design_partner_beta/development_aggregate.json
- evidence/design_partner_beta/validation_aggregate.json
- evidence/design_partner_beta/validation_freeze.json
- evidence/design_partner_beta/BETA_CHECKSUMS.md
- corpus_freeze_v0_2.json
- docs/CORPUS_V0_2.md
- docs/BENCHMARK_V0_2.md
- docs/DECISIONS_V0_2.md
- docs/STATUS.md current status and limitation sections

### Fault and method contracts

- docs/faults/LOOK_AHEAD.md
- docs/faults/UNIT_DRIFT.md
- docs/faults/DUPLICATE_OBSERVATIONS.md
- docs/faults/REVISION_OVERWRITE.md
- docs/faults/MISSING_OBSERVATIONS.md for additive post-MVP evidence only
- docs/SERIALIZATION_AND_HASHING.md

### Missing Observations and performance

- missing_observation_evaluation_v1.json
- performance_baseline_v1.json
- docs/PERFORMANCE_AND_EXECUTION.md

### Product and deployment boundaries

- docs/CLI_CONTRACT.md
- docs/DASHBOARD_AND_HTML.md, after resolving X-04
- docs/EXTERNAL_DATASETS.md
- docs/PRODUCTION_AUDIT_POLICIES.md
- docs/DESIGN_PARTNER_SHADOW_MODE.md
- docs/SELF_HOSTED_DEPLOYMENT.md
- docs/SELF_HOSTED_THREAT_MODEL.md
- docs/SUPPLY_CHAIN_SECURITY.md

### Artifacts not safe as current numeric sources

- Archived release metrics and IDs: historical evidence only.
- docs/RELEASE_NOTES_0.1.0.md until X-03 is resolved.
- The stale “no final held-out benchmark” sentence in
  docs/DASHBOARD_AND_HTML.md until X-04 is resolved.
- Any test count without a named commit/state and exact command.
- Any rounded v0.2 Decimal metric copied from prose rather than the aggregate
  JSON.

## Final publication gate

Before turning this ledger into a public presentation, re-read the exact saved
JSON artifacts, resolve X-01 through X-09, rerun the intended current quality
gates, and attach a version/commit identity to every number. Preserve the
distinction among rebuilt v0.1 release evidence, current synthetic v0.2
engineering evidence, real-data capability, and customer/production evidence.
