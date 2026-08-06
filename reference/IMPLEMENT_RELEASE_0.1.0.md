# Implementation status

This file is the operational handoff between Codex sessions. Keep it concise, factual, and current.

## Current phase

**Milestone 11 complete — Final Evidence and Release**

QuantCheck 0.1.0 is locally release-ready: release-only final-seed execution is freeze-gated, the
132-case held-out matrix is preserved, exact public evidence and failure analysis are published,
and wheel/sdist, clean-install, privacy, reproducibility, dashboard, and HTML checks pass. Remote
CI, Git tag/commit verification, registry publication, and human browser/video review remain
external gates.

## Immediate next task

Run remote CI from a checkout with Git metadata, perform the human browser/demo review, verify the
tagged source against `dist/SHA256SUMS`, and create the `v0.1.0` release if publication is approved.

## Fixed implementation choices

- Python: 3.12
- Package: `quantcheck`
- Dependency manager: `uv`
- Build backend: Hatchling
- Public schemas: Pydantic v2
- Lint and format: Ruff
- Type checking: MyPy
- Tests: pytest and Hypothesis
- CLI: Typer
- HTTP: HTTPX
- Tabular processing: pandas and PyArrow
- Dashboard: Streamlit, introduced only in Milestone 10

## Milestone 1 verification

- Added `json_types.py`, `schemas.py`, `serialization.py`, and `hashing.py`; updated public exports.
- Added schema, invalid-input, round-trip, property, hashing, identifier, and static golden-vector
  tests under `tests/`.
- Added the planned `pydantic>=2,<3` runtime dependency; no other runtime dependency was added.
- `uv sync --all-groups`: passed with CPython 3.12.13.
- `uv run ruff check .`: passed.
- `uv run ruff format --check .`: passed.
- `uv run mypy src tests`: passed.
- `uv run pytest`: passed; 54 tests passed and the Hypothesis plugin loaded.
- No decisions were added or revised.

## Milestone 2 verification

- Added deterministic snapshot construction, synthetic source-row and revision identifiers, a
  26-record manually reviewed fixture, explicit revision ordering, end-of-day selection, and
  sanitized audit-input conversion.
- Added the canonical checked-in fixture, documented regeneration command, and validity,
  determinism, subprocess, availability, revision, duplicate-candidate, hard-negative,
  sanitization, and Hypothesis tests.
- `uv sync --all-groups` and `uv sync --frozen --all-groups`: passed with CPython 3.12.13.
- `uv run ruff check .` and `uv run ruff format --check .`: passed.
- `uv run mypy src tests`: passed.
- `uv run pytest`: passed; 80 tests passed and the Hypothesis plugin loaded.
- `uv lock --check` and fixture regeneration verification: passed.
- No runtime or development dependency and no architecture decision changed.

## Milestone 3 verification

- Added the specified manifest, finding, audit, research, and evaluation artifact models plus a
  narrow look-ahead configuration and internal case result.
- Implemented order-independent eligibility and SHA-256 target selection, period-end substitution,
  modified-record identity, hidden-manifest construction, and non-mutating corrupted snapshots.
- Added a detector that accepts only `AuditInputSnapshot`, emits exact public-date evidence, and has
  no injector or manifest dependency.
- Added exact matching with wrong-class, unmatched, duplicate, and ambiguous preservation; case
  metrics use the documented null conventions and clean point-in-time denominator. F1 remains a
  derived case value because it is not a `DetectionMetrics` field.
- Added manifest-assisted exact replay and `availability_count_v0_1` comparison. The reviewed case
  changes the selected occurrence count from 18 clean to 20 corrupted and returns to 18 repaired.
- Added 38 unit, integration, adversarial, bounded-Hypothesis, round-trip, order-invariance, and
  cross-`PYTHONHASHSEED` tests; the full suite has 118 passing tests.
- Repeated logical artifacts, source-order reversal, and `PYTHONHASHSEED` values 1 and 987654 are
  byte-identical. The reviewed case has two injected faults, two findings, two true positives, no
  false positives or false negatives, precision/recall/F1 of 1, and false-positive rate 0/18.
- `uv sync --all-groups`, frozen sync, Ruff check/format, MyPy, pytest, lock verification, reviewed
  fixture regeneration, and all harness checksums pass with Python 3.12.13.
- No runtime or development dependency, lockfile, fixture, Milestone 1 golden vector, harness
  contract, or architecture decision changed.

## Milestone 4 verification

- Added `sec_adapter.py` with `SecClientConfig`, `SecConceptSpec`,
  `SecNormalizationConfig`, `SecCompanyFactsAdapter`, `SecRawCache`, fetch/replay results,
  deterministic cache paths, parsing, normalization, snapshot construction, and explicit SEC
  error types; added SEC source-row and native-revision ID helpers and public exports.
- Requests require a configured user-agent containing a contact email or URL, use an explicit
  HTTPX timeout, accept only canonical positive 10-digit CIKs, pace sequential requests at a
  configurable 0.2-second default interval, and retry only transport failures plus HTTP 429,
  500, 502, 503, and 504 with bounded exponential or accepted `Retry-After` delays.
- Cache entries use `companyfacts/CIK##########/`, immutable `raw-<sha256>.json` files, and one
  atomically replaced `accepted.json` pointer. Cache validation covers URL/CIK identity, metadata,
  raw filename, raw hash, JSON, and the Company Facts envelope; interrupted writes and failed
  refreshes leave the previous accepted entry usable.
- Normalization uses an explicit CIK, taxonomy/concept, period-shape, unit, form, and inclusive
  filing-date configuration. It preserves SEC namespace/concept/unit/frame/fiscal fields,
  accession numbers, exact decimal lexemes, duration or instant dates, source occurrence lineage,
  revisions, duplicate-looking rows, and `available_on == filed_on`; it rejects rather than guesses
  malformed allowlisted entries or unsupported dimension structures.
- Added the reviewed one-company field-shape fixture for CIK `0000320193`, concepts
  `us-gaap:Assets`, `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`, and
  `us-gaap:SalesRevenueNet`, USD units, forms 10-K/10-Q, and filing dates 2022-01-01 through
  2024-12-31. The 12 raw entries yield seven accepted records and five explicit single-entry
  exclusion categories.
- The normalized fixture has snapshot ID `snap_0e623d7461fb56b0d485b983` and content hash
  `31b41bb9309100e7eed354790cafd06cecf8b459b84f4597b70d72f544fe6155`.
  Reordered source mappings/lists, repeated runs, and `PYTHONHASHSEED` values 1 and 987654 produce
  byte-identical normalized logical records. Mock-online and offline replay produce byte-identical
  snapshots; different cache paths and retrieval timestamps preserve logical IDs and hashes.
