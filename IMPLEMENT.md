# Implementation status

This is the operational handoff between Claude Code sessions. Keep it concise, factual, and current.

## Current phase

**Milestone 11 complete — Final Evidence and Release**

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
a controlled frozen-vintage `growth_ranking_v0_1` sensitivity comparison. Milestone 8 adds the
benchmark layer over those four completed slices: strict normalized configuration and deterministic
expansion, explicit development/validation seed classes with final seeds still prohibited, an
explicit four-family dispatcher that runs all four detectors on one sanitized audit input,
public/private atomic artifact persistence with immutable case evidence, structured failures, safe
resume, and aggregation rebuilt exclusively from public artifacts. It changes no injector,
detector, matcher, scorer, replay rule, or research calculation. Milestone 9 replaces the
placeholder `argparse` entry point with the contracted six-command Typer CLI (`ingest sec`,
`inject`, `audit`, `evaluate`, `benchmark run`, `benchmark smoke`, `explain`) and a saved-stage
`inject`/`audit`/`evaluate` workflow, in `docs/CLI_CONTRACT.md`/ADR-007. The saved-stage workflow
(`quantcheck.saved_case_workflow`) reuses the exact functions `dispatch_benchmark_case` uses, in the
same order, so a staged run and a direct dispatch produce byte-identical artifacts for all four
fault families. It changes no injector, detector, matcher, scorer, replay rule, or research
calculation, and adds no second serializer or persistence path; `benchmark_dispatch.py`'s five
single-case helpers were renamed to public names (no behavior change) specifically to make that
reuse possible without duplicating logic. Milestone 10 adds the public-only presentation layer
over the artifacts Milestone 8 already writes: a strict `public_artifact_reader` trust boundary
(role allowlist, layered path security, schema validation, SHA-256 verification, identity
linkage), one immutable shared `presentation` model, a deterministic self-contained
`html_summary` renderer, and a standalone read-only Streamlit dashboard in `dashboard/` (outside
the package, so `import quantcheck` never pulls in Streamlit). Both surfaces render the same
model, execute no scientific logic, recompute no metric, and work with the entire `private/`
tree deleted. It changes no injector, detector, threshold, matcher, scorer, denominator,
severity, replay rule, research calculation, benchmark identity, expansion, or aggregation
semantic, and adds no CLI root command. Milestone 11 adds the release-evidence layer over all
of it: a single narrow `release_gate` final-seed authorization, the frozen
`release_contract`/`release_config` release matrix, a byte-verified `release_freeze`
release-candidate record, the `release_run` held-out execution path, `release_evidence`
public-only verification and leak scanning, and `release_checksums`/`CHECKSUMS.md`. The
version is now `0.1.0`. It changes no scientific behavior; its one correction to completed
code moved reserved-seed enforcement from *representation* to *execution* (ADR-010), which is
proven to have changed no result by a byte comparison of two independent held-out runs.

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

## Milestone 8 verification

### Scope and contracts

- Recovery Phase 8 — **benchmark artifacts and orchestration only**. The milestone adds a
  benchmark layer *over* the four completed fault families and changes none of their science.
  The diff to pre-existing source files is purely additive: 1,012 inserted lines and zero deleted
  or modified lines across `src/quantcheck/schemas.py`, `hashing.py`, and `__init__.py`.
- Benchmark specification version `quantcheck/benchmark/v1`. Every benchmark artifact carries it.
- Strict Pydantic contracts follow the existing convention — public schemas in `schemas.py`,
  identifier helpers in `hashing.py`, behavior in dedicated modules. No loose dictionary is used
  where a strict schema pattern existed. `CaseConfig` was deliberately **not** reused or extended:
  it is frozen by the Milestone 1 golden vectors.
- Rejected rather than guessed: unknown fields, unsupported fixture identifiers, unsupported fault
  profiles, unsupported severities, unsupported component versions, incompatible profile/fixture
  combinations, duplicate severities/seeds/profiles, empty severity or seed dimensions, an empty
  benchmark matrix, a clean control outside its profile's own dimensions, a research method from
  another family, an impossible seed-class claim, and a case count disagreeing with its cases.

### Seed classes

- `classify_benchmark_seed` partitions development `0-9` and validation `100-109`.
- Final/release seeds `1000-1009` are rejected at both the seed classifier and the profile schema.
  Milestone 8 adds **no** override, force flag, or held-out authorization parameter; a static test
  asserts no benchmark entry point exposes one. Release authorization belongs to Milestone 11.
- Seeds outside every partition (`10`, `99`, `110`, `999`, `1010`) are rejected, not guessed.

### Expansion and identity

- One logical configuration expands into explicit immutable `BenchmarkCaseConfig` cases:
  fault profiles x severities x permitted seeds, plus one optional clean control per profile.
- Normalization sorts severities `low < medium < high`, seeds ascending, and profiles by fault
  profile, so reordering logically equivalent lists produces identical bytes and an identical
  `benchmark_id`. Duplicate dimensions are rejected rather than silently deduplicated.
- `benchmark_id` (`bench_`) is the SHA-256 stable ID of the normalized configuration.
  Expanded cases use `bcase_` in two namespaces so a clean control can never collide with its
  fault sibling. The aggregate uses `agg_`.
- Case identity covers every scientific input: benchmark, fixture configuration, injector and
  detector component versions, detector configuration, severity, seed, seed class, target cap, and
  research configuration. Output root, working directory, temporary directory, clock, username,
  hostname, environment ordering, and `PYTHONHASHSEED` are excluded — asserted both by a field
  audit and by subprocess tests. Runtime facts live only in `RuntimeMetadata`.
- Completed fault-family manifest identities are untouched; the benchmark wraps them, never
  redefines them.
- Cases execute in lexicographic `benchmark_case_id` order.

### Four-family dispatch and all-detector behavior

- `dispatch_benchmark_case` is an explicit closed dispatcher over the four completed slices. It is
  not a plugin framework and duplicates no scientific implementation.
- Order is load clean fixture -> completed injector -> `sanitize_for_audit` -> **all four
  detectors on that one sanitized input** -> one finalized combined `AuditReport` -> only then the
  private manifest reaches the family's own matcher, replay, and research code. The control flow
  physically enforces the boundary.
- The combined report carries the *primary* family's `detector_id`, `detector_version`, and
  audit-report namespace, which is what lets the three scorers that assert report detector identity
  accept it with no change to their code.
- Manifest isolation: no detector call takes a manifest, clean snapshot, seed, severity, or target
  parameter; `run_all_detectors(audit_input, case)` has no manifest channel. The persisted audit
  input is byte-identical to `sanitize_for_audit(corrupted_snapshot)`, and its records carry no
  orchestration-added field a detector could read as an answer key.
- Clean controls build the legitimate uncorrupted audit input, run all four detectors, retain every
  finding, and are scored with the same `DetectionMetrics` contract at zero injected faults. A
  control carries its fault sibling's full configuration, so its eligible-clean denominator is
  computed by the *same* frozen eligibility function the injector uses and is directly comparable.

### Cross-detector findings

- Secondary findings are preserved, never suppressed. The reviewed fixture's Milestone 2
  independent-occurrence pair is found as one natural exact group by the Duplicate detector on
  every reviewed-fixture case, and a Revision Overwrite corruption also produces a valid Duplicate
  signal. Under strict primary-class scoring these count as false positives.
- Tests assert that a wrong-class finding never becomes a true positive, that duplicate identical
  findings do not inflate recall, and that `true_positive_findings == true_positive_faults`.
- Re-scoring the benchmark's own combined report with the family scorer directly produces
  byte-identical output, proving the wrapper changed no scoring semantics.

### Artifact tree and privacy

- Public: `benchmark_config.json`, `case_matrix.json`, `runtime_metadata.json`,
  `aggregate_report.json`, `index.json`, and per case `case_config.json`, `audit_input.json`,
  `audit_report.json`, `score.json`, `research_summary.json` (fault cases only), `status.json`.
- Private: `clean_snapshot.json`, `corrupted_snapshot.json`, `manifest.json`,
  `repaired_snapshot.json`, `research_impact.json`, `private_index.json`, and `diagnostics.json`
  for failures. A clean control's private tree holds only its clean snapshot and private index,
  because the clean snapshot still carries `entity_name` and `source_row_key`.
- A public artifact reference is a validated relative POSIX path whose segment grammar cannot
  express `..`, a leading `/`, a backslash, or `~`, and which rejects `private` as a segment. The
  public index is therefore structurally incapable of addressing private storage. Public and
  private use separate rooted stores.
- Privacy tests scan the serialized bytes on disk, collecting every JSON object key across the
  whole public tree and asserting a 60-name private-only set is absent — manifest and injector
  truth, stripped source-record fields, value-bearing research truth, and private diagnostics. A
  companion test asserts those same names *are* present in the private tree, so the scan cannot
  pass vacuously. Public bytes are also scanned for the output root, `/Users/`, `/home/`,
  `/var/folders/`, `/private/tmp`, `/tmp/`, drive letters, tracebacks, and secret-like tokens.

### Persistence, failures, and resume

- Every write is canonical (one serializer, no second JSON representation), then temporary file in
  the destination directory, flush, `fsync`, atomic `os.replace`. No temporary file survives a run.
- Case artifacts are immutable: identical bytes are reused untouched (verified by unchanged mtime),
  conflicting bytes raise an integrity error, and **no force-overwrite option exists** — asserted
  by signature inspection. Runtime metadata, the aggregate report, and the public index are
  per-run derived artifacts and are replaced, because they are rebuilt from immutable evidence.
