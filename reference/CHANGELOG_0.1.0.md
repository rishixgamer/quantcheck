# Changelog

All notable changes to QuantCheck are recorded here. The format follows Keep a Changelog, and the project uses semantic versioning.

## 0.1.0 — 2026-08-04

### Added

- Immutable Pydantic v2 contracts for financial facts, snapshots, audit inputs, findings, manifests, scores, and benchmark artifacts.
- Deterministic synthetic fixture and a small cache-first SEC Company Facts adapter with reviewed offline fixtures.
- Four fault families: look-ahead timestamp leakage, unit drift, duplicate observations, and revision overwrite.
- Manifest-blind detectors, exact fault-specific scoring, controlled manifest-assisted replay, and controlled research-impact scenarios.
- Deterministic 132-case release matrix: 120 fault cases and 12 clean controls.
- Six-command Typer CLI, public/private artifact separation, strict public reader, Streamlit dashboard, and deterministic HTML summary.
- Explicit release-only authorization for final seeds `1000`–`1009`, guarded by a byte-level release freeze.
- Public final evidence, technical results, reproducibility instructions, threat model, and release packaging.

### Fixed

- Accepted valid zero-impact duplicate research cases when injected duplicates fall outside the configured aggregate group.
- Restricted source-distribution discovery so generated artifacts and private manifests cannot enter release packages.

### Security

- Enforced sanitized detector inputs and manifest isolation.
- Added public artifact path, hash, cross-case, traversal, symlink, and private-tree rejection.
- Verified the public release copy and package contents contain no private benchmark artifacts, answer keys, secrets, caches, or local paths.

