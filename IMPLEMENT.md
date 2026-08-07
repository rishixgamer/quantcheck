# Implementation status

This is the operational handoff between Claude Code sessions. Keep it concise, factual, and current.

## Current phase

**Milestone 7 complete — Revision Overwrite**

The original source repository was lost. Historical 0.1.0 documentation survives under
`reference/`, but no historical implementation claim is considered current until rebuilt and
verified. Milestones 0–2 rebuilt the repository, canonical contract layer, reviewed synthetic
fixture, explicit revision selection, end-of-day point-in-time snapshots, and sanitized audit
boundary. Milestone 3 completes the narrow `lookahead_timestamp` /
`period_end_substitution` flow: deterministic injection and private truth, manifest-blind
detection over `AuditInputSnapshot`, exact one-to-one scoring, controlled
`availability_count_v0_1`, and private manifest-assisted exact replay. Milestone 4 adds one-CIK
synchronous HTTPX retrieval, exact-byte cache identity, integrity-checked offline replay, explicit
Company Facts allowlist normalization, and integration with the existing snapshot/audit path. It
contains no other fault family, benchmark framework, expanded CLI, or presentation logic.
Milestone 5 completes the narrow `unit_drift` / `value_scaled_unit_unchanged` flow: exact
comparable-series construction, deterministic scaled-value injection with unchanged unit, private
reversible truth, manifest-blind immediate-neighbor detection, exact scoring, controlled
`aggregate_value_v0_1`, and private manifest-assisted exact replay. Milestone 6 completes the
narrow `duplicate_observation` / `exact_occurrence_copy` flow: one exact fingerprint shared by
injection eligibility and manifest-blind detection, deterministic appended-copy injection with
private reversible truth, exact fingerprint-group matching/scoring with a fixed `medium` finding
severity, controlled `record_count_v0_1` plus reuse of the existing `aggregate_value_v0_1` for a
double-counting demonstration, and private manifest-assisted exact replay that removes only the
injected copies. Milestone 7 completes the narrow `revision_overwrite` /
`later_vintage_in_earlier_state` flow: explicit source-supported adjacent histories,
deterministic later-vintage replacement retaining historical availability, private reversible truth,
sanitized manifest-blind temporal-contradiction detection, exact scoring, private exact replay, and
a controlled frozen-vintage `growth_ranking_v0_1` sensitivity comparison. Benchmark artifacts and
all later product work remain unimplemented.

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

## Milestone 3 verification

### Scope and contracts

- Added the current authoritative narrow fault contract in `docs/faults/LOOK_AHEAD.md` and recorded
  only the behavior missing from surviving evidence in `docs/DECISIONS.md`. The lost historical
  fault document is not claimed to be recovered.
- Added immutable strict models: `LookAheadInjectionConfig`, `LookAheadMutation`,
  `FaultManifestEntry`, `FaultManifest`, `LookAheadEvidence`, `Finding`, `AuditReport`,
  `DetectionMetrics`, `ExactFindingMatch`, `ScoreReport`, `AvailabilityCountResult`, and
  `ResearchImpact`. Every tuple is canonicalized, relationships are validated, and every Decimal
  remains a canonical JSON string.
- Added dedicated versioned namespaces/helpers for modified records, faults, manifests, findings,
  audit reports, score reports, research results, and research impact. Modified records retain the
  ordinary `rec_` prefix so the sanitized ID cannot act as an injected-row flag; the dedicated
  namespace provides collision separation.

### Injection and private truth

- Eligibility requires a valid clean snapshot, `available_on == filed_on`,
  `period_end <= research_as_of_date < available_on`, and the configured minimum natural filing
  lag. Profiles are low `0.02`/7 days, medium `0.05`/14 days, and high `0.10`/30 days.
- Target counts use Decimal ceiling with minimum one, eligible-count bound, and an explicit positive
  cap (default 100). No eligible target raises `NoEligibleLookAheadTargetsError` rather than
  guessing.
- Selection ranks `(full SHA-256 digest, stable record_id)` over the Look-Ahead selection namespace,
  specification, seed, and eligibility-unit ID. Target ranks are zero-based and private.
- Injection changes exactly `record_id` and `available_on`; the latter becomes `period_end`.
  Filing, value, unit, dimensions, periods, accession, and source provenance remain unchanged. The
  clean input is never mutated.
- The private manifest records clean/corrupted snapshot IDs and hashes, all eligibility/configuration
  evidence, full original/corrupted records, and exact reversible mutations. Integrity validation
  recomputes severity, count, rank, selection digest, modified-record ID, fault ID, and manifest ID.

### Detection, scoring, research, and replay

- `detect_lookahead` accepts only `AuditInputSnapshot`. It has no manifest, clean-data, seed,
  severity, target, injection, scoring, or replay parameter/dependency. It emits the exact public
  rule `available_on == period_end < filed_on` when the record is visible by audit as-of, with
  leaked days, source evidence, deterministic explanation, derived low/medium/high severity, and
  `proven_by_contract` confidence. The reviewed clean control, zero EPS, and negative-income hard
  negatives emit no findings.
- `score_lookahead` consumes an already finalized immutable `AuditReport` and private manifest. It
  requires exact detector/class/subtype/rule/record/severity/confidence/date/source evidence and
  stable finding identity. Near matches are false positives; misses are false negatives; identical
  duplicates add false positives without recall; distinct competitors are ambiguous and cannot
  match.
- Metrics use Decimal only. Precision is null with no findings, recall with no faults, F1 when
  either input is null, and false-positive rate with a zero clean denominator. The clean denominator
  is `eligible_record_count - target_count`, never corrupted row or finding count.
- `availability_count_v0_1` applies the same pure `available_on <= research_as_of_date` calculation
  to clean, corrupted, and repaired snapshots. This is controlled occurrence-count evidence, not a
  trading or alpha claim.
- `manifest_assisted_exact_replay` is private answer-key replay, not detector-only remediation. It
  validates all artifact relationships, replaces only exact corrupted records with stored
  originals, is non-mutating and idempotent, and requires the restored snapshot ID/hash to equal the
  clean artifact exactly.

### Reviewed case evidence

- Source horizon `2024-04-30`, controlled research date `2024-04-14`, medium severity, seed 42.
  Clean snapshot: 13 records, 13 eligible, one selected fault, 12 eligible clean denominator.
- Selected original `rec_e8f91dcfc48c7955`; modified record `rec_5d2412c678714ae6`; selection
  digest `01e2596e60ddeea189c8424745d2c2db5deb56abd4515104f9934550d0f5593b`; fault
  `fault_6f59dbda440431ef`; finding `find_5507c4daa814e7a7`.
- Clean snapshot `snap_1ba1e74184f1123a` / hash
  `ae8395b1ce74541da8011a8c69e6daf945cdfe15315ca37be902c693de5b918a`; corrupted snapshot
  `snap_d290dc2684c09a62` / hash
  `9a8bb2f49e7d3493761b245ccc9b19ba896f3c7c69dc5993d454399c797d2ef2`; manifest
  `man_0b6bf9c4c5160852`; report `arep_d4838cacf3c5927e`; score
  `score_7fef38b1cc45f4a8`; impact `impact_d7904bf5ebb2c586`.
- One exact TP, zero FP/FN, precision/recall/F1 `1`, false-positive rate `0/12`. Controlled
  availability count is clean `0`, corrupted `1`, repaired `0`. Repaired snapshot bytes, ID, and
  hash equal clean exactly.

