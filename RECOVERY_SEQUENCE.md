# QuantCheck recovery sequence

Rebuild one verified vertical layer at a time. Never ask Claude Code to recreate the historical release in a single session.

## Phase 0 — bootstrap

Create the package, lockfile, quality tools, CI, and a minimal installed command. Exit only when clean-clone commands pass.

## Phase 1 — canonical domain layer

Implement immutable schemas, canonical JSON, Decimal handling, SHA-256 hashes, and row-order-independent stable IDs with golden vectors.

## Phase 2 — deterministic fixture and point-in-time engine

Build reviewed offline fixtures, revision ordering, `available_on <= as_of_date`, canonical snapshots, and sanitized audit-input conversion.

## Phase 3 — look-ahead vertical slice

Implement one complete flow: deterministic injection, private manifest, manifest-blind detection, exact matching/scoring, exact replay, and controlled research impact.

## Phase 4 — SEC adapter

Add cache-first HTTPX retrieval/replay and narrow, explicit Company Facts normalization. Keep ordinary tests hermetic.

## Phase 5 — Unit Drift

Add deterministic scale corruption, independent local-series detection, exact matching, replay, impact, hard negatives, and limitation tests.

## Phase 6 — Duplicate Observations

Add exact occurrence copy injection, fingerprint-group detection, strict matching, replay, double-counting impact, and hard negatives.

## Phase 7 — Revision Overwrite

Add explicit source-supported revision histories, later-vintage overwrite injection, sanitized temporal-contract detection, strict scoring, replay, and growth-ranking impact.

## Phase 8 — benchmark artifacts

Add strict configuration expansion, all-detector dispatch, public/private atomic persistence, failures, resume, and public-only aggregation.

## Phase 9 — CLI

Add the contracted command surface and saved-stage workflow with canonical JSON output, stable exit codes, and privacy-safe rendering.

## Phase 10 — presentation

Add a strict public reader, shared immutable presentation model, read-only Streamlit app, and deterministic self-contained HTML.

## Phase 11 — release evidence

Run rehearsal, freeze the candidate, authorize reserved final seeds only through the release path, generate public evidence, verify privacy and reproducibility, build packages, and document external gates honestly.

## Session rule

Each Claude Code session should complete one cohesive task, run targeted and full applicable checks, inspect the diff, and update `IMPLEMENT.md`. Commit after every passing milestone.
