# QuantCheck v0.2 benchmark corpus

The authoritative description of the v0.2 **data substrate**. It replaces the
v0.1 fixture as the clean source population; it changes no detector, no
threshold, no matching rule, and no v0.1 result.

> **v0.1.0 is untouched.** Not one frozen source file, release document, hash,
> threshold, or scientific claim changed. `CHECKSUMS.md` still verifies over its
> 88 files, `release_freeze.json` still verifies, and candidate
> `relc_2c6e945a71b85b39` / benchmark `bench_403a85e506ff66ea` / aggregate
> `agg_571aae0b7c60a4a5` remain exactly as tagged. See
> `tests/test_corpus_v01_isolation.py`.

## Why

The v0.1 held-out run exposed two measurement problems, both preserved rather
than tuned away:

1. **Three profile/severity cells had no eligible target at all.** The 26-record
   reviewed fixture contains no record with a 30-day natural filing lag
   (Look-Ahead `high`) and no source-supported adjacent revision above 2%
   (Revision Overwrite `medium` at 5% and `high` at 20%). Thirty cases failed
   `no_eligible_targets`. Those cells were never measured.
2. **The denominators that did report were thin.** `revision_overwrite`'s
   eligible-clean denominator over the whole 124-case matrix was **11**.

Neither is a detector defect, so neither is fixed by changing a detector. Both
are fixed by supplying data the frozen rules can find something in.

## What changed, in numbers

| | v0.1 | v0.2 |
| --- | --- | --- |
| Clean sources | 1 reviewed fixture (26 records) + 1 series fixture (5) | 12 corpus units, **4,320 records** |
| Partitions | seed partitions only | development / validation / **separately frozen held-out** |
| Issuers | 3 + 1 | 19 per partition, disjoint across partitions |
| Fiscal calendars | 1 (calendar quarters) | 4 fiscal year ends + a 4-4-5 retail calendar |
| Periods | 2 quarters | 8–12 consecutive fiscal quarters per unit |
| Concepts | 4 | 11 synthetic + 6 `us-gaap` in the public unit |
| Units of measure | 2 | USD, EUR, GBP, JPY, four per-share units, shares |
| Filing lags | 9 distinct values, 15–132 days, none in the 0–14 band | 0–90 days generated, 0–215 observed including revisions; every Look-Ahead band populated |
| Revision lineages | 2 (max 2.0% relative) | 56 per revisions unit (max **41.2%**) |
| Declared hard negatives | 2 | 15 per partition, each with a written reason |
| Look-Ahead `high` eligible | **0** | 40 best unit, 86 per partition |
| Revision Overwrite `medium` / `high` eligible | **0** / **0** | 42 / 28 per partition |
| Revision Overwrite `low` denominator | 11 (whole matrix) | 56 per partition |

## The corpus contract

A **corpus** is a versioned, partitioned set of **corpus units**. A unit is one
clean source: a deterministic in-package factory, a declared point-in-time
horizon, a provenance record, and a content hash.

`quantcheck/corpus/v2` — `src/quantcheck/corpus_contract.py`,
`src/quantcheck/corpus_schemas.py`.

### Source classes

| Class | Licence tier | In repository | What it is |
| --- | --- | --- | --- |
| `synthetic_adversarial` | `synthetic_repository` | yes | Wholly invented data from a pure factory. No real issuer is described. |
| `curated_public` | `public_government` | yes | An SEC EDGAR Company Facts envelope read through the frozen adapter. |
| `external_private` | `external_restricted` | **never** | An operator-supplied vendor or customer dataset. Never required. |

### Partitions

Three, declared in the source definition before any detector runs:
`development`, `validation`, `heldout`. Each holds the same four unit roles
built from the same cohort specifications with **disjoint issuers**, so the
partitions are the same experiment on different companies.

### Unit roles

| Role | Purpose |
| --- | --- |
| `broad` | 7 issuers, 4 fiscal calendars, filing lags 12–90 days, 12 quarters. Makes every Look-Ahead severity band eligible — including `high`. |
| `revisions` | 7 issuers with a declared `#r1`/`#r2` lineage on every concept, relative revisions spanning 1.4%–41.2%. Makes Revision Overwrite `medium` and `high` eligible. |
| `stress` | 4 volatile issuers plus the declared hard negatives. |
| `public` | A curated public Company Facts document through the frozen SEC adapter. |

