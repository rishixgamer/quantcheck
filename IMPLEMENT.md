# Implementation status

This is the operational handoff between Claude Code sessions. Keep it concise, factual, and current.

## Current phase

**Milestone 2 complete — Deterministic fixtures and point-in-time engine**

The original source repository was lost. Historical 0.1.0 documentation survives under `reference/`, but no historical implementation claim is considered current until rebuilt and verified. Milestone 0 rebuilt the reproducible repository foundation. Milestone 1 added the deterministic contract layer: strict JSON value types, immutable Pydantic v2 schemas, one canonical serialization path, SHA-256 hashing, and stable identifiers. Milestone 2 adds the deterministic, manually reviewed 26-record synthetic fixture; explicit, source-declared revision-lineage ordering; end-of-day point-in-time snapshot construction (`build_dataset_snapshot`); and the `sanitize_for_audit` trust-boundary conversion to `AuditInputSnapshot`. It contains no fault injection, detectors, manifests, scoring, SEC access, or benchmark logic.

## Milestone 0 verification

Files added:

- `pyproject.toml` — package metadata (`quantcheck`, `0.1.0.dev0`, `requires-python = ">=3.12,<3.13"`), Hatchling build backend, `dev` dependency group (Ruff, MyPy, pytest, Hypothesis), Ruff/MyPy/pytest configuration, `quantcheck = "quantcheck.cli:main"` console script, and an sdist exclude for `.claude`/`.serena` local tool config.
- `uv.lock` — generated lockfile.
- `.python-version` — pins `3.12`.
- `src/quantcheck/__init__.py` — package marker exposing `__version__`; no financial behavior.
- `src/quantcheck/cli.py` — stdlib `argparse`-based entry point supporting only `--help`/`--version`; no subcommands.
- `tests/__init__.py`, `tests/test_package.py`, `tests/test_cli.py` — smoke tests for package import and CLI help/version behavior (in-process and via `python -m`).
- `.github/workflows/ci.yml` — GitHub Actions workflow running `uv sync --frozen --all-groups`, `uv lock --check`, Ruff check/format, MyPy, pytest, `quantcheck --help`, and `uv build`.
- `.gitignore` — standard Python/uv/tooling ignores.
- `README.md` — added "Current implementation status" and "Development setup" sections (existing recovery-harness explanation preserved).

Commands run and outcomes (Python 3.12.13 via `uv python install 3.12`, `uv` 0.12.2, default writable `~/.cache/uv`, no environment workaround needed):

- `uv sync --all-groups`: passed; generated `uv.lock`.
- `uv sync --frozen --all-groups`: passed.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed (5 files).
- `uv run mypy src tests`: passed, strict mode, no issues in 5 source files.
- `uv run pytest`: passed, 4 tests, Hypothesis plugin loaded (not yet exercised by a property-based test — none is needed until financial logic exists).
- `uv lock --check`: passed.
- `uv run quantcheck --help`: exited 0 with usage text.
- `uv build --offline`: passed; built wheel and sdist. Wheel contains only `quantcheck/` package files and dist-info. Sdist initially included `.claude/` and `.serena/` local tool config; added a Hatchling sdist exclude at the time, but the sdist was **not** fully clean (see packaging correction below).

No environmental retries were needed.

## Packaging correction (post-Milestone-0 audit)

A follow-up audit found that after the `.claude`/`.serena` exclude fix, the sdist still bundled
the entire recovery harness: `reference/`, `prompts/`, `docs/`, `AGENTS.md`, `PROJECT_SCOPE.md`,
`MVP_ACCEPTANCE_CRITERIA.md`, `START_HERE.txt`, `RECOVERY_SEQUENCE.md`, and `IMPLEMENT.md`. The
wheel's long description also inherited the harness README's "rebuild harness" framing rather
than describing the actual package. Corrected by:

- Replacing the sdist `exclude`-only rule in `pyproject.toml` with an explicit `include`
  allowlist (`src/`, `tests/`, `pyproject.toml`, `uv.lock`, `README.md`, `.python-version`,
  `.gitignore`) plus a defensive `exclude` list covering the recovery/reference files, local
  tool directories (`.claude`, `.serena`, `.venv`), `dist/`, and caches/bytecode.