- Added 68 hermetic CIK, configuration, HTTP request, pacing, retry, rate-limit, cache,
  safe-write, normalization, provenance, integration, bounded-Hypothesis, source-order, and
  subprocess-determinism tests. The full suite has 186 passing tests; ordinary tests use only
  HTTPX `MockTransport` and make no live network request.
- Added direct runtime dependency `httpx>=0.28,<1` because the fixed harness required HTTPX but it
  was absent. `uv lock` selected HTTPX 0.28.1 and only its five transitive packages; no existing
  dependency was upgraded or removed. ADR-011 records this dependency decision.
- Added or changed: `pyproject.toml`, `uv.lock`, `docs/DECISIONS.md`, `src/quantcheck/__init__.py`,
  `exceptions.py`, `hashing.py`, `sec_adapter.py`, `scripts/generate_reviewed_sec_fixture.py`,
  `tests/test_sec_adapter.py`, and the SEC files plus README under `tests/fixtures/`; updated this
  handoff and the affected checksum entries.
- `uv sync --all-groups`, frozen sync, Ruff check/format, MyPy, all 186 tests, lock verification,
  both reviewed fixture checks, and every harness checksum pass with Python 3.12.13.
- Live SEC downloading was not run. The committed fixture is explicitly a curated public
  field-shape excerpt, not a claimed verbatim download; current SEC fair-access guidance must be
  verified before a public-release live run.

## Milestone 5 verification

- Added the exact `value_scaled_unit_unchanged` subtype. Eligible targets are end-of-day available
  nonzero observations in an exact `ComparableSeriesKey` with at least three chronological clean
  observations and at least one immediately adjacent nonzero comparator. The reviewed fixture has
  17 eligible clean observations.
- Selection uses the benchmark target-count rule and SHA-256 ranking over the Unit Drift namespace,
  spec version, seed, and stable record ID. Severity fixes factor/fraction pairs at low `100/0.02`,
  medium `1000/0.05`, and high `1000000/0.10`; unsupported subtype and transformation parameters
  are rejected.
- Injection changes only value, optional corrupted source text, and modified-record identity. It
  preserves unit, dimensions, lineage, provenance, and unaffected logical records; exact clean and
  corrupted values plus the factor remain in the private manifest.
- The detector accepts only `AuditInputSnapshot` and its own validated configuration. The frozen
  benchmark defaults are ratio threshold `50` and supported scale factors `100`, `1000`, and
  `1000000`. It uses exact `ComparableSeriesKey` grouping, chronological immediate neighbors,
  symmetric absolute Decimal ratios, and a supported correction that restores every usable local
  ratio below threshold. One-neighbor evidence is `suspicious`; two-neighbor evidence is `strong`.
- Hard negatives cover the reviewed acquisition-driven large jump, loss-to-profit and zero
  transitions, different entities, concepts, units, dimensions, and period shapes, insufficient
  history, restatement metadata without scale evidence, and explicit `source_status` value
  `legitimate_exception`. The reviewed clean control emits no findings.
- Matching requires exact Unit Drift class, `value.scale_discontinuity` rule, one exact corrupted
  record ID, and a candidate correction equal to the injected factor or reciprocal by Decimal
  comparison. Wrong class, wrong record/rule/factor, duplicates, unmatched findings, misses, and
  ambiguity remain explicit. The false-positive denominator is the 17 clean observations meeting
  the detector comparability prerequisites; null metric conventions remain unchanged.
- Controlled `manifest_assisted_exact_replay` restores original logical records and the clean
  snapshot hash without mutation and is idempotent. `aggregate_value_v0_1` selects one exact
  concept/namespace/unit/dimensions/period-shape group at the configured end-of-day cutoff and uses
  the same function for all three inputs. The reviewed aggregate is `1803000000` clean,
  `173001630000000` corrupted, and `1803000000` repaired; absolute change is `172999827000000`,
  relative change is `95951.096505823627287853577371048252911813643926789`, and exact replay
  equality is true.
- Added 73 focused cases: 22 configuration/eligibility/injection/determinism, 27 detector/isolation/
  hard-negative, 10 exact matching/metrics/regression, and 14 replay/aggregate/artifact/property/
  subprocess cases. The full suite has 259 passing tests. Unit Drift focused tests, all 38
  look-ahead tests, and all 68 SEC adapter tests pass independently.
- Repeated runs, reversed records, irrelevant ineligible records, runtime timestamp changes, and
  `PYTHONHASHSEED` values 1 and 987654 preserve the documented logical identities or canonical
  bytes. The reviewed seed-zero case has two faults, two findings, two exact matches, no false
  positives or negatives, precision/recall/F1 of 1, and false-positive rate 0/17. Stable Unit Drift
  IDs and finding hashes are regression-tested; both reviewed fixtures and Milestone 1 goldens are
  unchanged.
- Added `unit_drift_contract.py`, `unit_drift_series.py`, `unit_drift_injection.py`,
  `unit_drift_detection.py`, `unit_drift_scoring.py`, `unit_drift_repair.py`, and
  `unit_drift_case.py`; extended `schemas.py` and `research.py`; added `unit_drift_helpers.py` and
  four focused test modules; updated this handoff and its checksum.
- Frozen sync, Ruff check/format, MyPy, all 259 tests, lock verification, both reviewed fixture
  checks, focused/regression suites, and every harness checksum pass with Python 3.12.13. The
  initial plain `uv sync --frozen --all-groups` baseline attempt exited 127 because `uv` was not on
  `PATH`; the discovered `uv` 0.12.1 binary then exited 2 when its default cache path was blocked by
  the filesystem sandbox. All required commands were rerun successfully through that exact binary
  with a writable temporary uv cache; no project file was changed to address
  either environmental condition.
- No runtime or development dependency, `uv.lock`, reviewed fixture, golden vector, fault contract,
  or architecture decision changed.

## Milestone 6 verification

- Added the exact `exact_occurrence_copy` subtype for fault type `duplicate_observation` and rule
  `occurrence.exact_duplicate`. Severity defaults target 0.01/0.05/0.15 of eligible clean records;
  target counts use the benchmark minimum-one ceiling/cap rule.
- Eligibility operates on records available at the configured end-of-day cutoff and excludes every
  record already in a clean exact-fingerprint group larger than one. Selection ranks stable source
  record IDs with SHA-256 over the exact Duplicate namespace, spec version, seed, and eligible-unit
  key. The reviewed case has 26 eligible fingerprints and selects four targets at high severity.
- Injection preserves every original occurrence and creates one semantic copy per selected source.
  The copy preserves `source_row_id`, financial fields, provenance, and lineage, while receiving a
  distinct deterministic duplicate record ID using copy ordinal 1. Manifest roles are original
  1 / corrupted group 2 / created 1 / removed 0 / reference 0, with source-to-created relationships
  confined to the private manifest.