### Files added

- Runtime: `lookahead_contract.py`, `lookahead_injection.py`, `lookahead_detection.py`,
  `lookahead_manifest.py`, `lookahead_scoring.py`, `lookahead_replay.py`,
  `lookahead_research.py`.
- Current contracts: `docs/faults/LOOK_AHEAD.md`, `docs/DECISIONS.md`.
- Tests: `tests/lookahead_support.py`, six focused behavior/integration modules,
  `test_milestone3_properties.py`, and `test_milestone3_determinism_subprocess.py`.

### Files changed

- `schemas.py`, `hashing.py`, `__init__.py` — Look-Ahead artifacts, dedicated identities, and public
  API; no existing field or identifier payload changed.
- `docs/SERIALIZATION_AND_HASHING.md`, `README.md`, `IMPLEMENT.md` — current identifier contract,
  implemented status, and operational handoff.
- `pyproject.toml`, `uv.lock`, the checked-in fixture, fixture factory, point-in-time engine, audit
  boundary, CLI, and Milestone 1 golden-vector file are unchanged.

### Tests and commands

- Added **104 tests**: contracts 14, injection 25, detection/isolation 14, scoring 13,
  research/replay 13, reviewed integration 6, properties/static safety 12, subprocess determinism 7.
  Full suite: **515 passed** (411 prior + 104 new), no warnings.
- Every required command exited 0: `uv sync --all-groups`, frozen sync, Ruff check and format check,
  strict MyPy, full pytest, `uv lock --check`, CLI help, fixture regeneration check,
  `uv build --offline`, and `git diff --check`.
- Existing focused regressions passed independently: schemas 95, serialization 43, hashing 43,
  golden vectors 16, fixtures 40, point-in-time 15, revision ordering 23, audit boundary 15,
  Milestone 2 properties 11, Milestone 1 subprocess determinism 10, and Milestone 2 subprocess
  determinism 8. All eight new test modules also passed independently.
- Explicit `PYTHONHASHSEED` 0/1/987654 runs produced the same complete-artifact digest
  `feac93bc723741978530c963fc902b71d92b01e0abd0183c957f54f1904e80ea`. Tests also cover reversed
  source order, mapping insertion order, different working directories, altered temp/output/user
  environment values, repeated processes, and no `random`/`uuid`/built-in `hash`/object `id` use.

### Packaging and dependencies

- `uv build --offline` produced the wheel and sdist. The wheel contains all 16 runtime modules plus
  dist-info; the sdist contains the runtime tree and all 515 tests under the existing allowlist.
- Archive name/content scans found no `reference/`, prompts, recovery/governance documents, local
  tool directories, environments, caches, bytecode, build directories, local username/path,
  private keys, access-key shapes, saved manifests, or hidden case artifacts.
- A clean Python 3.12 wheel install pulled only the declared Pydantic dependency family, imported no
  pandas, NumPy, HTTPX, Typer, PyArrow, Streamlit, and reproduced the full reviewed case IDs and exact
  replay outside the checkout.
- No dependency was added; `pyproject.toml` and `uv.lock` are byte-unchanged. The first archive-list
  attempt used unavailable bare `python` and was rerun successfully with `uv run python`. A separate
  temporary cleanup command was blocked before execution by environment policy; the same review
  passed without cleanup. Neither was a project failure.

## Milestone 4 verification

### Scope and contracts

- Added the narrow, synchronous `SecCompanyFactsAdapter`, not a generic ingestion layer. It accepts
  one explicit CIK, constructs only
  `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`, uses HTTPX, and never performs
  ticker lookup, multi-company orchestration, statement reconstruction, or live-network tests.
- `SecClientConfig` is frozen and rejects missing, blank, placeholder, identity-free, or
  contact-free user agents. A valid value carries an explicit organization/tool identity plus a
  non-placeholder email address or HTTP(S) contact URL. Timeout, minimum request interval, retry
  count, backoff, and accepted `Retry-After` bound are explicit and validated without side effects.
- Current official SEC API/fair-access pages were checked on 2026-08-06: Company Facts uses a
  ten-digit zero-padded CIK endpoint, automated callers must declare a user agent, and current fair
  access guidance caps aggregate access at 10 requests/second. No live Company Facts request was
  made.
- CIK normalization accepts only positive ASCII-digit integers/strings up to ten digits and emits
  exactly ten digits. Boolean, zero, negative, nonnumeric, whitespace-bearing, Unicode-digit,
  overlong, and otherwise ambiguous values are rejected.

### HTTP, retry, and cache behavior

- Requests send explicit `User-Agent` and `Accept: application/json` headers, pass the configured
  HTTPX timeout on every attempt, disable redirects, and wrap transport/HTTP failure categories
  while preserving their causes. Only transport errors and HTTP 429/500/502/503/504 retry; the
  default is two retries with deterministic `0.5 * 2^n` backoff.
- Sequential attempts use a configurable 0.2-second default minimum interval (5 requests/second,
  below current SEC guidance). `Retry-After` supports only bounded non-negative integer
  delay-seconds; wall-clock-dependent HTTP-date and malformed/out-of-bound forms fall back to the
  deterministic schedule. Sleep and monotonic functions are injectable, so tests never really
  wait.
- Cache layout is `companyfacts/CIK##########/raw-<sha256>.json` plus canonical `accepted.json`.
  Raw SHA-256 covers exact `response.content` bytes before parsing or normalization. Accepted
  metadata contains only schema version, canonical CIK, canonical URL, raw filename, and raw
  digest—no retrieval timestamp, cache path, machine, user, or runtime state.
- Every load revalidates safe path containment, metadata field set/canonical bytes, URL/CIK,
  filename/digest relationship, raw-file presence and non-symlink status, exact raw hash, finite
  JSON, and the Company Facts envelope. Immutable raw creation uses a flushed temporary file plus
  non-overwriting hard-link establishment; accepted-pointer replacement uses a flushed
  same-directory temporary file plus `os.replace` and directory synchronization.
- Valid cache hits avoid network access. `replay` is offline-only. Explicit refresh bypasses a valid
  pointer, but transport, HTTP, malformed-body, conflicting-content, or atomic-pointer failures do
  not replace the previous accepted state. Identical acceptance is idempotent.

### Narrow normalization and provenance

- `SecNormalizationConfig` freezes one CIK plus exact taxonomy/concept/unit/period-shape rows,
  forms, and inclusive filing-date bounds. Input sequences are copied and sorted; duplicate specs,
  unknown constructor fields, malformed names/dates, and empty allowlists are rejected.
- Source JSON integers stay exact integers and fractional/exponent numbers parse directly to
  `Decimal`; no financial value passes through `float`. Boolean, string, null, collection, and
  non-finite values are rejected. Dates are strict calendar dates. Instant entries require no
  start; duration entries require valid `start <= end`.
- Valid but non-allowlisted taxonomy, concept, unit, form, date, or period shape produces a stable
  explicit exclusion. Malformed entries under an allowlisted taxonomy/concept/unit—missing fields,
  invalid periods/accessions/metadata, or arbitrary segment/dimension keys—raise
  `InvalidAllowlistedFactError`; no partial result is returned.
- Every accepted record is the existing immutable `FinancialFact` with canonical entity
  `CIK##########`, exact namespace/concept/unit/form/dates/accession, `dimensions=()`, and
  `available_on == filed_on`. The source locator is the SEC endpoint, never the cache directory.