- Rewriting `README.md` to describe the bootstrapped `quantcheck` repository directly (Milestone
  0 complete, what is not yet implemented, development setup, repository layout) instead of the
  "recovery harness" copy/paste instructions. `reference/` remains and is described as historical
  evidence only.
- Adding `.serena/` to `.gitignore` (directory left in place, only untracked from Git).

Rebuilt wheel and sdist after the fix; both verified clean of `.claude`, `.serena`, `reference/`,
recovery prompts/documents, local paths, secrets, caches, and generated environments.

## Milestone 1 verification

### Files added

- `src/quantcheck/json_types.py` — the `JsonValue` domain alias, `CanonicalizationError`, and the
  exact scalar encodings/parsers for `Decimal`, `date`, and UTC `datetime`. Standard library only.
- `src/quantcheck/schemas.py` — `CanonicalModel` base (frozen, `extra="forbid"`, `strict=True`)
  plus `SourceReference`, `Dimension`, `FinancialFact`, `AuditInputRecord`, `DatasetSnapshot`,
  `AuditInputSnapshot`, `CaseConfig`, `RuntimeMetadata`, `ArtifactIdentity`.
- `src/quantcheck/serialization.py` — the single canonical path: `to_canonical_json`,
  `canonical_json_text`, `canonical_json_bytes`, `parse_canonical_json`.
- `src/quantcheck/hashing.py` — `sha256_hex_of_bytes`, `canonical_sha256`, `stable_id`, the four
  assigned identifier helpers, three identity verifiers, and `build_artifact_identity`.
- `docs/SERIALIZATION_AND_HASHING.md` — the current prose contract (see conflict note below).
- `tests/support.py`, `tests/test_schemas.py`, `tests/test_serialization.py`,
  `tests/test_json_types.py`, `tests/test_round_trip.py`, `tests/test_hashing.py`,
  `tests/test_golden_vectors.py`, `tests/test_properties.py`,
  `tests/test_determinism_subprocess.py`.

### Files changed

- `src/quantcheck/__init__.py` — public exports for the contract layer; version unchanged.
- `pyproject.toml` — added the planned runtime dependency `pydantic>=2,<3`. Nothing else changed.
- `uv.lock` — regenerated via `uv`. Added `pydantic 2.13.4`, `pydantic-core 2.46.4`,
  `annotated-types 0.8.0`, `typing-inspection 0.4.2`. No existing package was upgraded or removed.

### Schema inventory conflict (resolved)

