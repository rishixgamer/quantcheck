# Duplicate Observations fault contract

This is the current authoritative contract for Recovery Phase 6. It defines
only:

```text
fault_type: duplicate_observation
fault_subtype: exact_occurrence_copy
primary rule: occurrence.exact_duplicate
specification: quantcheck/duplicate-exact-occurrence-copy/v1
```

The historical release says this subtype copied an exact source occurrence,
used SHA-256 target ranking, 1%/5%/15% severity fractions, one created copy
per fault, exact fingerprint-group scoring, and manifest-assisted replay. Its
source and original fault document did not survive. The missing rebuilt-v1
choices are recorded in ADR-004 (`docs/DECISIONS.md`); no historical
identifier, artifact byte sequence, fixture eligibility count, or benchmark
result is claimed.

## Roles and trust boundary

- Injection accepts an identity-valid clean `DatasetSnapshot` plus a strict
  `DuplicateInjectionConfig`.
- It returns a separate corrupted snapshot (with created copies appended,
  never replacing anything) and a private `DuplicateManifest`.
- `sanitize_for_audit` projects the corrupted snapshot into an
  `AuditInputSnapshot`.
- `detect_duplicate_observations` accepts only that sanitized snapshot. There
  is no detector configuration: exact fingerprint matching has no free
  parameter to tune. The detector receives no manifest, clean value, seed,
  severity, target fraction/count, selected IDs, rank, copy ordinal, or
  repair/scoring input.
- `score_duplicate_observations` receives an already finalized immutable
  `AuditReport` and the private manifest. It never runs detection.

No Duplicate stage mutates caller-owned models or collections.

## The exact fingerprint

`DuplicateFingerprint` is the one canonical representation shared by
injection eligibility and detection. Its fields are exactly:

- `entity_id`;
- `concept_namespace`, `concept`;
- `value` (canonical `Decimal` — numerically, not textually, compared);
- `unit`;
- `dimensions` (canonical axis/member tuple);
- `period_type`, `period_start`, `period_end`;
- `filed_on`, `available_on`;
- `accession_number`;
- `source_name`, `source_locator`.

`record_id` is deliberately excluded: a generated copy's record identity must
never prevent it from grouping with its source occurrence. `form` and
`entity_name` are deliberately excluded: `form` is a non-semantic label, and
`entity_name` never crosses the `AuditInputRecord` boundary at all. No
"revision" or private source-row-key field participates, because
`AuditInputRecord` has no such field (Milestone 2's audit boundary drops
`source_row_key` on purpose) — a fingerprint the detector cannot compute
would make injection eligibility diverge from what the detector can actually
prove. `source_name`/`source_locator` are the public stand-in for "source
row" identity at the sanitized boundary.

`duplicate_fingerprint_hash` hashes one canonical fingerprint through the
dedicated `quantcheck/duplicate-fingerprint/v1` namespace, never through
ad-hoc string concatenation.

**Detector visibility and injector eligibility are the same computation.**
Because the fingerprint is built from `AuditInputRecord`-visible fields only,
two clean source occurrences that already agree on every one of those fields
are indistinguishable to the detector — even before any fault is injected.
The checked-in reviewed fixture contains exactly this case (entity 3's Q1
`Assets`, declared as an independent-occurrence pair in Milestone 2): the
detector legitimately proves it as one exact group with zero faults
injected. This is intentional, not a defect: the milestone's own scope note
says "the detector may still observe naturally occurring exact groups when
the public contract requires that behavior; injection eligibility and
detector visibility are separate concepts." Injection simply never selects a
record that is already in such a group as a source.

## Eligibility

The clean snapshot must have a valid content-derived identity, and every
contained record must satisfy `available_on <= snapshot.as_of_date`. Records
are grouped by exact fingerprint hash over the same `available_on <= as_of_date`
visibility rule. A record is eligible exactly when its fingerprint group has
size exactly one (a singleton). A record already sharing its fingerprint with
another clean record — whether a legitimate independent occurrence or an
already-duplicated group — is never an injection target. If there are no
eligible records, injection raises `NoEligibleDuplicateTargetsError`.

## Severity, target count, and selection

Severity profiles are fixed:

| Severity | Target fraction |
| --- | ---: |
| low | `0.01` |
| medium | `0.05` |
| high | `0.15` |

```text
target_count = min(
    eligible_count,
    max_targets,
    max(1, ceil(eligible_count * target_fraction)),
)
```

The ceiling is computed with `Decimal`, never binary float. `max_targets` is a
strict positive configuration value and defaults to 100.

Each eligible record receives this full SHA-256 selection digest:

```text
sha256(canonical_json({
  "namespace": "quantcheck/duplicate-target-selection/v1",
  "spec_version": "quantcheck/duplicate-exact-occurrence-copy/v1",
  "seed": <non-negative integer>,
  "eligibility_unit_id": <stable clean record_id>
}))
```

Records rank by `(selection_digest, record_id)`. Selected order is zero-based
and recorded privately as `target_rank`.

