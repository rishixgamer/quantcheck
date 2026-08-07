# Implementation status

This is the operational handoff between Claude Code sessions. Keep it concise, factual, and current.

## Current phase

**Milestone 1 complete — Canonical schemas, serialization, hashing, and identifiers**

The original source repository was lost. Historical 0.1.0 documentation survives under `reference/`, but no historical implementation claim is considered current until rebuilt and verified. Milestone 0 rebuilt the reproducible repository foundation. Milestone 1 adds the deterministic contract layer on which all later behavior depends: strict JSON value types, immutable Pydantic v2 schemas, one canonical serialization path, SHA-256 hashing, and stable identifiers. It contains no fixtures, point-in-time selection, injection, detection, or scoring.

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

## Known limitations

- No fixtures, point-in-time selection, revision ordering, sanitization function, SEC access,
  injectors, detectors, manifests, scoring, benchmark artifacts, or dashboard/HTML exist. None of
  the historical 0.1.0 test counts, benchmark metrics, or hashes are reproduced or claimed.
- The lost `docs/SERIALIZATION_AND_HASHING.md` could not be recovered. The rebuilt contract is a
  reasoned reconstruction, not a restoration, and no historical golden value is reproducible.
- Only the four identifier helpers listed above have specified payloads. Manifest, finding, report,
  modified-record, and duplicate-occurrence identifiers are **not** specified; when those artifacts
  are contracted, they must get dedicated helpers rather than improvised payloads. Until then
  callers use generic `stable_id` with an explicit new namespace.
- `AuditInputSnapshot` exists as a schema only. `sanitize_for_audit` — the function that converts a
  `DatasetSnapshot` into it — is Milestone 2 and is deliberately absent, so the audit boundary is
  declared but not yet enforced by a conversion path.
- Schemas require explicit `filed_on` and `available_on` but cannot prove the external rule that
  justifies a difference between them; adapters and injectors must supply that context later.
- Canonical strings are compared code point for code point; no Unicode normalization is applied, so
  NFC and NFD spellings of the same grapheme are distinct logical values.
- The CLI has no subcommands and is expected to be replaced entirely at the CLI milestone
  (Recovery Phase 9).
- CI (`.github/workflows/ci.yml`) has not yet run on GitHub Actions; it has only been validated by
  running its constituent commands locally.

## Exact next task

Implement Milestone 2 (Recovery Phase 2): the deterministic fixture and point-in-time engine —
reviewed offline fixtures reproducible by seed, explicit revision ordering, end-of-day
`available_on <= as_of_date` selection, canonical snapshot construction, and the
`sanitize_for_audit` conversion producing `AuditInputSnapshot` from a `DatasetSnapshot`. Reuse the
Milestone 1 canonical path, schemas, and identifier helpers unchanged; do not alter the frozen
golden vectors. Do not implement fault injection, detection, scoring, SEC access, or benchmark
logic in that task.

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

2026-08-06 (Milestone 1 complete — canonical schemas, serialization, hashing, identifiers)