The previous "exact next task" listed `FaultManifest`, `FaultManifestEntry`, `Finding`,
`AuditReport`, `ScoreReport`, and `DamageReport` alongside the contract-layer models. That list was
copied from the *design-time* plan in `reference/DEVELOPMENT_MILESTONES.txt` ("Milestone 2: Define
canonical domain schemas"). The historical implementation log
(`reference/IMPLEMENT_RELEASE_0.1.0.md`) shows those artifact models were actually added in
historical Milestone 3, not Milestone 1. They are omitted here because they encode fault, scoring,
and detection semantics that this milestone must not invent. Only the contract layer is
implemented.

### Serialization contract is defined, not recovered

`reference/AGENTS_ORIGINAL.md` invariant 8 points at `docs/SERIALIZATION_AND_HASHING.md`. **That
file did not survive** — no copy exists under `reference/`. Surviving documents state only that
Decimal is serialized as a JSON string and hashes are SHA-256. All finer rules (exponent form,
negative zero, key ordering, identifier prefixes, digest truncation) are therefore **defined for
the rebuild** in the new `docs/SERIALIZATION_AND_HASHING.md`.

**No historical hash or identifier is reproduced or claimed.** The release digests in
`reference/README_RELEASE_0.1.0.md` cannot be reconstructed because their payloads and
serialization rules are lost. The golden vectors in `tests/test_golden_vectors.py` freeze the
rebuilt contract only.

### Decimal scale correction

An initial draft preserved a `Decimal`'s declared scale, so `Decimal("1.50")` encoded as `"1.50"`.
A test caught the resulting inconsistency: Python's `Decimal` equality is numeric, so
`Decimal("1.50") == Decimal("1.5")` and the two models compared **equal while hashing
differently**. That would also make the same economic fact filed as `1234567` and later as
`1234567.00` look like two distinct facts to duplicate and revision analysis. The contract now
normalizes the exponent, so numerically equal values always produce identical bytes. Callers
needing a source's declared precision must carry it as separate explicit metadata.

### Commands run

Each run individually, all exit 0:

- `uv sync --all-groups`: passed; resolved 19 packages.
- `uv sync --frozen --all-groups`: passed; checked 18 packages.
- `uv run ruff check .`: passed, "All checks passed!".
- `uv run ruff format --check .`: passed, 18 files already formatted.
- `uv run mypy src tests`: passed, strict, no issues in 18 source files.
- `uv run pytest`: passed, **299 tests**, Hypothesis plugin loaded, no warnings.
- `uv lock --check`: passed.
- `uv run quantcheck --help`: exited 0 with usage text (Milestone 0 CLI unchanged).
- `uv build --offline`: passed; wheel and sdist built.
- `git diff --check`: passed, no whitespace errors.

Targeted runs: schemas 95, serialization 43, json types 61, round trip 13, hashing 43, golden
vectors 16, properties 14, subprocess determinism 10.

### Determinism evidence

- Cross-process subprocess checks under `PYTHONHASHSEED` `0`, `1`, and `987654` produce identical
  canonical bytes, SHA-256 digests, and stable identifiers.
- Child processes run from different working directories and with altered `TMPDIR`,
  `QUANTCHECK_OUTPUT_DIR`, `USER`, and `LOGNAME` produce identical output.
- Mapping insertion order, snapshot record order, and dimension order do not affect bytes or IDs.
- Golden digests were verified **independently of this codebase** by piping the exact expected text
  through `shasum -a 256`. The full digest of the record-ID envelope is
  `65fda11bcd81ffa12482ed99e6b7c0d01300e85c67c97b91e5072ba9ab39e514`, whose first 16 characters are
  exactly the digest part of `rec_65fda11bcd81ffa1`, confirming both envelope shape and truncation.
- An AST-level test asserts no module imports `uuid` or calls `hash`, `id`, `uuid4`, or `random`.

### Packaging

Wheel contains only the six `quantcheck/` modules plus dist-info. Sdist contains only `src/`,
`tests/`, `pyproject.toml`, `uv.lock`, `README.md`, `.python-version`, `.gitignore`, `PKG-INFO`.
Extraction scans found no `reference/`, `prompts/`, `docs/`, governance documents, `.claude`,
`.serena`, `.venv`, caches, bytecode, local paths, usernames, secrets, or historical release
claims. A clean `uv venv` install of the wheel installs only Pydantic and its own dependencies,
imports without pandas/NumPy/HTTPX/Streamlit/PyArrow, and reproduces the golden vectors.

## Milestone 2 verification

### Files added

- `src/quantcheck/point_in_time.py` — `build_dataset_snapshot`, the end-of-day
  `available_on <= as_of_date` selection rule, `parse_declared_revision_lineage`,
  `RevisionLineage`, and `AmbiguousRevisionHistoryError`.
- `src/quantcheck/fixtures.py` — the pure, offline, seedless-random-free
  reviewed-fixture factory: `RowSpec`, `default_row_specs`,
  `build_fixture_records`, `generate_reviewed_fixture`,
  `reviewed_fixture_payload`, `canonical_reviewed_fixture_bytes`.
- `src/quantcheck/audit_boundary.py` — `sanitize_for_audit`, the
  `DatasetSnapshot` → `AuditInputSnapshot` trust-boundary conversion.
- `scripts/generate_reviewed_fixture.py` — regenerates or (`--check`) verifies
  the checked-in fixture; not part of the wheel or sdist (dev-only, like
  `AGENTS.md`/`docs/`; the fixture bytes themselves remain fully reproducible
  from the installed package via `canonical_reviewed_fixture_bytes()`).
- `tests/fixtures/reviewed_financial_facts.json` — the checked-in canonical
  fixture (26 records, seed `0`).
- `tests/fixtures/README.md` — fixture purpose, contents, and regeneration
  instructions.
- `tests/test_fixtures.py`, `tests/test_point_in_time.py`,
  `tests/test_revision_ordering.py`, `tests/test_audit_boundary.py`,
  `tests/test_milestone2_properties.py`,
  `tests/test_milestone2_determinism_subprocess.py`.

### Files changed

- `src/quantcheck/hashing.py` — added `revision_id` (prefix `rev`, namespace
  `quantcheck/revision/v1`) and `REVISION_NAMESPACE`. Every Milestone 1
  helper is unchanged.
- `src/quantcheck/__init__.py` — exported the new public API (`__all__` grew
  from 34 to 59 entries). No existing export changed.
- `docs/SERIALIZATION_AND_HASHING.md` — added `revision_id` to the assigned
  namespaces/prefixes table, with a note on why it is not stored on any
  schema field. The rest of the document, including every Milestone 1 rule,
  is unchanged.
- `pyproject.toml`, `uv.lock` — **unchanged**. No dependency was added.

### Fixture evidence

- 26 synthetic records: 3 entities (`CIK0000000001`–`CIK0000000003`), 4
  concepts (`Revenues`, `NetIncomeLoss`, `Assets`, `EarningsPerShareDiluted`),
  2 quarters, 2 units (`USD`, `USD/shares`), both `instant` and `duration`
  period types, dimensioned and dimension-free facts, two source-declared
  revision histories (3-revision and 2-revision), one independent
  duplicate-candidate pair, one same-business-key/different-dimension pair,
  and two hard-negative observations (a `0.00` diluted EPS and a negative
  `NetIncomeLoss` loss quarter). No deliberately corrupted record exists in
  it. Full inventory in `tests/fixtures/README.md`.
- Regeneration: `uv run python scripts/generate_reviewed_fixture.py`;
  verification: `uv run python scripts/generate_reviewed_fixture.py --check`
  — passed, checked-in bytes match regenerated canonical bytes exactly.
- The fixture factory (`quantcheck.fixtures`) touches no filesystem, clock,
  or random-number source. A `seed` parameter exists for interface
  consistency with `CaseConfig.seed`, but the checked-in fixture (seed `0`)
  is not seed-randomized: exactly one field — entity 1's `entity_name`
  (`"Aster Analytics Corp"` vs. `"Aster Analytics Corporation"`) — varies
  with the seed, and every other row is fixed regardless of seed. This is
  tested directly (`test_different_seed_only_changes_the_one_documented_field`).
- `revision_id(lineage_id=..., sequence=...)` gives every declared revision a
  stable, order-independent, testable identity (namespace
  `quantcheck/revision/v1`, prefix `rev`), verified deterministic and
  lineage/sequence-discriminating by both example and Hypothesis tests.
- **No historical fixture bytes are reproduced or claimed.** This fixture is
  newly authored for the rebuild; the historical "26-record manually
  reviewed fixture" mentioned in `reference/IMPLEMENT_RELEASE_0.1.0.md` is
  evidence of *scale and intent* only, not a byte-identity target.

### Temporal and revision behavior

- **Availability rule**: exactly `record.available_on <= as_of_date`.
  `filed_on` is preserved provenance and never controls eligibility on its
  own (`test_filed_on_alone_never_controls_eligibility`). Same-day
  availability (`available_on == as_of_date`) is included.
- **Revision-selection rule**: two records belong to one revision history
  only when a source explicitly says so — a `"<lineage_id>#r<sequence>"`
  marker declared inside the record's own `SourceReference.source_row_key`
  (`quantcheck.point_in_time.parse_declared_revision_lineage`). Records
  without the marker are independent source occurrences and are never
  merged, deduplicated, or compared by business key. Within a declared
  lineage, the highest-sequence member whose `available_on <= as_of_date`
  is selected; every other member of that lineage (earlier revisions, and
  any revision not yet available) is excluded from that snapshot. A later
  revision can never appear in an earlier snapshot.
- **Ambiguity handling**: `AmbiguousRevisionHistoryError` (a `ValueError`
  subclass) is raised, rejecting rather than guessing, when a declared
  lineage has a repeated sequence number, members that disagree on the
  economic fact (entity/concept/unit/dimensions/period), or availability or
  filing dates that are not monotonic in declared-sequence order.
- **Duplicate preservation**: independent occurrences and duplicate
  candidates (including byte-identical economic content under different
  `record_id`s) are never merged or deduplicated by the point-in-time
  engine — that judgment belongs to a future deduplication milestone, not
  this one.
- Selection and canonical output are independent of input order: internal
  grouping runs over a `dict` keyed by lineage id, but lineage resolution
  sorts explicitly by declared sequence (never by input position or dict
  iteration order), and `DatasetSnapshot`/`AuditInputSnapshot` always sort
  their final `records` by `record_id` (Milestone 1 behavior, unchanged).
  Verified by property tests over full permutations of the fixture and by
  explicit reversed-order tests.
- `build_dataset_snapshot` never mutates its `records` argument (verified by
  property test) and produces byte-identical canonical output on repeated
  calls with the same logical input.

### Audit boundary

- **Preserved fields**: `record_id`, `entity_id`, `concept_namespace`,
  `concept`, `value`, `unit`, `dimensions`, `period_type`, `period_start`,
  `period_end`, `filed_on`, `available_on`, `form`, `accession_number`,
  `source_name`, `source_locator`, plus the snapshot's `dataset_name` and
  `as_of_date` — exactly the `AuditInputRecord`/`AuditInputSnapshot` field
  set from Milestone 1, unchanged.
- **Removed fields**: `entity_name` and `source.source_row_key` (and
  therefore any declared revision-lineage marker it carries) never reach
  `AuditInputRecord`, because that schema does not declare those fields.
  `sanitize_for_audit` cannot construct a model with fields it does not
  accept — the boundary is enforced by the schema itself, not by a
  best-effort filter.
- **Isolation evidence**: dedicated tests assert that canonical audit-input
  bytes never contain `source_row_key`, `entity_name`, a `#r<n>` lineage
  marker, `seed`, `fixture_name`, or `spec_version`, including a targeted
  case where the source record's `entity_name` and lineage marker are
  deliberately distinctive strings and are proven absent from the sanitized
  bytes byte-for-byte.
- `sanitize_for_audit` never mutates its `DatasetSnapshot` argument (checked
  by comparing canonical bytes before/after) and is deterministic and
  order-independent (checked by both example and property tests).

### Tests added

- `tests/test_fixtures.py` (40 tests) — fixture shape, checked-in-file
  parity, content coverage (entities/concepts/periods/units/period
  types/dimensions/hard negatives), revision-history and duplicate-candidate
  presence, same-seed/different-seed/reordering determinism, and the
  regeneration script's write and `--check` modes (including missing-file
  and drifted-file failure paths, loaded directly via `importlib` so the
  actual script file is exercised).