- Added `sec_source_row_id` (`srow_`, namespace
  `quantcheck/sec-companyfacts-source-row/v1`) over canonical CIK, taxonomy, concept, unit, the
  complete parsed entry, and a positive equivalence-class duplicate ordinal. This keeps occurrence
  identity stable under source-list reorder while preserving exact multiplicity. Fiscal/frame
  metadata participates in the opaque row identity because the frozen schema has no dedicated
  location for it.
- The adapter never appends the point-in-time engine's `#r<n>` marker. Accession, amended form,
  matching business keys, or different frames do not prove revision lineage, so every SEC source
  occurrence remains independent. Existing `build_dataset_snapshot` and `sanitize_for_audit` are
  reused without modification; source row/fiscal/frame details do not cross the audit boundary.

### Reviewed fixture evidence

- Added a 2,273-byte curated public field-shape fixture for CIK `0000320193`. It is not a verbatim
  download and no live SEC access is claimed. Its raw SHA-256 is
  `332a506af4ceef5cd9ebb17cb0c1f9f04805ca1535c44f0083e019992f73c2d9`.
- Twelve entries cover `us-gaap:Assets`,
  `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`,
  `us-gaap:SalesRevenueNet`, one unsupported concept, one unsupported taxonomy, USD/EUR,
  10-K/10-Q/8-K, instant/duration shapes, zero/negative values, date boundaries, exact accessions,
  and duplicate-looking independent occurrences. The reviewed allowlist accepts seven records and
  emits five exclusions (taxonomy, concept, unit, form, and pre-range filing date). Tests derive
  malformed allowlisted and segment-bearing variants and prove rejection.
- Normalized-record SHA-256 is
  `bc8e4c09c6421409a20f323ce4219f6a8b4ccf1bfa9db11f98e8ca3ac1a43bf2`. The late reviewed snapshot
  is `snap_1695316352716659` with SHA-256
  `79dbe97de337d64ed9be1ee670e1bfea702d03ef7a6f3bca15f825106f17a68a`. Its sanitized audit input
  is `audit_2076ec17a9143e61` with SHA-256
  `b251d53bd880cf8b80c554fdb0879304f3f3cb5ff1232698b9ff5b082201435b`.
- The seven source rows are `srow_ba7e32a9c5ca64f1`, `srow_9ec0cbb21a07aaeb`,
  `srow_156e220cea0ae9a7`, `srow_ca613dc2217fdf6e`, `srow_7d9c859f47607ed4`,
  `srow_d2bfc4a6ad277d29`, and `srow_02dcee3e2b7986b7`. These are rebuilt v1 values, not historical
  IDs.

### Files and dependencies

- Added runtime `src/quantcheck/sec_adapter.py` and `src/quantcheck/sec_fixture.py`; development
  script `scripts/generate_reviewed_sec_fixture.py`; checked-in fixture
  `tests/fixtures/sec_companyfacts_curated.json`; and four focused test modules covering adapter,
  HTTP/cache, properties/static safety, and subprocess determinism.
- Changed `hashing.py` only to add the dedicated SEC source-row namespace/helper; changed
  `__init__.py` only to expose Milestone 4 behavior; updated fixture documentation, current
  serialization/identity documentation, README status, decisions, and this handoff. The frozen
  canonical schema file, existing serializers, snapshot builder, audit boundary, Look-Ahead files,
  and Milestone 1 golden vectors were not changed for Milestone 4.
- Added direct runtime dependency `httpx>=0.28,<1`; `uv.lock` resolves HTTPX 0.28.1 plus five new
  transitive packages: AnyIO 4.14.2, Certifi 2026.7.22, HTTP Core 1.0.9, h11 0.16.0, and idna 3.18.
  No existing dependency was upgraded or removed. ADR-002 records only the unspecified rebuild
  choices above.

### Tests, determinism, and packaging

- Added **111 tests**: adapter/normalization/integration 63, HTTP/cache 34, bounded properties and
  static safety 7, subprocess determinism 7. The final full suite is **626 passed** (515 prior +
  111 new), with no warnings.
- All required commands exited 0: normal/frozen sync, Ruff check/format check, strict MyPy, full
  pytest, lock check, CLI help, both reviewed-fixture `--check` commands, offline build, and
  `git diff --check`. Existing schema, serialization, hashing, goldens, fixture, point-in-time,
  revision, audit, Look-Ahead, property, and subprocess suites pass independently. New files pass
  independently at 63/34/7/7 tests.
- Final command outcomes were: `uv sync --all-groups` resolved 25/checked 24 packages;
  `uv sync --frozen --all-groups` checked 24; Ruff reported all checks passed and 51 formatted
  files; MyPy reported no issues in 49 source files; `uv run pytest` reported 626 passed;
  `uv lock --check` resolved 25; CLI help exited 0; both fixture checks matched canonical bytes;
  the offline build produced the wheel and sdist; and `git diff --check` exited 0. A mistyped,
  non-applicable probe for `scripts/generate_reviewed_fixtures.py` exited 2 because that path does
  not exist; the actual existing `scripts/generate_reviewed_fixture.py --check` then exited 0.
- Fresh processes under `PYTHONHASHSEED` 0, 1, and 987654 produce identical normalized record bytes,
  source-row IDs, exclusions, snapshot, and audit input. Source-list reversal, different cache and
  working directories, and changed temp/output/user environment values also produce identical
  logical output. Exact raw digest deliberately changes when raw whitespace/order bytes change,
  while normalized logical records remain identical.
- `uv build --offline` produced a 22-entry wheel containing all 18 runtime modules and a 58-file
  sdist containing 34 test/fixture files, including the curated SEC response. Development scripts
  remain outside the existing sdist allowlist. No accepted pointer, cache directory, downloaded
  response, private manifest/artifact, reference/prompt/governance tree, local configuration,
  environment, bytecode/cache/build tree, actual user/check-out path, credential, secret, or
  personal/operational user-agent contact value is packaged. The sdist's literal `/Users/` and
  `/home/` strings are negative-test markers, not local paths.
- A clean Python 3.12.13 wheel environment installed only the declared Pydantic and HTTPX families,
  imported `quantcheck` and `quantcheck.sec_adapter`, regenerated/normalized the reviewed fixture,
  reproduced the reviewed snapshot ID/hash, ran `quantcheck --help`, and imported none of pandas,
  NumPy, PyArrow, Streamlit, Typer, or Matplotlib.

## Milestone 5 verification

### Scope and contracts

- Added the authoritative rebuilt-v1 contract in `docs/faults/UNIT_DRIFT.md` for exactly
  `unit_drift` / `value_scaled_unit_unchanged`, primary rule `value.scale_discontinuity`, and
  specification `quantcheck/unit-drift-value-scale/v1`. Historical behavior is evidence only; no
  historical fixture eligibility count, ID, hash, metric, or artifact byte sequence is claimed.
- Added strict immutable `ComparableSeriesKey`, `UnitDriftInjectionConfig`,
  `UnitDriftDetectorConfig`, `UnitDriftMutation`, `UnitDriftManifestEntry`, `UnitDriftManifest`,
  `UnitDriftNeighborEvidence`, `UnitDriftEvidence`, `UnitDriftResearchConfig`,
  `AggregateValueResult`, and `AggregateValueImpact` contracts. Existing generic `Finding`,
  `AuditReport`, `DetectionMetrics`, `ExactFindingMatch`, and `ScoreReport` envelopes are reused
  without changing their existing fields.