- The terminal success status is written last, after every required artifact is persisted; it is
  never written over a prior *successful* status. File existence alone is never treated as success.
- Failure stages: fixture load, expansion, dispatch, injection, audit sanitization, detection,
  scoring, repair, research, serialization, persistence, aggregation. Categories: configuration,
  no-eligible-targets, integrity, persistence, internal. Public failures carry a stage, category,
  normalized code, and a **fixed constant** message per category, so no exception text, value, or
  path can reach a public artifact. Private diagnostics keep the exception class and a
  whitespace-collapsed message, with no stack trace.
- One failed case does not stop the others: a three-profile run with a deliberately ineligible Unit
  Drift horizon fails that case and completes the other two. The failed case stays in the matrix
  and the status totals and is excluded from pooled detection metrics.
- Resume revalidates before reusing: status schema, case identity, every referenced path and
  content hash, the stored case configuration's exact bytes, audit-input/report/score linkage, the
  research summary, and the private index's artifacts and hashes. Tested for all four scenarios —
  valid prior success reused without dispatch, prior failure retried, partial output completed, and
  invalid prior success classified as an integrity failure whose conflicting artifacts are left
  untouched while aggregation independently downgrades it to incomplete.

### Aggregation

- `aggregate_from_public_artifacts` is handed the public store and can address nothing else. A test
  copies only the public tree to a fresh location with no `private/` directory at all and
  reproduces the saved aggregate bytes exactly.
- Counts micro-sum; metrics are computed once from the summed counts. A test computes the
  macro-average and asserts it differs, so switching to averaging would fail.
- Groups: overall, by fault profile, by severity, by seed class, and by seed. Every grouping is
  validated as a total partition of the configured matrix.
- Null conventions: precision is `TP / findings`, and with no findings it is `1` for a successful
  fault-free group and null for a fault-bearing group; recall is null with no injected faults; F1
  is null whenever precision or recall is null; false-positive rate is null with no eligible-clean
  denominator. Failed and incomplete cases remain in status totals and leave pooled metrics alone.
- Public research summaries expose only the research method, whether the controlled output changed,
  and whether exact replay restored it. Controlled counts and deltas stay private, because a
  Look-Ahead availability delta or a Duplicate record-count delta *is* the injected target count.

### Smoke benchmark evidence

`smoke_benchmark_config()` — 12 cases, entirely offline, no network. Four fault profiles at
development seed `0` and validation seed `100` (8 fault cases) plus one clean control per profile
(4 controls). Look-Ahead, Unit Drift, and Duplicate run at `medium`; Revision Overwrite runs at
`low` (see the limitation below). Measured by this implementation, not copied from any historical
document:

- `benchmark_id` `bench_654c76bb7eea251a`, `aggregate_report_id` `agg_1dedb2ca9aec9240`
- configured 12, successful 12, failed 0, incomplete 0
- injected faults 10, findings 20
- true-positive faults 10, false-negative faults 0
- true-positive findings 10, false-positive findings 10
- eligible clean denominator 118
- precision `0.5`
- recall `1`
- F1 `0.66666666666666666666666666666666666666666666666667`
- false-positive rate `0.084745762711864406779661016949152542372881355932203`
- research output changed in 8 of 8 fault cases; exact replay restored the clean output in 8 of 8
- by fault profile — Duplicate 4 faults / 7 findings / 4 TP / 3 FP / denominator 63; Look-Ahead
  2 / 5 / 2 / 3 / 37; Revision Overwrite 2 / 5 / 2 / 3 / 3; Unit Drift 2 / 3 / 2 / 1 / 15
- by seed class — development 5 faults / 12 findings / 5 TP / 7 FP / denominator 79; validation
  5 / 8 / 5 / 3 / 39
- clean controls — Unit Drift 0 findings (denominator 5); Look-Ahead, Duplicate, and Revision
  Overwrite 1 finding each (denominators 13, 21, 1). Every control finding is the reviewed
  fixture's documented natural exact-duplicate pair, which ADR-004 already records as legitimate
  detector behavior on clean data.

Precision below one is the honest consequence of retaining cross-detector findings. No scientific
behavior was tuned to improve it.

### Files added

- `src/quantcheck/benchmark_contract.py` — frozen benchmark conventions: specification version,
  seed partitions and classifier, the closed four-profile list, artifact tree names, required
  public artifacts, and the fixed redacted public failure messages.
- `src/quantcheck/benchmark_fixtures.py` — the closed registry of clean sources, plus the new
  deterministic five-observation Unit Drift benchmark series.
- `src/quantcheck/benchmark_expansion.py` — normalization, benchmark/case identity, profile-fixture
  compatibility, and deterministic expansion.
- `src/quantcheck/benchmark_dispatch.py` — the explicit four-family dispatcher, the all-detector
  run, the combined report, the clean-control score, and the sanitized research summary.
- `src/quantcheck/benchmark_store.py` — canonical atomic persistence with immutable-by-default
  semantics and no force-overwrite path.
- `src/quantcheck/benchmark_runner.py` — orchestration, the failure taxonomy, resume validation,
  and the public index.
- `src/quantcheck/benchmark_aggregate.py` — public-only aggregation and the null conventions.
- `src/quantcheck/benchmark_smoke.py` — the 12-case offline smoke configuration.

### Files changed

- `src/quantcheck/schemas.py` — added benchmark identifier patterns, the public relative-path
  validator, seed-partition ranges, benchmark Literal aliases, and the benchmark configuration,
  case, matrix, runtime, artifact-reference, failure, diagnostics, research-summary, score, status,
  index, and aggregate schemas. Additive only; no existing model changed.
- `src/quantcheck/hashing.py` — added the four benchmark namespaces and their ID helpers.
- `src/quantcheck/__init__.py` — added the benchmark exports.
- `docs/DECISIONS.md` — added ADR-006.
- `IMPLEMENT.md` — this handoff.

### Tests added

192 Milestone 8 cases across eight modules, plus `tests/benchmark_support.py`:

- `tests/test_benchmark_config.py` (38) — strict construction, unknown-field/unsupported-value
  rejection, duplicate and empty dimensions, incompatible combinations, seed classification,
  final-seed prohibition and the absence of any escape hatch, expansion coverage and ordering,
  reorder-invariance, stable and verifiable identities, and runtime exclusion from identity.
- `tests/test_benchmark_dispatch.py` (40) — all four families dispatch, all four detectors per
  case, the primary-family report identity, manifest isolation by signature and by type,
  cross-detector preservation, wrong-class and duplicate-finding scoring, unchanged family scorer
  semantics, clean-control behavior, control/fault denominator comparability, and the research
  adapter.
- `tests/test_benchmark_artifacts.py` (25) — public/private placement, index relative paths and
  hashes, private-reference and traversal rejection, serialized-byte privacy scans in both
  directions, local/temp/home path scans, immutable reuse and conflict rejection, absence of a
  force option, store-root escape rejection, no leftover temporary files, and status-written-last.
- `tests/test_benchmark_failure_resume.py` (35) — failure isolation, visibility in totals,
  exclusion from pooled metrics, public redaction, private diagnostics, per-case retry policy,
  one-benchmark-per-root, valid-success reuse, partial-output completion, corrupt and edited
  prior success, tampered and missing private evidence, missing private index, immutable conflict
  rejection during rerun, stale diagnostics, resume disabled, and the exception classification table.
- `tests/test_benchmark_aggregate.py` (15) — public-only rebuild with no private tree, disk-only
  byte reproduction, micro-summing versus macro-averaging, every grouping partition, seed-class
  separation, clean-control contribution, and the exact null conventions.
- `tests/test_benchmark_smoke.py` (14) — the documented 12-case shape, both seed classes, no
  held-out seed, offline success, recall and cross-detector false positives, research outcomes,
  repeated-run reuse, output-root independence, unrelated parent files, public-only reconstruction,
  and canonical round-tripping of every public artifact.
- `tests/test_milestone8_properties.py` (14) — Hypothesis properties for seed classification,
  reorder-invariance, expansion size and ordering, case identity, aggregate null conventions across
  arbitrary counts, and public-path safety; plus static checks that no benchmark module reads the
  clock or a random source, imports a heavy dependency, or admits a manifest into a detector path.
- `tests/test_milestone8_determinism_subprocess.py` (11) — the whole benchmark in fresh processes
  under `PYTHONHASHSEED` `0`/`1`/`987654`, different and deeply nested output roots, changed
  working directory, `TMPDIR`, `USER`, `LOGNAME`, `HOSTNAME`, unrelated parent-directory files,
  repeated processes, public-only rebuild, and reversed configuration lists.

### Commands run

All from the project root with a writable temporary `uv` cache; every command exited `0`.

- `uv sync --all-groups` — resolved 25 packages, checked 24.
- `uv sync --frozen --all-groups` — checked 24 packages.
- `uv run ruff check .` — all checks passed.
- `uv run ruff format --check .` — 120 files already formatted.
- `uv run mypy src tests` — success, no issues in 118 source files.
- `uv run pytest` — **1,153 passed**.
- `uv lock --check` — resolved 25 packages, lockfile current.
- `git diff --check` — clean.
- `uv run python scripts/generate_reviewed_fixture.py --check` — matches regenerated bytes.
- `uv run python scripts/generate_reviewed_sec_fixture.py --check` — matches curated bytes.
- `PYTHONHASHSEED=1 uv run pytest` and `PYTHONHASHSEED=987654 uv run pytest` — 1,153 passed each.
- Focused regressions — golden/serialization/round-trip/json-types 133; schemas 95; hashing 43;
  fixtures 40; point-in-time 15; revision ordering 23; audit boundary 15; properties 14; package 1.
