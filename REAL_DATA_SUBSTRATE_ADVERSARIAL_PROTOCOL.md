# QuantCheck real-data-substrate adversarial validation protocol

## Frozen status

This protocol defines a new study, separate from the completed observational
SEC run. It is to be committed before any fault injection, detector output, or
score is examined. Structural eligibility counts were inspected solely to
establish feasibility and are frozen below. No injected outcomes have been
generated at the time of this freeze.

No detector, threshold, injector, scoring rule, schema, or product code may be
changed for this study. Any execution defect that prevents the frozen protocol
from running must be reported; it must not be repaired after outcome inspection
and silently rerun under the same study identity.

## Research question

How do QuantCheck's existing deterministic injectors, manifest-blind detectors,
and exact scorers behave when the clean substrate consists of selected real SEC
Company Facts observations with their original values and provenance?

This is **real-data-substrate adversarial validation**. It is not a search for
natural SEC defects, an observational prevalence study, a vendor-history test,
or evidence that the injected corruptions occurred in SEC data.

## Frozen source substrate

Use only the five normalized snapshots preserved by the observational study:

| Issuer | Snapshot ID | Canonical SHA-256 |
| --- | --- | --- |
| Alphabet | `snap_a53c2b4e6bf66eaf` | `d328647f09c8a3f099eeaabc87fba11af07e01c9f209b92f150f87de38a0b872` |
| Amazon | `snap_16ec02da084c8e17` | `d1e041a5b72dd12629076d5336a8c4230ea3e203e7823903f6aece592a842c56` |
| Apple | `snap_84a55b7ca95a375f` | `7b332134aca42263b55835d825394b5d236c86a6afed2386eb8b33ed6e47ca88` |
| JPMorgan | `snap_80b3fbca435e46ab` | `75410508de281e20eb343f071fba7a72075c17eb198262632bf2cb76094af55c` |
| Microsoft | `snap_af671de0a0e69a14` | `eec8bd268fcf01d0716dc785dbd64321cc778ad8016517bcf1740097aa445183` |

The records are the original accepted `us-gaap:Assets` and
`us-gaap:NetIncomeLoss` values, units, dates, accessions, source locators, and
source-row provenance from filings dated 2021-01-01 through 2024-12-31. The
audit cutoff remains 2024-12-31. The combined 472-record substrate must have
snapshot ID `snap_5eee9e1e6a6613f2` and canonical SHA-256
`efebaf6fc7204bf570f9f50b7332c4a062fb3297858f390dce80620627b80203`.

No live SEC request is allowed. Later endpoint data are out of scope.

## Frozen selection algorithms and exclusions

### Look-Ahead and Duplicate Observations

Use all 472 combined records without changing any clean value or provenance.

### Unit Drift

The original adapter retains repeated source occurrences at the same chronology
coordinate, which makes every exact Unit Drift series inapplicable. Apply this
predeclared, value-preserving selection rule:

1. Group by the existing exact `ComparableSeriesKey` plus `period_end` and
   `period_start` (or `period_end` for instant facts).
2. If records at one coordinate contain more than one distinct Decimal value,
   exclude the entire coordinate rather than infer revision semantics.
3. Otherwise retain the latest filed occurrence, breaking ties by
   `available_on`, accession number (empty string for null), and stable
   `record_id`, all ascending with the maximum tuple selected.
4. Do not alter any field on the retained occurrence.

Frozen structural accounting: 265 coordinate groups; 201 equal-value repeated
occurrences collapsed; eight records at two conflicting-value coordinates
excluded; 263 records retained. The resulting snapshot must have ID
`snap_875bba34e465d51f`, canonical SHA-256
`5ba093bd607568b4d6097259ae99e5ee95f7640b31b6178666957e64290dd0b6`,
and 239 existing comparable observations.

## Per-detector eligibility and denominators

| Family | Frozen clean substrate | Eligibility rule | Opportunities per case | Injected targets per medium-severity case |
| --- | --- | --- | ---: | ---: |
| Look-Ahead | all 472 records | Existing rule; `period_end <= 2023-12-31 < available_on`, filing-equals-availability, at least 14-day filing lag | 73 | 4 |
| Duplicate Observations | all 472 records | Existing singleton exact-fingerprint rule | 472 | 24 |
| Unit Drift | 263-record selected substrate | Existing comparable-observation rule | 239 | 12 |
| Revision Overwrite | none | Requires source-declared revision lineage and eligible historical/later vintage relationship | 0 | 0 |

Revision Overwrite is **NOT_APPLICABLE** and will not be injected, detected, or
scored. Creating inferred lineage would violate the source-semantics boundary.

For scoring, use each existing scorer's own `eligible_clean_denominator`; do
not use 472 as a common denominator. The same substrate is reused across seeded
cases, so case observations and injected fault instances are not independent.

## Frozen configurations

Run seeds `101`, `202`, and `303` for each applicable family.

- Look-Ahead: existing `period_end_substitution`, medium severity,
  `research_as_of_date=2023-12-31`, `max_targets=100`.
- Duplicate Observations: existing `exact_occurrence_copy`, medium severity,
  `max_targets=100`.
- Unit Drift: existing `value_scaled_unit_unchanged`, medium severity,
  `max_targets=100`; existing detector defaults `ratio_threshold=50` and
  supported factors `100`, `1000`, and `1000000`.
- Detectors receive only `sanitize_for_audit(corrupted_snapshot)`.
- Scoring receives the finalized detector report and the corresponding private
  manifest only after detection completes.

Run one clean control for each applicable detector on its corresponding clean
substrate before the seeded case loop. Preserve every control finding and every
seeded finding.

## Frozen metrics

For each case report: eligible opportunities, injected faults, findings, exact
true-positive faults/findings, false negatives, false positives, precision,
recall, F1, eligible-clean denominator, and false-positive rate using existing
score contracts. Also report clean-control finding counts.

Family-level micro totals may be reconstructed by summing counts and then
recomputing ratios. Do not report confidence intervals, population estimates,
or natural-defect prevalence. Report target overlap across seeds as a
dependence diagnostic, not as an error.

## Interpretation rules

1. Call the manipulated observations **injected faults on real SEC substrate**,
   never natural SEC errors.
2. Separate clean-control detector output, injected-case detector output, and
   hidden-manifest scoring.
3. Preserve misses, unmatched alerts, ambiguous matches, and null metrics.
4. Do not tune or exclude a case after seeing detector output.
5. A positive result validates only the frozen adversarial cases; a negative or
   mixed result remains reportable.

## Outputs

Write immutable study artifacts under
`evidence/real_data_substrate_adversarial/`, with answer-key manifests under a
clearly separated `private/` subtree and detector/score artifacts under
`public/`. Summarize them in `REAL_DATA_SUBSTRATE_ADVERSARIAL_RESULTS.md` and
keep the observational and adversarial claims distinct in all publication
text.
