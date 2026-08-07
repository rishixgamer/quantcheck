# Look-Ahead Timestamp fault contract

This is the current authoritative contract for Recovery Phase 3. It defines
only the `lookahead_timestamp` / `period_end_substitution` vertical slice at
specification version `quantcheck/lookahead-period-end/v1`.

The lost historical release referenced a fault document under `docs/faults/`,
but that file did not survive. Historical evidence fixes the period-end
substitution, SHA-256 selection, severity thresholds, exact scoring,
availability-count comparison, and manifest-assisted replay. The remaining
reconstruction decisions are recorded in `docs/DECISIONS.md`; no historical
artifact identity or byte sequence is claimed.

## Inputs and roles

- Injection accepts an identity-valid clean `DatasetSnapshot` and a strict
  `LookAheadInjectionConfig`.
- The corrupted snapshot and `FaultManifest` are separate outputs. The
  manifest is private.
- `sanitize_for_audit` projects the corrupted snapshot into an
  `AuditInputSnapshot`.
- `detect_lookahead` accepts only that sanitized snapshot. It has no manifest,
  clean-data, seed, severity, target-count, target-rank, or injector input.
- Scoring accepts the already finalized immutable `AuditReport` and the
  private manifest. It does not run detection.

## Eligibility

A clean record is eligible exactly when all of these are true:

1. The clean snapshot identity matches its canonical contents.
2. The research cutoff does not follow the snapshot's source horizon.
3. The record is available by the source horizon.
4. The clean snapshot has no pre-existing `available_on < filed_on` defect.
5. For the record, `available_on == filed_on`. Delayed or otherwise unsupported
   source-availability semantics are ineligible rather than guessed.
6. `period_end <= research_as_of_date < available_on`.
7. `filed_on - period_end` meets the severity's minimum natural filing lag.

Severity profiles are fixed:

| Severity | Target fraction | Minimum filing lag |
| --- | ---: | ---: |
| low | `0.02` | 7 days |
| medium | `0.05` | 14 days |
| high | `0.10` | 30 days |

If there are no eligible targets, injection raises
`NoEligibleLookAheadTargetsError`. Otherwise:

```text
target_count = min(
    eligible_count,
    max_targets,
    max(1, ceil(eligible_count * target_fraction)),
)
```

The ceiling is computed with `Decimal`, never binary float. `max_targets` is a
strict positive configuration value and defaults to 100.

## Selection and mutation

Each eligible record receives this full SHA-256 selection digest:

```text
sha256(canonical_json({
  "namespace": "quantcheck/lookahead-target-selection/v1",
  "spec_version": "quantcheck/lookahead-period-end/v1",
  "seed": <non-negative integer>,
  "eligibility_unit_id": <stable clean record_id>
}))
```

Records rank by `(selection_digest, record_id)`. Selected order is zero-based
and recorded privately as `target_rank`.

The exact mutation is:

```text
corrupted.available_on = original.period_end
```

Only `record_id` and `available_on` change. The derived record ID uses a
dedicated modified-record namespace but the normal `rec_` prefix. Sharing the
record prefix is intentional: a visible `mod_` prefix would leak an
injected-row flag across the audit boundary. Every other field, including
`filed_on`, value, unit, dimensions, period, accession, and source provenance,
is logically identical.

## Private manifest

The manifest records clean/corrupted snapshot IDs and hashes, configuration,
the full eligible record-ID set, target count, and one entry per selected
fault. Each entry contains the selection digest/rank, stable fault identity,
complete original and corrupted records, and exact reversible date mutation.

None of the following appears in the sanitized audit input: original record,
true availability, manifest role, selection digest/rank, eligible/selected
sets, seed, severity, target fraction/count, cap, or expected finding count.

## Public detection rule

Rule `temporal.period_end_available_before_filing` is proven when:

```text
available_on == period_end < filed_on
and available_on <= audit_as_of_date
```

One finding is emitted per affected record. Public evidence contains only the
affected record ID, period end, reported availability date, preserved filing
date, audit as-of date, leaked-day count (`filed_on - available_on`), and
public source name/locator. Confidence is `proven_by_contract`. Finding
severity is low below 14 leaked days, medium from 14 through 29, and high from
30 onward. Explanations are deterministic.

## Exact matching and metrics

A finding matches a manifest entry only when detector identity/version,
fault class/subtype, rule, one affected corrupted record ID, derived severity,
confidence, every public evidence field, and the finding's stable identity all
match exactly. Near matches remain false-positive findings. Missed entries
remain false-negative faults.

Matching is one-to-one. An identical repeated finding yields one accepted
match and additional duplicate false positives. Distinct findings competing
for one entry, or one finding matching multiple entries, are ambiguous and do
not count as true positives.

The false-positive denominator is:

```text
eligible_clean_denominator = eligible_record_count - target_count
```

Metric conventions:

- precision is null when there are no findings;
- recall is null when there are no injected faults;
- F1 is null when precision or recall is null, and zero when both defined
  inputs sum to zero;
- false-positive rate is null when the eligible clean denominator is zero.

All defined ratios use `Decimal` with deterministic precision.

## Controlled research and exact replay

`availability_count_v0_1` applies exactly:

```text
count(record.available_on <= research_as_of_date)
```

to each supplied snapshot. It is a controlled occurrence count, not a trading,
alpha, return, Sharpe, or financial-loss claim.

`manifest_assisted_exact_replay` is private answer-key replay. It validates
manifest identity, configuration, SHA-256 selection, IDs, mutations, and
snapshot hashes before replacing exact corrupted records with their stored
originals. It creates a new snapshot, is idempotent for an already restored
snapshot, and must reproduce the clean snapshot ID and hash exactly. It is not
detector-only or automatic remediation.