- The detector accepts only serialized or in-memory `AuditInputSnapshot` plus a strict empty
  detector configuration. It groups the documented fingerprint fields: source row, entity and
  concept namespaces/IDs, canonical value, unit, period dates, filing and availability dates,
  accession, revision, and dimensions. It emits one stable, proven-by-contract finding per group,
  including the fingerprint/hash, sorted IDs, source row, and group size. Public finding severity
  is fixed at medium by ADR-012 because the fault specification did not assign one.
- Hard negatives cover different source rows, entities and namespaces, concepts and namespaces,
  values, units, dimensions, period shapes/dates, filing/availability dates, accessions, revisions,
  legitimate amendments, same-value source occurrences, and same values in other periods. The
  higher-authority fingerprint contract excludes `form`, labels, and non-semantic notes, so those
  fields alone do not split a group. The reviewed clean control emits no findings.
- Matching requires the exact Duplicate class and rule, exact original/created two-record group,
  consistent manifest roles, and exact public fingerprint/hash/group evidence. Wrong class/rule,
  fingerprint, source/created relationship, partial/additional groups, duplicates, unmatched
  findings, misses, and ambiguity remain explicit. Duplicate findings cannot increase recall. The
  false-positive denominator is the 26 distinct clean singleton fingerprints eligible for grouping.
- Controlled `manifest_assisted_exact_replay` validates manifest roles, fingerprint evidence, and
  duplicate IDs, removes only injected created occurrences, preserves original and legitimate
  clean records, restores the exact clean snapshot ID/hash, is non-mutating, and is idempotent.
- `aggregate_value_v0_1` uses the same pure calculation for clean/corrupted/repaired inputs and
  changes the reviewed exact Revenue/USD/consolidated/duration aggregate from `1803000000` to
  `2008000000`, then back to `1803000000`; the exact signed double-counting change is `205000000`
  and group record count changes 17 to 20 to 17. `record_count_v0_1` changes total occurrences
  26 to 30 to 26 and duplicate groups 0 to 4 to 0. Both repaired output hashes equal clean.
- Added 71 focused tests: 25 configuration/eligibility/injection/identity/determinism, 23 detector/
  isolation/fingerprint hard-negative, 10 exact matching/metrics/ambiguity, and 13 repair/impact/
  artifact/property/subprocess cases. The full suite has 330 passing tests; the 38 Look-Ahead,
  68 SEC adapter, and 73 Unit Drift tests pass independently.
- Repeated runs, reversed source and audit records, irrelevant ineligible clean groups, serialized
  audit reload, bounded Hypothesis seeds, and `PYTHONHASHSEED` values 1 and 987654 preserve exact
  logical bytes. The reviewed case has four faults, four findings, four exact matches, no false
  positives or negatives, precision/recall/F1 of 1, and false-positive rate 0/26. Detector source
  inspection and audit-byte assertions confirm no manifest, seed, severity, target count, copy
  ordinal, role, or source-created answer key crosses the audit boundary.
- Added `duplicate_contract.py`, `duplicate_fingerprint.py`, `duplicate_injection.py`,
  `duplicate_detection.py`, `duplicate_scoring.py`, `duplicate_repair.py`, and `duplicate_case.py`;
  extended `schemas.py` and `research.py`; added `duplicate_helpers.py` and four focused test
  modules; updated ADR-012, this handoff, and the affected checksums.
- Frozen sync, Ruff check/format, MyPy, focused and regression suites, all 330 tests, lock
  verification, both reviewed fixture checks, Milestone 1 goldens, cross-hash-seed checks, and every
  harness checksum pass with Python 3.12.13 and `uv` 0.12.1 through the writable cache
  a writable temporary uv cache.
- No runtime or development dependency, `pyproject.toml`, `uv.lock`, reviewed fixture, golden
  vector, fault specification, or architecture contract changed. ADR-012 records the subtype label
  and fixed public finding severity needed to complete otherwise underspecified artifact fields.

## Milestone 7 verification

- Added fault type `revision_overwrite`, exact subtype `later_vintage_in_earlier_state`, spec
  `0.1.0`, and primary rule `revision.later_vintage_in_earlier_state`. ADR-013 fixes only the
  previously underspecified relative-size formula/zero policy, eligibility-unit payload, public
  finding severity/evidence nesting, subtype label, and exact growth-ranking calculation.
- Eligible units group only by canonical `EconomicFactKey`, use strict source-supported revision
  order, and select the latest clean occurrence visible at the case end-of-day cutoff plus its next
  truly unavailable revision. Clean availability must equal filing; accessions, revision IDs, and
  source rows must be distinct; controlled context fields must agree; values must differ; and
  `abs(later - historical) / abs(historical)` must meet the severity minimum of 0.01/0.05/0.20.
  Zero historical values and ambiguous, same-day, delayed-availability, same-value, unrelated, or
  changed-context histories are rejected or ineligible rather than guessed.
- Target fractions are low 0.02, medium 0.05, and high 0.10 with the benchmark
  zero/minimum-one/ceiling/cap rule. Selection ranks the full canonical history-unit SHA-256 by the
  Revision namespace, fault spec, seed, and stable unit ID. The reviewed medium case has one
  eligible Aster Q1 R1→R2 history and selects it; synthetic focused controls exercise a 25% revision
  at high severity.
- Injection replaces the historical occurrence with a modified occurrence carrying the later
  value/lexical value, source row, filing date, accession, revision ID, and source locator while
  retaining the historical `available_on`. It preserves economic identity and controlled context,
  keeps the true later source record in the full snapshot, and leaves all unrelated records
  logically unchanged. Manifest roles are original 1 / corrupted 1 / created 1 / removed 1 /
  reference 1, with canonical hidden copies of the exact historical and reference records plus
  reversible mutations and point-in-time relationship evidence.
- The detector accepts only `AuditInputSnapshot` and a strict empty configuration. It emits fixed
  high-severity, `proven_by_contract` findings when a non-null-accession source occurrence satisfies
  `available_on <= audit as_of_date < filed_on` and `available_on < filed_on`. Evidence contains the
  exact economic fact key, record/revision/source-row/accession identity, availability/filing/as-of
  dates, source name/locator, and detector-visible lineage context. Source inspection and canonical
  audit-byte assertions prove no manifest, injector, repair, original value/ID, seed, case severity,
  target fraction/count, rank, or expected finding count crosses the audit boundary.
- Primary matching requires the exact fault class, spec/subtype, rule, one corrupted occurrence,
  later revision/source/accession identity, as-of date, complete public evidence payload, and
  internally consistent original/reference/corrupted manifest roles. Wrong or incomplete evidence,
  wrong class/rule/record/relationship, additional records, duplicates, misses, unmatched findings,
  and ambiguity remain explicit. A generic Look-Ahead finding on the same record is a preserved
  cross-detector signal and a false positive under strict Revision Overwrite primary precision.