### Point-in-time horizons

Each unit declares its own `snapshot_as_of_date` and `research_as_of_date`.
These are **pre-registered**, part of the unit's identity, and hashed into its
`corpus_unit_id`. The census never searches over them.

| Role | Snapshot as-of | Research as-of |
| --- | --- | --- |
| `broad` | 2024-08-31 | 2024-05-15 |
| `revisions` | 2024-06-30 | 2024-04-15 |
| `stress` | 2024-12-31 | 2024-11-15 |
| `public` | 2024-08-31 | 2024-05-15 |

## Source-selection rules

Nine documented inclusion rules, cited by identifier on every unit and enforced
by schema validation. Full text in `corpus_contract.CORPUS_INCLUSION_RULES`.

| Rule | Summary |
| --- | --- |
| IR-01 | A unit is admitted for a diversity axis declared **before** it is generated. |
| IR-02 | A unit's partition is declared in its source definition and never changed. Reassignment is a new corpus, not an edit. |
| IR-03 | **No unit may be added, removed, resized, or re-parameterised on the basis of observed detector performance.** Corpus changes are justified by eligibility or diversity only. |
| IR-04 | Issuer identities are disjoint across partitions. |
| IR-05 | Detector-visible naming carries no partition information. |
| IR-06 | Every unit is regenerated by a pure in-package factory. No clock, randomness, filesystem layout, or network. |
| IR-07 | Hard negatives are natural but unusual *legitimate* observations, declared individually with the reason each is legitimate. |
| IR-08 | Licensed customer or vendor data is never committed, and no record content from it enters any repository artifact. |
| IR-09 | A curated public unit records whether its bytes are a verbatim saved response. |

IR-03 is the anti-tuning rule and the one that matters most. The held-out
partition's records cannot be materialized without an explicit authorization
(below), so there is no held-out performance to select against even in
principle.

## Licensing and privacy boundaries

**Synthetic data** is wholly invented and carries this repository's licence.
Entity identifiers are ten-digit CIK-shaped values derived from SHA-256 of an
issuer key — they are *not* real registrants.

**The curated public unit is a placeholder, and says so.** It is a curated
field-shape document in the real Company Facts contract, using real `us-gaap`
concept names and real unit and form vocabularies, with **placeholder
registrants and purpose-built values**. No live SEC request has been made and no
saved response is reproduced. This is recorded machine-readably as
`corpus_public.CURATED_PUBLIC_IS_PLACEHOLDER` and as `verbatim_source=False` on
every such unit's provenance, so no artifact can imply a retrieval that did not
happen.

*Substituting genuine bytes* requires replacing `curated_public_envelope` with
the saved response and re-running the freeze. The allowlist, the normalization
path, the contract, the census, and every test stay exactly as they are — which
is the entire point of routing the public source class through the frozen
adapter.

**External private data** is never committed and never required. It is addressed
by a caller-supplied directory or `QUANTCHECK_EXTERNAL_CORPUS_ROOT`; unset is
the supported default. Three properties are structural, not promised:

* an `external_private` unit's `CorpusUnitSpec` is **rejected by schema
  validation** if it carries a `content_hash` or a diversity profile, both of
  which are derived from record content;
* `redacted_external_summary` returns identity, partition, and a record count —
  nothing else;
* the declared SHA-256 is verified against the raw bytes *before* anything is
  parsed, so a drifted file is refused rather than admitted under the wrong
  identity.

The default corpus contains **zero** external units. Every test, gate, and
command in this repository runs offline without one.

## The held-out gate

The same shape as `quantcheck.release_gate`, and the same line — ADR-010's
execution-not-representation split:

* A held-out unit may be **described** freely. Its identifier, partition,
  provenance, horizon, content hash, and eligibility counts are committed
  evidence, and refusing to name them would make the freeze record unreadable by
  the tooling built to report it.