- `tests/test_point_in_time.py` (15 tests) — availability boundary
  (`<`, `==`, `>` the cutoff), empty selections, quarter-end vs. filing-day
  cutoffs, `filed_on`-alone never controlling eligibility, snapshot identity
  verification, non-mutation, and order independence.
- `tests/test_revision_ordering.py` (23 tests) — marker parsing, early/late
  cutoff selection, non-contamination, reversed input order, equal-value
  revisions staying separate, independent occurrences never merging, and
  every documented ambiguity/contradiction rejection path, plus `revision_id`
  determinism.
- `tests/test_audit_boundary.py` (15 tests) — field preservation, cutoff
  preservation, identity verification, non-mutation, order independence,
  round-trip fidelity, and prohibited-field-absence checks.
- `tests/test_milestone2_properties.py` (11 tests) — bounded Hypothesis
  coverage of the availability cutoff, full-permutation snapshot/audit-input
  order independence, non-mutation, `revision_id` properties, and the
  AST-level "no `uuid`/`hash`/`id`/`random`" static check extended to
  `fixtures.py`, `point_in_time.py`, `audit_boundary.py`, and
  `scripts/generate_reviewed_fixture.py` (mirroring the Milestone 1 check in
  `tests/test_hashing.py`, which is otherwise untouched).