- Family regressions by keyword — Look-Ahead 104, Unit Drift 121, Duplicate 123, Revision
  Overwrite 112, SEC 108, benchmark 174.
- Prior-suite regression with all eight Milestone 8 modules ignored — **961 passed**, so every
  Milestone 0-7 test remains green and none was weakened.
- `uv build` — wheel and sdist built; the wheel contains the eight benchmark modules and no
  recovery or reference material.
- Clean-wheel check — installing the built wheel into a fresh virtual environment and running the
  smoke offline reproduced `bench_654c76bb7eea251a`, 12/12 successful, precision `0.5`, recall `1`,
  a matching public-only aggregate rebuild, and no heavy dependency import.

### Determinism evidence

Repeated runs, reversed configuration lists, reordered mappings, different and deeply nested output
roots, a changed working directory, unrelated parent-directory files, canonical
serialization/reload, public-only disk aggregation, fresh subprocesses, and `PYTHONHASHSEED`
`0`/`1`/`987654` all preserve the benchmark id, case ids, per-case public bytes, and aggregate
bytes. A byte-identical successful rerun reuses all 12 cases after full validation and dispatches
none.

### Dependencies and packaging

No runtime or development dependency was added, removed, or upgraded. `pyproject.toml` and
`uv.lock` are unchanged. The benchmark layer uses only the standard library and Pydantic, which was
already present.


## Milestone 9 verification

### Scope and contracts

- Added the rebuilt v1 CLI contract in `docs/CLI_CONTRACT.md` and ADR-007 in `docs/DECISIONS.md`.
  `RECOVERY_SEQUENCE.md` fixes Phase 9's scope in one sentence and names no command, flag, or exit
  code; no current `docs/CLI_CONTRACT.md` existed before this milestone. Historical evidence under
  `reference/` (a lost six-command Typer CLI, exit codes `0/2/3/4/5/10`) is used as design
  inspiration only — no historical flag syntax, JSON field, or exit code is claimed byte-identical.
- Replaced the Milestone 0 placeholder `argparse` entry point in `src/quantcheck/cli.py` with a
  Typer application exposing exactly six root commands: `ingest sec`, `inject`, `audit`, `evaluate`,
  `benchmark run`, `benchmark smoke`, plus `explain`. No `--version` flag, no `snapshot`/`score`/
  `damage`/`run-case`/`demo`/dashboard/HTML/aggregate-rebuild/release/force-overwrite command, and no
  flag anywhere that authorizes a held-out or final/release seed. The installed console script keeps
  pointing at `quantcheck.cli:main`, unchanged in `pyproject.toml`; `main` now wraps a Typer `app`
  rather than `argparse.ArgumentParser`, invoked in non-standalone mode so it stays a plain,
  directly-testable `argv -> int` function rather than one that calls `sys.exit` itself.

### Saved-stage workflow

- Added `src/quantcheck/saved_case_workflow.py`: `inject_case`, `audit_case`, `audit_snapshot`, and
  `evaluate_case` over the existing `BenchmarkCaseConfig` — the same fully expanded case type
  `expand_benchmark_cases` already produces. No second case-definition format was created.
- Every scientific step is a direct call into the exact function `dispatch_benchmark_case` uses, in
  the same order, over the same persisted evidence: `clean_snapshot_for_case`, `inject_for_case`,
  `sanitize_for_audit`, `run_all_detectors`, `combined_audit_report`, `score_for_case`,
  `replay_for_case`, `research_for_case`, `fault_score`, `research_summary_for_case`. To make this
  reuse possible without either duplicating logic or reaching into another module's private names,
  `benchmark_dispatch.py`'s five single-case helpers (`_clean_snapshot`, `_inject`, `_score`,
  `_replay`, `_research`, plus `_eligible_clean_denominator`, `_control_score`, `_fault_score`,
  `_research_summary`, `_lookahead_research_date`) were renamed to their public forms — a
  behavior-preserving rename, verified by rerunning the full pre-existing Milestone 8 benchmark
  suite unchanged before writing any Milestone 9 test. `run_all_detectors` now takes
  `detector_configs: BenchmarkDetectorConfigs` directly instead of a full `case`, so a standalone
  audit over an arbitrary snapshot (not produced by `inject`) can reuse it without fabricating a
  benchmark case; `dispatch_benchmark_case` itself is otherwise unchanged and was re-verified
  byte-identical.
- `inject` persists the public `case_config.json` and, for a fault case, the private
  `corrupted_snapshot.json`/`manifest.json`; a `clean_control` case stops after the private
  `clean_snapshot.json`. `audit` reads only the clean-or-corrupted snapshot `inject` already
  persisted (or, in its `--case`/`--snapshot`/`--output` form, an arbitrary canonical
  `DatasetSnapshot`), sanitizes it exactly once, and runs the manifest-blind detector tuple — it
  never imports or constructs a manifest type. `evaluate` requires a finalized public
  `audit_report.json` already on disk, is the first saved-stage command that reads the manifest, and
  rejects a `clean_control` case outright (it has no manifest; its terminal saved-stage artifact is
  its own `audit` output). Saved-stage output reuses the exact `AtomicArtifactStore`
  public/private split and `cases/<benchmark_case_id>/<artifact>.json` layout the benchmark runner
  already uses.
- **Equivalence is verified directly, not just documented.** For all four fault families, a staged
  `inject -> audit -> evaluate` run over the CLI and a single `dispatch_benchmark_case` call produce
  byte-identical `audit_input`, `audit_report`, `score`, `research_summary`, `clean_snapshot`,
  `corrupted_snapshot`, `manifest`, `repaired_snapshot`, and `research_impact` bytes
  (`tests/test_cli_saved_stage.py`), and a clean control's staged `audit_report` matches its direct
  dispatch counterpart too.

### SEC ingestion, benchmark, and explain

- `ingest sec` wraps `SecCompanyFactsAdapter` exactly (`fetch`/`replay`/`normalize`/
  `build_snapshot`), unchanged from Milestone 4. `SecNormalizationConfig` is a plain dataclass, not a
  Pydantic schema, so its CLI-input JSON is validated by an explicit exact-field-set check
  (`load_sec_normalization_config`) before construction — this widens nothing the adapter already
  accepted. `--replay-only` wraps the adapter's own offline `.replay()`; every SEC test pre-seeds the
  raw cache before invoking the CLI, so none of them can make a live network request. `--refresh` and
  `--replay-only` are mutually exclusive.
- `benchmark run`/`benchmark smoke` call `run_benchmark`/`smoke_benchmark_config` unchanged, building
  `RuntimeMetadata` from the clock only at the CLI boundary (never inside the library). There is no
  committed `configs/smoke.json`; `benchmark smoke` calls the existing in-code
  `smoke_benchmark_config()` builder directly, matching the pre-existing offline smoke test. Both
  commands preserve resume/revalidation, structured failures, and public/private separation
  unchanged, and both exit `5` whenever the returned aggregate's
  `failed_case_count + incomplete_case_count > 0` — decided from the aggregate's own counts, never
  from a raised exception, since per-case failures never propagate out of `run_benchmark`.
- `explain` reads only `public/`: a saved finding's `rule_id`/`severity`/`confidence`/`explanation`/
  `affected_record_ids`, or a case's fault profile, finding count/IDs, and (for a benchmark-run tree)
  its terminal `status.json` outcome. It never loads a manifest, never reruns a detector, and never
  reruns the benchmark; deleting the entire private tree does not affect it (tested directly).

### Machine/human output and exit codes

- Added `src/quantcheck/cli_support.py`: exit-code constants, `emit_json` (a thin wrapper around the
  existing `canonical_json_bytes` — no competing `json.dumps`-based serializer), strict config
  loaders (`load_case_config`, `load_benchmark_config`, `load_sec_normalization_config`,
  `load_json_file`, `load_staged_case_config`, `load_case_config_by_id`), `build_runtime_metadata`,
  and `classify_cli_exception`/`fail` — the single exit-code/message decision point every command
  shares. `load_json_file` reuses `parse_canonical_json` directly, which rejects a JSON float outright
  (verified by test) rather than silently widening it into a `Decimal` field.
- Exit codes: `0` success; `2` user/configuration input (bad path, bad JSON, unknown field, invalid
  enum, prohibited/duplicate seed, broken artifact identity); `3` saved-artifact/integrity/
  persistence (`SavedStageError`/`ArtifactIntegrityError`/`ArtifactPersistenceError`); `4` SEC
  source/cache/normalization (`SecAdapterError` and subclasses); `5` a structured
  failed-or-incomplete benchmark outcome; `10` unexpected internal error, reported with the fixed
  sentence "an unexpected internal error occurred" and never the exception's own message. `--help`
  exits `0`; a bare command group with no subcommand (including bare `quantcheck`) shows the same
  help but exits `2` — standard Click/Typer `no_args_is_help` usage-error semantics, not a bespoke
  choice.