- Exact comparable-series identity is entity, concept namespace/concept, unit, canonical
  dimensions, period type, and inclusive duration length (null for instant facts). Members are
  end-of-day visible under `available_on <= as_of_date`; duplicate period coordinates exclude the
  ambiguous whole series. An eligible nonzero target belongs to a series of at least three visible
  observations and has at least one nearest previous/next nonzero neighbor. Zero observations stay
  in chronology but are neither targets nor comparators; negative values remain eligible.

### Injection and private truth

- Severity fixes exact scale-factor/fraction pairs: low `100`/`0.02`, medium `1000`/`0.05`, and
  high `1000000`/`0.10`. The Decimal ceiling rule has minimum one, the eligibility bound, and a
  positive default cap of 100.
- Target selection ranks `(full SHA-256 digest, record_id)` over the dedicated target-selection
  namespace, spec version, non-negative seed, and clean record ID. Ranks are contiguous and
  zero-based. Injection changes only `value` (`original * scale_factor`) and `record_id`; unit,
  dimensions, dates, provenance, lineage semantics, and unselected records are unchanged. Modified
  records keep the ordinary `rec_` prefix so record identity does not disclose manifest role.
- The private manifest stores clean/corrupted IDs and hashes, complete eligibility/configuration,
  comparable series and usable clean neighbors, digest/rank, complete original/corrupted records,
  exact values/factor, and reversible fault truth. Integrity validation recomputes the severity
  profile, target count, full ranking, modified-record IDs, fault IDs, and manifest ID.

### Detection, scoring, replay, and aggregate impact

- `detect_unit_drift` accepts only `AuditInputSnapshot` and public `UnitDriftDetectorConfig`.
  Defaults are exact Decimal threshold `50` and approved factors `100`, `1000`, `1000000`. It uses
  nearest nonzero chronological neighbors and symmetric absolute Decimal ratios at 50-digit working
  precision. Every before-ratio must be at least the threshold and every corrected ratio strictly
  below it. Candidate corrections test division and multiplication and use the documented stable
  tie-breaker. One usable neighbor is `suspicious`; two are `strong`; factor maps to low/medium/high
  severity.
- Exact scoring requires Unit Drift detector/class/subtype/rule/identity, one corrupted record,
  factor-derived severity, neighbor-derived confidence, exact public context/source evidence, the
  injected factor or reciprocal correction, and the private original value. Duplicates cannot
  increase recall; distinct competitors are ambiguous. The false-positive denominator is every
  clean observation meeting the comparability prerequisites, including selected targets.
- `manifest_assisted_exact_unit_drift_replay` validates private truth and the exact input artifact,
  replaces only exact corrupted records, preserves unrelated records, is idempotent on the exact
  clean artifact, and reproduces clean canonical bytes, ID, and SHA-256 hash.
- `aggregate_value_v0_1` applies the same pure end-of-day Decimal sum to one exact comparable series
  for clean, corrupted, and repaired snapshots. Relative change is signed change divided by the
  absolute clean aggregate and is null for a zero clean aggregate. This is controlled occurrence
  sensitivity, not statement reconstruction, a backtest, or a financial-performance claim.

### Reviewed controlled case and isolation

- Focused case: source horizon `2024-12-31`, medium severity, seed 6, five comparable/eligible
  observations, one target, and clean denominator 5. Selected original
  `rec_6b610ff093ee62dc` value `120`; modified `rec_f4c7d21fbe061111` value `120000`; selection
  digest `1bda7d27884bd89fd62938f123c10bd787e5b666698cf46b483f20c2537443c4`; fault
  `fault_c2c24b75cfab5aae`; finding `find_afde3680181961bb` with `strong` confidence.
- Clean snapshot `snap_125c3a8a1fa654e0` / hash
  `9dd5ad54b67d8129f35eab3f32213a505fa6ea379605734b2e361188d83ae8b7`; corrupted snapshot
  `snap_61a8fb4594869fdf` / hash
  `f357716e863cf5a03a23bf7128c6d2daefc0782d47be12681f21a223f2b8aa2e`; manifest
  `man_57fd1e8c6a6c79e8`; audit input `audit_0e390a054547e409`; report
  `arep_d69a0d5f107bfafa`; score `score_8d85cb73c6063a0c`; impact
  `impact_21770573695e9bc4`.
- Exact score is one TP, zero FP/FN, precision/recall/F1 `1`, and false-positive rate `0/5`.
  Aggregate value is clean `600`, corrupted `120480`, repaired `600`; signed/absolute change is
  `119880`, relative change `199.8`, and exact restoration is true.
- The current reviewed 26-record fixture remains unchanged and emits no findings because every
  exact series has insufficient history. Focused negatives cover zero/sign transitions, ordinary
  movement, unsupported extreme movement, entity/namespace/concept/unit/dimension/period-shape
  separation, insufficient history, no nonzero neighbor, amendment metadata, ambiguous chronology,
  and unrelated observations.
- Detector signature/source inspection proves it receives only sanitized input plus public config
  and imports no injector, manifest, scoring, or replay module. Serialized audit input/report checks
  exclude original records/values, mutation/factor, selection/rank, seed, severity, target
  fraction/count/cap, fault IDs, and manifest hashes. No detector-visible `source_status` or other
  exception/answer-key field was added.

### Files, tests, verification, and packaging

- Added nine runtime modules: `unit_drift_contract.py`, `unit_drift_series.py`,
  `unit_drift_math.py`, `unit_drift_injection.py`, `unit_drift_manifest.py`,
  `unit_drift_detection.py`, `unit_drift_scoring.py`, `unit_drift_replay.py`, and
  `unit_drift_research.py`; added `docs/faults/UNIT_DRIFT.md`; and added shared support plus eight
  focused test modules.
- Extended `schemas.py`, `hashing.py`, and `__init__.py` only for Unit Drift contracts, identities,
  and exports. `json_types.py` now removes insignificant fixed-point zeroes textually instead of
  calling context-sensitive `Decimal.normalize()`, preserving arbitrary finite coefficients while
  leaving all Milestone 1 golden vectors unchanged. Updated `docs/DECISIONS.md`,
  `docs/SERIALIZATION_AND_HASHING.md`, README, and this handoff. Added two explicit
  `LookAheadEvidence` type-narrowing assertions to existing tests after the shared finding-evidence
  union exposed four MyPy errors; Look-Ahead runtime behavior is unchanged.
- Added **109 tests**: contracts 25, injection 19, detection/isolation/hard negatives 21, scoring
  15, replay/research 12, integration 4, bounded properties/static safety 7, and subprocess
  determinism 6. Full suite: **735 passed** (626 prior + 109 new), no warnings.
- All required commands exited 0: normal/frozen sync, Ruff check/format check, strict MyPy, full
  pytest, lock check, CLI help, both reviewed-fixture checks, offline build, and `git diff --check`.
  Final outcomes: sync resolved 25/checked 24 packages; Ruff reported all checks passed and 69
  formatted files; MyPy found no issues in 67 source files; pytest collected and passed 735 tests;
  both fixture byte streams matched; and wheel/sdist build succeeded. Every requested canonical,
  serialization, hashing, golden, fixture, point-in-time, revision, audit, Look-Ahead, SEC,
  property, and subprocess suite also passed independently. During recovery, the first full MyPy
  run found the four stale Look-Ahead union accesses described above; the two narrowing assertions
  fixed them, and the affected suites plus final MyPy pass.