- The false-positive denominator is the count of clean revision-history units meeting the exact
  case eligibility and severity prerequisites with the cutoff between known revisions. The reviewed
  case is 1/1 exact match with no false positives or negatives, precision/recall/F1 of 1, and false-
  positive rate 0/1. Existing no-fault, no-finding, and zero-denominator null conventions remain.
- Controlled `manifest_assisted_exact_replay` validates injector/spec identity, hashes, all role
  relationships, hidden records, source-supported chronology, relative-size evidence, fault and
  modified-record IDs, mutations, public matching evidence, and the unchanged later reference. It
  restores the exact clean snapshot ID/hash without mutation, is idempotent, preserves unrelated
  records and legitimate later revisions, and rejects inconsistent or forged manifests safely.
- Added `growth_ranking_v0_1`: exact configured prior/current periods, latest strictly ordered
  visible revision per entity/period, Decimal `(current - prior) / abs(prior)`, deterministic
  descending ranking, and entity-identity tie breaks. The same pure function changes Aster's
  reviewed growth from `0.11111111111111111111111111111` to
  `0.16666666666666666666666666667`, leaves the reviewed rank/top-two membership unchanged, records
  a maximum absolute growth change of `0.05555555555555555555555555556`, and returns exactly to the
  clean output hash after replay.
- Added seven implementation modules (`revision_overwrite_contract`, `series`, `injection`,
  `detection`, `scoring`, `repair`, and `case`), extended `schemas.py` and `research.py`, and added
  `revision_overwrite_helpers.py` plus four focused test modules. The 121 focused cases comprise 47
  configuration/eligibility/injection, 24 detection/isolation/hard-negative, 25 matching/metrics,
  and 25 repair/impact/determinism cases; the complete suite has 451 passing tests.
- Repeated runs, reversed full-source and audit order, reordered nested mappings, unrelated records,
  irrelevant revision groups, canonical serialization/reload, bounded Hypothesis seeds, subprocess
  execution, and `PYTHONHASHSEED` values 1 and 987654 preserve the required selected targets or exact
  logical bytes. Look-Ahead, SEC, Unit Drift, Duplicate, schema, serialization, golden, and audit-
  boundary regressions pass independently; both reviewed fixture regeneration checks are unchanged.
- Frozen sync, Ruff check/format, strict MyPy, focused and regression suites, all 451 tests, lock
  verification, fixture checks, explicit hash-seed comparisons, and every harness checksum pass
  with Python 3.12.13 and `uv` 0.12.1 through a writable temporary cache.
- No runtime or development dependency, `pyproject.toml`, `uv.lock`, reviewed fixture, golden vector,
  fault specification, or architecture contract changed. Changed files are `IMPLEMENT.md`,
  `CHECKSUMS.md`, `docs/DECISIONS.md`, `src/quantcheck/schemas.py`, `research.py`, the seven Revision
  Overwrite modules, and the five focused helper/test files.

## Milestone 8 verification

- Added benchmark specification `0.1.0` contracts for normalized logical configuration, explicit
  development seeds `0-9` and validation seeds `100-109`, prohibited final seeds `1000-1009`, exact
  fault profiles, expanded cases, public/private references and indexes, case status and failure,
  sanitized score/research summaries, runtime metadata, standard in-memory case results, and
  aggregate group/report schemas. Unknown fields, unsupported fixtures/components/severities,
  incompatible configurations, duplicate dimensions/seeds, empty matrices, and impossible status
  combinations are rejected.
- Expansion supports Look-Ahead, Unit Drift, Duplicate Observations, and Revision Overwrite across
  configured severities and classified seeds. Benchmark fault case IDs include all four exact
  detector configurations, while `fault_case_id` preserves the byte-for-byte completed
  fault-family identity used by its private manifest; controls use a dedicated namespace. Benchmark
  ID is the full logical-configuration SHA-256. Inputs are normalized and cases execute
  sequentially by lexicographic benchmark case ID; output roots, runtime timestamps, and environment
  details are excluded from logical identity.
- The explicit dispatcher delegates to the four completed case functions without passing manifests
  into detectors or changing injector, detector, matching, replay, or research behavior. Every case
  runs all four detectors on the sanitized audit input; findings are combined canonically and the
  existing fault-specific matcher/scorer applies strict primary-class precision, retaining
  cross-detector findings as false positives where required. Clean controls likewise run all four
  detectors. The adapter preserves Duplicate record-count impact privately and exposes only
  record-free/value-free research summary fields publicly.
- The 12-case smoke configuration uses medium severity, fault cases at development seed `0` and
  validation seed `100`, and one clean control per fault profile using seed `0`. All 12 cases
  succeeded offline. They injected 10 faults and emitted 15 findings: 10 true-positive faults, zero
  false-negative faults, 10 true-positive findings, five false-positive cross/primary findings, and
  186 eligible clean units. Overall micro precision is
  `0.6666666666666666666666666667`, recall `1`, F1
  `0.7999999999999999999999999996`, and false-positive rate
  `0.02688172043010752688172043011`; eight fault cases changed the controlled research output and
  all eight reproduced the clean research output after exact manifest-assisted replay.
- Public benchmark artifacts are configuration, case matrix, runtime metadata, aggregate report,
  and public index. Successful public case artifacts are configuration, sanitized audit input,
  audit report, score, optional fault-case research summary, and terminal status. Private case
  artifacts contain the clean/corrupted snapshots, manifest, repaired snapshot, evaluation, full
  research impact, and optional Duplicate record-count impact. Index paths are relative and public
  indexes cannot navigate into private files. Serialized-content tests exclude manifest fields,
  hidden role relationships, local paths, seed/severity/target data in audit input, and private
  record-level/value evidence from public output.
- Canonical serialization is validated before a same-directory temporary write, file flush,
  `fsync`, and atomic `os.replace`. Success status is written last. Identical immutable artifacts
  are reused; conflicting bytes are rejected. Resume verifies status schema, case identity, paths,
  content hashes, score, research summary, and known private schemas before reuse. Failed cases are
  retried, partial prior output can complete, and an invalid prior success becomes an integrity
  failure without silently replacing the conflicting logical artifact.
- Structured failures recognize fixture loading, expansion, dispatch and the stage-specific
  injection, audit sanitization, detection, scoring, repair, research, serialization, persistence,
  and aggregation stages. Public failures use stable categories, normalized exception codes, and
  fixed redacted messages; private diagnostics retain the exception class and message without a
  stack trace. Terminal failed cases remain in aggregation and other cases continue. Missing or
  invalid status/score artifacts count as incomplete rather than disappearing.
