# QuantCheck project guidance

## Mission

QuantCheck is a deterministic Python framework for testing whether point-in-time
financial research data can manufacture misleading results through timestamp
leakage, unit corruption, duplicate observations, or revision-history failure.
Keep the implementation and public evidence within this scope.

## Fixed technical choices

- Python 3.12, `uv`, Hatchling, Pydantic v2, Ruff, MyPy, pytest, Hypothesis
- Typer, HTTPX, pandas, and PyArrow; Streamlit only for the read-only dashboard
- Day-level financial availability and end-of-day research decisions for v0.1
- `Decimal` for financial values, canonical JSON strings, and SHA-256 hashes

## Scientific invariants

1. Detectors receive only a sanitized `AuditInputSnapshot`, never manifests,
   pre-corruption values, injected-row flags, or injector-only metadata.
2. The same clean snapshot, configuration, seed, and code version produce the
   same logical corruption and artifacts.
3. Caller-owned inputs are never modified in place.
4. Period, filing, availability, as-of, and runtime dates remain distinct.
5. Financial values use `Decimal`; public JSON serializes them as canonical strings.
6. IDs and hashes do not depend on row position or Python hash randomization.
7. Findings include a rule ID, affected records, evidence, explanation, and
   confidence classification.
8. Every detector is evaluated against clean controls.
9. Scoring reads the private manifest only after the audit report is finalized.
10. Ordinary tests make no live network requests.
11. Unsupported source semantics are rejected or explicitly recorded, never guessed.
12. Synthetic, controlled, and real-data claims remain clearly distinguished.
13. Historical metrics and hashes are not copied into new output unless reproduced
    from the rebuilt implementation.

## Scope discipline

Do not add authentication, SaaS infrastructure, real-money trading, generic
backtesting, machine learning, intraday claims, React, microservices, Kubernetes,
or new fault families to the v0.1 implementation.

## Verification rule

A change is complete only when its acceptance criteria, positive/negative/edge/
regression tests, applicable quality gates, serialization contracts, and financial
semantics pass. Keep the diff scoped, preserve unrelated worktree changes, and
report any unverified external or production evidence explicitly.