- Fresh subprocesses under `PYTHONHASHSEED` 0, 1, and 987654 produced identical complete clean,
  corrupted, manifest, audit-input, report, score, repaired, and impact artifacts. Reversed source
  order, different working directories, changed temp/output/user environment, repeated processes,
  and bounded Hypothesis seeds also preserve required identities/bytes.
- `uv build --offline` produced a 31-entry wheel with all 27 runtime modules and a 76-file sdist.
  Name/content scans found no reference/prompt/governance tree, local configuration/environment,
  caches/bytecode, accepted SEC cache, saved private case artifact, actual checkout path,
  credential, or secret. The sdist includes test source that deliberately names private field
  markers for negative isolation tests; it contains no populated private benchmark truth.
- A clean Python 3.12.13 virtual environment installed the wheel offline with only the declared
  Pydantic and HTTPX dependency families, imported `quantcheck`, ran CLI help, completed the full
  Unit Drift inject/audit/score/replay/aggregate path, reproduced exact clean replay, and imported
  none of pandas, NumPy, PyArrow, Streamlit, Typer, or Matplotlib. Milestone 5 added no dependency;
  `pyproject.toml` and `uv.lock` changes in the working tree belong to completed Milestone 4.

## Milestone 6 verification

### Scope and contracts

- Added the authoritative rebuilt-v1 contract in `docs/faults/DUPLICATE_OBSERVATIONS.md` for
  exactly `duplicate_observation` / `exact_occurrence_copy`, primary rule
  `occurrence.exact_duplicate`, and specification
  `quantcheck/duplicate-exact-occurrence-copy/v1`. Historical behavior is evidence only; no
  historical fixture eligibility count, ID, hash, metric, or artifact byte sequence is claimed.
- Added strict immutable `DuplicateFingerprint`, `DuplicateInjectionConfig`, `DuplicateMutation`,
  `DuplicateManifestEntry`, `DuplicateManifest`, `DuplicateEvidence`, `RecordCountResult`, and
  `RecordCountImpact` contracts. `Finding.evidence` gained a `DuplicateEvidence` branch
  (`record_ids` plural, `fingerprint_hash`, `group_size`) with its affected-record check extended
  accordingly; every existing Look-Ahead/Unit Drift finding shape is unchanged.
  `ScoreReport.scoring_spec_version` gained `"quantcheck/duplicate-scoring/v1"` alongside the two
  existing values. Existing generic `Finding`, `AuditReport`, `DetectionMetrics`,
  `ExactFindingMatch`, and `ScoreReport` envelopes are reused without changing their existing
  fields.
- One canonical fingerprint (`DuplicateFingerprint`, built by `duplicate_fingerprint`) is shared by
  injection eligibility and manifest-blind detection. It contains entity, concept
  namespace/concept, canonical value, unit, dimensions, period shape/dates, filing/availability
  dates, accession, and source name/locator — deliberately excluding `record_id` (so a generated
  copy always groups with its source), `form` (non-semantic), and any revision/source-row-key
  field (not present on `AuditInputRecord` at all, per the Milestone 2 audit boundary).
  `duplicate_fingerprint_hash` hashes it through the dedicated
  `quantcheck/duplicate-fingerprint/v1` namespace.

### Injection and private truth

- Eligibility groups clean records visible under `available_on <= as_of_date` by exact fingerprint
  hash; only singleton groups (fingerprint shared by no other clean record) are eligible sources.
  Severity fixes exact target fractions: low `0.01`, medium `0.05`, high `0.15`. The Decimal
  ceiling rule has minimum one, the eligibility bound, and a positive default cap of 100.
- Target selection ranks `(full SHA-256 digest, record_id)` over the dedicated
  `quantcheck/duplicate-target-selection/v1` namespace, spec version, non-negative seed, and clean
  record ID. Ranks are contiguous and zero-based.
- Injection **appends** exactly one created copy per selected source — it never replaces a record,
  because exact-occurrence-copy corruption is additive. The created record is identical to the
  original in every `FinancialFact` field except `record_id`; the derived ID uses the dedicated
  `quantcheck/duplicate-created-record/v1` namespace over `(original_record_id, spec_version,
  copy_ordinal=1)` but keeps the ordinary `rec_` prefix so it does not disclose an injected-row
  role. Unselected records remain byte-identical, and the clean input is never mutated.
- The private manifest stores clean/corrupted IDs and hashes, complete eligibility/configuration,
  the exact fingerprint hash, digest/rank, complete original/created records, and the reversible
  copy relationship (`DuplicateMutation`). Manifest roles are unambiguous by construction for this
  narrow subtype (one original, one created, group size two, zero removed, zero reference — no
  fabricated role is invented). Integrity validation recomputes the severity profile, target count,
  full ranking, fingerprint hash, created-record ID, and fault ID.

### Detection, scoring, replay, and controlled impact

- `detect_duplicate_observations` accepts only `AuditInputSnapshot` — there is no detector
  configuration, because exact fingerprint matching has no free parameter. It groups visible
  records by the same exact fingerprint hash and emits one finding per group of size two or more,
  with sorted affected record IDs, the fingerprint hash, group size, and the shared fingerprint
  evidence fields. Confidence is fixed `proven_by_contract`; public finding severity is fixed
  `medium` (ADR-004), because the specification assigns no severity-bearing signal to a duplicate
  finding the way Look-Ahead has leaked days or Unit Drift has a scale factor.
- **The checked-in reviewed fixture's Milestone 2 independent-occurrence pair (entity 3, Q1
  `Assets`) is byte-identical in every `AuditInputRecord` field**, so running the detector on the
  raw, uninjected clean fixture legitimately proves it as one natural exact group. This is by
  design, not a defect: injection eligibility and detector visibility are the same computation, so
  injection correctly excludes this pre-existing group as a source, while the detector correctly
  reports it as a true duplicate-fingerprint group. See ADR-004.
- Exact scoring requires Duplicate detector/class/subtype/rule/identity, the exact two-record
  affected-ID group, fixed severity/confidence, exact public fingerprint evidence, and stable
  finding identity. Duplicates cannot increase recall; distinct competitors are ambiguous. The
  false-positive denominator is every clean record belonging to a singleton fingerprint group,
  including selected targets (`eligible_record_count`) — the Unit Drift convention, not Look-Ahead's
  eligible-minus-target convention.
- `manifest_assisted_exact_duplicate_replay` validates private truth and the exact input artifact,
  then **removes** only the injected created records (never replaces, since injection never
  replaced anything), preserves every original and every legitimate clean duplicate group
  (including naturally occurring ones), is idempotent on the exact clean artifact, and reproduces
  clean canonical bytes, ID, and SHA-256 hash.
- `record_count_v0_1` (new) reports total occurrence count and duplicate-group count for one
  snapshot; `compare_duplicate_record_count` applies the identical pure calculation to
  clean/corrupted/repaired snapshots. The existing `aggregate_value_v0_1` /
  `compare_unit_drift_research` pure functions are reused **unmodified** for a double-counting
  demonstration, because an injected copy shares its original's `ComparableSeriesKey` and the
  existing method is already fault-family-agnostic — this satisfies the instruction to reuse rather
  than duplicate the calculation.

### Reviewed controlled case and isolation

- Focused case: source horizon `2024-08-31` (all 23 point-in-time-visible records from the 26-row
  reviewed fixture, after revision selection), high severity, seed 7. 21 eligible singleton
  fingerprints (the natural pair is excluded), 4 selected targets. Selected fault
  `fault_1060b0016101c508`; created record `rec_4b48250fd3675159`.