- Aggregation is rebuilt exclusively from the saved public matrix, statuses, scores, and sanitized
  research summaries. It micro-sums counts overall and by fault, severity, seed class, and seed;
  failed/incomplete cases remain in status totals and are excluded from pooled metrics. Precision
  is null for a no-finding fault group and one for a nonempty fault-free successful group; recall is
  null with no injected faults; F1 is null if precision or recall is null; false-positive rate is
  null with no eligible clean denominator. Public-only disk rebuild reproduces the saved aggregate
  bytes and does not require manifests or the private tree.
- Added six benchmark implementation modules plus exports and explicit benchmark artifact error
  classes. Added 74 Milestone 8 cases: 21 contract/expansion, 15 dispatch/execution, 9 artifact and
  privacy, 15 failure/rerun, 9 aggregation, and 5 smoke/subprocess determinism cases. The complete
  suite has 525 passing tests; all 451 prior tests remain green.
- Repeated execution, reversed configuration lists, canonical serialization/reload, different
  output roots, unrelated parent files, disk-only rebuild, subprocess runs, and
  `PYTHONHASHSEED=1`/`987654` preserve the tested logical IDs and bytes. Byte-identical successful
  reruns skip dispatch after full validation. Controlled failure tests prove one failed case does
  not erase the successful control or other persisted outcomes.
- Frozen sync, Ruff check/format, strict MyPy, all 525 tests, focused benchmark/fault/SEC/
  serialization/golden regressions, lock verification, both reviewed fixture checks, explicit smoke
  and disk-only reruns, subprocess hash-seed checks, privacy scans, and every harness checksum pass
  with Python 3.12.13 and `uv` 0.12.1 through a writable temporary cache.
- No runtime/development dependency, `pyproject.toml`, `uv.lock`, reviewed fixture, golden vector,
  prior fault implementation, or fault specification changed. ADR-014 records only the previously
  missing benchmark identity, expansion, persistence, failure, resume, grouping, and null rules.
  Changed files are `IMPLEMENT.md`, `CHECKSUMS.md`, `docs/DECISIONS.md`, `src/quantcheck/__init__.py`,
  `exceptions.py`, the six `benchmark*.py` modules, `tests/benchmark_helpers.py`, and the six
  `tests/test_benchmark_*.py` modules.

## Milestone 9 verification

- Added the exact Typer surface `ingest sec`, `inject`, `audit`, `evaluate`, `benchmark run`,
  `benchmark smoke`, and `explain`. Root no-argument and `--help` behavior exit successfully and
  list only the six contracted root commands. V0.1 intentionally has no version flag, separate
  `python -m quantcheck` entry point, dashboard command, aggregate-rebuild command, force option,
  or held-out-seed command. The installed `quantcheck` console script points only to
  `quantcheck.cli:app`.
- Expanded `CLI_CONTRACT.md` and added ADR-015 to fix the previously missing exact argument and
  option syntax, strict JSON configuration ownership, output paths, machine envelope, plain human
  rendering, no-argument/version behavior, privacy rules, rerun behavior, and exit mapping. The
  committed `configs/smoke.json` is byte-equivalent to `smoke_benchmark_config()`; the reviewed SEC
  config preserves one explicit CIK, concept/unit/period allowlist, filing window, forms, and a
  contact-free user-agent label.
- CLI configuration loading uses strict existing Pydantic schemas and rejects missing files,
  directories, non-JSON suffixes, malformed/invalid UTF-8 JSON, unknown fields, invalid enums,
  duplicate/held-out seeds, incompatible smoke matrices, and schema-invalid saved artifacts. It
  never converts Decimal through float, inserts paths into logical identity, silently defaults
  after validation failure, or creates the output tree before all command inputs validate.
- Added a reusable saved-case workflow over canonical `BenchmarkCaseConfig`. `inject` delegates to
  the exact fault-family injector; `audit` accepts a sanitized input or canonical snapshot,
  performs the configured end-of-day selection and only `sanitize_for_audit`, then runs the saved
  detector tuple without a manifest parameter; `evaluate` validates manifest/snapshot/audit links
  and delegates matching, scoring, exact repair, and the configured research comparison without
  rerunning injection or detection. All four saved-stage results are byte-identical to the existing
  complete benchmark dispatcher.
- Standalone paths reuse `AtomicArtifactStore`: injection writes a public case config and private
  corrupted snapshot/manifest; audit writes only public sanitized input/report; evaluation writes
  only private repaired/evaluation/research artifacts; SEC raw content remains in the existing
  accepted cache and its normalized snapshot is public. Immutable identical bytes are reused and
  conflicts are rejected; no second serialization, hashing, atomic-write, or overwrite system was
  added.
- Command-local `--json` emits exactly one canonical result envelope to stdout. It preserves nulls,
  exact strings, stable key ordering, and output-root-relative public paths without prose or ANSI.
  Human output is stable plain text. Expected diagnostics go to stderr without tracebacks. Exit
  codes are 0 success, 2 user/configuration input, 3 saved-artifact/collision/integrity/persistence,
  4 SEC source/cache/normalization, 5 structured failed or incomplete benchmark, and 10 unexpected
  internal error. Failed and incomplete benchmark outcomes retain sanitized public counts and never
  claim success.
- Serialized privacy assertions exclude manifests, target counts/IDs, pre-corruption values,
  original/reference role relationships, value-bearing private research artifacts, private paths,
  local absolute paths, secrets, and private exception messages from machine and human output.
  `explain` accepts only a saved public audit-report finding or case status and never reruns a
  detector.
- Added 53 CLI tests: 25 contract/help/validation/error cases, 12 saved-workflow/delegation/privacy
  cases, 10 benchmark/resume/subprocess cases, and six offline SEC cases. The complete suite now has
  578 passing tests; the prior 525 tests remain green. The independent CLI, 74 benchmark, 38
  Look-Ahead, 73 Unit Drift, 71 Duplicate, 121 Revision Overwrite, 68 SEC, and 74 combined
  serialization/schema/fixture/audit-boundary suites all pass.
- Repeated CLI runs reuse validated successes without dispatch, different output roots and option
  ordering preserve logical IDs and machine data, public-only aggregate reconstruction reproduces
  saved bytes, subprocess machine output parses cleanly, and `PYTHONHASHSEED=1` and `987654` return
  identical benchmark/report identifiers and counts. The documented 12-case smoke command and one
  standalone inject/audit/evaluate/explain chain succeeded offline; a controlled invalid-input
  command returned canonical JSON and exit 2.
- Added direct runtime ranges `typer>=0.12,<1` and `rich>=13,<15` exactly when the CLI first used
  them. The lock selects Typer 0.27.1, Rich 14.3.4, annotated-doc 0.0.5, markdown-it-py 4.2.0,
  mdurl 0.1.2, and shellingham 1.5.4; Pygments 2.20.0 was already present through pytest. No prior
  package was upgraded or removed. Rich is used only by Typer help rendering, not by application
  result rendering.
