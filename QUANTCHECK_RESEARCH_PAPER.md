# QuantCheck: Adversarial Testing of Point-in-Time Financial Research Data

**Finalized research manuscript — Milestone 3S**
**Evidence cutoff:** 2026-08-13
**Canonical evidence register:** [QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md](QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md)

## Abstract

Point-in-time financial research can be distorted when a dataset exposes a fact
before it was available, changes a value's scale without changing its unit,
duplicates an occurrence, or substitutes a later revision into an earlier
historical state. QuantCheck is a deterministic Python framework for creating
these four narrow controlled faults, auditing a sanitized manifest-blind input,
and exactly scoring findings against private truth only after detection is
finalized. Its primary controlled evidence is a frozen v0.1 held-out benchmark:
124 configured cases on reviewed synthetic fixtures: 120 fault cases and four
clean controls. Ninety fault cases succeeded, 30 were retained as structurally
ineligible, and all four controls succeeded, for 94 successful cases total.
Across successful cases, 130 injected faults produced 208 findings, with strict primary-family
precision 0.625, recall 1, and 78 retained cross-detector false positives. This
is a controlled contract result, not a real-world performance estimate.

Two real-source evidence layers were evaluated separately. An observational SEC
Company Facts run processed 472 selected observations—180 Assets and 292
NetIncomeLoss—from five issuers. It demonstrated pipeline execution and an
exact-duplicate null result, but Look-Ahead, Revision Overwrite, and Unit Drift
were not applicable under the selected adapter semantics. A distinct
Git-frozen adversarial study then preserved the SEC-derived values and
provenance while using existing injectors. Across nine cases, Look-Ahead,
Duplicate, and Unit Drift exactly matched all 120 injected fault instances;
Unit Drift also emitted four strict false positives, giving Unit Drift micro
precision 0.9 and recall 1. The 120 faults were manufactured test conditions,
not naturally occurring SEC defects. Revision Overwrite remained inapplicable
because the adapter did not declare revision lineage. The evidence supports
specified controlled contracts and real-source pipeline execution, not natural
error prevalence, vendor-scale accuracy, or production readiness.

## 1. Introduction

Financial research can appear persuasive while relying on a historical state
that could not have existed at the stated decision date. A filing can be made
visible too early; a scale factor can corrupt a value while its unit label looks
unchanged; one fact can be counted twice; or a later revision can replace a
historical fact. These are data-integrity risks, not claims about security
valuation or a trading opportunity.

QuantCheck asks a narrow question: can a point-in-time financial research
dataset be adversarially tested for specified ways it could manufacture a
misleading result? The system uses deterministic fault injection, a private
manifest, sanitized manifest-blind detection, exact post-detection scoring,
and controlled research-output sensitivity calculations. It does not provide
investment recommendations, trading strategies, general statement
reconstruction, or universal SEC ingestion.

This paper separates three evidence classes: a frozen controlled synthetic
benchmark, which is the primary performance evidence; an observational SEC
integration study, which assesses a narrow real-source execution and
applicability question without ground truth; and a prospectively frozen
adversarial experiment that introduces controlled faults into real SEC-derived
observations. A synthetic match is not a natural-error discovery, a successful
ingestion run is not broad detector validation, and an injected fault on a real
observation is not evidence that the issuer reported a defect.

## 2. Point-in-time financial data and research contamination

QuantCheck distinguishes period end, filing date, availability date, research
as-of date, and runtime date. Under the v0.1 day-level contract, a fact is
visible when available_on is on or before as_of_date. Conflating these dates
can create a plausible but historically impossible research state. [1, A-04]

The framework's controlled research-output calculations illustrate sensitivity
to a specified corruption: availability count for Look-Ahead, configured exact
aggregates for Unit Drift and Duplicate, and a frozen-vintage growth ranking for
Revision Overwrite. A changed controlled output is not return, alpha, Sharpe,
financial loss, or actual investment performance. [1, C-11; 2]

## 3. Threat model

The scientific boundary prevents a detector from reading its answer key.

| Stage | Permitted information | Excluded information |
| --- | --- | --- |
| Injector | Clean snapshot and strict configuration | Detector outputs and scores |
| Private manifest | Targets, originals, mutations, selection evidence | Detector input |
| Detector | Sanitized audit input and public configuration | Manifest, clean values, target IDs, seed, severity, injection metadata |
| Scorer | Finalized audit report plus private manifest | Ability to rerun or modify detection |
| Reviewer | Preserved finding and adjudication evidence | Authority to erase inconvenient findings |