* Its records may not be **materialized** without an authorization covering the
  **complete** held-out partition. A subset authorization is refused.

`corpus_gate.held_out_corpus_units` is a context manager over a `ContextVar`. It
imports nothing from `quantcheck`, reads no environment variable, and is opened
by exactly one file outside the tests: `scripts/corpus_freeze.py`. Static tests
assert all of that.

## The eligible-unit census

`src/quantcheck/corpus_eligibility.py` computes nothing of its own. Every count
is the **frozen v0.1 eligibility computation**, called unchanged:

| Fault profile | Frozen computation | One eligible unit is |
| --- | --- | --- |
| `lookahead_timestamp` | `lookahead_contract.is_eligible_lookahead_target` | an eligible clean record |
| `unit_drift` | `unit_drift_series.build_comparable_observations` | a comparable observation |
| `duplicate_observation` | `duplicate_fingerprint.build_duplicate_groups` (singletons) | a singleton fingerprint group |
| `revision_overwrite` | `revision_overwrite_series.build_revision_history_units` | a revision history unit |

These are the same functions `benchmark_dispatch.eligible_clean_denominator`
already uses for a v0.1 clean control, so **a v0.2 denominator is directly
comparable with a v0.1 one**, not merely similar.

### Adequacy floors

Two numbers, declared in the contract before any evidence existed so they cannot
be chosen afterwards to make a cell pass:

* `MINIMUM_CELL_ELIGIBLE_UNITS = 8` — the *best single unit* in a partition,
  because one benchmark case runs against one clean source.
* `MINIMUM_PARTITION_ELIGIBLE_UNITS = 24` — the partition-wide total, so a
  pooled denominator is not dominated by one unit.

A cell's status is derived arithmetic, never a judgement: `eligible`,
`declared_unsupported` (declared before the freeze), or `insufficient` (a corpus
defect).

### Result: all 36 cells eligible

Identical in all three partitions:

| Fault profile | `low` best / total | `medium` best / total | `high` best / total |
| --- | --- | --- | --- |
| `duplicate_observation` | 596 / 1114 | 596 / 1114 | 596 / 1114 |
| `lookahead_timestamp` | 58 / 115 | 50 / 107 | **40 / 86** |
| `revision_overwrite` | 56 / 56 | **42 / 42** | **28 / 28** |
| `unit_drift` | 532 / 859 | 532 / 859 | 532 / 859 |

The bolded cells are the three v0.1 could not measure at all. Nothing is
`declared_unsupported`; nothing is `insufficient`.

Unit Drift and Duplicate report identical counts across severities because
neither has a severity-dependent *eligibility* rule — a property of the frozen
contracts, asserted by test.

## Partition-isolation (leakage) guarantees

`tests/test_corpus_partition_isolation.py`. Six independent routes closed:

1. **Vocabulary.** Every detector-visible string *value* is either present in
   every partition — shared taxonomy such as `us-gaap`, `Revenues`, `USD`,
   `10-Q` — or present in exactly one and hash-opaque.
2. **Opacity.** Partition-specific values are SHA-256 derived, so no partition
   can be read off one. A cohort code is hexadecimal and every partition token
   contains a non-hex character, so the property is structural.
3. **Structure.** `AuditInputRecord` has no partition, corpus, or unit field, it
   drops `source_row_key`, and `run_all_detectors` has no corpus parameter.
4. **Identity.** Entity ids, record ids, and source locators are disjoint across
   partitions.
5. **Imports.** No detector module mentions the corpus layer.
6. **Construction.** `check_detector_visible_naming` refuses a unit whose
   `source_name`, `source_locator`, or `audit_dataset_name` carries a partition
   token, so the property cannot be lost in a rename.

Deliberately **not** a substring search for "development": the real `us-gaap`
concept `ResearchAndDevelopmentExpense` contains it, appears identically in all
three partitions, and carries no partition information. Renaming a real taxonomy
concept to satisfy a naive test would be tuning data to a test.

## Hard negatives

Ten documented kinds; 15 per partition. Each is a *legitimate* observation, and
several are expected to produce findings — that is what they are for. Measuring
what the frozen rules cost on realistic data beats hiding it.