- Frozen sync, Ruff check/format, strict MyPy, focused/regression suites, all 578 tests, lock
  verification, both reviewed fixture checks, serialization goldens, explicit help and command
  invocations, offline SEC replay, smoke rerun, public-only aggregate rebuild, subprocess hash-seed
  checks, privacy scans, and every updated harness checksum pass with Python 3.12.13 and `uv` 0.12.1
  through a writable temporary uv cache. The first dependency-add attempt failed only because
  sandbox DNS was unavailable; the approved retry resolved and locked the required packages.
- Changed files are `README.md`, `IMPLEMENT.md`, `CHECKSUMS.md`, `pyproject.toml`, `uv.lock`,
  `docs/CLI_CONTRACT.md`, `docs/DECISIONS.md`, both files under `configs/`,
  `src/quantcheck/benchmark_dispatch.py`, `cli.py`, `cli_models.py`, `saved_case_workflow.py`,
  `tests/cli_helpers.py`, and the four `tests/test_cli_*.py` modules. No existing fault family,
  detector, scorer, repair rule, research calculation, benchmark schema, reviewed fixture, golden
  vector, dashboard, or final held-out result changed.

## Milestone 10 verification

- Added `public_artifact_reader.py` with a strict `public/artifact_index.json` entry point,
  existing Pydantic schema reuse, every-indexed-byte SHA-256 verification, runtime-schema and
  benchmark/case/audit/score/research/failure link validation, fixed approved roles, matrix-derived
  incomplete preservation, and absolute/Windows/traversal/private/cross-case/symlink-escape path
  rejection. The loader resolves and reads only below the selected `public/` tree and works after
  the entire private tree is removed.
- Added one immutable `BenchmarkPresentation` transformation shared without duplication by the
  Streamlit and HTML surfaces. It converts canonical metric strings directly to `Decimal`, retains
  nulls, failed and incomplete cases, exact saved aggregate groups, sanitized research
  counts/booleans, and public findings/evidence. It omits roots, destinations, `fault_case_id`,
  clean snapshot hashes, manifests, hidden role relationships, pre-corruption/private research
  values, and private diagnostics.
- Added the standalone read-only `dashboard/app.py` entry point with overview/status/overall
  metrics, saved group tables, all-default case filters, selected-case public configuration,
  score/research/failure display, forensic finding evidence, and visible methodology/limitations.
  It requires `--artifacts`, stops with sanitized errors, uses only Streamlit-native components,
  and has no CLI integration. `.streamlit/config.toml` disables usage telemetry for offline use.
- Added `html_summary.py` and the thin `scripts/render_html_summary.py` wrapper. The semantic UTF-8
  report embeds CSS only, escapes every artifact-derived string, contains the required identity,
  metric, research, case, failure/incomplete, finding, privacy, and limitation sections, and embeds
  no JavaScript, remote resource, render timestamp, environment/output path, or random identifier.
  Atomic writes reuse identical bytes and reject conflicts, invalid suffixes, directories, and
  unwritable destinations without partial output.
- Added `docs/DASHBOARD_AND_HTML.md` and ADR-016 to fix the strict public-only format, loader and
  path rules, saved-metric/null policy, launch commands, deterministic HTML contract, output
  collisions, offline workflow, telemetry setting, and the authority resolution that the
  pre-release Milestone 10 UI does not implement the lower-authority plan's eventual manifest
  reveal. README now documents both standalone commands while the exact six CLI root commands
  remain unchanged.
- Added 52 focused tests: 18 reader/path/schema/hash/identity/state cases in
  `test_public_artifact_reader.py`; seven exact model/group/null/research/order cases in
  `test_presentation.py`; 13 HTML determinism/escaping/privacy/output/subprocess cases in
  `test_html_summary.py`; eight official Streamlit AppTest/argument/error/case cases in
  `test_dashboard.py`; and six source/runtime/serialized-boundary/import-isolation cases in
  `test_presentation_isolation.py`. Shared session fixtures create one smoke, one failed, and one
  valid incomplete saved benchmark. The full suite has 630 passing tests; all 578 prior tests remain
  green without weakened assertions.
- The offline demonstration ran the committed 12-case smoke configuration at benchmark ID
  `247ecdbf581f6437fb04d0ff4337165cfe07a116f7f374690e13798dc6b39203`, copied only `public/`, and
  validated report ID `4a2e530dc4a5fcb352e9eaa9423ef34a976a01bd57f8a0964058f7a84265fbca`.
  Dashboard/model headlines matched the saved aggregate at 12 configured/successful, zero
  failed/incomplete, precision `0.6666666666666666666666666667`, recall `1`, and F1
  `0.7999999999999999999999999996`. Two different HTML destinations were byte-identical at SHA-256
  `eac37a19944b6a2f1dfeed0088a8634e9116f09399b99aae2f8f1b67b61b77d9`; subprocess parsing,
  `PYTHONHASHSEED=1`/`987654`, output-root independence, escaping, and private-field/path scans pass.
- Frozen sync, Ruff check/format, strict MyPy, all 630 tests, lock verification, CLI/benchmark/four-
  family/SEC/schema/golden/audit-boundary regressions, both reviewed fixture checks, explicit HTML
  hash-seed tests, public-only rendering, headless Streamlit AppTest, a local Streamlit health
  startup, and every updated harness checksum pass with Python 3.12.13 and `uv` 0.12.1 through
  a writable temporary uv cache. The first lock/sync attempts failed only because the default
  cache and sandbox DNS were unavailable; approved retries resolved and installed the locked
  dependency. The first local Streamlit bind was sandbox-blocked; the approved local-only retry
  started Uvicorn on port 8765 and its health request succeeded. No interactive browser was opened.
- Added direct runtime range `streamlit>=1.60,<2`; the lock selects Streamlit 1.60.0 and 34
  transitive packages required by Streamlit. No prior package was upgraded or removed. ADR-016 is
  the only new decision. No fault family, detector, matching/scoring/denominator, repair, research,
  benchmark identity/aggregate, CLI root command, fixture, golden vector, held-out seed, or release
  evidence changed.
- Changed files are `.streamlit/config.toml`, `README.md`, `IMPLEMENT.md`, `CHECKSUMS.md`,
  `pyproject.toml`, `uv.lock`, `docs/DASHBOARD_AND_HTML.md`, `docs/DECISIONS.md`,
  `src/quantcheck/exceptions.py`, `public_artifact_reader.py`, `presentation.py`, `html_summary.py`,
  `dashboard/__init__.py`, `dashboard/app.py`, `scripts/render_html_summary.py`,
  `tests/conftest.py`, `presentation_helpers.py`, `test_public_artifact_reader.py`,
  `test_presentation.py`, `test_html_summary.py`, `test_dashboard.py`, and
  `test_presentation_isolation.py`. Known limits are benchmark spec `0.1.0`, local read-only
  Streamlit, no browser-level automation beyond official AppTest/headless startup, no committed
  benchmark truth for the UI, and no manifest/private-value browsing.