- Clean snapshot `snap_f61ce32ea30f8432`; corrupted snapshot `snap_1ce1415f3fe029cf` (27 records);
  manifest `man_9bcade00876bf919`; audit report `arep_3a83b9b91e37e28f` (5 findings — 4 exact
  matches plus the one natural unrelated group); score `score_0f8d9a664bd1e73c`; record-count
  impact `impact_d45a2505e5f6048a`.
- Exact score is 4 true positives, 0 false negatives, 1 false positive (the natural group, an
  honest unmatched finding, not a miss), precision `0.8`, recall `1`, F1 `8/9`, false-positive rate
  `1/21`. `record_count_v0_1` is total occurrences `23 → 27 → 23` and duplicate-group count
  `1 → 5 → 1`; both repaired values equal clean exactly. The double-counting reuse demonstration
  shows the corrupted aggregate equal to the clean aggregate plus the duplicated original's value,
  restored exactly after replay.
- Detector signature/source inspection proves it receives only sanitized input (no detector config
  parameter at all) and imports no injector, manifest, scoring, or replay module. Serialized audit
  input/report checks exclude original/created records, copy ordinal, selection/rank, seed,
  severity, target fraction/count/cap, fault IDs, and manifest hashes.

### Files, tests, verification, and packaging

- Added seven runtime modules: `duplicate_contract.py`, `duplicate_fingerprint.py`,
  `duplicate_injection.py`, `duplicate_manifest.py`, `duplicate_detection.py`,
  `duplicate_scoring.py`, `duplicate_replay.py`, and `duplicate_research.py`; added
  `docs/faults/DUPLICATE_OBSERVATIONS.md`; and added `tests/duplicate_support.py` plus eight
  focused test modules.
- Extended `schemas.py`, `hashing.py`, and `__init__.py` only for Duplicate contracts, identities,
  and exports. Updated `docs/DECISIONS.md` (ADR-004), `docs/SERIALIZATION_AND_HASHING.md`, README,
  and this handoff. The frozen canonical schema fields for `FinancialFact`/`AuditInputRecord`, the
  reviewed fixture bytes, point-in-time engine, audit boundary, Look-Ahead files, SEC adapter, and
  Unit Drift files were not changed for Milestone 6.
- Added **110 tests**: contracts 23, injection 14, detection/isolation/hard negatives 26, scoring
  15, replay/research 11, integration 7, bounded properties/static safety 8, and subprocess
  determinism 6. Full suite: **845 passed** (735 prior + 110 new), no warnings.
- All required commands exited 0: normal/frozen sync, Ruff check/format check, strict MyPy, full
  pytest, lock check, CLI help, both reviewed-fixture checks, offline build, and `git diff --check`.
  Final outcomes: sync resolved 25/checked 24 packages; Ruff reported all checks passed and 86
  formatted files; MyPy found no issues in 84 source files; pytest collected and passed 845 tests;
  both fixture byte streams matched (byte-identical to their Milestone 2/4 checked-in copies —
  Duplicate work did not touch either fixture); and wheel/sdist build succeeded. Every requested
  canonical, serialization, hashing, golden, fixture, point-in-time, revision, audit, Look-Ahead,
  SEC, Unit Drift, property, and subprocess suite also passed independently at its previously
  documented count.
- Fresh subprocesses under `PYTHONHASHSEED` 0, 1, and 987654 produced identical complete clean,
  corrupted, manifest, audit-input, audit-report, score, repaired, and record-count-impact
  artifacts. Reversed source order, different working directories, changed temp/output/user
  environment, and repeated fresh processes also preserve required identities/bytes.
- `uv build --offline` produced a 39-entry wheel with all 34 runtime modules and a 93-file sdist.
  Name/content scans found no reference/prompt/governance tree, local configuration/environment,
  caches/bytecode, accepted SEC cache, saved private case artifact, actual checkout path,
  credential, or secret; the sdist's literal `/Users/` and `/home/` strings are negative-test
  markers carried over from Milestone 3/4, not local paths, and the `.claude`/`.serena`/`.venv`
  strings that appear are Hatchling exclude-list text in `pyproject.toml`/`.gitignore`, not bundled
  directories (confirmed by directory listing).
- A clean Python 3.12.13 virtual environment installed the wheel with only the declared Pydantic
  and HTTPX dependency families, imported `quantcheck`, and completed the full Duplicate
  inject/audit/score/replay/record-count path (including exact clean replay) without importing
  pandas, NumPy, PyArrow, Streamlit, Typer, or Matplotlib. Milestone 6 added no dependency;
  `pyproject.toml` and `uv.lock` changes already present in the working tree belong to completed
  Milestone 4.

## Milestone 7 verification

### Scope and contracts

- Added the authoritative rebuilt-v1 contract in `docs/faults/REVISION_OVERWRITE.md` for exactly
  `revision_overwrite` / `later_vintage_in_earlier_state`, primary rule
  `revision.later_vintage_in_earlier_state`, and specification
  `quantcheck/revision-overwrite-later-vintage/v1`. Historical material is supporting evidence
  only; no historical fixture count, identifier, hash, metric, or artifact byte sequence is
  reproduced or claimed.
- Added strict immutable `EconomicFactKey`, `RevisionOverwriteInjectionConfig`,
  `RevisionOverwriteDetectorConfig`, `RevisionHistoryUnit`, `RevisionOverwriteMutation`,
  `RevisionOverwriteManifestEntry`, `RevisionOverwriteManifest`, and
  `RevisionOverwriteEvidence` contracts, plus `GrowthRankingConfig`, `GrowthRankingEntry`,
  `GrowthRankingResult`, and `GrowthRankingImpact` for the narrow controlled research result.
  Existing generic `Finding`, `AuditReport`, `DetectionMetrics`, `ExactFindingMatch`, and
  `ScoreReport` envelopes are reused; `ScoreReport` now explicitly admits the dedicated Revision
  Overwrite scoring specification.
- Added dedicated `runit_`, modified-record, fault, manifest, finding, report, score, research,
  and impact namespaces/helpers. The corrupted record retains the ordinary `rec_` prefix so it
  cannot act as a detector-visible injected-row flag.

### Eligibility, injection, and private truth

- Eligibility requires a source-declared `<lineage_id>#r<sequence>` history, an unambiguous exact
  economic key, preserved entity name/source name, monotonic declared filing/availability order,
  the latest historical revision visible at the source cutoff, and its immediate genuinely
  unavailable next revision. Clean availability must equal filing for both revisions; record/source
  row/accession/revision identities must be distinct; accessions must be non-null; values must
  differ; and the historical value must be nonzero.
- Relative size is exactly `abs(later - historical) / abs(historical)` at 50-digit Decimal working
  precision. Low/medium/high require `0.01`/`0.05`/`0.20` and select
  `0.02`/`0.05`/`0.10` of eligible units using Decimal ceiling, minimum one, a positive default
  cap of 100, and `(full SHA-256 selection digest, history-unit ID)` ranking with zero-based ranks.
- Injection substitutes the later value, filing date, form, accession, and source provenance into a
  newly identified replacement record while retaining historical availability. Economic context and
  unselected rows are unchanged; the legitimate later source record remains in the full supplied
  source history. Inputs are not mutated.
