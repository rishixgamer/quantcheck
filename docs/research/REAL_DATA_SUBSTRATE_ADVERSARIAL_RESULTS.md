# QuantCheck real-data-substrate adversarial results

## Study identity

The protocol, eligibility freeze, and evaluation-only runner were committed as
Git commit `2150583111dc58a39a15a5584f1ee68fd56ecc66` before any injected
outcome was generated. The run completed at `2026-08-13T17:46:12Z` using that
commit and the protocol SHA-256
`6d452f5c3aef3fff8c74421dcc3a81dd246ea68cd713efa99508a337f0efaab2`.

The clean substrate contains 472 selected observations from five pinned SEC
Company Facts histories. No live request occurred. The study preserved the
original accepted values and provenance and used existing deterministic
injectors to manufacture faults on that substrate.

## Clean controls

| Detector | Clean substrate | Applicable opportunities | Clean-control findings |
| --- | --- | ---: | ---: |
| Look-Ahead Timestamp | 472 records | 73 under the 2023-12-31 research cutoff | 0 |
| Duplicate Observations | 472 records | 472 singleton fingerprints | 0 |
| Unit Drift | 263 conservatively selected records | 239 comparable observations | 0 |
| Revision Overwrite | none | 0 | **NOT_APPLICABLE** |

The Unit Drift selection collapsed 201 equal-value repeated occurrences and
excluded eight records at two coordinates with conflicting values. It retained
each selected SEC observation unchanged. This was a frozen eligibility
operation, not a detector change.

## Seeded exact-scoring results

All cases used medium severity and seeds 101, 202, and 303.

| Family | Seed | Eligible opportunities | Injected faults | Findings | Exact TP | FP | FN | Precision | Recall | F1 | Existing eligible-clean denominator | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Look-Ahead | 101 | 73 | 4 | 4 | 4 | 0 | 0 | 1 | 1 | 1 | 69 | 0 |
| Look-Ahead | 202 | 73 | 4 | 4 | 4 | 0 | 0 | 1 | 1 | 1 | 69 | 0 |
| Look-Ahead | 303 | 73 | 4 | 4 | 4 | 0 | 0 | 1 | 1 | 1 | 69 | 0 |
| Duplicate | 101 | 472 | 24 | 24 | 24 | 0 | 0 | 1 | 1 | 1 | 472 | 0 |
| Duplicate | 202 | 472 | 24 | 24 | 24 | 0 | 0 | 1 | 1 | 1 | 472 | 0 |
| Duplicate | 303 | 472 | 24 | 24 | 24 | 0 | 0 | 1 | 1 | 1 | 472 | 0 |
| Unit Drift | 101 | 239 | 12 | 13 | 12 | 1 | 0 | 12 / 13 | 1 | 0.96 | 239 | 1 / 239 |
| Unit Drift | 202 | 239 | 12 | 13 | 12 | 1 | 0 | 12 / 13 | 1 | 0.96 | 239 | 1 / 239 |
| Unit Drift | 303 | 239 | 12 | 14 | 12 | 2 | 0 | 6 / 7 | 1 | 12 / 13 | 239 | 2 / 239 |

Every injected fault was exactly matched. Unit Drift also produced four strict
unmatched warnings. The hidden-manifest scorer correctly retained them as false
positives; they were not removed or relabelled to improve the metric.

## Family-level micro reconstruction

| Family | Fault instances | Findings | Exact TP | FP | FN | Precision | Recall | F1 | Summed eligible-clean denominator | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Look-Ahead | 12 | 12 | 12 | 0 | 0 | 1 | 1 | 1 | 207 | 0 |
| Duplicate | 72 | 72 | 72 | 0 | 0 | 1 | 1 | 1 | 1,416 | 0 |
| Unit Drift | 36 | 40 | 36 | 4 | 0 | 0.9 | 1 | 0.94736842105263157894736842105263157894736842105263 | 717 | 0.0055788005578800557880055788005578800557880055788006 |

The summed denominators repeat the same clean substrate across three seeded
cases. They support reconstruction of these cases only, not independent-sample
inference.

## Human review of the four unmatched Unit Drift warnings

All four affected records were non-target observations in the same exact
series as one or more injected targets. Each became suspicious only after an
adjacent value was multiplied by the frozen ×1000 transformation; the Unit
Drift clean control emitted zero findings. Human review therefore classified
the four warning instances as **correlated/redundant warnings** caused by the
multi-target injection context. This does not alter their strict scoring as
false positives. Full record-level evidence is in
`REAL_DATA_SUBSTRATE_ADVERSARIAL_ADJUDICATION.md`.

## Dependence diagnostics

- Look-Ahead: 12 unique target records across 12 fault instances; no target
  repeated across seeds.
- Duplicate: 67 unique targets across 72 fault instances; five records appeared
  in more than one seed.
- Unit Drift: 32 unique targets across 36 fault instances; four records appeared
  in more than one seed.

These are deterministic seeded cases on reused substrate, not independent
draws.

## A. What QuantCheck detected

Across nine applicable injected cases, QuantCheck emitted 124 findings: 120
exact matches to 120 injected faults and four additional Unit Drift warnings.
All three clean controls emitted zero findings. Revision Overwrite was not run.

## B. What human review concluded

The existing end-to-end injector, audit boundary, detector, and exact scorer
worked on the frozen real SEC substrate for Look-Ahead, Duplicate Observations,
and Unit Drift. The four unmatched Unit Drift warnings were injection-correlated
secondary alerts, retained as strict false positives. No natural SEC defect was
established.

## C. What remains uncertain

The study does not measure performance on naturally occurring errors, broader
concepts or issuers, vendor feeds, undeclared revision histories, or different
injection severities. Target selection is deterministic and substrate reuse
limits statistical independence. Revision Overwrite remains untested on this
real-source substrate.

## Safe conclusion

On 472 selected observations from five pinned SEC Company Facts histories,
QuantCheck's existing deterministic Look-Ahead, Duplicate, and Unit Drift
workflows detected all 120 prospectively specified injected fault instances
across nine seeded cases. Four additional Unit Drift warnings were retained as
strict false positives and reviewed as injection-correlated alerts. Clean
controls emitted no findings. Revision Overwrite was not applicable because
the adapter did not declare revision lineage. These results validate the frozen
adversarial cases on real-data substrate; they do not establish natural-error
prevalence or general real-world detector accuracy.