## Milestone 11 verification

- Added the exact release partition `1000`–`1009` and strict validation that final seeds cannot be
  mixed, omitted, extended, or mislabeled. Ordinary benchmark APIs, the six-command CLI, and saved
  inject/audit/evaluate stages reject final cases before creating output. Only
  `run_frozen_release_benchmark` can dispatch them after verifying the candidate record and every
  frozen source/configuration byte.
- Added canonical `configs/rehearsal.json` and `configs/release.json`, release freeze builder/checker,
  final runner, and public evidence verifier. The matrix is 4 profiles × 3 severities × 10 seeds =
  120 fault cases, plus one control per profile/severity = 12 controls and 132 configured cases.
- The validation rehearsal ran all 132 cases. Two duplicate cases initially failed because the case
  orchestrator incorrectly required corruption to change the configured aggregate even when a
  valid duplicate fell outside that group. The pre-freeze fix now preserves those valid zero-impact
  cases while retaining record-count evidence. Rehearsal then completed 132/132 with report ID
  `bd80a545ce9b5d64c30a898eaa0c170102b564a8d32e117cbaa459f762bbdc26`;
  public-only rebuild, dashboard AppTest, resume, two hash seeds, and byte-identical HTML passed.
- Candidate 1 (`b5c4afe7340f129e4876e6ea0ba1cba74bd2076fd323da43751d7829b744de73`)
  was invalidated before any final seed ran because default sdist discovery packaged private
  rehearsal artifacts. Candidate 2 added an explicit Hatchling allowlist, passed package scans, and
  froze at `2026-08-04T00:45:25Z`. Its ID is
  `2f1bbc3d8a4e80715ac378691df90805c6c78f5cd32c3be49a0a49b537d439fb`;
  freeze SHA-256 is `5cdf0313dbdf2115ac85e9b2c299a5d1fb62305bb07757ae9ecd8bf60f3260b9`.
- The first frozen held-out execution completed all 132 cases with zero failed/incomplete. Benchmark
  ID is `e5a1770a7599c76d628769fbc8d534f7e3807f455241d8a5306299100ae811bc`,
  matrix ID `d57f0e45bb434145978fb13c41c7a6d1c031e068f47a17ab943c9df437e44670`,
  report ID `6606132b146a24300dc55ce67e6ef8cb5995c2628b2c371c7c30e4d4fa6225b9`,
  and public index ID `29a4e2d98ac3d01253bef4debf14a860141b5d73b7e360e9f72b9101df63eca3`.
- Final micro evidence is 170 injected faults, 247 findings, 165 true-positive faults/findings, five
  false-negative faults, 82 false-positive findings, and 2,035 eligible clean units. Exact precision
  is `0.6680161943319838056680161943`, recall `0.9705882352941176470588235294`, F1
  `0.7913669064748201438848920862`, and false-positive rate
  `0.04029484029484029484029484029`. All 12 controls emitted zero findings. Controlled research
  changed in 107/120 fault cases and all 120 exact replays reproduced the clean research output.
- Per-family precision/recall: duplicate `1`/`1`; look-ahead `0.5`/`1`; revision overwrite `0.5`/`1`;
  unit drift `0.6140350877192982456140350877`/`0.875`. Unit drift retained five honest misses and 22
  false positives from immediate-neighbor ambiguity. Look-ahead/revision correlated violations
  retained 60 cross-detector false-positive findings under strict primary-label scoring.
- Two complete frozen reruns under `PYTHONHASHSEED=1` and `987654` produced byte-identical 783
  indexed public and 882 indexed private logical artifacts. Runtime metadata is intentionally
  excluded. Reversed logical dimensions normalized to the same benchmark and matrix; public-only
  aggregate reconstruction, presentation, alternate output roots, identical resume, canonical
  reload, and immutable-conflict rejection passed. Original/public-only/repeat HTML bytes share
  SHA-256 `78422911eef3f0e6fed32416ba1eed36046b363ed805a154bb4aeeaad64c80ee`.
- Created an approved public-only evidence root with 785 public files, deterministic HTML, and no
  private tree. Reader/rebuild/presentation/HTML/AppTest pass; no symlink, answer-key field,
  manifest, private diagnostic, local path, cache path, token signature, credential, raw SEC cache,
  or private reference was found. Streamlit AppTest rendered 132/132/0/0/12 without exception. The
  sandbox blocked a loopback server bind and the approval reviewer was unavailable, so the live
  health endpoint remains an explicitly external environment gate.
- Package metadata is version `0.1.0`, Python `>=3.12,<3.13`, MIT, and Hatchling. Wheel/sdist build
  offline and contain no generated artifact tree, manifests, caches, bytecode, secrets, or local
  paths. A clean temporary environment installed the exact lock and wheel, passed dependency
  compatibility, CLI help, 12/12 smoke, public loading, HTML rendering, and confirmed ordinary
  `import quantcheck` does not import Streamlit. Exact final package/archive hashes are stored
  outside the self-containing sdist in `dist/SHA256SUMS`.
- Added 15 focused tests over the Milestone 10 baseline: ten final-partition/freeze/release-path
  tests, one duplicate zero-impact regression, and four evidence arithmetic/document/package tests.
  The final full suite has 645 passing tests. Frozen sync, Ruff check/format, standard and extended
  strict MyPy, lock/fixture/freeze/checksum validation, focused fault/CLI/benchmark/SEC/presentation
  suites, smoke, release, public-only, determinism, package-content, and clean-install gates pass.
- Added no dependency and changed no lock selection, detector threshold, matching rule, denominator,
  severity, target selection, fault configuration, research calculation, or saved held-out result.
  ADR-017 records the release partition/freeze and ADR-018 the MIT license. Added `LICENSE`,
  `CHANGELOG.md`, `CONTRIBUTING.md`, `RELEASE_NOTES.md`, final results, reproducibility, threat model,
  demo storyboard, machine evidence, candidate history, and local gate status. No Git metadata is
  present; remote CI, commit/tag, registry, live SEC, hosted site, and publication claims were not
  fabricated.

## Completed work

- V2 Codex harness created.
- Toolchain decisions fixed.
- Temporal and same-day semantics fixed.
- Public artifact contracts specified.
- Canonical serialization and hashing specified.
- Fault-specific benchmark rules specified.
- Milestone 0 repository bootstrap and local quality toolchain completed.
- Milestone 1 canonical schemas, serialization, hashing, identifiers, and goldens completed.
- Milestone 2 deterministic synthetic fixture, point-in-time, revision, and sanitization utilities
  completed.