- `tests/test_milestone2_determinism_subprocess.py` (8 tests) — the fixture,
  snapshot, and audit-input path under `PYTHONHASHSEED` `0`/`1`/`987654`,
  varied working directory, and varied `TMPDIR`/`QUANTCHECK_OUTPUT_DIR`/
  `USER`/`LOGNAME`.

**Total: 112 new tests. Full suite: 411 tests (299 Milestone 0/1 baseline +
112 Milestone 2), all passing.**

### Commands run

Each run individually, all exit 0:

- `uv sync --all-groups`: passed; resolved 19 packages (unchanged from
  Milestone 1).
- `uv sync --frozen --all-groups`: passed; checked 18 packages.
- `uv run ruff check .`: passed, "All checks passed!".
- `uv run ruff format --check .`: passed, 28 files already formatted.
- `uv run mypy src tests`: passed, strict, no issues in 27 source files.
- `uv run pytest`: passed, **411 tests**, Hypothesis plugin loaded.
- `uv lock --check`: passed.
- `uv run quantcheck --help`: exited 0, output byte-identical to Milestone 0/1
  (the CLI was not touched).
- `uv build --offline`: passed; wheel and sdist built.
- `git diff --check`: passed, no whitespace errors.
- `uv run python scripts/generate_reviewed_fixture.py --check`: passed.

