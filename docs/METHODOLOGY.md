# QuantCheck methodology and trust boundaries

## What the framework does

QuantCheck builds a point-in-time financial snapshot, injects one controlled
defect into it, hides the truth of that injection in a private manifest,
sanitises the corrupted data, runs manifest-blind detectors over it, and only
then scores the finalised findings against the manifest. It separately measures
whether a controlled research output changed, and whether manifest-assisted
exact replay restores the clean result.

## Architecture and trust boundaries

```
reviewed fixture (clean)
        │
        ▼
build_dataset_snapshot ──────────────► DatasetSnapshot (clean)
        │                                     │
        │ injector (seed, severity)           │  ┌─ TRUST BOUNDARY ─┐
        ▼                                     ▼  │                   │
DatasetSnapshot (corrupted) + FaultManifest ─────┤ sanitize_for_audit │
        │                    (PRIVATE)            │                   │
        │                                         ▼                   │
        │                             AuditInputSnapshot (PUBLIC)     │
        │                                         │                   │
        │                                 four detectors              │
        │                                         │                   │
        │                              finalised AuditReport          │
        │                                         │                   │
        └────────── after finalisation only ──────┤                   │
                                                  ▼                   │
                              matcher · scorer · replay · research    │
                                                  └───────────────────┘
```

Three boundaries are enforced by control flow, not by convention:

1. **Detectors never receive the manifest.** No detector function has a
   `manifest`, `clean_snapshot`, `seed`, `severity`, or `targets` parameter.
   `run_all_detectors(audit_input, detector_configs)` has no manifest channel at
   all, so the isolation holds at the signature level.
2. **Scoring happens only after the audit report is finalised.**
   `dispatch_benchmark_case` produces the combined report before any manifest
   is loaded. The ordering is structural.
3. **Public artifacts cannot address private storage.** A public artifact
   reference is a validated relative POSIX path whose grammar cannot express
   `..`, a leading `/`, a backslash, or `~`, and which rejects `private` as a
   segment. Public and private use separately rooted stores.

## Point-in-time semantics

* A record becomes visible when `available_on <= as_of_date`. Selection is
  end-of-day at day granularity.
* `period_end`, `filed_on`, `available_on`, `as_of_date`, and runtime dates are
  five distinct concepts and are never conflated.
* Revision membership is **declared**, never inferred: a record joins a lineage
  through a `"<lineage_id>#r<sequence>"` marker inside its own
  `SourceReference.source_row_key`. Two records sharing entity, concept, period,
  unit, and dimensions but carrying no marker are independent occurrences —
  including legitimate duplicates.
* Selection takes the highest declared `sequence` whose `available_on <=
  as_of_date`, and separately requires `available_on` and `filed_on` to be
  non-decreasing in declared-sequence order. A history is never accepted on
  sequence alone or on dates alone; disagreement raises
  `AmbiguousRevisionHistoryError`.
* Because `AuditInputRecord` never carries `source_row_key`, the lineage marker —
  and with it the whole revision answer key — cannot cross the audit boundary
  even by accident.

## Scoring methodology

* **Exact one-to-one matching.** A finding matches a fault only by exact
  identity: modified record id for Look-Ahead, Unit Drift, and Revision
  Overwrite; exact fingerprint group for Duplicate Observations. There is no
  fuzzy, positional, or proximity matching.
* **Strict primary-label scoring.** All four detectors run on every case, and
  every finding is retained. A case is scored against its own fault family only,
  so a correct finding from another family counts as a false positive. This
  depresses precision deliberately and is never suppressed.
* **A wrong-class finding is never a true positive**, and duplicate identical
  findings cannot inflate recall. `true_positive_findings == true_positive_faults`
  is asserted by schema validator and by test.
* **False-positive denominators are per-family and explicit**: eligible clean
  record count (Look-Ahead), all comparable observation count (Unit Drift),
  eligible record count (Duplicate), eligible revision unit count (Revision
  Overwrite). Each is computed by the *same* frozen eligibility function the
  injector uses, so a control's denominator is directly comparable to its fault
  sibling's.
* **Micro-summing, never macro-averaging.** Counts are summed across cases and
  metrics computed once from the sums. A test computes the macro-average and
  asserts it differs, so switching would fail.
* **Null conventions.** Precision is `TP / findings`; with no findings it is `1`
  for a successful fault-free group and null for a fault-bearing group. Recall
  is null with no injected faults. F1 is null whenever precision or recall is
  null. False-positive rate is null with no eligible-clean denominator. Failed
  and incomplete cases stay in status totals and leave pooled metrics alone.
* **Metrics are exact `Decimal` end to end.** Nothing passes through binary
  float, and an undefined metric stays `None` — never `0`, `NaN`, or `"n/a"`.
  Only rendered text says `n/a`.

## Research-impact methodology

Each family has one narrow controlled comparison, run over clean, corrupted, and
manifest-assisted repaired states of the same configured context:

| Family | Method | What it compares |
| --- | --- | --- |
| Look-Ahead | `availability_count_v0_1` | occurrences visible at an explicit research cutoff |
| Unit Drift | `aggregate_value_v0_1` | sum of visible occurrences in one exact group |
| Duplicate | `record_count_v0_1` | occurrence count, plus aggregate double-counting |
| Revision Overwrite | `growth_ranking_v0_1` | frozen-vintage two-period growth ranking |

These are sensitivity demonstrations, not backtests. Public research summaries
expose only the method, whether the output changed, and whether exact replay
restored it — never the counts or deltas, because a Look-Ahead availability
delta or a Duplicate record-count delta *is* the injected target count.

## Fault catalogue

Each family has its own frozen contract document:

* [Look-Ahead Timestamp](faults/LOOK_AHEAD.md) — `period_end_substitution`
* [Unit Drift](faults/UNIT_DRIFT.md) — `value_scaled_unit_unchanged`
* [Duplicate Observations](faults/DUPLICATE_OBSERVATIONS.md) — `exact_occurrence_copy`
* [Revision Overwrite](faults/REVISION_OVERWRITE.md) — `later_vintage_in_earlier_state`

Severity is a per-family numeric definition, frozen in the release candidate:

| Family | `low` | `medium` | `high` |
| --- | --- | --- | --- |
| Look-Ahead | 2% targets, ≥7-day lag | 5%, ≥14-day | 10%, ≥30-day |
| Unit Drift | 2% targets, ×100 | 5%, ×1000 | 10%, ×1000000 |
| Duplicate | 1% targets | 5% | 15% |
| Revision Overwrite | 2% targets, ≥1% revision | 5%, ≥5% | 10%, ≥20% |

## Determinism

The same clean snapshot, configuration, seed, and code version always produce
the same logical corruption and the same artifact bytes. Identifiers and hashes
never depend on DataFrame row position or Python hash randomisation; output
root, working directory, temporary directory, clock, username, hostname, and
`PYTHONHASHSEED` are excluded from every logical identity and live only in
`RuntimeMetadata`. See [REPRODUCIBILITY.md](REPRODUCIBILITY.md).