- Every `--json` payload is an explicit finite field allowlist — a plain `dict[str, object]` passed
  straight to `canonical_json_bytes` — verified directly for `inject` and `evaluate` by asserting the
  exact key set. Human output is one stable line of plain text per command, no ANSI, no absolute
  local path.

### Privacy verification

- `audit` (both forms) is manifest-blind at the function-signature level: `audit_snapshot` and
  `audit_case` have no `manifest` parameter, verified by static introspection
  (`test_audit_is_manifest_blind_at_the_function_boundary`). `evaluate_case` also has no
  caller-supplied `manifest` parameter — it reads the manifest from disk only after confirming a
  finalized audit report exists — while its own delegates (`score_for_case`, `replay_for_case`) do
  require one, confirmed directly.
- Adversarial stdout scans (`tests/test_cli_privacy.py`), run across the full staged workflow for all
  four fault families, prove that no CLI stdout (human or `--json`) ever contains a manifest field
  name (`original_record`, `corrupted_record`, `mutation`, `target_rank`, `selection_digest`), the
  private `manifest_id`, an absolute local/home path, or (for the three families whose injector
  replaces the original record) the pre-injection `record_id`. `duplicate_observation` is a
  documented, deliberate exception to the last check: its injector *adds* a copy rather than
  replacing the original, so the original record's own `record_id` legitimately remains visible as
  one half of the real duplicate pair in public detector evidence — proving this required
  understanding the family's injection shape, not weakening the check.
- `ingest sec` output never contains the cache directory path or any path under the test's temporary
  root, verified directly against both the JSON payload and the human line.

### Files added

- Runtime: `saved_case_workflow.py`, `cli_support.py`; `cli.py` fully rewritten (Typer, replacing the
  Milestone 0 `argparse` placeholder).
- Contracts: `docs/CLI_CONTRACT.md`; ADR-007 in `docs/DECISIONS.md`.
- Tests: `tests/cli_helpers.py`, `tests/test_cli_config.py`, `tests/test_cli_saved_stage.py`,
  `tests/test_cli_benchmark.py`, `tests/test_cli_sec.py`, `tests/test_cli_explain.py`,
  `tests/test_cli_privacy.py`, `tests/test_cli_subprocess.py`; `tests/test_cli.py` rewritten for the
  new CLI's actual (Click/Typer `no_args_is_help`) behavior, replacing its Milestone 0 assertions.

### Files changed

- `src/quantcheck/benchmark_dispatch.py` — five private single-case helpers renamed to public names
  (see above); `run_all_detectors` takes `detector_configs` instead of `case`. Behavior-preserving:
  `dispatch_benchmark_case`'s own output is unchanged and the full pre-existing Milestone 8 test
  suite passes unmodified except for the two tests that asserted the old private names/signature
  directly (`tests/test_benchmark_dispatch.py`), which were updated to the new public names.
- `tests/test_milestone8_properties.py`, `tests/test_schemas.py` — the two "no heavy dependency
  imported" checks were moved into a fresh subprocess. Both previously asserted `typer` absent from
  the whole process's `sys.modules`; once any test file in the same pytest run legitimately imports
  `quantcheck.cli` (which does need Typer), that global check fails for a reason unrelated to the
  module actually under test. The subprocess form checks only what `import quantcheck`/the benchmark
  modules themselves pull in, which is unchanged.
- `pyproject.toml`, `uv.lock` — added `typer>=0.12,<1` (resolved `0.27.1`) as a direct runtime
  dependency. No other dependency changed.
- `src/quantcheck/__init__.py` — exported the new public API surface
  (`saved_case_workflow`/`cli_support` symbols, the renamed `benchmark_dispatch` helpers).
- `README.md`, `docs/DECISIONS.md`, `IMPLEMENT.md` — current CLI usage/status, ADR-007, this handoff.

### Tests and commands

- Added **93 tests**: config loading/seed taxonomy 13, saved-stage workflow/equivalence 18,
  benchmark run/smoke 8, SEC ingestion 7, explain 5, privacy 25, subprocess/determinism 15, plus 2
  net new root-CLI tests replacing the 3 Milestone 0 ones. Full suite: **1,246 passed** (1,153 prior
  + 93 new), no warnings.