- The private manifest retains complete historical/later/corrupted records, eligibility proof,
  profile/configuration, selection digest/rank, reversible mutation, IDs, and clean/corrupted
  snapshot hashes. Validation recomputes all deterministic claims, including source-declared
  lineage/revision identities, relative size, ranking, modified-record ID, fault ID, and manifest
  ID.

### Detection, scoring, replay, and research

- `detect_revision_overwrite` accepts only `AuditInputSnapshot` and a strict empty public config.
  It has no injector, manifest, scoring, or replay dependency. It proves the public contradiction
  `available_on <= audit_as_of_date < filed_on` with `available_on < filed_on` and non-null
  accession provenance, emitting deterministic high-severity `proven_by_contract` evidence. The
  public boundary excludes historical/later records, values, lineage markers, source row keys,
  revision IDs, seed, severity, selection, ranks, and private hashes.
- Exact scoring requires every detector/class/subtype/rule/record/evidence/identity field to match.
  Near matches are false positives and misses are false negatives; repeated identical findings do
  not increase recall. The false-positive denominator is all eligible revision-history units,
  including selected units. A valid Look-Ahead finding on the same corrupted row remains a visible
  cross-detector signal and an unmatched Revision Overwrite primary false positive.
- Private manifest-assisted replay validates the exact corrupted artifact and replaces only exact
  corrupted rows. It is non-mutating and idempotent on the clean artifact; repaired canonical
  bytes, snapshot ID, and SHA-256 equal clean exactly.
- The growth example uses a pure frozen-vintage construction: each April historical clean,
  corrupted, or repaired state is preserved unchanged, and identical later-Q2 records selected
  from the full clean source history at the August research cutoff are added to every branch.
  `growth_ranking_v0_1` then uses the same Decimal `(current - prior) / abs(prior)` ranking for all
  branches. It is controlled research sensitivity only, not a backtest or trading claim.

### Reviewed controlled case

- Reviewed source: the existing 26-record synthetic fixture; historical cutoff `2024-04-30`,
  research cutoff `2024-08-31`, low severity, seed 7. The clean historical snapshot has 13 records,
  one eligible `E2-NI-Q1-2024` R1→R2 unit, and one selected fault. It replaces CIK 2 Q1
  `NetIncomeLoss` `250000.00` with the later `245000.00` provenance while retaining the original
  April availability.
- Clean snapshot `snap_9ccebecfbab28347` / hash
  `e9ce9ce358a916e819719a31aadc2b546205c99c8e3543add5eac09b2d322d3f`; corrupted snapshot
  `snap_558bb8cd38d16f45` / hash
  `0d7ea415a6003efcec753cbcd0e420391a6184b76236a23eb9b534767b447af9`; selection digest
  `76bbaf2380aaf04126d95af22898eb5a0c572eec1c53dc73ebf4429473f34661`; fault
  `fault_2b66b6f371c24e07`; manifest `man_7a0431e79f46f9f8`; audit input
  `audit_2e9f7fa542fca759`; report `arep_f2a9f4e8fdf453e4`; finding
  `find_d6371e871f8e9e26`; score `score_2f1ffc11323a1e9b`; impact
  `impact_0c79963fac7b9114`.
- Exact scoring is one TP, zero FP/FN, precision/recall/F1 `1`, and false-positive rate `0/1`.
  Clean/corrupted/repaired research result IDs are `rsch_ae4a3634ae67b578`,
  `rsch_92506ae6f3db3515`, and `rsch_ae4a3634ae67b578`. CIK 2 growth changes from `-1.5` to
  `-1.5102040816326530612244897959183673469387755102041`; maximum absolute change is
  `0.0102040816326530612244897959183673469387755102041`; rank and top-one membership remain
  unchanged; repaired research equals clean exactly.

### Tests, verification, packaging, and dependencies

- Added **116 Revision Overwrite tests**: contracts/private-integrity 23, eligibility/injection 32,
  detection/isolation/hard negatives 11, scoring/cross-detector behavior 22, replay/research 9,
  reviewed integration 7, bounded properties/static safety 6, and subprocess determinism 6. Full
  suite: **961 passed** (845 prior + 116 new), no warnings.
- Focused Revision Overwrite modules pass independently: 116 passed. Hard negatives cover correct
  historical/later states, later availability at cutoff, no later revision, malformed/independent
  histories, repeated/wrong ordering, same-day and delayed availability, zero/same/below-threshold
  values, changed entity/namespace/concept/unit/dimensions/period shape, changed entity/source
  context, reused accession, missing accession, amendment metadata, future exclusion, forged source
  row/revision identity, clean zero/negative fixture observations, and valid Look-Ahead cross-signals.
- Every required command exited 0: `uv sync --all-groups` (25 resolved/24 checked), frozen sync
  (24 checked), Ruff check, Ruff format check (103 files), strict MyPy (101 source files), full
  pytest (961), `uv lock --check` (25 resolved), CLI help, both fixture `--check` commands,
  `uv build --offline`, and `git diff --check`.
- Fresh subprocesses compare byte-identical clean/corrupted snapshots, manifests, audit inputs,
  reports, scores, repaired snapshots, frozen research inputs, and impacts under `PYTHONHASHSEED`
  0/1/987654. Reversed source order, different working directories, changed temporary/output/user
  environment values, and repeated fresh processes also preserve those logical artifacts.
- Offline build produced a 43-module wheel and a 110-entry sdist containing 58 test modules,
  including all eight Revision Overwrite runtime modules and focused tests. Archive path/content
  scans found zero recovery/reference/governance paths, local checkout/user paths, accepted SEC
  cache entries, or saved private case/manifest artifacts. A clean Python 3.12.13 wheel install
  pulled only the declared Pydantic/HTTPX families, passed the full Revision Overwrite
  inject/audit/replay smoke, ran CLI help, and imported none of pandas, NumPy, PyArrow, Streamlit,
  Typer, or Matplotlib.
- No dependency was added for Milestone 7. Existing `pyproject.toml`/`uv.lock` worktree changes are
  from completed Milestone 4. ADR-005 records the rebuilt Revision Overwrite provenance and
  frozen-vintage decisions.

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
- **The missing Look-Ahead fault document is reconstructed, not recovered.** Surviving evidence
  fixes period-end substitution, SHA-256 ranking, severity lag bands, exact scoring, the controlled
  count, and manifest-assisted replay. ADR-001 in `docs/DECISIONS.md` freezes the previously missing
  cap, ordinal, research-window, identity, and null conventions for rebuilt v1 artifacts.
- **Modified records use a dedicated namespace but the ordinary `rec_` prefix.** A dedicated
  visible `mod_` prefix would disclose injector role through `AuditInputSnapshot`, violating the
  stronger manifest-isolation invariant. Only the private manifest labels original and corrupted
  roles; collision separation remains in the hashed namespace.
- **SEC cache and occurrence identities are rebuilt v1 contracts.** ADR-002 freezes exact raw-byte
  hashing, the `accepted.json` layout, retry/pacing classification, Decimal JSON parsing, the
  `srow_` identity payload/duplicate ordinal, independent-occurrence treatment, and
  `available_on == filed_on`. These choices complete current requirements without copying
  historical bytes or expanding the frozen financial schemas.
- **Unit Drift local-series and metric details are rebuilt v1 contracts.** ADR-003 freezes exact
  duration-shape grouping, ambiguous-coordinate exclusion, nonzero neighbor search, zero-based
  ranking/default cap, correction tie-breaking, finding confidence/severity, the all-comparable
  clean denominator, aggregate zero policy, and fault-specific namespaces. It also records the
  exact fixed-point Decimal serialization correction. No historical Unit Drift artifact is claimed.
