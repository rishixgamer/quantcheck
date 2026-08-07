# Unit Drift fault contract

This is the current authoritative contract for Recovery Phase 5. It defines
only:

```text
fault_type: unit_drift
fault_subtype: value_scaled_unit_unchanged
primary rule: value.scale_discontinuity
specification: quantcheck/unit-drift-value-scale/v1
```

The historical release says that this subtype used exact comparable series,
100/1,000/1,000,000 multipliers, immediate local ratios, threshold 50, exact
scoring, aggregate-value sensitivity, and manifest-assisted replay. Its source
and original fault document did not survive. The missing rebuilt-v1 choices
are recorded in ADR-003; no historical identifier, artifact byte sequence,
fixture eligibility count, or benchmark result is claimed.

## Roles and trust boundary

- Injection accepts an identity-valid clean `DatasetSnapshot` plus a strict
  `UnitDriftInjectionConfig`.
- It returns a separate corrupted snapshot and private `UnitDriftManifest`.
- `sanitize_for_audit` projects the corrupted snapshot into an
  `AuditInputSnapshot`.
- `detect_unit_drift` accepts only that sanitized snapshot and a public
  `UnitDriftDetectorConfig`. It receives no manifest, clean value, seed,
  severity, target fraction/count, selected IDs, rank, or repair/scoring input.
- `score_unit_drift` receives an already finalized immutable `AuditReport` and
  the private manifest. It never runs detection.

No Unit Drift stage mutates caller-owned models or collections.

## Severity and configuration

Injection profiles are fixed:

| Severity | Scale factor | Target fraction |
| --- | ---: | ---: |
| low | `100` | `0.02` |
| medium | `1000` | `0.05` |
| high | `1000000` | `0.10` |

The scale factor is not a free injection parameter. Configuration rejects
unknown fields, Boolean/negative seeds, nonpositive caps, unsupported labels,
and arbitrary transformation parameters.

The detector defaults to ratio threshold `50` and supported factors `100`,
`1000`, and `1000000`. A caller may use a nonempty unique subset of those
factors and any exact Decimal threshold greater than one. Other factors,
duplicates, floats, non-finite values, and empty sets are rejected. Input
collections are copied, numerically canonicalized, and sorted.

## Exact comparable series and chronology

`ComparableSeriesKey` contains exactly:

- entity ID;
- concept namespace and concept;
- unit;
- canonical dimension axis/member tuple;
- period type; and
- inclusive duration length in days for duration facts, or null for instant
  facts.

There is no concept, currency, taxonomy, dimension, or period-shape
normalization. Instant and duration facts never share a series. Duration
facts of different exact lengths never share a series.

Visible members are ordered by period end, period start (or period end for an
instant), and then record ID. If two members have the same period coordinate,
the complete series is excluded because local chronology would be ambiguous.
Input order is never used.

## Eligibility

The clean snapshot must have a valid content-derived identity, and every
contained record must satisfy `available_on <= snapshot.as_of_date`. A target
is eligible exactly when:

1. its value is nonzero;
2. it belongs to one unambiguous exact comparable series;
3. that series contains at least three end-of-day-visible observations; and
4. at least one nearest previous or next nonzero observation exists.

Zero observations remain in chronology but are not targets or usable
comparators; neighbor search proceeds to the nearest nonzero observation on
each side. Negative values are eligible and ratios use absolute magnitudes.
Invalid canonical facts are rejected by their schemas. Ambiguous chronology
and insufficient series are excluded rather than guessed. No eligible target
raises `NoEligibleUnitDriftTargetsError`.

The clean reviewed 26-record fixture has only two chronological periods per
exact series and is therefore a clean negative control, not a reproduction of
the historical claim that another fixture had 17 eligible observations.

## Target count, selection, and injection

For at least one eligible observation:

```text
target_count = min(
    eligible_count,
    max_targets,
    max(1, ceil(eligible_count * target_fraction)),
)
```

The calculation uses Decimal arithmetic. `max_targets` is positive and
defaults to 100.

Each eligible record receives the full digest:

```text
sha256(canonical_json({
  "namespace": "quantcheck/unit-drift-target-selection/v1",
  "spec_version": "quantcheck/unit-drift-value-scale/v1",
  "seed": <non-negative integer>,
  "eligibility_unit_id": <clean record_id>
}))
```

Records rank by `(selection_digest, record_id)`. Ranks are contiguous and
zero-based. Selection is independent of row order and unrelated ineligible
records.

For each target:

```text
corrupted.value = original.value * severity.scale_factor
corrupted.unit = original.unit
```

Only `value` and `record_id` change. The derived ID uses the dedicated Unit
Drift modified-record namespace but retains the ordinary `rec_` prefix so it
does not expose an injected-row role. Entity, concept, unit, dimensions,
period dates/shape, filing and availability dates, form, accession, source,
and lineage semantics are preserved. Unselected records remain byte-identical.

## Private manifest