- Every required command exited 0 individually: `uv sync --all-groups`, `uv sync --frozen
  --all-groups`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`
  (128 source files, no issues), `uv run pytest` (1,246 passed), `uv lock --check`,
  `uv run quantcheck --help`, `uv build --offline`, `git diff --check`.
- Focused/positive-path re-runs also passed independently: the complete pre-Milestone-9 suite (1,153
  tests) unchanged in behavior; every new `tests/test_cli_*.py` module standalone; the four-family
  saved-stage equivalence tests; the offline SEC ingestion suite (hermetic, no network); benchmark
  run/smoke including a tampered-prior-success case correctly producing exit `5`; and the adversarial
  privacy scans.

### Determinism and subprocess evidence

- `tests/test_cli_subprocess.py` runs the CLI as a real subprocess (`python -m quantcheck.cli` and
  the installed `quantcheck` console script), asserts stdout under `--json` is exactly one parseable
  JSON line with stderr kept separate and traceback-free, and re-runs the full
  `inject`/`audit`/`evaluate` saved-stage workflow under `PYTHONHASHSEED` `0`, `1`, and `987654`,
  confirming byte-identical `audit_report.json`, `score.json`, `research_summary.json`, and
  `manifest.json` across all three. Option-order independence (`--json` before vs. after
  `--output`) was also verified directly.

### Packaging and dependencies

- `uv build --offline` produced a wheel containing all 53 runtime modules (the 51 from Milestone 8
  plus the two new `cli_support.py`/`saved_case_workflow.py`; `cli.py` was rewritten, not added) plus
  dist-info, and an sdist containing
  the full `src/`/`tests/` tree under the existing allowlist (no `pyproject.toml` allowlist change was
  needed). Archive scans found no `reference/`, `.claude`, `.serena`, `/Users/`/`/home/` local paths,
  private keys, or secret-shaped strings; the only "manifest" hits in either archive are the four
  legitimate `*_manifest.py` source module names.
- A clean `uv venv --python 3.12` install of the wheel pulled exactly the declared dependency
  families — Pydantic, HTTPX, and now Typer (`typer` 0.27.1, plus its own `rich` 15.0.0,
  `shellingham` 1.5.4, `annotated-doc` 0.0.5, `markdown-it-py` 4.2.0, `mdurl` 0.1.2, `pygments`
  2.20.0) — imported `quantcheck` without pandas/NumPy/PyArrow/Streamlit/matplotlib, ran
  `quantcheck --help`, and ran a full `benchmark smoke` to completion with exit 0.
- No environmental retries were needed.


## Milestone 10 verification

### Scope and contracts

- `RECOVERY_SEQUENCE.md` fixes Phase 10's scope in one sentence and names no artifact format,
  path rule, null policy, or launch command. ADR-008 in `docs/DECISIONS.md` and the new
  `docs/DASHBOARD_AND_HTML.md` freeze the rebuilt v1 presentation contract. Historical evidence
  under `reference/` (a lost `public_artifact_reader.py`/`presentation.py`/`html_summary.py`/
  `dashboard/app.py` set keyed on `public/artifact_index.json`, and a `streamlit>=1.60,<2`
  runtime range) is design evidence only: the rebuilt public tree's actual index is
  `public/index.json`, and no historical byte, hash, metric, test count, or dependency version
  is claimed or reproduced.
- Presentation only. No fault family, injector, detector, threshold, matching rule, scoring rule,
  false-positive denominator, severity semantic, research calculation, replay rule, benchmark
  case identity, expansion, or aggregation semantic changed. No CLI root command was added: the
  surface is still exactly `ingest`, `inject`, `audit`, `evaluate`, `explain`, `benchmark`
  (verified directly against the Typer app). No force-overwrite path exists. Reserved final
  seeds `1000-1009` remain rejected and none was executed. Package version stays `0.1.0.dev0`.

### Strict public artifact reader

- Added `src/quantcheck/public_artifact_reader.py`. It reuses the existing public Pydantic
  schemas, the existing canonical parser, the existing `AtomicArtifactStore`, and the existing
  SHA-256 identity; it defines no second artifact format and no loose-dictionary path. It reads
  either an output root containing `public/` or a copied-out public tree, the same convention
  `aggregate_from_public_root` already uses.
- Root artifact filenames moved into `benchmark_contract.PUBLIC_ROOT_ARTIFACT_NAMES` so the
  runner and the reader share one mapping; `benchmark_runner`'s five `BENCHMARK_*_PATH`
  constants now reference it. Behaviour-preserving: the full pre-existing benchmark and CLI
  suites pass unchanged.
- Role allowlist is exactly `PUBLIC_ROOT_ARTIFACT_NAMES` + `PUBLIC_CASE_ARTIFACT_NAMES`. An
  unknown role is rejected, never skipped or guessed.
- Path security is layered and never repairs: the existing `PUBLIC_RELATIVE_PATH_PATTERN` makes
  `..`, absolute POSIX paths, backslashes, drive letters, and `~` unrepresentable; a `private`
  segment is refused separately; and the resolved location must stay under the resolved root,
  which catches symlink escapes and symlinks into the private tree.
- Tree-level integrity raises `PublicArtifactError` (missing/malformed root artifact, bad index
  hash, missing indexed artifact, unknown or mispathed role, cross-case reference, benchmark
  identity disagreement, status naming a different case). A case whose *success claim* is
  unsubstantiated becomes `incomplete` - exactly what `benchmark_aggregate` independently does -
  so the reader can never contradict the saved aggregate about a case outcome. A new check also
  refuses a tree whose saved `aggregate_report.json` status counts disagree with its saved case
  statuses.
- The reader's result carries no filesystem root, destination, or temporary path at all.

### Shared presentation model, HTML, and dashboard

- Added `src/quantcheck/presentation.py`: `BenchmarkPresentation` and its parts, built on the
  existing `CanonicalModel` (frozen, `extra="forbid"`, strict), so the whole model serializes
  through the existing canonical serializer and privacy scans run against real bytes. Overall
  and grouped metrics are the saved aggregate's own numbers copied across, never recomputed;
  case order follows the saved matrix. `schemas.py` was not touched (its golden vectors are
  frozen).
- Metrics stay `Decimal | None` end to end, never through binary `float`. An undefined metric
  stays `None` in the model - never `0`, `NaN`, `""`, or `"n/a"`; only rendered text says `n/a`.
- Added `src/quantcheck/html_summary.py`: UTF-8, embedded CSS only, no JavaScript, no remote or
  CDN resource, no render timestamp, no random identifier, no environment path, every
  artifact-derived string escaped. Output reuses the existing persistence conventions - atomic
  write, identical existing bytes reused untouched, conflicting bytes rejected as
  `ArtifactIntegrityError`, no partial file on failure, and no force option.
- Added `dashboard/app.py` and `dashboard/__init__.py`: a thin standalone read-only Streamlit
  app requiring an explicit `--artifacts` root, using Streamlit-native components only, with
  overview, status counts, overall metrics, saved group summaries, case filters, selected-case
  summary/score/sanitized research, findings with evidence and explanations, failure and
  incomplete information, methodology, privacy boundary, and known limitations. Every filter
  defaults to showing everything. `.streamlit/config.toml` disables usage telemetry.
- Added `scripts/render_html_summary.py`, matching the existing `scripts/` pattern. Neither
  surface is wired into the CLI.

### Privacy and isolation evidence

- The presentation code's transitive `quantcheck` import closure is exactly
  `benchmark_contract`, `benchmark_store`, `hashing`, `json_types`, `schemas`, `serialization`,
  and `unit_drift_math` - no manifest, injector, detector, scorer, replay, or research module.
  That closure is pinned by test, so a future import cannot widen it unnoticed.
- Reader, model, HTML, and dashboard all succeed against a copy of `public/` with the entire
  private tree physically absent (0 manifests, 0 private artifacts, 73 public files), producing
  a byte-identical model and byte-identical HTML.
- Serialized model, rendered HTML, and sanitized Streamlit text contain no manifest id, fault id,
  or injector selection digest; no manifest/injector field name; no private exception message or
  class; and no local filesystem path.
- **Pre-injection record identity is checked per case, not page-wide, and this was verified
  rather than assumed.** An initial page-wide scan flagged six `rec_*` ids. Tracing each one
  showed Look-Ahead never leaks its originals; `duplicate_observation` legitimately publishes
  its original (its injector *adds* a copy, so the original is one half of the real duplicate
  pair - the same documented exception as `docs/CLI_CONTRACT.md`); and each Unit Drift original
  appeared only in the *clean control* (where that record is genuinely clean and public) and in
  the *other seed's* case (where it was never a target and is an ordinary neighbour). Neither
  appeared in its own case. The test now asserts the property that actually matters: the record
  a case's own injector replaced never appears in that case's own output.

### Smoke and public-only demonstration

Ran the existing committed 12-case offline smoke configuration (development seed `0`, validation
seed `100` only) into a fresh temporary root via `quantcheck benchmark smoke`:

- benchmark id `bench_654c76bb7eea251a`, aggregate report id `agg_1dedb2ca9aec9240`;
- 12 configured, 12 succeeded, 0 failed, 0 incomplete; 8 fault cases, 4 clean controls;
- precision `0.5`, recall `1`, F1 `0.66666666666666666666666666666666666666666666666667`,
  false-positive rate `0.084745762711864406779661016949152542372881355932203`.

The presentation model's headline numbers were asserted equal to the saved aggregate field by
field. Copying only `public/` to a separate location (private tree absent, 0 manifests) and
repeating reader, model, HTML, and dashboard validation produced an identical aggregate, a
byte-identical model, and identical HTML. HTML SHA-256
`d3e433c80a79de47fd3566788938db7497c98fe4a2acd449abbd2b6a3d926107` was produced identically from
both trees, into two different destinations, under `PYTHONHASHSEED` `0`, `1`, and `987654` (six
combinations, one hash), and again from a clean wheel install with Streamlit absent entirely.
No metric is hard-coded from historical 0.1.0 documentation; these are this implementation's own.

### Files added and changed

- Runtime added: `src/quantcheck/public_artifact_reader.py`, `src/quantcheck/presentation.py`,
  `src/quantcheck/html_summary.py`.
- Outside the package, added: `dashboard/__init__.py`, `dashboard/app.py`,
  `scripts/render_html_summary.py`, `.streamlit/config.toml`.
- Changed: `src/quantcheck/benchmark_contract.py` (new `PUBLIC_ROOT_ARTIFACT_NAMES` mapping),
  `src/quantcheck/benchmark_runner.py` (five path constants now reference that mapping),
  `src/quantcheck/__init__.py` (new exports, updated docstring), `pyproject.toml` (new
  `dashboard` dependency group; sdist exclude widened to `/dashboard`, `/scripts`, `/.streamlit`),
  `uv.lock`, `README.md`, `docs/DECISIONS.md` (ADR-008), `IMPLEMENT.md`.
- Docs added: `docs/DASHBOARD_AND_HTML.md`.
- Tests added: `tests/presentation_helpers.py`, `tests/test_public_artifact_reader.py`,
  `tests/test_presentation.py`, `tests/test_html_summary.py`, `tests/test_dashboard.py`,
  `tests/test_presentation_isolation.py`.

### Tests and commands

- Added **145 tests**: reader/path-security/integrity 48, presentation model 17, HTML
  determinism/escaping/privacy/output 36, Streamlit AppTest 21, isolation/privacy 23. Full
  suite: **1,391 passed** (1,246 prior + 145 new). No prior test was weakened or removed.
- Every required command exited 0: `uv sync --all-groups`, `uv sync --frozen --all-groups`,
  `uv run ruff check .`, `uv run ruff format --check .` (142 files), `uv run mypy src tests`
  (137 source files, no issues), `MYPYPATH=src uv run mypy --explicit-package-bases dashboard
  scripts` (5 source files, no issues), `uv run pytest` (1,391 passed), `uv lock --check`,
  `uv run quantcheck --help`, `uv build --offline`, `git diff --check`.
- Focused re-runs all passed independently: schema/serialization/golden/hashing 285;
  fixtures/point-in-time/audit-boundary 93; Look-Ahead 85; Unit Drift 103; Duplicate 96;
  Revision Overwrite 104; SEC 97; benchmark layer 167; CLI 96; packaging 1; all determinism
  subprocess suites 61; new presentation suite 145. Both reviewed-fixture `--check` scripts
  (synthetic and SEC) report byte-identical regeneration.
- `PYTHONHASHSEED=1` and `PYTHONHASHSEED=987654` each ran the full 124-test presentation
  determinism/privacy subset green.
- A real headless Streamlit startup succeeded on the first attempt: Uvicorn bound to
  `127.0.0.1:8765` and `/_stcore/health` returned `ok`. No browser was opened.

### Packaging and dependencies

- Added the `dashboard` dependency group `streamlit>=1.40,<2`; the lock selects Streamlit
  `1.61.1` plus its transitive packages. The `uv.lock` diff is purely additive (490 insertions,
  0 deletions): no previously locked package was upgraded, downgraded, or removed.
- Streamlit is deliberately **not** a runtime dependency (ADR-008): `dashboard/` is excluded from
  the wheel and sdist under the same rule already documented for `scripts/`, so declaring it at
  runtime would burden every consumer with ~35 packages (pandas, NumPy, PyArrow, Tornado) for
  code the distribution does not ship. This diverges from the historical release's direct runtime
  range; the divergence is recorded rather than hidden.
- `uv build --offline` produced a 60-entry wheel containing the 56 runtime modules (53 prior plus
  `public_artifact_reader.py`, `presentation.py`, `html_summary.py`) and dist-info, and an sdist
  containing only `src/`, `tests/`, `pyproject.toml`, `uv.lock`, `README.md`, `.python-version`,
  and `.gitignore`. Scans of both archives found no `reference/`, prompts, `.claude`, `.serena`,
  `.venv`, `dist/`, caches, bytecode, `docs/`, `dashboard/`, `scripts/`, `.streamlit`, generated
  artifact tree, private manifest, SEC cache, secret, credential, real checkout path, or
  username. The only `manifest`-named wheel entries are the four legitimate `*_manifest.py`
  source modules; the only `/Users/` occurrences in the sdist are literal marker strings inside
  privacy assertions in test sources (a pre-existing pattern).
- A clean `uv venv --python 3.12` install of the wheel pulled only the Pydantic/HTTPX/Typer
  families - **Streamlit is not installed at all** - and `import quantcheck` imported no
  Streamlit, pandas, NumPy, PyArrow, matplotlib, or Altair. From that clean environment the
  reader, model, and HTML renderer reproduced the identical HTML SHA-256, and
  `quantcheck --help` exited 0.
- No environmental retries were needed at any point.


## Milestone 11 verification

### Scope and release status

- Recovery Phase 11 — **final evidence and release only**. No fault family, injector, detector,
  threshold, matcher, denominator, severity rule, research formula, replay rule, benchmark
  identity, expansion, aggregation semantic, CLI root command, or dashboard behavior was
  redesigned. Version bumped `0.1.0.dev0` -> `0.1.0` per the Milestone 0 decision that the real
  version is set at the release milestone. `LICENSE` (MIT) added and declared via
  `license-files`.
- **Release status: locally complete release candidate, not published.** No commit, tag, push,
  GitHub release, or registry upload was made or attempted.

### Freeze mechanism and release candidate

- `release_freeze.json` — canonical `ReleaseFreezeRecord`, identity prefix `relc_`, namespace
  `quantcheck/release-candidate/v1`. Freezes package version, Python requirement, benchmark spec
  version, fault-profile list, severity list, final seed list, clean-control policy, case totals,
  four fault specifications (type/subtype/injector/detector/scoring versions, matching rule,
  false-positive denominator rule, replay method), twelve severity definitions, the detector
  configuration hash, the Unit Drift ratio threshold, both reviewed fixture identities and
  hashes, the benchmark id, the normalized release configuration hash, the expanded matrix hash,
  the lockfile hash, and the SHA-256 of 67 explicitly listed frozen files.
- Verification is byte-level and refuses to repair. `run_release_benchmark` validates the request
  with the gate still closed, opens the authorization, rebuilds the configuration, verifies the
  candidate, and only then dispatches. A drifted input refuses the run **with no output tree
  created at all**.
- **Final candidate: `relc_2c6e945a71b85b39`**, freeze record SHA-256
  `7584be72c2fa3882c3a61c0ba47354cd3e45f53cd1f4d0bb70f9a012e59f42eb`.

### A candidate was invalidated before the final candidate, and is preserved

- `relc_a573d64b0345a5b5` completed a full 124-case held-out run first, then was invalidated by a
  **release-plumbing defect, not by detector performance**: `schemas.py` refused to *deserialize*
  a reserved seed, so the strict public reader could not load the released
  `public/benchmark_config.json` and the public evidence package could not be aggregated,
  presented, or rendered.
- Smallest correctness fix (ADR-010): enforcement moved from representation to execution via the
  new `benchmark_contract.require_seed_execution_authorized`, called by configuration building,
  expansion, the dispatcher, and all three saved-stage functions. `schemas.py` keeps only
  coherence rules.
- All quality gates were rerun, a new candidate was frozen and fully verified, and the matrix was
  run once against it. **Both runs are preserved**;
  `release_evidence/candidate_1_relc_a573d64b0345a5b5/` holds the first with its freeze record.
- **Proof the correction changed no science:** the two public trees have identical file sets (595
  files) and **593 of 594 indexed artifacts are byte-identical** — every case config, audit input,
  audit report, score, research summary, status, plus the benchmark config, case matrix, and
  aggregate report. Only `runtime_metadata.json` (runtime-specific by schema design) and
  `index.json` (which embeds its hash) differ. Both runs report the identical
  `bench_403a85e506ff66ea`, `agg_571aae0b7c60a4a5`, precision `0.625`, and recall `1`.

### Final-seed security boundary

- One primitive, `release_gate`: accepts **only** the complete reserved partition (subset,
  superset, duplicate, mixed, or off-by-one refused), context-manager scoped via a `ContextVar`,
  removed even when the block raises, refuses to nest, requires a candidate identifier, and
  imports nothing from `quantcheck`.
- Ordinary interfaces refuse execution: `build_benchmark_config`, `expand_benchmark_cases`,
  `dispatch_benchmark_case`, `run_benchmark`, `inject_case`/`audit_case`/`evaluate_case`, and
  every CLI command (`benchmark run` exit 2, `benchmark smoke` never touches one, saved-stage
  commands exit 2). Near-miss seeds `10/99/110/999/1010/1100/10000` stay refused with *and*
  without an authorization. No CLI flag, parameter, or environment variable authorizes anything;
  static AST tests confirm only `release_gate` and `release_run` open an authorization and that
  `cli.py` never references the gate.

### Rehearsal (before the freeze, ordinary seeds only)

Release-shaped configuration over development seeds `0-9` and validation seeds `100-109`:
`bench_81a335e01dba9417`, **244 cases**, 184 successful, 60 failed, 0 incomplete; precision
`0.66326530612244897959183673469387755102040816326531`, recall `1`. Exercised all four families,
all three severities, clean controls, expansion, sequential execution, persistence,
public/private separation, aggregation, failure handling, resume, public-only reconstruction,
strict reading, presentation, deterministic HTML, Streamlit AppTest, privacy scans,
traversal/symlink defenses, subprocess determinism across three hash seeds, different output
roots, and immutable-conflict rejection. **No release-plumbing defect was found at this stage,
and no final seed executed.** The rehearsal correctly predicted the three structurally
ineligible cells.

### Final held-out benchmark

Configuration: 4 fault profiles x 3 severities x 10 reserved final seeds = **120 fault cases**,
plus **4 clean controls** (one per profile — the maximum `BenchmarkProfile.clean_control` can
express; ADR-009) = **124 cases**. Per-profile fixtures, horizons, research contexts, and
detector configuration are the reviewed smoke configuration reused verbatim; only severity and
seed were expanded. Entirely offline; no live SEC call.

`bench_403a85e506ff66ea`, `agg_571aae0b7c60a4a5`, config SHA-256
`a29c131b83d85323b379436e674efbadff7e382f5e0ca09c7dd3e3bef46e6f3c`, matrix SHA-256
`2a1ffbc7d2ff32a0965ccfea3076ac17f46a20d2de6c0d9fc6590799e629cc13`.

- configured 124, successful 94, **failed 30**, incomplete 0
- injected fault units 130, findings 208
- true-positive faults 130, **false-negative faults 0**
- true-positive findings 130, false-positive findings 78
- eligible clean denominator 1070
- precision `0.625`
- recall `1`
- F1 `0.76923076923076923076923076923076923076923076923077`
- false-positive rate `0.072897196261682242990654205607476635514018691588785`
- research output changed 90 of 90; exact replay restored 90 of 90
- by fault profile — Duplicate 70 faults / 101 findings / 70 TP / 31 FP / denom 651 / P
  `0.69306930693069306930693069306930693069306930693069`; Unit Drift 30 / 45 / 30 / 15 / 155 / P
  `0.66666666666666666666666666666666666666666666666667`; Look-Ahead 20 / 41 / 20 / 21 / 253 / P
  `0.4878048780487804878048780487804878048780487804878`; Revision Overwrite 10 / 21 / 10 / 11 /
  11 / P `0.47619047619047619047619047619047619047619047619048`. Recall is `1` for all four.
- by severity — high P `0.76923076923076923076923076923076923076923076923077`, medium
  `0.59701492537313432835820895522388059701492537313433`, low
  `0.52631578947368421052631578947368421052631578947368`; recall `1` at every severity.
- by final seed — all ten seeds ran; recall `1` at every seed; precision `0.52` (seed 1000, which
  also carries the four controls) to `0.68421052631578947368421052631578947368421052631579`.
- clean controls — Unit Drift 0 findings (denom 5); Look-Ahead, Duplicate, and Revision Overwrite
  1 finding each (denoms 13, 21, 1). All four have `injected_faults=0`.

### Honest failure analysis

- **All 30 failures are `stage=injection`, `category=no_eligible_targets`**, in exactly three
  cells at ten seeds each: Look-Ahead `high` (needs a 30-day filing lag), Revision Overwrite
  `medium` and `high` (need 5% and 20% relative revisions against the fixture's single 2%
  history). These are frozen thresholds meeting a small reviewed fixture. They were kept in the
  matrix and remain visible in the statuses and the aggregate rather than being configured away.
- **Best precision** Duplicate `0.693…`; **worst** Revision Overwrite `0.476…`. **Recall is `1`
  everywhere** — zero false negatives in the whole matrix, which is a measurement on a 26-record
  synthetic fixture, not a general sensitivity claim.
- **Precision rises with severity** (`0.526` -> `0.597` -> `0.769`): the cross-detector background
  is roughly constant while true positives grow.
- **All 78 false positives are cross-detector findings under strict primary-label scoring**, not
  malfunctions. Public findings by rule: `occurrence.exact_duplicate` 133,
  `value.scale_discontinuity` 45, `temporal.period_end_available_before_filing` 20,
  `revision.later_vintage_in_earlier_state` 10. The dominant contributor is the reviewed
  fixture's documented natural independent-occurrence pair (ADR-004).
- **Revision Overwrite's false-positive rate is exactly `1`** over an eligible-clean denominator
  of **11**. Reported as saved, with the denominator, rather than suppressed.
- No fault family produced a legitimate zero research impact in this matrix.

### Public-only evidence, privacy, and adversarial review

- `release_evidence/public_only/` holds the public tree with **no private tree at all**. Against
  it: 595 public files, 0 private files, 0 manifests; strict reader loads it; rebuilt aggregate is
  byte-identical to the saved one; presentation model SHA-256
  `2c2788ca2673f67f807c89760ddbc030ddde13b8395b65be9300af6566ef7f68`; HTML SHA-256
  `2ba3c7746e18df90699a99ddd4ce0e0dc100bb6fa2b0ead7f88e4887e52ac795`; Streamlit AppTest renders
  1,515 text chunks / 113,608 characters with 30 visible failure elements and no exception; a
  real headless startup on `127.0.0.1:8766` returned `/_stcore/health` = `ok`.
- Scans found no private object key, local/home/temp path, secret marker, traceback, symlink, or
  traversable path in public bytes, the presentation model, the HTML, the dashboard text, or the
  freeze record. The same pass confirmed the private tree *does* hold `mutation`,
  `original_value`, `selection_digest`, `entity_name`, and `target_rank`, so the public scan
  cannot pass vacuously.
- Adversarial review verified: detectors take no manifest/clean-snapshot/seed/severity parameter;
  audit inputs carry no answer-key field; `true_positive_findings == true_positive_faults` (130)
  so duplicates cannot inflate recall; cross-detector findings stay visible; controls carry zero
  injected faults; failed cases remain in matrix, statuses, and aggregate (124 status files, 94/30/0);
  every fault, severity, and seed group is present even when weak; traversal and symlink escapes
  rejected; artifact conflicts rejected without overwrite.
- One nuance recorded rather than hidden: the `frozen_target_fraction` field name in the freeze
  record is prefixed precisely so a public constant never collides with the private manifest's
  `target_fraction` key in the context-free scan. No scan exemption was added.

### Reproducibility

`PYTHONHASHSEED` `0`/`1`/`987654` in fresh subprocesses produce identical model, HTML, and
aggregate hashes; all 595 public artifacts canonical round-trip; HTML is byte-identical to two
destinations; conflicting bytes at an existing destination are rejected; the public-only rebuild
equals the saved aggregate; an identical rerun reuses all 94 successful cases and dispatches 0;
an independent output root reproduces every logical byte. `runtime_metadata.json` and
`index.json` differ by design and are named explicitly rather than glossed over.

### Packaging

- `uv build --offline` -> wheel `quantcheck-0.1.0-py3-none-any.whl` SHA-256
  `ff1fff1880796803cf9454c1199c78e3e71bd41889301eb728e75a798dbbef91` (198,481 bytes, 68 entries,
  includes `dist-info/licenses/LICENSE`); sdist `quantcheck-0.1.0.tar.gz` SHA-256
  `cfc1497d171bc23c01e9558e7f8bb83f5ccfb4ec904019bb05b0b0be43fe75f7` (335,123 bytes, 161 entries).
- Archive scans found no generated artifact tree, manifest, private artifact, reference/recovery
  material, SEC cache, cache directory, bytecode, `release_evidence/`, `release_freeze.json`,
  `CHECKSUMS.md`, `docs/`, `dashboard/`, `scripts/`, secret, or real checkout path. The only
  `manifest`-named entries are the four legitimate `*_manifest.py` modules.
- Clean `uv venv --python 3.12` install of the wheel: version `0.1.0`; **Streamlit not installed
  at all**; `import quantcheck` pulls in no Streamlit/pandas/NumPy/PyArrow/matplotlib/Altair;
  `quantcheck --help` exit 0; offline `benchmark smoke` exit 0 reproducing
  `bench_654c76bb7eea251a` / `agg_1dedb2ca9aec9240` / precision `0.5`; public artifact loading and
  HTML rendering reproduce SHA-256
  `d3e433c80a79de47fd3566788938db7497c98fe4a2acd449abbd2b6a3d926107`, **identical to the
  Milestone 10 recorded value**; reserved seeds still refused from the installed wheel.

### Files added and changed

- Runtime added: `release_gate.py`, `release_contract.py`, `release_config.py`,
  `release_freeze.py`, `release_run.py`, `release_evidence.py`, `release_checksums.py`.
- Runtime changed: `schemas.py` (seed-class `final`, coherence-only seed rules, no-mixing rule),
  `benchmark_contract.py` (`require_seed_execution_authorized`, `ALL_SEED_CLASSES`,
  authorization-aware classifier), `benchmark_dispatch.py` and `saved_case_workflow.py` (execution
  guards), `__init__.py` (exports, docstring).
- Scripts added: `release_freeze.py`, `run_release_benchmark.py`, `verify_release_evidence.py`,
  `release_checksums.py`. No CLI command was added.
- Root added: `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `CHECKSUMS.md`, `release_freeze.json`.
- Docs added: `docs/METHODOLOGY.md`, `docs/ARTIFACTS_AND_PRIVACY.md`, `docs/THREAT_MODEL.md`,
  `docs/REPRODUCIBILITY.md`, `docs/FINAL_BENCHMARK_RESULTS.md`, `docs/LIMITATIONS.md`,
  `docs/RELEASE_CHECKLIST.md`, `docs/RELEASE_NOTES_0.1.0.md`.
