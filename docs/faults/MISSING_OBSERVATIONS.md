# Missing Observations

## Selection basis and claim boundary

Post-MVP Milestone H considered Missing Observations and Entity Identity. The repository's
design-partner package states that no customer evaluation, adjudication, or pilot result exists,
and the historical discovery notes propose both families without ranking customer pain. The
available evidence therefore does not distinguish them. Missing Observations is implemented first
only by the milestone's explicit tie-break rule. This is not evidence that customers reported more
missingness pain, and the checked evaluation is synthetic contract evidence, not customer evidence.

The additive specification is `quantcheck/missing-observation/v1`. It does not change the frozen
v0.1 schemas, detectors, benchmark, release evidence, CLI, mapping, policy, or shadow contracts.

## Core rule: absence requires authority

The detector never infers that every entity must report every quarter. It can evaluate a cell only
when `MissingObservationDetectorConfigV1` contains an identity-verified
`ExpectedObservationV1` with:

- exact entity, concept namespace/concept, unit, dimensions, period type, source name, and source
  locator;
- exact period start/end;
- the day by which the observation is expected; and
- a non-blank source/customer-contract evidence reference.

Expectations whose `expected_by` is after the audit cutoff are explicitly `not_evaluated`: a
future expectation is explicitly not evaluated. A gap
without an expectation is outside detector authority and emits no finding, even when adjacent
quarters suggest a cadence. One or more exact matching records make the cell present; duplicate
semantics remain the Duplicate Observations detector's concern.

The public expectation context distinguishes what evidence supports the expectation. It is not an
injector flag:

| Context | Detector rule | Controlled injection mechanism |
| --- | --- | --- |
| explicit required observation | `missing.explicit_expected_observation` | random missingness |
| declared reporting schedule | `missing.reporting_gap` | periodic/reporting gaps |
| declared entity coverage | `missing.entity_coverage_gap` | entity-dependent missingness |
| declared concept coverage | `missing.concept_coverage_gap` | concept-dependent missingness |
| declared survivorship cohort | `missing.survivorship_cohort_gap` | survivorship-like filtering |
| declared source-feed coverage | `missing.source_feed_outage` | source-feed outage |

The first rule does not claim that an observed absence is statistically random. `random_missingness`
is controlled private injection truth; the detector proves only that a generally required cell is
absent. Likewise, source-feed-outage and survivorship findings require the corresponding declared
coverage/cohort evidence rather than inferring cause from row absence alone.

## Deterministic injection and private truth

`inject_missing_observations(clean_snapshot, detector_config, injection_config)` validates the
clean snapshot and the public expectation identity, finds due expectations that match exactly one
clean record, and removes selected records without modifying caller-owned objects.

- Random and periodic mechanisms rank eligible expected cells by SHA-256 over specification,
  mechanism, severity, seed, and expectation ID. Periodic targets must have declared earlier and
  later cells in the same exact series.
- Entity- and concept-dependent mechanisms deterministically select one eligible entity/concept
  group, then rank within that group.
- Survivorship-like filtering removes the complete declared entity scope.
- Source-feed outage removes the complete declared source/window scope.
- A survivorship/outage scope larger than `max_targets` is rejected; it is never partially deleted
  merely to satisfy a cap.

Low/medium/high row-selection fractions are `0.10`/`0.25`/`0.50` for the first four mechanisms.
Complete-scope mechanisms record the same severity profile but remove the whole declared scope.
The private `MissingObservationManifestV1` stores every deleted `FinancialFact`, the complete
eligibility set, deterministic digest/rank, exact clean/corrupted identities and hashes, and the
public evidence the detector must independently reproduce. It is never an audit input.

## Sanitized detector and exact evaluation

The detector signature is exactly `(audit_input: AuditInputSnapshot,
config: MissingObservationDetectorConfigV1)`. It has no manifest, clean snapshot, seed, severity,
target, injector, scorer, or replay channel. `sanitize_for_audit` remains unchanged: entity names,
source-row keys, deleted records/values, selection digests, ranks, and fault IDs do not cross it.

For each due expectation with zero exact matches, the detector emits one immutable finding. Public
evidence contains the expectation, declared evidence reference, audit cutoff, zero observed match
count, and at most the nearest earlier/later visible records in the same exact series. Supporting
records are context, not a substitute ID for the absent row. A finding never exposes the deleted
record ID or value.

Only after the report is finalized does `score_missing_observations` read the private manifest.
Matching is exact on finding identity and the complete expected evidence. One fault matches at most
one finding; duplicate findings do not increase recall; near/unrelated findings are false positives;
misses are false negatives. The clean denominator is the count of mechanism-scoped clean expected
cells.

`manifest_assisted_exact_missing_observation_replay` is private manifest-assisted answer-key
replay. It reinserts
only exact deleted records and requires canonical repaired bytes, snapshot ID, and SHA-256 to equal
the clean snapshot. It is not detector-only repair.

`declared_expected_cohort_mean_v1` applies one Decimal count/sum/mean calculation to the due
expected cohort in clean, corrupted, and repaired states. It demonstrates controlled research
sensitivity to changing cohort composition. It is not a statement reconstruction, backtest,
return, alpha, Sharpe ratio, loss estimate, or customer impact claim.

## Held-out synthetic evaluation

The evaluation configuration is fixed before execution: development, validation, and held-out
partitions each contain one case for each of the six mechanisms, 16 clean observations per case,
medium severity, disjoint synthetic entity/source identifiers, and a fixed seed per case. A
standard-library `ContextVar` gate permits held-out materialization only for the complete six-case
set and one exact freeze ID; subsets, duplicates, nesting, ordinary APIs, and environment flags do
not authorize it.

The saved `missing_observation_evaluation_v1.json` contains aggregate public case evidence only.
It includes clean-control, exact-match, research-change, and replay-restoration counts plus artifact
IDs/hashes. It excludes manifests, deleted records/values, source-row keys, selection digests,
ranks, aggregate values, and cohort means. Its schema fixes `synthetic_contract_evidence=true` and
`customer_evidence=false`.

The frozen configuration is `mefreeze_7b192c639c93010f`, configuration SHA-256
`da80dfbba2b6dcf4122c533d74d97109190a7bfa44231a6f8b87ac9167567f0c`. The saved evidence is
`meval_51a9d73ee7d716a7`, 6,403 bytes, SHA-256
`bae2d0bb65a007ba0d1c1b2e3b549e23dbf5ff123ff69bb403cf09d0cdba064a`. Development,
validation, and held-out partitions each report six cases, 26 injected faults/findings/exact true
positives, zero false positives/false negatives/clean-control findings, six controlled research
changes, six exact restorations, and precision/recall/F1 `1`. Those perfect results follow from a
synthetic fixture in which every deleted cell has an explicit correct expectation; they are not a
general detector-sensitivity or customer-feed claim.

## Limitations

- Explicit expectations can be wrong; QuantCheck proves consistency with the declared contract,
  not that the contract itself is economically correct. Source/data owners must approve it.
- The detector does not infer fiscal calendars, first/last expected endpoints, taxonomy
  equivalence, issuer life-cycle state, industry membership, or outage cause.
- It does not estimate a missing value, infer which upstream system caused a gap, or repair without
  private controlled truth.
- The synthetic held-out result measures this explicit-expectation contract on generated cases. It
  does not establish real-feed precision/recall or demonstrate customer pain.
- Entity Identity remains unimplemented pending demonstrated customer evidence or a later explicit
  prioritization decision.
