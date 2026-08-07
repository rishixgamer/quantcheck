# Revision Overwrite fault contract

This is the current authoritative contract for Recovery Phase 7. It defines
only:

```text
fault_type: revision_overwrite
fault_subtype: later_vintage_in_earlier_state
primary rule: revision.later_vintage_in_earlier_state
specification: quantcheck/revision-overwrite-later-vintage/v1
```

Historical material establishes the intended risk: a later reported revision
must not silently replace the fact available in an earlier research state. It
does not establish rebuilt IDs, artifacts, fixture counts, or benchmark
results. The missing rebuilt-v1 choices are recorded in ADR-005; no historical
artifact identity or byte sequence is claimed.

## Roles and trust boundary

- Injection accepts an identity-valid historical `DatasetSnapshot`, the full
  clean `FinancialFact` source history, and a strict
  `RevisionOverwriteInjectionConfig`.
- It returns a separate corrupted historical snapshot and a private
  `RevisionOverwriteManifest`.
- `sanitize_for_audit` projects the corrupted snapshot to an
  `AuditInputSnapshot`.
- `detect_revision_overwrite` accepts only that sanitized snapshot and the
  strict empty `RevisionOverwriteDetectorConfig`. It receives no manifest,
  clean/historical value, later reference, revision ID, source row key, seed,
  severity, target fraction/count, selected IDs, rank, injector, scorer, or
  replay input.
- `score_revision_overwrite` receives an already finalized immutable
  `AuditReport` and the private manifest. It never invokes detection.

No stage mutates caller-owned models or collections. All financial arithmetic
uses `Decimal`; public Decimal JSON uses the repository's canonical string
encoding.

## Explicit revision eligibility

Revision history exists only when each source row declares the existing
`<lineage_id>#r<positive sequence>` marker. Matching business keys, amended
forms, accessions, or similar values never infer a revision relationship.

`EconomicFactKey` is exactly entity ID, concept namespace/concept, unit,
canonical dimensions, and period shape/dates. One eligible unit contains the
latest source-supported historical revision visible at the snapshot cutoff and
the next declared sequence that is not yet visible. The full lineage must be
unambiguous: sequences are unique; economic context, entity name, and source
name agree; and filing/availability dates are nondecreasing in declared order.
Contradictory histories raise `AmbiguousRevisionHistoryError`; unsupported
unambiguous histories are ineligible rather than guessed.

An adjacent historical/later pair is eligible only when all of these hold:

1. the clean snapshot contains the exact historical record and not the later
   record;
2. `historical.available_on <= snapshot.as_of_date < later.available_on`;
3. both clean records use the supported source semantic
   `available_on == filed_on`;
4. later filing and availability are strictly later than historical filing and
   availability;
5. record IDs, source row keys, accessions, and derived revision IDs are
   distinct, and both accessions are non-null;
6. values differ and the historical value is nonzero; and
7. the exact relative revision size meets the selected severity threshold:

```text
abs(later.value - historical.value) / abs(historical.value)
```

Zero historical values have undefined relative size and are ineligible. A
malformed marker is an independent occurrence, never guessed to be a revision.

## Severity, count, and deterministic selection

| Severity | Minimum relative revision size | Target fraction |
| --- | ---: | ---: |
| low | `0.01` | `0.02` |
| medium | `0.05` | `0.05` |
| high | `0.20` | `0.10` |

For at least one eligible history unit:

```text
target_count = min(
    eligible_count,
    max_targets,
    max(1, ceil(eligible_count * target_fraction)),
)
```

The calculation uses `Decimal`; `max_targets` is positive and defaults to
100. Each unit receives this full SHA-256 digest:

```text
sha256(canonical_json({
  "namespace": "quantcheck/revision-overwrite-target-selection/v1",
  "spec_version": "quantcheck/revision-overwrite-later-vintage/v1",
  "seed": <non-negative integer>,
  "eligibility_unit_id": <canonical adjacent history-unit ID>
}))
```

Units rank by `(selection_digest, eligibility_unit_id)`. Selected ranks are
contiguous and zero-based. Source-record order, candidate-history order, and
unrelated records cannot affect selection.

## Injection and private manifest

For each selected historical occurrence, injection creates a new ordinary
`rec_` record ID in the dedicated Revision Overwrite modified-record namespace
and replaces only that occurrence in the returned historical snapshot. It
copies the later revision's value, filing date, form, accession, and complete
source provenance while retaining the historical `available_on` date. The
economic key, entity, dimensions, period shape/dates, and all unrelated rows
remain unchanged. The actual later source record remains in the caller's full
source history; it is not inserted into the historical snapshot.