- Changed: `pyproject.toml` (version, `license-files`, sdist `LICENSE`), `uv.lock` (version line
  only), `README.md`, `docs/DECISIONS.md` (ADR-009, ADR-010), `.gitignore`
  (`release_evidence/`), `IMPLEMENT.md`.
- Tests added: `tests/release_support.py`, `test_release_gate.py`, `test_release_freeze.py`,
  `test_release_run.py`, `test_release_evidence.py`, `test_release_checksums.py`,
  `test_release_final_seed_rejection.py`.
- Tests updated, not weakened: `test_presentation_isolation.py` (import-closure pin widened by the
  one named stdlib-only leaf `release_gate`, still an exact set equality) and
  `test_benchmark_config.py` (two seed assertions moved to the execution boundary where the rule
  now lives, with the guard additionally asserted).

### Tests and commands

- Added **204 tests**: gate 32, final-seed rejection 74, freeze 30, run 18, evidence 26,
  checksums 14, plus shared support. Full suite **1,595 passed** (1,391 prior + 204).
- The complete pre-Milestone-11 suite with all six release modules ignored still reports exactly
  **1,391 passed**, so no prior test was weakened or removed.
- Full suite green under `PYTHONHASHSEED` `0`, `1`, and `987654` (1,595 each).
- Targeted suites: schema/serialization/golden/hashing 271; fixtures/point-in-time/audit-boundary
  93; Look-Ahead 113; Unit Drift 130; Duplicate 134; Revision Overwrite 121; SEC 122; benchmark
  229; CLI 100; presentation 145; determinism/subprocess 79; release-only 204; properties 79;
  packaging 1.
