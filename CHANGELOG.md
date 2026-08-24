# Changelog

All notable changes to QuantCheck are recorded here. This project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0.dev0] — Unreleased

### Added

* Persisted, resumable 390-case development and 390-case validation evidence
  runs over the frozen v0.2 corpus, with mandatory paired clean controls,
  terminal status artifacts, exact-count aggregates, and byte-identical
  public-only reconstruction.
* A validation preregistration freeze that refuses validation until all
  development cases succeed and binds both configs/matrices, the development
  aggregate, and the science-source hashes.
* A design-partner beta-candidate freeze plus deterministic SPDX 2.3 package
  SBOM, in-toto/SLSA v1 provenance statement, and evidence checksums. Local
  provenance is explicitly unsigned; a trusted CI attestation remains an
  external release gate.

### Changed

* Package version advanced from the immutable `v0.1.0` release to the explicit
  pre-release version `0.2.0.dev0`; the historical tag, release freeze, and
  `CHECKSUMS.md` are not rewritten.
* PyArrow `>=24,<25` is now a direct runtime dependency because Parquet and
  Arrow IPC are supported production inputs. Imports remain lazy for CSV and
  Python-row use.
* Container assembly canonicalizes virtual-environment entry order, ownership,
  and timestamps before extraction. The reproducibility gate requires identical
  digest-addressed OCI manifest, config, and layer identity. Raw outer-tar
  archive bytes, headers, and member order remain diagnostics and do not fail
  the image-identity gate by themselves.
* The cited candidate commit `3b47da9` has green Security workflow run
  `32693592309`, including exact two-build OCI manifest/config/layer identity
  and dependency, secret, image, and SBOM gates. This does not claim a published
  image digest or trusted release attestation.

### Not claimed

* No customer data, design-partner adjudication, pilot outcome, live-source
  evidence, production deployment, signed attestation, or held-out v0.2 result
  is represented by this engineering closure.

## [0.1.0] — 2026-08-08

Immutable historical baseline, published from the `v0.1.0` tag as a GitHub
release. It has no PyPI upload; install from its attached wheel, sdist, or
source checkout.

### Added

* **Canonical contract layer** — strict JSON value types with exact
  `Decimal`/`date`/UTC-timestamp encodings, immutable Pydantic v2 schemas, one
  canonical serialization path, SHA-256 content hashes, and prefixed
  row-order-independent stable identifiers with golden vectors.
* **Point-in-time engine** — a deterministic 26-record reviewed synthetic
  fixture, explicit declared revision lineages, end-of-day
  `available_on <= as_of_date` selection, and the `sanitize_for_audit` trust
  boundary.
* **Look-Ahead Timestamp** (`period_end_substitution`) — deterministic
  injection, private manifest, manifest-blind detection, exact scoring,
  controlled `availability_count_v0_1`, manifest-assisted exact replay.
* **SEC Company Facts adapter** — one CIK, cache-first HTTPX retrieval, exact-byte
  cache identity, integrity-checked offline replay, explicit allowlist
  normalization. Ordinary tests are hermetic.
* **Unit Drift** (`value_scaled_unit_unchanged`) — exact comparable-series
  construction, deterministic scaled-value injection with unchanged unit,
  immediate-neighbour ratio detection, controlled `aggregate_value_v0_1`.
* **Duplicate Observations** (`exact_occurrence_copy`) — one exact fingerprint
  shared by injection eligibility and detection, appended-copy injection,
  fingerprint-group matching, controlled `record_count_v0_1`.
* **Revision Overwrite** (`later_vintage_in_earlier_state`) — explicit
  source-supported adjacent histories, later-vintage substitution retaining
  historical availability, sanitized temporal-contradiction detection,
  controlled frozen-vintage `growth_ranking_v0_1`.
* **Benchmark layer** — strict normalized configuration and deterministic
  expansion, explicit seed classes, a closed four-family dispatcher running all
  four detectors per case, atomic public/private artifact persistence with
  immutable case evidence, structured failures, safe resume, and aggregation
  rebuilt exclusively from public artifacts.
* **CLI** — a six-root-command Typer surface (`ingest sec`, `inject`, `audit`,
  `evaluate`, `benchmark run`, `benchmark smoke`, `explain`) with a saved-stage
  workflow byte-equivalent to a direct dispatch, canonical JSON output, and the
  `0/2/3/4/5/10` exit-code taxonomy.
* **Public-only presentation** — a strict public artifact reader with a role
  allowlist and layered path security, one immutable shared presentation model,
  a deterministic self-contained HTML summary, and a standalone read-only
  Streamlit dashboard. All work with the entire private tree deleted.
* **Release evidence** — `release_gate` final-seed authorization,
  `release_contract`/`release_config` frozen release matrix, `release_freeze`
  release-candidate record with byte-level verification, `release_run` held-out
  execution, `release_evidence` public-only verification and leak scanning, and
  `release_checksums` with `CHECKSUMS.md`.
* Release documentation: methodology, artifacts and privacy, threat model,
  reproducibility, final benchmark results, limitations, release checklist,
  release notes, contributor guidance, and this changelog.
* `LICENSE` (MIT), declared via `license-files` in `pyproject.toml`.

### Changed

* Package version `0.1.0.dev0` → `0.1.0`.
* `BenchmarkSeedClass` gained a third member, `final`, so held-out artifacts can
  label their own partition. Development and validation artifacts are unchanged.
* Reserved final seeds are gated at **execution** rather than at
  **representation**. `benchmark_contract.require_seed_execution_authorized` is
  called by configuration building, expansion, the dispatcher, and all three
  saved-stage functions. Deserializing a saved held-out artifact is permitted so
  that released public evidence stays readable by the reader and presentation
  surfaces, which execute nothing.

### Security

* Reserved final seeds `1000`–`1009` cannot be executed through any ordinary
  interface. The single authorization primitive accepts only the complete
  reserved partition, is scoped to a context manager, refuses to nest, requires
  a frozen candidate identifier, and imports nothing from the package.
* The release path verifies every frozen input byte for byte before dispatching
  a single case, and refuses without creating an output tree.

### Known limitations

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md). In brief: four narrow fault
subtypes, synthetic reviewed fixtures, controlled research comparisons rather
than backtests, manifest-assisted replay rather than automatic repair, a
one-CIK SEC adapter with no live attestation, and a local read-only dashboard.
No historical 0.1.0 metric or hash is reproduced or claimed.