The detector's output is a mechanical claim about detector-visible fields. It
is not, by itself, proof that a public issuer made an accounting error. The
boundary instead makes the controlled experiment auditable: injection and
truth are separate from detection, and matching occurs only afterward. [1,
A-07–A-10]

## 4. QuantCheck architecture

The core pipeline is clean snapshot → deterministic injection → corrupted
snapshot plus private manifest → sanitization → manifest-blind detector →
finalized audit report → exact scoring with private manifest.

Financial values are Decimal; public JSON encodes them as canonical strings.
Logical identities use canonical JSON and SHA-256 and are designed not to
depend on row position or Python hash randomization. Sanitization removes fields
the detector must not receive, including source-row lineage markers. [1,
A-05–A-08]

This boundary deliberately constrains what a detector can prove. In particular,
the system does not infer revision lineage from accession similarity, form,
value, or date proximity. That restraint limits some real-source applicability
but prevents an apparent validation result from being manufactured by guessing.

**Recommended Figure 1 — architecture and trust boundary.** Show the private
manifest/injector path separately from the sanitized detector input, with
scoring as the first point at which a finalized report meets private truth. Do
not depict detectors as reading raw source payloads or manifests.

## 5. Fault model

### 5.1 Look-Ahead Timestamp

The supported subtype, period_end_substitution, replaces a clean eligible fact's
availability date with its period end while retaining its filing date. The
detector flags a visible record when the availability date is the period end and
precedes the filing date. Frozen low, medium, and high profiles require natural
filing lags of 7, 14, and 30 days respectively. This is not an intraday
timestamp, source latency, or arbitrary availability-error detector. [1,
B-01, B-07]

**Recommended Figure 2 — Look-Ahead timeline.** Show period end, research
cutoff, and filing/true availability. Mark the moved availability date as a
controlled test mutation, not a natural filing event.

### 5.2 Unit Drift

The value_scaled_unit_unchanged subtype multiplies a nonzero value by 100,
1,000, or 1,000,000 while preserving its unit and context. The detector uses
an exact comparable-series key and immediate nonzero neighbors. Under the fixed
default, it considers a supported correction when local ratios meet threshold
50 and the correction restores usable ratios below 50. It does not perform
currency conversion, unit normalization, or arbitrary anomaly detection. [1,
B-02]

### 5.3 Duplicate Observations

The exact_occurrence_copy subtype appends one copy of a clean singleton exact
fingerprint. The detector emits one finding for every visible fingerprint group
of size two or larger. It is exact-copy detection rather than fuzzy
deduplication, entity resolution, amended-filing interpretation, or general
data cleanup. [1, B-03]

### 5.4 Revision Overwrite

The later_vintage_in_earlier_state subtype substitutes later value and
provenance for a historical occurrence while retaining historical availability.
Its eligibility requires explicit source-declared revision lineage and an
adjacent eligible historical/later relationship. Accessions, forms, values, or
dates never create lineage by inference. [1, B-04; 6]

## 6. Manifest-blind evaluation methodology

For each case, QuantCheck validates the clean snapshot and strict configuration,
deterministically selects eligible targets, injects a corruption and private
manifest, sanitizes the corrupted snapshot, and runs the detector. The exact
scorer receives the private manifest only after the audit report has been
finalized.

Matching is one-to-one and requires the documented fault type, rule, affected
records, and required public evidence. Extra findings cannot increase recall;
misses remain false negatives; and a mechanically valid cross-detector warning
can remain a strict false positive for the primary fault family. Clean controls
use the same detector and score contracts and stay visible in results. [1,
A-09–A-10]

The methodology intentionally reports rather than suppresses unhelpful-looking
findings. A flattering metric that silently discards a cross-detector alert or
secondary warning would be less scientifically informative.

## 7. Controlled benchmark protocol

The primary controlled result is the frozen v0.1 held-out benchmark. It uses
four profiles, three severities, and ten reserved final seeds 1000–1009: 120
fault cases plus four clean controls, or 124 configured cases. The substrate is
the reviewed offline synthetic fixture of 26 records plus a five-observation
Unit Drift series. It is not a live SEC or vendor-data benchmark. [3,
Configuration]

The saved candidate is relc_2c6e945a71b85b39, benchmark
bench_403a85e506ff66ea, and aggregate report agg_571aae0b7c60a4a5. An earlier
complete candidate was preserved but invalidated because its public evidence
could not be deserialized; the later correction was proven not to alter
scientific artifacts. [3, Release candidate]