- Milestone 3 deterministic look-ahead injection, sanitized detection, exact scoring, controlled
  replay, and research-impact vertical slice completed.
- Milestone 4 cache-first SEC Company Facts download/replay, exact normalization, provenance, and
  hermetic verification completed.
- Milestone 5 exact Unit Drift injection, sanitized local-ratio detection, strict matching,
  manifest-assisted replay, and aggregate-impact vertical slice completed.
- Milestone 6 exact occurrence-copy injection, sanitized fingerprint-group detection, strict
  matching, manifest-assisted removal, and double-counting impact vertical slice completed.
- Milestone 7 explicit revision-history selection, later-vintage overwrite injection, sanitized
  primary/cross-detector evidence, strict scoring, exact replay, and growth-ranking impact vertical
  slice completed.
- Milestone 8 deterministic configuration and expansion, four-family dispatch, public/private
  atomic artifacts, structured failures, safe resume, disk-only aggregation, and offline smoke
  benchmark completed.
- Milestone 9 strict Typer CLI, installed entry point, saved-stage workflow, canonical machine
  output, stable exit behavior, privacy-safe rendering, and offline command verification completed.
- Milestone 10 strict public-only presentation loading, shared immutable view model, read-only
  Streamlit forensic dashboard, and deterministic self-contained HTML summary completed.
- Milestone 11 explicit frozen final-seed execution, held-out evidence, public-only release package,
  failure analysis, reproducibility/adversarial verification, and local package release completed.

## Current risks

- GitHub Actions is configured but has not run in this local harness.
- This checkout has no `.git` metadata, so review used direct file inspection rather
  than `git diff`.
- Research artifacts omit top-level identity and timestamp fields required by the common artifact
  convention; they are deferred pending a contract clarification.
- Only source, modified, and duplicate record IDs have fully specified payload helpers. Other
  prefixes use the generic stable-ID function until their artifact payloads are specified.
- Schemas require explicit filing and availability dates but cannot prove the external rule that
  justifies a difference between them; adapters and injectors must supply that context later.
- Snapshot and audit-input identifiers use the generic stable-ID function because their dedicated
  artifact payload helpers remain unspecified; full content integrity remains in snapshot hashes.
- The fault documents do not specify an ordinal base or a separate finding-severity mapping.
  Milestone 3 uses zero-based selected order and maps the documented 7/14/30-day lag thresholds to
  low/medium/high findings; changing either convention would change logical artifacts.
- Repair is controlled manifest-assisted exact replay, not detector-only or automatic remediation.
  It does not establish detector-only or automatic production remediation.
- The benchmark and CLI support only the reviewed synthetic fixture, explicit development,
  validation, and freeze-gated final seed partitions, sequential local execution, and the
  `resume_identical` policy. They have no force overwrite, parallel/distributed scheduler,
  database, cloud persistence, or dashboard command. The separate dashboard is a read-only
  saved-artifact view. The smoke benchmark remains correctness evidence; the 120-case release
  matrix is separately frozen and published.
- Standalone inject/audit/evaluate intentionally consume a fully expanded saved
  `BenchmarkCaseConfig`; v0.1 does not provide a second free-form case builder. `evaluate` is a
  controlled manifest-assisted scoring/replay boundary and all value-bearing outputs remain
  private. `explain` reads only public findings and statuses and is not a general artifact browser.
- Invalid benchmark configuration is rejected by strict Pydantic construction before a run exists;
  therefore it cannot produce an artifact-tree failure. Fixture-loading and expansion failures do
  produce benchmark-level public/private failure artifacts and indexes; a physically unwritable
  destination can still prevent its own failure artifact, leaving the configured case incomplete.
- The completed fault-family case functions are monolithic orchestration APIs. An unexpected error
  raised directly by one is conservatively classified as `dispatch`; finer injection/detection/
  scoring/repair/research stages are preserved when a stage-aware orchestration boundary raises
  `BenchmarkStageError`, as the controlled failure tests demonstrate.
- Benchmark code provenance is the explicit distribution label `quantcheck-0.1.0`, component
  versions, Python version, and platform. This checkout has no VCS metadata, so runtime provenance
  cannot include a verified source commit.
- Unit Drift v0.1 deliberately uses only immediate local ratios. Simultaneously scaled adjacent
  targets can mask each other, while a one-neighbor endpoint can make the clean neighbor appear to
  be the scaled observation. The final evidence preserves five misses and 22 unit-drift false
  positives in exact scoring rather than changing selection after seeing detector output.
- Unit Drift legitimate-exception suppression recognizes only detector-safe
  `source_status == "legitimate_exception"`; it does not infer acquisitions or other business
  events from values. The aggregate scenario is a controlled sum of all available occurrences in
  one exact configured group, not statement reconstruction or revision consolidation.
- Duplicate Observations v0.1 supports one exact occurrence copy per fault only. It intentionally
  excludes `record_id`, `form`, labels, and non-semantic notes from its fingerprint, does not use
  fuzzy/business-key deduplication, and does not infer safe deletion from detector output. A clean
  exact fingerprint group is ineligible for injection but remains detector-visible and would be
  preserved by manifest-assisted repair. The aggregate impact is a configured exact group sum,
  not financial-statement reconstruction or revision consolidation.
- Revision Overwrite v0.1 supports only explicit adjacent source occurrences with clean
  filing-date availability, non-null distinct accessions, unchanged controlled context, and a
  nonzero historical value. It does not infer restatements, reconstruct statements, interpret
  amendments, or perform detector-only remediation. The reviewed changed-value history meets low
  and medium relative-size thresholds but not the 20% high threshold; high-severity behavior is
  proven with an explicit synthetic focused history and requires a suitably impactful source case
  in any future high-severity release matrix. The Milestone 8 smoke uses medium severity only.
  Growth impact is a controlled two-period ranking sensitivity, not a trading or financial-loss
  claim.
- SEC v0.1 is intentionally synchronous and one CIK response at a time. It has no automatic cache
  expiry, refresh scheduler, filing HTML parser, statement reconstruction, ticker history, concept
  harmonization, scale conversion, or general segment-dimension support; an allowlisted entry that
  exposes unsupported `dimensions` or `segment` structure is rejected.
- The reviewed SEC fixture is a small curated field-shape test input rather than a live-download
  attestation. Live behavior and current SEC fair-access guidance remain unverified in this
  environment, and no real SEC user-agent/contact value is committed.

## Required handoff update after each task

Record:

- milestone and task completed;
- files changed;
- commands run and outcomes;
- decisions added or revised;
- known limitations;
- exact next task.

## Last updated

2026-08-04