| Kind | Why it is legitimate |
| --- | --- |
| `legitimate_independent_duplicate` | Two independent source occurrences with no declared lineage. A real feed emits these. |
| `consolidation_dimension_lookalike` | Same business key, distinguished only by a `ConsolidationItems` dimension. |
| `genuine_recovery_from_near_zero` | A real collapse-and-recovery quarter whose local ratio exceeds the frozen 50× threshold. |
| `genuine_loss_quarter` | A negative value is not a corruption. |
| `genuine_zero_value` | A real quarter with no spend. |
| `delayed_vendor_availability` | Filed publicly before it reached the subscriber. `available_on` after `filed_on` is legitimate. |
| `identical_value_restatement` | A refiling that corrected a footnote and left the number alone. |
| `fiscal_year_change_stub_period` | A 45-day stub from a calendar change; its own comparable series. |
| `share_split_adjusted_step` | A real ten-for-one split — an order of magnitude, well inside the 50× threshold. |
| `same_day_filing_and_period_end` | A zero filing lag, below every Look-Ahead band. |

## Commands

```bash
# Development + validation census. Needs no authorization; run this while
# developing the corpus, so the held-out partition stays untouched.
uv run python scripts/corpus_freeze.py --census

# Verify the committed freeze record (rebuilds, so it opens the held-out gate).
uv run python scripts/corpus_freeze.py --check

# Rewrite it. A deliberate act: it re-freezes the held-out partition.
uv run python scripts/corpus_freeze.py --write

# The corpus test suite.
uv run pytest tests/test_corpus_*.py

# v0.1 is unaffected.
uv run python scripts/release_checksums.py --check
```

## The frozen record

`corpus_freeze_v0_2.json`, 63,051 bytes,
SHA-256 `ab8dde4dce9e7db650b88da0ec0f1209c465efdef1b1a2a8d0e71bebc9ea3caa`.

| | |
| --- | --- |
| Freeze | `cfrz_040ae8f12d864289` |
| Corpus | `corp_a55d14a60c2f89d6` |
| Census | `cens_4512c0c8f3fdb747` |

It commits every unit's hash, diversity, and exact eligible-unit denominators
across all three partitions — and **no record content**: no `records`, no
`record_id`, no `source_row_key`. It is evidence about a dataset, not a copy of
one. Reading it needs no authorization; rebuilding it does.

Deliberately outside `CHECKSUMS.md`, which covers the immutable v0.1 release
surface only.

## Limitations

* **The corpus freeze is a substrate record, not benchmark result evidence.**
  The additive `quantcheck/benchmark/v2` contract can now run development and
  validation units, but no aggregate benchmark result or v0.2 release candidate
  is frozen here. `BenchmarkFixtureId` and `benchmark_fixtures.py` remain frozen
  v0.1 modules; v0.2 names corpus units through its own versioned config.
* **Only development test cases have exercised detector execution so far.** No
  full development or validation rehearsal has been saved, and no held-out
  corpus unit has been materialized for performance evaluation. The census
  itself still measures clean-data eligibility only.
* **The curated public unit is a placeholder.** Real public bytes have not been
  retrieved. Current SEC guidance must be rechecked before any live run.
* **The `curated_public` unit cannot support Revision Overwrite.** A Company
  Facts response carries no declared lineage marker, so the source class
  structurally cannot express a revision history. Declared, not worked around.
* **Zero external units exist.** The `external_private` class is implemented and
  tested against synthetic external roots under `tmp_path`; no real vendor
  dataset has been exercised.
* **Partitions are structurally symmetric by construction** — same cohort
  specifications, different issuers. That makes results comparable, but it also
  means the held-out partition is not an independent sample of the world; it is
  an independent sample of the same generator.
* **The corpus is still predominantly synthetic.** 4,104 of 4,320 records are
  `synthetic_adversarial` and 216 are the curated public placeholder. External validity is improved along every declared
  axis, but this is not a real vendor feed.
* **`FinancialFact` is unchanged.** Every axis the corpus needed was already
  representable, so no versioned contract change was justified. See ADR-V2-001.