## 8. Controlled benchmark results

| Metric | Frozen v0.1 held-out result |
| --- | ---: |
| Configured cases | 124 |
| Successful / failed / incomplete | 94 / 30 / 0 |
| Injected fault units | 130 |
| Findings | 208 |
| Exact true-positive findings / strict false-positive findings | 130 / 78 |
| False-negative faults | 0 |
| Eligible-clean denominator | 1,070 |
| Strict micro precision | 0.625 |
| Strict micro recall | 1 |
| Strict micro F1 | 0.76923076923076923076923076923076923076923076923077 |
| False-positive rate | 0.072897196261682242990654205607476635514018691588785 |

Table 1. Primary controlled-benchmark aggregate. The denominator is the
contract-specific eligible-clean denominator, not all rows or findings. These
are successful injected cases on a small reviewed synthetic fixture, not a
production precision, recall, or accuracy estimate. Source: [3].

| Primary family | Configured / successful / failed | Faults | Findings | TP / FP | Eligible-clean denominator | Precision | Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Duplicate Observations | 31 / 31 / 0 | 70 | 101 | 70 / 31 | 651 | 0.6930693069 | 1 |
| Unit Drift | 31 / 31 / 0 | 30 | 45 | 30 / 15 | 155 | 0.6666666667 | 1 |
| Look-Ahead | 31 / 21 / 10 | 20 | 41 | 20 / 21 | 253 | 0.4878048780 | 1 |
| Revision Overwrite | 31 / 11 / 20 | 10 | 21 | 10 / 11 | 11 | 0.4761904762 | 1 |

Table 2. Primary-family results. Revision Overwrite's false-positive rate is 1
because its denominator is only 11; it must not be compared casually with
Duplicate's denominator of 651. Source: [1, C profile breakdown].

**Recommended Figure 3 — benchmark by family.** Use a small multiple of strict
precision, recall, and denominator. Place no-target cases in a separate visual
channel; never convert them into zero recall.

## 9. Failure analysis

All 30 failed benchmark cases were structural ineligibility at injection, not
crashes, and no target was injected in them.

| Cell | Failed cases | Frozen structural reason |
| --- | ---: | --- |
| Look-Ahead / high | 10 | Requires a 30-day natural filing lag; the reviewed fixture has none. |
| Revision Overwrite / medium | 10 | Requires a 5% revision; the only declared history changes by 2%. |
| Revision Overwrite / high | 10 | Requires a 20% revision; the same history changes by 2%. |

Table 3. Retained no-target cells. These cases are N/A for fault-detection
recall, not failed detector detections. Source: [3, Honest failure analysis].

All 78 strict false positives are cross-detector findings under the documented
primary-family convention. The dominant source is a documented natural exact
duplicate pair in the reviewed fixture; a Revision Overwrite corruption can
also yield a valid Duplicate signal. Keeping those warnings explains the
metric's lower precision without pretending that every cross-detector signal is
a detector malfunction. [1, C-14]

**Recommended Figure 4 — retained outcome taxonomy.** Stack exact matches,
cross-detector strict false positives, misses, and no-target cases by primary
family. Label the thin Revision Overwrite denominator directly.

## 10. Controlled research-output sensitivity

Ninety of the 94 successful benchmark cases had a configured controlled
research-output calculation. All 90 changed after injection, and private
manifest-assisted exact replay restored the clean result in all 90. The other
successful cases have no configured sensitivity calculation; no-target cases
have no injected comparison. [1, C-11–C-12]

This demonstrates sensitivity of specified calculations to specified faults.
Replay uses private answer-key truth and is not automatic detector-only repair.
Neither result is investment-performance or financial-loss evidence.

## 11. Real-source observational evaluation

The observational SEC study asked whether existing SEC normalization,
point-in-time snapshotting, sanitization, and detector execution could run on a
narrow public-source cohort. The purposive sample was Apple, Microsoft,
Alphabet, Amazon, and JPMorgan. It retained USD Assets with instant periods and
USD NetIncomeLoss with duration periods from 10-K and 10-Q filings dated
2021-01-01 through 2024-12-31, at an end-of-day 2024-12-31 audit cutoff. [7]

The study accepted 472 observations: 180 Assets and 292 NetIncomeLoss. All four
detectors executed and emitted zero findings, but they did not have the same
opportunity set:

| Detector | Applicability / opportunity count | Findings | Correct interpretation |
| --- | ---: | ---: | --- |
| Exact Duplicate | Applicable: 472 exact fingerprint groups | 0 | All 472 groups were singletons; no duplicate group was found. |
| Look-Ahead | **NOT_APPLICABLE:** 0 | 0 | Availability equals filing date; no available-before-filing opportunity existed. |
| Revision Overwrite | **NOT_APPLICABLE:** 0 | 0 | Adapter declared independent occurrences and no revision relationship. |
| Unit Drift | **NOT_APPLICABLE:** 0 comparable observations | 0 | Repeated chronology coordinates excluded every exact comparable series. |

Table 4. Detector-specific applicability in the SEC observational run. The 472
observations are not a common detector denominator. Source: [8].

The supported conclusion is limited: the pipeline processed the selected
public-source histories and Exact Duplicate had a null result. The run does not
validate all four detectors on natural SEC histories, certify selected facts as
correct, or show that Unit Drift candidates failed a threshold. No Unit Drift
candidate was eligible.

The observational protocol was locally specified before source-payload
inspection but its pre-execution freeze was not independently
publication-verifiable. The retained source hashes define the analyzed bytes;
individual live-download versus cache-reuse status was not retained. The study
must not be described as preregistered. [7, Status; 9]

## 12. Real-data-substrate adversarial evaluation

The follow-up asked a controlled question: do existing deterministic injectors,
manifest-blind detectors, and exact scorers work when the clean substrate is
selected SEC-derived observations with original values and provenance? It was
not a search for natural SEC errors. Its protocol, eligibility freeze, and
evaluation-only runner were committed before outcomes at
2150583111dc58a39a15a5584f1ee68fd56ecc66. [10]

The study reused the 472 cached observations offline. Look-Ahead and Duplicate
used all 472. For Unit Drift, a predeclared value-preserving rule collapsed
equal-value repeated occurrences by deterministic latest-occurrence selection
and excluded conflicting-value coordinates rather than infer revisions. It
retained 263 observations and 239 comparable observations. The operation changed
neither selected values nor detector logic. Revision Overwrite was not
applicable because SEC revision lineage was not declared. [10]

Every applicable family used medium severity and seeds 101, 202, and 303, with
one clean control. Clean controls emitted zero findings.

| Family | Cases | Fault instances | Findings | Exact matches | Strict FP | FN | Micro precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Look-Ahead | 3 | 12 | 12 | 12 | 0 | 0 | 1 | 1 | 1 |
| Duplicate Observations | 3 | 72 | 72 | 72 | 0 | 0 | 1 | 1 | 1 |
| Unit Drift | 3 | 36 | 40 | 36 | 4 | 0 | 0.9 | 1 | 0.94736842105263157894736842105263157894736842105263 |
| Revision Overwrite | 0 | — | — | — | — | — | **NOT_APPLICABLE** | **NOT_APPLICABLE** | **NOT_APPLICABLE** |

Table 5. Exact hidden-manifest scoring on real SEC-derived substrate. Faults
were introduced by QuantCheck; they are not observations of natural SEC
errors. Source: [11].

Across nine applicable cases, all 120 injected fault instances had exact
matches. Four additional Unit Drift warnings remain strict false positives.
Human review found each was a non-target record in the same exact series as one
or more injected neighbors, and the clean Unit Drift control had zero warnings.
They are therefore adjudicated as correlated/redundant warnings caused by the
multi-target injection context. That human classification does not alter the
strict score. Preserving the four warnings is scientifically meaningful because
it exposes a local-neighbor interaction rather than hiding it to improve Unit
Drift precision. [11–12]

The adversarial study is stronger than the observational run for its three
applicable families because it has hidden truth and exact scoring. It does not
measure natural-error prevalence, general production behavior, vendor feeds,
other issuers or concepts, different severities, or independent random samples.

**Recommended Figure 5 — evidence taxonomy.** Place three distinct panels side
by side: synthetic controlled benchmark; observational SEC
pipeline/applicability run; and Git-frozen adversarial faults on SEC-derived
substrate. State prominently: “120 injected faults, not 120 natural SEC
defects.”

**Recommended Figure 6 — real-source results.** Render Table 4 as an
applicability table, not a zero-valued aggregate chart. For Table 5, show fault
instances, exact matches, and strict extra warnings by family; show Revision
Overwrite separately as N/A rather than aggregating it into a rate.

## 13. Reproducibility