## Injection behavior

For each selected source occurrence, exactly one semantic copy is created and
**appended** to the snapshot — the original is preserved unchanged and
nothing is replaced. The created record is identical to the original in
every `FinancialFact` field except `record_id`. The created record's ID uses
the dedicated `quantcheck/duplicate-created-record/v1` namespace over
`(original_record_id, spec_version, copy_ordinal)`, but keeps the ordinary
`rec_` prefix: a visible role-specific prefix would leak an injected-row flag
across the audit boundary. `copy_ordinal` is fixed at `1` — v0.1 creates one
copy per fault only.

## Private manifest

The manifest records clean/corrupted snapshot IDs and hashes, configuration,
the full eligible record-ID set, target count, and one entry per selected
fault. Each entry contains the selection digest/rank, the exact fingerprint
hash, stable fault identity, complete original and created records, and the
exact reversible copy relationship (`DuplicateMutation`). Manifest roles are
unambiguous by construction for this narrow subtype: one original, one
created, group size two, zero removed, zero reference — there is no
fabricated "removed" or "reference" role because exact-occurrence-copy
injection never removes or references anything.

None of the following appears in the sanitized audit input: original record,
created record, manifest role, selection digest/rank, eligible/selected sets,
seed, severity, target fraction/count, cap, copy ordinal, or expected finding
count.

## Public detection rule

Rule `occurrence.exact_duplicate` groups visible audit records by the exact
fingerprint hash. One finding is emitted per group with size two or more —
not one finding per row. Public evidence contains the sorted affected record
IDs, the fingerprint hash, group size, and the shared fingerprint fields
(entity, concept namespace/concept, canonical value, unit, dimensions, period
shape/dates, filing/availability dates, accession, source name/locator).
Confidence is `proven_by_contract`, because exact fingerprint equality is a
structural proof, not a statistical inference. **Public finding severity is
fixed at `medium`** (see ADR-004): the fault specification assigns no
severity-bearing signal to a duplicate finding the way Look-Ahead has leaked
days or Unit Drift has a scale factor, so severity cannot be derived from
public evidence.

The detector proves only that a set of sanitized occurrences satisfies the
exact duplicate contract. It never proves which member is the injected copy
— that source/created relationship exists only in the private manifest.

## Exact matching and metrics

A finding matches a manifest entry only when detector identity/version, fault
class/subtype, rule, the exact two-record affected-ID group
(`{original.record_id, created.record_id}`), fixed severity, confidence,
every public fingerprint evidence field, and the finding's stable identity
all match exactly. Near matches (wrong class/rule, wrong group membership,
wrong fingerprint hash, wrong confidence/severity) remain false-positive
findings. Missed entries remain false-negative faults. Matching is
one-to-one: an identical repeated finding yields one accepted match and
additional duplicate false positives; distinct findings competing for one
entry are ambiguous and do not count as true positives. **Duplicate findings
cannot increase recall.**

The false-positive denominator is:

```text
eligible_clean_denominator = eligible_record_count
```

This is every clean record belonging to a singleton fingerprint group at the
snapshot cutoff, **including selected targets** — the same convention Unit
Drift uses, not Look-Ahead's eligible-minus-target convention (see ADR-004
for why).

Metric conventions:

- precision is null when there are no findings;
- recall is null when there are no injected faults;
- F1 is null when precision or recall is null, and zero when both defined
  inputs sum to zero;
- false-positive rate is null when the eligible clean denominator is zero.

All defined ratios use `Decimal`.

## Manifest-assisted exact replay

`manifest_assisted_exact_duplicate_replay` is private answer-key replay. It
validates manifest identity, configuration, SHA-256 selection, fingerprint
hashes, created-record identity, fault identity, and the exact
corrupted-snapshot identity/hash before **removing** exactly the injected
created records — never replacing anything, since nothing was replaced by
injection. It preserves every original occurrence and every legitimate clean
duplicate group (including naturally occurring ones), creates a new snapshot,
is idempotent for an already restored snapshot, and must reproduce the clean
snapshot ID and hash exactly. It is not detector-only or automatic
remediation.

## Controlled research impact

`record_count_v0_1` applies exactly:

```text
total_record_count = len(snapshot.records)
duplicate_group_count = count(fingerprint groups with size >= 2)
```

to one supplied snapshot, and `compare_duplicate_record_count` applies the
identical pure calculation to clean, corrupted, and repaired snapshots. This
is a controlled total-occurrence/duplicate-group count, not a trading, alpha,
return, Sharpe, or financial-loss claim.

Alongside it, the existing `aggregate_value_v0_1` /
`compare_unit_drift_research` pure functions (unchanged, from
`quantcheck.unit_drift_research`) are reused directly to demonstrate
double-counting: because an injected copy shares its original's
`ComparableSeriesKey`, summing one exact configured group over the corrupted
snapshot double-counts the copied value, and exact replay restores the clean
sum exactly.
