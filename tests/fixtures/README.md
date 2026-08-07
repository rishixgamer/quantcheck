# Reviewed fixture

`reviewed_financial_facts.json` is a **synthetic, public, offline, manually
reviewed** fixture of 26 `FinancialFact` records. It is fully invented data —
three fictitious entities (`CIK0000000001`–`CIK0000000003`), synthetic
accession numbers, and made-up values. It does not describe any real company,
and no historical QuantCheck fixture bytes are reproduced or claimed.

## Regeneration and verification

The fixture is produced entirely by
`quantcheck.fixtures.canonical_reviewed_fixture_bytes`, a pure function with
no filesystem, clock, or randomness dependency. Regenerate or verify it with:

```bash
uv run python scripts/generate_reviewed_fixture.py            # write
uv run python scripts/generate_reviewed_fixture.py --check    # verify only, exits nonzero on drift
```

`--check` exits nonzero if the checked-in file's bytes differ from freshly
regenerated canonical bytes. This is enforced by `tests/test_fixtures.py`.

## What the fixture covers

- **3 entities** (`CIK0000000001`, `CIK0000000002`, `CIK0000000003`).
- **4 concepts**: `Revenues`, `NetIncomeLoss` (duration), `Assets` (instant),
  `EarningsPerShareDiluted` (duration).
- **2 quarterly periods** (2024 Q1, Q2) and **2 units** (`USD`, `USD/shares`).
- **Two source-supported revision histories**: entity 1's Q1 `Revenues` has
  three revisions (a preliminary 10-Q figure, a 10-Q/A restatement, and a
  10-K/A restatement); entity 2's Q1 `NetIncomeLoss` has two. Each revision
  is a distinct record with its own `record_id`; the lineage and sequence
  are declared explicitly in the record's `source_row_key` (see
  `quantcheck.point_in_time.parse_declared_revision_lineage`) — never
  inferred from matching entity/concept/period/unit alone.
- **An independent-occurrence / duplicate-candidate pair**: entity 3's Q1
  `Assets` appears as two separate records with identical economic content
  but distinct `record_id`s and no declared lineage between them — a case a
  later deduplication milestone must recognize without treating them as
  revisions of one another.
- **A same-business-key, different-economic-identity pair**: entity 1's Q1
  `Assets` appears with and without a `ConsolidationItems` dimension —
  looks similar, is not a duplicate.
- Dimensioned and dimension-free facts, one duration fact with two
  dimensions, same-day `filed_on == available_on` cases throughout, and two
  legitimate "hard negative" observations (a loss quarter with a negative
  `NetIncomeLoss`, and a `0.00` diluted EPS) that a naive detector should not
  treat as corruption.

## Seed

The checked-in copy uses `quantcheck.fixtures.DEFAULT_FIXTURE_SEED` (`0`).
The seed only ever changes one documented field — entity 1's `entity_name`
("Aster Analytics Corp" vs. "Aster Analytics Corporation") — so that
different-seed variation is deterministic, small, and does not depend on
`random`.