The private manifest contains clean/corrupted snapshot IDs and hashes,
configuration/profile, all eligible history units, target count, selection
digest/rank, complete historical/later/corrupted records, reversible mutation,
and stable fault ID. Validation recomputes the severity profile, history-unit
and revision IDs, source-declared lineage, relative size, full ranking,
modified-record ID, mutation, fault ID, and manifest ID. Private source rows
and revision IDs never cross the audit boundary.

## Public detector rule

The detector proves the public temporal contradiction only when a visible
audit record has non-null accession provenance and:

```text
available_on <= audit_as_of_date < filed_on
and available_on < filed_on
```

One deterministic high-severity, `proven_by_contract` finding is emitted per
such record under `revision.later_vintage_in_earlier_state`. Evidence contains
the affected record ID, exact public economic key, observed value,
availability/filing/audit dates, accession, form, source name/locator, and a
canonical hash over that public provenance. It intentionally contains no
historical record, later reference, lineage marker, source row key, or derived
revision ID.

This structural detector can also observe a valid Look-Ahead-style temporal
contradiction on the same record. That cross-detector signal remains visible;
it is not relabeled or suppressed to improve Revision Overwrite precision. The
detector does not claim to infer a full restatement history from the sanitized
record alone.

## Exact matching and metrics

A Revision Overwrite finding matches one manifest entry only when all public
fields are exact: valid finding identity; detector ID/version; fault
type/subtype; rule; one corrupted record ID; fixed severity/confidence;
economic key; observed value; availability/filing/audit dates; accession;
form; source name/locator; and public provenance hash. A wrong class, rule,
record, accession, date, source, value, evidence field, additional affected
record, or finding identity is not a match.

Source-row and revision-ID truth is deliberately private, so a conflict in
that relationship is rejected by manifest integrity validation rather than
being fabricated as detector-visible evidence. Matching is one-to-one:
identical duplicate findings add false positives without increasing recall;
distinct competing candidates remain ambiguous; misses remain false negative
faults. A valid Look-Ahead finding is an unmatched Revision Overwrite false
positive under primary scoring.

The false-positive denominator is every eligible clean revision-history unit,
including selected units:

```text
eligible_clean_denominator = eligible_unit_count
```

Precision is null with no findings; recall is null with no injected faults;
F1 is null when either is null (otherwise the exact Decimal harmonic mean);
and false-positive rate is null when the denominator is zero.

## Manifest-assisted exact replay

`manifest_assisted_exact_revision_overwrite_replay` is private answer-key
replay, not automatic or detector-only remediation. It validates the manifest
and exact corrupted artifact, replaces only exact corrupted occurrences with
their stored historical records, preserves unrelated records and the
legitimate later source history, and is idempotent for the exact clean
artifact. The repaired snapshot must reproduce the clean canonical bytes,
snapshot ID, and SHA-256 hash exactly.

## Controlled frozen-vintage growth impact

An earlier historical snapshot cannot honestly contain an unavailable future
comparison period. `build_frozen_vintage_growth_snapshot` therefore freezes
each clean/corrupted/repaired historical state unchanged, independently builds
the full clean source history at the later `research_as_of_date`, and adds only
the configured current-period records identically to all three branches. It
never changes the detector input or silently substitutes a later revision into
the frozen prior state.

`growth_ranking_v0_1` then applies the same pure calculation to each research
snapshot. It uses one exact configured duration context and prior/current
period pair, excludes an entity with a zero prior value, rejects ambiguous
same-entity/period observations, and calculates:

```text
growth = (current_value - prior_value) / abs(prior_value)
```

Results sort by descending Decimal growth with entity-ID tie breaks. The impact
records changed entities, maximum absolute growth change, ranking/top-membership
changes, and exact repaired-to-clean restoration. It is a controlled research
sensitivity demonstration only—not a statement reconstruction, backtest,
trading result, alpha, Sharpe, return, or financial-loss claim.

## Known limitations

Revision Overwrite v0.1 supports only explicit adjacent source-supported
histories with clean filing-date availability, unchanged controlled context,
distinct non-null accessions, and nonzero historical values. It does not infer
restatements, interpret amendments, reconstruct statements, resolve vendors,
or perform detector-only repair. The public detector establishes a narrow
temporal contradiction, while private manifest validation establishes the full
revision relationship used for injection and exact replay.