- Every required command exited 0 individually: `uv sync --all-groups`,
  `uv sync --frozen --all-groups`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run mypy src tests` (151 files), `MYPYPATH=src uv run mypy --explicit-package-bases dashboard
  scripts` (9 files), `uv run pytest`, `uv lock --check`, `uv run quantcheck --help`,
  `uv build --offline`, `git diff --check`, both reviewed-fixture `--check` scripts,
  `scripts/release_freeze.py --check`, `scripts/run_release_benchmark.py`,
  `scripts/verify_release_evidence.py`, `scripts/release_checksums.py --check`.
- No environmental retries were needed at any point.

### Dependencies

No runtime or development dependency was added, removed, or upgraded. The release layer uses only
the standard library and Pydantic. `uv.lock` changed by exactly one line (the package version).

### Git and CI

Working tree holds the release for review. Nothing was committed, staged, tagged, pushed, or
published. `git diff --check` is clean; `release_evidence/` is gitignored so no generated artifact
tree, manifest, cache, or secret can be staged. **GitHub Actions has not run** — the workflow was
validated only by executing its constituent commands locally, and remote CI remains an external
gate.


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
- **Benchmark identity, artifact tree, resume, and aggregate conventions are rebuilt v1
  contracts.** ADR-006 freezes the benchmark/case/aggregate identity payloads and namespaces, the
  exclusion of the package version from logical identity, normalization and execution ordering, the
  primary-family combined-report identity, clean controls carrying their fault sibling's full
  configuration, the public/private artifact layout and relative-path grammar, immutable-versus-
  derived write policy, resume validation, the failure stage/category taxonomy with fixed public
  messages, the aggregate null conventions, the minimal sanitized research summary, and the two
  configuration facts the current implementation forces (the second benchmark fixture for Unit
  Drift and `low` severity for Revision Overwrite). No historical benchmark artifact is claimed.
- **CLI command surface, saved-stage workflow, JSON envelope, and exit codes are rebuilt v1
  contracts.** ADR-007 freezes the six-command Typer surface, the reuse of `BenchmarkCaseConfig` as
  the saved-stage case format (no second configuration schema), the renamed public
  `benchmark_dispatch` single-case helpers that make byte-identical staged/direct-dispatch
  equivalence possible without duplicating logic, the `AtomicArtifactStore` public/private layout
  reused unchanged for saved-stage output, the canonical-serializer-only JSON envelope, the
  `0/2/3/4/5/10` exit-code taxonomy, and the `no_args_is_help` no-argument/help behavior. No
  historical CLI flag syntax, JSON field name, or exit-code assignment is claimed byte-identical to
  the lost release.
- **Public-only presentation boundary, shared model, HTML determinism, and the Streamlit
  dependency are rebuilt v1 contracts.** ADR-008 freezes the reader's role allowlist and layered
  path rules, the strict-tree/preserved-incomplete split (tree-level integrity raises; an
  unsubstantiated success claim becomes `incomplete`, matching `benchmark_aggregate` exactly), the
  aggregate-versus-status consistency check, the single immutable presentation model both surfaces
  render, exact `Decimal`/null semantics, the deterministic self-contained HTML contract and its
  reuse/conflict output behaviour, the standalone read-only dashboard shape, and the decision to
  carry Streamlit as a `dashboard` dependency group rather than a runtime dependency. No
  historical presentation byte, hash, metric, or dependency version is claimed.

## Known limitations

- Only the narrow Look-Ahead `period_end_substitution` subtype, narrow Unit Drift
  `value_scaled_unit_unchanged` subtype, narrow Duplicate Observations `exact_occurrence_copy`
  subtype, narrow Revision Overwrite `later_vintage_in_earlier_state` subtype, narrow SEC
  adapter, the Milestone 8 benchmark layer, the Milestone 9 CLI, the Milestone 10 public-only
  presentation layer, and the Milestone 11 release-evidence layer exist. None of the historical
  0.1.0 metrics, hashes, or test totals is reproduced or claimed; every figure here is this
  implementation's own.
- **Three of the twelve release profile/severity cells have no eligible target on the reviewed
  fixture** and fail all ten final seeds with `no_eligible_targets`: Look-Ahead at `high` (30-day
  filing lag), Revision Overwrite at `medium` and `high` (5% and 20% relative revisions against a
  single 2% history). 30 of 124 final cases therefore failed. No threshold was relaxed and no
  fixture horizon was shopped for to make them pass.
- **Revision Overwrite's held-out false-positive rate is exactly `1` over an eligible-clean
  denominator of 11**, because the reviewed fixture contains one source-supported adjacent
  revision history. The rate is arithmetically correct and statistically thin; it is reported as
  saved, alongside its denominator.
- **Held-out recall is `1` for every family, severity, and seed** - zero false negatives. This is
  a measurement on a 26-record synthetic fixture and a five-observation series, not a general
  detector-sensitivity claim.
- **`runtime_metadata.json` and `index.json` are deliberately not byte-reproducible** across runs:
  the former records the wall clock, platform, and interpreter by schema design, and the latter
  embeds its content hash. Every other logical artifact is byte-identical across runs, output
  roots, and hash seeds.
- The CLI's `audit --case/--snapshot/--output` standalone form always runs every one of the four
  manifest-blind detectors and brands the combined report with one caller-chosen `fault_profile`'s
  identity, exactly like the benchmark dispatcher's own combined-report convention. There is no
  per-detector opt-out and no way to run only one family's detector through the CLI; that would be a
  new detector-selection contract, not a Phase 9 concern.
  `evaluate` therefore has no saved-stage counterpart for a `clean_control` case; its terminal
  artifact is its own `audit` output, matching `dispatch_benchmark_case`'s clean-control branch.
- `ingest sec`'s CLI-input JSON shape for `SecNormalizationConfig` requires the exact field set
  `cik`/`concepts`/`forms`/`filed_from`/`filed_through` with no optional/omitted fields and no
  alternate spelling; this is a deliberately narrow, explicit loader for one dataclass, not a general
  JSON-schema-to-dataclass mapper.
- The CLI has no `benchmark aggregate` command to rebuild an aggregate report from a copied-out
  public tree with no private evidence present, even though
  `quantcheck.benchmark_aggregate.aggregate_from_public_root` already supports it; Phase 9's required
  command list is `ingest sec`/`inject`/`audit`/`evaluate`/`benchmark run`/`benchmark smoke`/
  `explain` only, and adding a further command was judged out of scope rather than a convenience
  worth including.
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
  and research identifiers are specified, and Milestone 8 adds dedicated benchmark configuration,
  fault-case, clean-control-case, and aggregate-report namespaces with their own payloads rather
  than borrowing any of them.
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
- CI (`.github/workflows/ci.yml`) has not yet run on GitHub Actions; it has only been validated by
  running its constituent commands locally.
- The benchmark supports exactly two clean sources and one profile-to-fixture mapping each.
  Unit Drift requires the new `quantcheck/benchmark-unit-drift-series/v1` fixture because the
  reviewed fixture is a documented two-period insufficient-history control with no eligible Unit
  Drift target at any severity or horizon, and Revision Overwrite runs only at `low` severity on
  the reviewed fixture because its single source-supported adjacent history has a 2% relative
  revision — clearing the 1% `low` threshold but not the 5% `medium` one. Neither frozen rule was
  relaxed to make the benchmark uniform. The new series fixture is an additive, deterministic,
  offline benchmark support source; it does not change, replace, or regenerate the reviewed
  fixture's bytes.
- The smoke's precision of `0.5` is dominated by legitimate cross-detector findings, chiefly the
  reviewed fixture's Milestone 2 independent-occurrence pair that the Duplicate detector correctly
  reports on every reviewed-fixture case. This is retained detector behavior under strict
  primary-class scoring, not a detector defect and not a tuning target.
- One output root holds exactly one logical benchmark: a second, different configuration written
  into the same root is rejected as an immutable conflict rather than silently taking it over.
- When a prior success fails revalidation, the run result reports that case as `failed` with code
  `prior_success_invalid` while the untouched on-disk status still reads `succeeded`; aggregation
  independently downgrades it to `incomplete`. The two views deliberately disagree, because
  overwriting the conflicting status would destroy the evidence the failure exists to preserve.
- Private failure diagnostics from an earlier attempt are retained in the private tree even after
  a later attempt succeeds. They are forensic history, never read back as case state.
- Benchmark execution is sequential and local by design. There is no parallelism, no HTML or
  dashboard rendering, no database or cloud persistence, and no force-overwrite path anywhere,
  including through the Milestone 9 CLI. Milestone 10 adds dashboard and HTML rendering as
  separate, standalone, read-only surfaces over already-saved artifacts; neither runs inside the
  benchmark, and neither is reachable from the CLI.
- `CHECKSUMS.md` now exists (Milestone 11). No historical format survived and no prior contract
  defined one, so ADR-009 freezes the smallest deterministic format: a Markdown document whose
  body is a fenced block of `<sha256>  <path>` lines, sorted by path, covering the committed
  release surface (67 frozen source/lock files, the freeze record, and 20 release documents - 88
  files total). Generated benchmark artifacts are deliberately excluded; they are reproduced from
  the frozen configuration rather than committed. Verified by
  `uv run python scripts/release_checksums.py --check`.
- The dashboard is a local, read-only, single-user Streamlit app: no authentication, accounts,
  web backend, hosted deployment, or browser-level automation beyond Streamlit's official
  `AppTest` and a local headless health startup. There is no general artifact browser, no
  manifest browsing, and no private-value browsing.
- The public reader deliberately raises on a status file that exists but does not validate,
  where `benchmark_aggregate` records the case as incomplete. Aggregation must never crash
  mid-run; the reader is a verification tool and is loud instead. The two agree on every
  non-tampered tree, and the reader additionally refuses a tree whose saved aggregate
  contradicts its saved statuses.
- Case filters use only public dimensions the saved artifacts already carry (fault profile,
  severity, status, seed class). No new scientific category was invented for the UI.
- No benchmark truth is committed to the repository for the presentation surfaces to display;
  both require artifacts produced locally.
- `dashboard/` and `scripts/` are intentionally outside the wheel and sdist, so an installed
  distribution ships neither the dashboard nor Streamlit. The installed package still provides
  the reader, model, and HTML renderer.

## Exact next task

**v0.1 implementation is complete.** All eleven recovery phases are done and every locally
controllable Milestone 11 gate passes. There is no unfinished v0.1 implementation milestone.

The next task is **external publication and release review**, which requires actions this
environment cannot perform and which nobody has authorized:

1. Human review of the working tree diff and of `docs/RELEASE_CHECKLIST.md`.
2. Commit the release, then create the `v0.1.0` tag — **only on explicit authorization**.
3. Push and let GitHub Actions run `.github/workflows/ci.yml` for the first time. Remote CI is
   currently an unverified external gate.
4. Decide whether to publish a GitHub release and/or a package registry upload. Nothing has been
   uploaded and no registry credentials were used.
5. Optionally record the three-minute demonstration from the storyboard in
   `docs/RELEASE_CHECKLIST.md`. No video exists.

If post-MVP work is preferred instead of publishing, the honest highest-value candidates — each
requiring its own milestone and a new release candidate — are: a larger or real-vendor fixture so
the three structurally ineligible profile/severity cells have targets and the thin denominators
grow; and a per-detector selection contract so cross-detector findings can be reported without
counting against strict primary precision. Neither may be started as a way to improve the
existing held-out numbers, which are now frozen evidence.

## Fixed implementation choices

- Python: 3.12
- Package: `quantcheck`
- Dependency manager: `uv`
- Build backend: Hatchling
- Public schemas: Pydantic v2, introduced in Milestone 1
- Lint and format: Ruff
- Type checking: MyPy
- Tests: pytest and Hypothesis
- CLI: Typer, introduced at the Milestone 9 CLI milestone (`typer>=0.12,<1`, resolved `0.27.1`)
- HTTP: HTTPX, introduced with the SEC adapter
- Tabular processing: pandas and PyArrow, introduced only when required
- Dashboard: Streamlit, introduced at the Milestone 10 presentation milestone as the
  optional `dashboard` dependency group (`streamlit>=1.40,<2`, resolved `1.61.1`)
- Release version: `0.1.0`, set at the Milestone 11 release-evidence milestone

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

2026-08-08 (Milestone 11 complete — final evidence and release; candidate
`relc_2c6e945a71b85b39`, benchmark `bench_403a85e506ff66ea`, aggregate `agg_571aae0b7c60a4a5`)
