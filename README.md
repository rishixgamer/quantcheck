# QuantCheck Recovery Harness

This folder is a **rebuild harness**, not the completed QuantCheck source repository.

The original source code was lost. The surviving documents under `reference/` describe the project concept, the intended architecture, the historical 0.1.0 behavior, and the prior release evidence. Treat them as specifications and historical evidence—not as proof that the new repository already implements those features.

## Start here

1. Copy this folder into a new empty `quantcheck` repository.
2. Initialize Git immediately.
3. Open Claude Code from the repository root.
4. Paste `prompts/00_BOOTSTRAP_REPOSITORY.md` into Claude Code.
5. Do not start the next milestone until all current milestone checks pass and `IMPLEMENT.md` is updated.

## Important recovery rule

Do not copy the historical release `README` or historical `IMPLEMENT` file to the repository root. They claim a completed 0.1.0 release, 645 passing tests, and generated benchmark hashes. In a blank rebuild, those claims are not yet true. They are stored under `reference/` so Claude can use them to reconstruct behavior without confusing historical state with current state.

## Intended build sequence

1. Repository/toolchain bootstrap
2. Canonical schemas, serialization, hashing, and stable IDs
3. Deterministic fixtures and point-in-time snapshots
4. Look-ahead vertical slice
5. Narrow SEC adapter
6. Unit Drift
7. Duplicate Observations
8. Revision Overwrite
9. Benchmark runner and public/private artifacts
10. CLI
11. Read-only dashboard and deterministic HTML
12. Release evidence and packaging

The exact behavioral target is summarized in `RECOVERY_SEQUENCE.md` and supported by the historical files under `reference/`.