Targeted runs: fixtures 40, point-in-time 15, revision ordering 23, audit
boundary 15, Milestone 2 properties 11, Milestone 2 subprocess determinism 8,
Milestone 1 golden vectors 16 (unchanged, re-run to confirm).

### Determinism evidence

- Cross-process subprocess checks under `PYTHONHASHSEED` `0`, `1`, and
  `987654` produce identical fixture bytes, snapshot ids/hashes, audit-input
  ids/hashes, and `revision_id` values.
- Child processes run from different working directories and with altered
  `TMPDIR`, `QUANTCHECK_OUTPUT_DIR`, `USER`, and `LOGNAME` produce identical
  output.
- Full-permutation Hypothesis tests over the 26-record fixture confirm
  snapshot identity and sanitized audit-input bytes are independent of input
  order.
- The checked-in fixture file's bytes are proven, in-process and across
  subprocesses, to equal `canonical_reviewed_fixture_bytes()` regenerated
  from the same seed.

### Packaging

Wheel contains exactly the nine `quantcheck/` modules (the six from
Milestone 1 plus `audit_boundary.py`, `fixtures.py`, `point_in_time.py`) plus
dist-info — confirmed by listing the built wheel. Sdist contains `src/`,
`tests/` (including the new `tests/fixtures/` directory — covered by the
existing `/tests` allowlist entry, so `pyproject.toml` needed no change),
`pyproject.toml`, `uv.lock`, `README.md`, `.python-version`, `.gitignore`,
`PKG-INFO`. `scripts/` is **not** included in the sdist (it falls outside the
existing allowlist, same as `AGENTS.md`/`docs/`); this is a known limitation,
noted below. Extraction scans of both archives found no `reference/`,
`prompts/`, `docs/`, governance documents, `.claude`, `.serena`, `.venv`,
caches, bytecode, local paths (`rishihaldar`, `/Users/`, `/home/`), or
secret-shaped strings. A clean `uv venv --python 3.12` install of the wheel
pulls only `pydantic`/`pydantic-core`/`annotated-types`/`typing-inspection`/
`typing-extensions`, imports without pandas/NumPy/HTTPX/Streamlit/PyArrow,
and reproduces the fixture, snapshot, and audit-input identities.

## Decisions

- **Milestone 1 identifier scheme.** `stable_id` hashes a versioned envelope
  (`{"id_scheme": "quantcheck/stable-id/v1", "namespace": ..., "payload": ...}`) and keeps the
  first 16 hex characters after a `<prefix>_`. Assigned: `rec`/source-record,
  `snap`/dataset-snapshot, `audit`/audit-input-snapshot, `case`/case-config. Recorded as a decision
  because the historical contract is lost and later milestones must not silently diverge.
- **Decimal canonical form is numeric, not scale-preserving.** See the correction above.
- **Snapshot identity is not stored-and-trusted.** `DatasetSnapshot.snapshot_id` is a validated
  required field rather than a computed one, because computing it inside `schemas.py` would create
  a `schemas` <-> `hashing` import cycle. `hashing.py` provides the ID helpers plus
  `*_identity_matches` verifiers, which are tested.