QuantCheck uses canonical JSON, Decimal serialization, SHA-256 identities, and
stable record, finding, and fault identifiers. The frozen v0.1 public artifacts
can be reconstructed without the private tree. Tested subprocesses across
selected hash seeds and reordered inputs preserve logical artifacts; runtime
metadata and the index are intentionally runtime-specific. [13]

The observational study preserves source hashes, normalized records, snapshots,
sanitized inputs, and detector-execution artifacts. The adversarial study adds
a pre-outcome Git commit, protocol freeze, private manifests, public audit and
score artifacts, and a run record. These artifacts make the paper traceable;
they do not make the local evaluation an independent production replication.

## 14. Limitations

The principal limitation is external validity. The v0.1 benchmark is small and
synthetic. Its recall of 1 applies to successful injected cases only; 30
structurally ineligible cells remain visible and were not measured for recall.
Its strict false positives are cross-detector findings under a documented
primary-family convention. [3]

The observational SEC study is a narrow purposive sample with two concepts,
selected forms, one time window, one cutoff, and day-level
filing-equals-availability semantics. Three of four detectors were N/A, not
successful zero-performance tests. The local observational freeze is not
independently publication-verifiable. [7–9]

The adversarial SEC-derived study uses medium severity, three deterministic
seeds, and reused substrate; its cases are not independent draws. Unit Drift
needed a frozen selection rule for repeated chronology coordinates. Revision
Overwrite is unvalidated on real SEC substrate because source-declared lineage
was absent and the framework correctly refuses to infer it. The four Unit
Drift false positives are retained evidence of correlated-warning behavior.

QuantCheck is not production ready. The current worktree is 0.2.0.dev0; there
is no published candidate image, trusted provenance attestation,
customer-authorized data evaluation, customer adjudication, or production
deployment evidence. [1, A-02 and G]

## 15. Future work

Future studies should expand evidence rather than optimize the reported
metrics: independently timestamped protocols, broader explicitly mapped source
cohorts, source-declared revision histories, more real-data substrates and
severity profiles, and blinded human review of naturally emitted findings. Each
should preserve detector configuration, eligibility denominators, exclusions,
and every alert.

Separate authorized product work might use mapped external datasets or a
customer-controlled read-only shadow evaluation. Neither should be called
validation until the source, adjudication, and evidence are actually present.
No trading system or generic SEC ingestion program follows from this work.

## 16. Conclusion

QuantCheck supplies a narrow reproducible framework for adversarially testing
point-in-time financial research data against four specified mechanisms. Its
primary evidence is a frozen synthetic benchmark whose successes, structural
ineligibility failures, and cross-detector warnings remain visible.

The real-source evidence is deliberately narrower. The observational SEC run
demonstrated pipeline execution and a null exact-duplicate result but did not
broadly validate three inapplicable detector families. The separately frozen
adversarial study exactly matched 120 controlled faults introduced into
SEC-derived observations and retained four additional Unit Drift warnings as
strict false positives. Revision Overwrite remained inapplicable.

The evidence supports specified controlled contracts and transparent limits. It
does not establish natural SEC defect discovery, general real-world accuracy,
or production readiness.

## Evidence references

1. [QuantCheck public evidence ledger](QUANTCHECK_PUBLIC_EVIDENCE_LEDGER.md).
2. [Methodology](docs/METHODOLOGY.md).
3. [Final held-out benchmark results](docs/FINAL_BENCHMARK_RESULTS.md).
4. [Look-Ahead fault contract](docs/faults/LOOK_AHEAD.md).
5. [Unit Drift fault contract](docs/faults/UNIT_DRIFT.md).
6. [Revision Overwrite fault contract](docs/faults/REVISION_OVERWRITE.md).
7. [Observational SEC protocol](REAL_DATA_STUDY_PROTOCOL.md).
8. [Observational SEC results](REAL_DATA_RESULTS.md).
9. [Observational SEC limitations](REAL_DATA_LIMITATIONS.md).
10. [Adversarial protocol](REAL_DATA_SUBSTRATE_ADVERSARIAL_PROTOCOL.md) and
    [freeze record](evidence/real_data_substrate_adversarial_protocol_freeze.json).
11. [Adversarial results](REAL_DATA_SUBSTRATE_ADVERSARIAL_RESULTS.md) and
    [run record](evidence/real_data_substrate_adversarial/study_run.json).
12. [Unit Drift warning adjudication](REAL_DATA_SUBSTRATE_ADVERSARIAL_ADJUDICATION.md).
13. [Reproducibility](docs/REPRODUCIBILITY.md).