- **Duplicate Observations fingerprint, severity, denominator, and appended-copy injection shape
  are rebuilt v1 contracts.** ADR-004 freezes the exact fingerprint field list (excluding
  `record_id`, `form`, and any revision/source-row-key field not present on `AuditInputRecord`),
  the fixed `medium` public finding severity, the `eligible_record_count` false-positive
  denominator, the append-not-replace injection shape, and the dedicated created-record namespace.
  It also records the deliberate decision to let the reviewed fixture's Milestone 2
  independent-occurrence pair be found as one natural exact group by the raw, uninjected detector
  run, since injection eligibility and detector visibility are the same computation. No historical
  Duplicate Observations artifact is claimed.
- **Revision Overwrite source proof and frozen-vintage research are rebuilt v1 contracts.** ADR-005
  freezes explicit adjacent-lineage eligibility, relative-size/profile/count rules, private
  source-row/revision proof, the public temporal-contradiction evidence boundary, full-eligible-unit
  false-positive denominator, dedicated identities, retained-historical-availability substitution,
  and the separate frozen-vintage Q2 growth construction. No historical Revision Overwrite artifact
  is claimed.

## Known limitations

- Only the narrow Look-Ahead `period_end_substitution` subtype, narrow Unit Drift
  `value_scaled_unit_unchanged` subtype, narrow Duplicate Observations `exact_occurrence_copy`
  subtype, narrow Revision Overwrite `later_vintage_in_earlier_state` subtype, and narrow SEC
  adapter exist. The benchmark framework and dashboard/HTML remain absent. None of the historical
  0.1.0 metrics, hashes, or test totals is reproduced or claimed.
- Look-Ahead injection supports clean records whose source semantic is exactly
  `available_on == filed_on`. Delayed publication or other source-specific availability semantics
  are ineligible rather than guessed. The detector intentionally proves only
  `available_on == period_end < filed_on`; other timestamp-anomaly subtypes are outside v1.
- `availability_count_v0_1` is a controlled occurrence-count comparison using an explicit research
  cutoff within a later source horizon. It is not a generic vintage engine, ranking/backtester,
  trading result, alpha, return, Sharpe, loss, or production-impact claim.
- Exact replay is private manifest-assisted answer-key evidence. It does not establish automatic or
  detector-only repair, and public findings intentionally cannot reconstruct the hidden true record.
- Unit Drift uses only immediate local Decimal ratios. Simultaneously scaled adjacent observations
  can mask each other, while a one-neighbor endpoint can attribute the discontinuity to the clean
  neighbor. Exact scoring preserves those misses and false positives. The current reviewed fixture
  is a clean insufficient-history control; positive and aggregate evidence uses a focused synthetic
  series. No `source_status` exemption, acquisition inference, currency conversion, unit relabeling,
  taxonomy harmonization, fuzzy/ML detector, or automatic correction is implemented.
- `aggregate_value_v0_1` is a controlled sum of visible occurrences in one exact configured group,
  not statement construction, revision consolidation, a backtest, return, alpha, Sharpe ratio,
  portfolio result, financial-loss estimate, or production-impact claim.
- Duplicate Observations v0.1 supports exactly `exact_occurrence_copy`: one created copy per fault,
  matched by a fingerprint over public/semantic fields only. It is not fuzzy deduplication,
  business-key deduplication, near-duplicate detection, semantic similarity, amended-filing
  interpretation, restatement detection, entity resolution, or automatic cleanup of arbitrary
  production data. It cannot and does not infer which member of a duplicate group is the "bad" row
  to remove — that relationship is private manifest truth, recovered only through
  manifest-assisted replay. `record_count_v0_1` and the aggregate double-counting reuse are
  controlled occurrence/double-counting sensitivity evidence, not a trading, alpha, or
  financial-loss claim.
- `growth_ranking_v0_1` is a deliberately narrow frozen-vintage sensitivity demonstration. It uses
  one exact configured two-period duration context, requires one selected observation per entity and
  period, excludes zero-prior entities, and adds later current-period data identically to frozen
  clean/corrupted/repaired historical states. It is not a general vintage engine, statement
  reconstruction, revision consolidation, backtest, trading, return, alpha, Sharpe, or loss claim.
- The lost `docs/SERIALIZATION_AND_HASHING.md` could not be recovered (Milestone 1). The rebuilt
  contract is a reasoned reconstruction, not a restoration, and no historical golden value is
  reproducible. This applies equally to the Milestone 2 reviewed fixture: it is newly authored,
  not a recovery of the historical fixture's bytes.
- Look-Ahead, Unit Drift, Duplicate Observations, and Revision Overwrite manifest, finding, report,
  and research identifiers are now specified. Benchmark identifiers remain unspecified and must get
  dedicated helpers with their own contracts rather than borrowing these payloads.
- Revision-lineage declaration is a single, narrow convention (a `"#r<n>"` suffix inside
  `source_row_key`), not a general restatement detector. Revision Overwrite uses only adjacent,
  source-supported histories with clean filing-date availability, unchanged controlled context,
  distinct non-null accessions, and nonzero historical values. It cannot infer that two records are
  revisions from matching values or business-key fields alone, interpret amendments, reconstruct
  statements, resolve vendor vintages, or perform detector-only repair. The public detector proves
  a temporal contradiction; the private manifest proves the full revision relationship.
- The SEC adapter supports one CIK at a time, one exact Company Facts endpoint/envelope, entity-wide
  facts with no segments, explicit concepts/units/forms/date ranges/period shapes, and
  `available_on == filed_on`. It does not reconstruct statements, infer quarterly/annual or
  amendment/revision meaning, normalize scale/currency, harmonize concepts, parse filing HTML,
  support delayed/vendor availability, expire caches, download in parallel, or make intraday
  claims. Current SEC guidance must be rechecked before any future live/public run.
- The checked-in SEC fixture is a curated public field-shape excerpt, not an actual saved response.
  Live SEC download behavior has only been exercised through HTTPX `MockTransport`; no network or
  production-readiness attestation is claimed.
- `scripts/generate_reviewed_fixture.py` and `scripts/generate_reviewed_sec_fixture.py` are not
  included in the sdist (see the packaging decision above); they are repository development tools,
  not distributed capabilities. Both fixture byte streams remain reproducible from the installed
  wheel.
- Schemas require explicit `filed_on` and `available_on` but cannot prove the external rule that
  justifies a difference between them; adapters and injectors must supply that context later.
- Canonical strings are compared code point for code point; no Unicode normalization is applied, so
  NFC and NFD spellings of the same grapheme are distinct logical values.
- The CLI has no subcommands and is expected to be replaced entirely at the CLI milestone
  (Recovery Phase 9).
- CI (`.github/workflows/ci.yml`) has not yet run on GitHub Actions; it has only been validated by
  running its constituent commands locally.

## Exact next task

Implement Recovery Phase 8 — **benchmark artifacts only**: strict configuration expansion,
all-detector dispatch, public/private atomic persistence, structured failures, safe resume, and
public-only aggregation as defined in `RECOVERY_SEQUENCE.md`. Reuse the completed four
fault-family vertical slices without altering their contracts. Do not begin Phase 9 CLI or Phase 10
presentation work.

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

2026-08-07 (Milestone 7 complete — Revision Overwrite)