- **`available_on < filed_on` is deliberately permitted.** Look-Ahead injection is defined as making
  a record available before its preserved filing date, so the contract layer must be able to
  represent it. Only `period_start <= period_end` is enforced.
- CLI entry point uses the Python standard library `argparse` rather than Typer for Milestone 0. Typer remains the fixed long-term CLI choice per `AGENTS.md`/`AGENTS_ORIGINAL.md`; introducing it now for a help-only placeholder would add a dependency for no behavioral benefit and risks establishing a competing/incomplete CLI shape before the contracted command surface (Recovery Phase 9) is designed. Revisit at the CLI milestone.
- Package version is `0.1.0.dev0` (not `0.1.0`) to avoid implying the historical 0.1.0 release is reproduced; the real `0.1.0` version should be set at the release-evidence milestone.
- `pytest` and `mypy` version ranges are unpinned upper-bound minors (`>=X,<Y+1`) consistent with keeping dependency additions minimal and explicit; exact resolved versions are captured in `uv.lock`.

- **Revision lineage is declared inside `source_row_key`, not as a new schema field.**
  `FinancialFact`'s field set is frozen by the Milestone 1 golden vectors — adding any field,
  even an optional one, would change every fact's canonical bytes and break
  `tests/test_golden_vectors.py`. A record's membership in a revision history is therefore
  declared directly inside its own source-defined `SourceReference.source_row_key`, using the
  `"<lineage_id>#r<sequence>"` marker (`quantcheck.point_in_time.parse_declared_revision_lineage`).
  This has a useful side effect for the audit boundary: since `AuditInputRecord` never carries
  `source_row_key`, the lineage marker — and therefore the entire revision-answer-key shape —
  cannot cross `sanitize_for_audit` even by accident.
- **`revision_id` is a derived, testable identifier, not a persisted one.** For the same reason
  above, `revision_id(lineage_id=..., sequence=...)` (namespace `quantcheck/revision/v1`, prefix
  `rev`) exists to give a declared `(lineage_id, sequence)` pair its own stable identity for
  identifier-stability tests, but it is not stored on any schema field or artifact.
- **Revision grouping requires an explicit marker; it never falls back to a business key.**
  Two records that share entity/concept/period/unit/dimensions but carry no declared lineage
  marker (or different lineage ids) are treated as independent source occurrences — including
  duplicate candidates — never as revisions of each other. This was an explicit task requirement:
  inferring revision relationships from matching fields alone would let a legitimate duplicate
  silently vanish during point-in-time selection.
- **Revision ordering trusts declared sequence, and requires it to agree with source-supported
  dates.** Selection uses the highest declared `sequence` whose `available_on <= as_of_date`; the
  engine separately requires `available_on` and `filed_on` to be non-decreasing in that same
  declared-sequence order, and raises `AmbiguousRevisionHistoryError` otherwise. A history is
  never accepted on sequence alone or on dates alone.
- **Fixture seed varies exactly one field, deterministically, without `random`.** The fixture
  factory accepts a `seed` for interface consistency with `CaseConfig.seed` and to satisfy the
  "different seeds produce documented variation" requirement, but nothing in `quantcheck.fixtures`
  imports `random`: only entity 1's `entity_name` is chosen by `seed % 2`. The checked-in fixture
  is not a randomized sample; it is the reviewed, seed-`0` case.
- **`scripts/` is intentionally outside the sdist allowlist.** The regeneration script is a
  repository development tool, not a runtime dependency of the installed package; the fixture
  bytes it writes are independently reproducible from the installed wheel via
  `quantcheck.fixtures.canonical_reviewed_fixture_bytes()`. No `pyproject.toml` change was needed
  or made for Milestone 2.

## Known limitations

- No fault injection (Look-Ahead or otherwise), detectors, manifests, scoring, SEC access,
  benchmark artifacts, or dashboard/HTML exist yet. None of the historical 0.1.0 test counts,
  benchmark metrics, or hashes are reproduced or claimed.
- The lost `docs/SERIALIZATION_AND_HASHING.md` could not be recovered (Milestone 1). The rebuilt
  contract is a reasoned reconstruction, not a restoration, and no historical golden value is
  reproducible. This applies equally to the Milestone 2 reviewed fixture: it is newly authored,
  not a recovery of the historical fixture's bytes.