The manifest records clean/corrupted snapshot IDs and hashes, configuration,
the complete eligible ID set, target count, and one entry per selected fault.
Each entry contains the exact comparable key and series IDs, usable clean
neighbor IDs, digest/rank, stable fault ID, complete original/corrupted
records, and exact original/corrupted values and factor. Schema and integrity
validation recompute the profile, count, SHA-256 ranking, selection digests,
modified-record IDs, fault IDs, mutation relationship, and permitted field
changes.

None of this private truth crosses `sanitize_for_audit`.

## Public detector rule

The detector groups visible audit records by the same exact key and uses the
same chronology and comparability prerequisites. For every nonzero candidate:

1. choose the nearest previous and next nonzero observations, where present;
2. compute each symmetric absolute Decimal ratio
   `max(abs(candidate / neighbor), abs(neighbor / candidate))` at deterministic
   50-digit working precision;
3. require every before-correction ratio to be at least the configured
   threshold;
4. test both exact division and multiplication by each approved supported
   factor; and
5. retain only corrections for which every after-correction ratio is strictly
   below the threshold.

If several corrections qualify, choose deterministically by minimum maximum
after-ratio, then minimum sum of after-ratios, smaller approved factor, and
division before multiplication. One finding is emitted for the selected
correction. One usable neighbor gives confidence `suspicious`; two give
`strong`. Finding severity is derived from factor 100/1,000/1,000,000 as
low/medium/high.

Public evidence includes the affected record, exact comparable key and period,
visibility cutoff, observed/corrected values, scale and multiplicative
correction factors, operation, threshold, chronological neighbor IDs/values,
before/after ratios, usable-neighbor count, and public source name/locator.
Finding and report order and identity are deterministic.

## Exact matching and metrics

A finding matches one manifest entry only when all of the following are exact:

- valid Unit Drift finding identity and detector identity/version;
- fault family/subtype and `value.scale_discontinuity` rule;
- one exact corrupted record ID;
- factor-derived severity and neighbor-count-derived confidence;
- comparable key, period, availability cutoff, observed value, and source;
- candidate scale factor equal to the injected factor;
- correction factor equal to the factor or its reciprocal; and
- corrected value equal to the private original value.

Matching is one-to-one. Wrong-class/rule/record/factor/evidence findings remain
unmatched false positives, misses remain false negatives, identical duplicate
findings cannot increase recall, and distinct competitors are ambiguous.

The Unit Drift false-positive denominator is the count of **all clean
observations meeting the comparability prerequisites**, including selected
targets. It is not total rows, corrupted rows, findings, target count, or the
Look-Ahead denominator convention.

- precision is null for no findings;
- recall is null for no faults;
- F1 is null when precision or recall is null, and zero when defined inputs
  sum to zero; and
- false-positive rate is null for a zero clean comparability denominator.

All defined ratios use Decimal.

## Manifest-assisted exact replay

`manifest_assisted_exact_unit_drift_replay` is private answer-key replay. It
validates manifest identity and relationships plus the exact input snapshot
identity/hash, replaces only exact corrupted records with stored originals,
rejects missing/altered/forged inputs, preserves unrelated records, and is
idempotent on the exact clean artifact. The repaired snapshot must reproduce
the clean canonical bytes, ID, and SHA-256 hash. This is not detector-only or
automatic remediation.

## Controlled aggregate impact

`aggregate_value_v0_1` sums the Decimal values of end-of-day-visible records
in one configured exact `ComparableSeriesKey`. It applies the identical pure
calculation to clean, corrupted, and repaired snapshots and reports exact
aggregates, included IDs/counts, signed and absolute change, relative change,
and stable result/impact identities. Relative change is signed change divided
by the absolute clean aggregate; it is null when the clean aggregate is zero.

This is controlled aggregate-value sensitivity over occurrences. It is not a
financial statement, statement reconstruction, revision consolidation,
backtest, return, alpha, Sharpe ratio, portfolio result, or financial-loss
claim.

## Hard negatives and known limitations

Tests freeze zero and sign transitions, ordinary local movement, unsupported
extreme movement, different entities/namespaces/concepts/units/dimensions,
instant versus duration and different duration lengths, insufficient history,
no usable nonzero neighbor, amendment metadata without scale evidence, and
same values in unrelated groups.

The historical implementation mentioned a detector-safe `source_status`
exception, but the rebuilt `AuditInputRecord` has no such field. No exemption
or injector-only field is added; amendment/business-event meaning is not
inferred from values.

Immediate-neighbor detection is intentionally narrow. Adjacent simultaneous
corruptions can mask each other. At a series endpoint, a single discontinuity
can be directionally ambiguous and may attribute the scale problem to the
clean neighbor. Exact scoring preserves these misses and false positives; it
does not tune selection after seeing detector output. Currency conversion,
unit relabeling, taxonomy harmonization, fuzzy/ML detection, and automatic
correction are outside this contract.