- Manifest, finding, report, and duplicate-occurrence identifiers are still **not** specified
  (only `source_record_id`, `dataset_snapshot_id`, `audit_input_snapshot_id`, `case_config_id`,
  and now `revision_id` have assigned payloads). When those artifacts are contracted, they must
  get dedicated helpers rather than improvised payloads.
- Revision-lineage declaration is a single, narrow convention (a `"#r<n>"` suffix inside
  `source_row_key`), not a general restatement detector. It only creates *correct clean* revision
  histories and selects the historically visible version; it cannot infer that two records are
  revisions of each other from matching values or business-key fields alone, by design. General
  restatement detection belongs to a later milestone (the historical numbering's Milestone 7,
  Revision Overwrite).
- `build_dataset_snapshot` and `sanitize_for_audit` operate on data already in the canonical
  `FinancialFact`/`DatasetSnapshot` domain. Nothing normalizes raw external data (e.g., SEC XBRL)
  into that domain yet; that is the SEC-adapter milestone, still absent.
- `scripts/generate_reviewed_fixture.py` is not included in the sdist (see the packaging decision
  above); it is a repository development tool, not a distributed capability. The fixture bytes it
  writes remain independently reproducible from the installed wheel.
- Schemas require explicit `filed_on` and `available_on` but cannot prove the external rule that
  justifies a difference between them; adapters and injectors must supply that context later.
- Canonical strings are compared code point for code point; no Unicode normalization is applied, so
  NFC and NFD spellings of the same grapheme are distinct logical values.
- The CLI has no subcommands and is expected to be replaced entirely at the CLI milestone
  (Recovery Phase 9).
- CI (`.github/workflows/ci.yml`) has not yet run on GitHub Actions; it has only been validated by
  running its constituent commands locally.

## Exact next task

Implement Recovery Phase 3 — the narrow, complete **Look-Ahead vertical slice** (historical
Milestone 6): the required artifact schemas that belong to that milestone (fault manifest entries,
findings, scoring/report shapes — scoped to Look-Ahead only, not the full four-fault set),
deterministic Look-Ahead injection against a `DatasetSnapshot` built by `build_dataset_snapshot`,
a hidden manifest recording the true vs. corrupted `available_on`, sanitized detection over the
`AuditInputSnapshot` produced by `sanitize_for_audit` (the detector must never see the manifest),
exact finding-to-manifest matching, scoring, and one controlled research-impact comparison (e.g., a
simple point-in-time ranking that changes between the clean and corrupted snapshot). Reuse the
Milestone 1 canonical path/schemas/identifiers and the Milestone 2 fixture, point-in-time engine,
and audit boundary unchanged; do not alter the frozen Milestone 1 golden vectors or the checked-in
Milestone 2 fixture bytes. Do not implement Unit Drift, Duplicate Observations, Revision Overwrite,
the SEC adapter, the full benchmark-case framework, the CLI, or the dashboard in that task.

## Fixed implementation choices

- Python: 3.12
- Package: `quantcheck`
- Dependency manager: `uv`
- Build backend: Hatchling
- Public schemas: Pydantic v2, introduced in Milestone 1
- Lint and format: Ruff
- Type checking: MyPy
- Tests: pytest and Hypothesis
- CLI: Typer, introduced at the contracted milestone unless a minimal entry-point dependency is deliberately deferred
- HTTP: HTTPX, introduced with the SEC adapter
- Tabular processing: pandas and PyArrow, introduced only when required
- Dashboard: Streamlit, introduced only after benchmark and CLI stability

## Historical target

The prior release documentation describes a 0.1.0 implementation with four fault families, a 132-case frozen benchmark, a strict CLI, public/private artifacts, and read-only presentation. Those documents are design and acceptance references, not current status.

## Required handoff update after each task

Record:

- milestone and task completed;
- files changed;
- commands run and exact outcomes;
- decisions added or revised;
- known limitations;
- exact next task.

## Last updated

2026-08-06 (Milestone 2 complete — deterministic fixtures and point-in-time engine)
