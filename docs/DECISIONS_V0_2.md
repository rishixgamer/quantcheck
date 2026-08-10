# QuantCheck v0.2 decisions

Architecture decisions for the v0.2 benchmark corpus substrate.

This is a **separate document from `docs/DECISIONS.md`** on purpose.
`docs/DECISIONS.md` is one of the twenty release documents whose bytes
`CHECKSUMS.md` freezes for the immutable `v0.1.0` tag; appending to it would
break that manifest and change the released evidence. ADR-001 through ADR-010
stay exactly as tagged, and the v0.2 decisions are numbered `ADR-V2-nnn` so the
two sequences can never be confused.

---

## ADR-V2-001 — `FinancialFact` is unchanged; no versioned contract change

**Status.** Accepted.

**Context.** The v0.2 mandate permits a versioned change to the canonical
`FinancialFact` contract *if a demonstrated missing field requires one*. The
corpus needs to express: multiple issuers, several fiscal calendars, long period
histories, a wide spread of filing lags, several currencies and per-share and
share units, declared revision histories, dimensioned facts, volatility, and ten
kinds of hard negative.

**Decision.** Change nothing. Every axis is already representable:

* issuer — `entity_id`, `entity_name`;
* fiscal calendar — `period_start` / `period_end` are free dates, so a 4-4-5
  retail period end is expressible without a calendar field;
* filing lag — `filed_on` minus `period_end`, already two distinct concepts;
* unit of measure — `unit` is a free token;
* revision history — the frozen `"<lineage>#r<n>"` marker inside
  `SourceReference.source_row_key`, which `sanitize_for_audit` already drops;
* vendor-delayed availability — `available_on` distinct from `filed_on`;
* dimensioned facts — `dimensions`.

**Consequences.** `src/quantcheck/schemas.py` is untouched, so the v0.1 freeze
record and checksum manifest still verify. The audit boundary is unchanged, so
every v0.1 detector isolation guarantee carries over unmodified. A corpus unit's
partition lives only in corpus metadata and has nowhere to hide in a record —
which is what makes ADR-V2-004's leakage guarantee structural rather than
procedural.

**Rejected.** Adding a `corpus_unit_id` or `fiscal_calendar` field to
`FinancialFact`. Both would be convenient for reporting and both would create a
channel from the corpus into detector-visible data. Reporting reads the corpus
definition instead.

---

## ADR-V2-002 — Corpus adequacy floors are declared before evidence, not after

**Status.** Accepted.

**Context.** v0.1 reported a `revision_overwrite` false-positive rate of `1`
over an eligible-clean denominator of `11`. Arithmetically correct,
statistically meaningless. A corpus needs a stated notion of "enough clean
population for a measurement in this cell to mean anything" — and if that
threshold is chosen after seeing which cells pass, it means nothing either.

**Decision.** Two numbers, frozen in `corpus_contract.py` before any corpus
existed:

* `MINIMUM_CELL_ELIGIBLE_UNITS = 8`, applied to the **best single unit** in a
  partition. One benchmark case runs against one clean source, so a cell spread
  thinly over three units is not measurable by any one case. Eight is the
  smallest count at which the lowest configured target fraction (1% for
  Duplicate, 2% elsewhere, each with a minimum-one ceiling) still selects a
  target from a population large enough to leave clean units behind it.
* `MINIMUM_PARTITION_ELIGIBLE_UNITS = 24`, applied to the partition-wide total,
  so a pooled false-positive denominator is not dominated by one unit.

`CorpusEligibilityRollup` validates that the floors on a saved rollup are the
contract's floors, so a census cannot lower them locally.

**Consequences.** A cell's status is derived arithmetic. `insufficient` is a
corpus defect to fix or declare, never a result to accept.

**These are corpus thresholds, not detector thresholds.** They change how much
data a cell must have; they change nothing about what a detector finds. No
frozen v0.1 threshold moved.

---

## ADR-V2-003 — The census calls the frozen v0.1 eligibility rules, unchanged

**Status.** Accepted.

**Context.** The v0.2 numbers must be readable *against* the v0.1 numbers. A
reimplemented eligibility rule — however faithful — would make every comparison
an argument about whether the two implementations agree.

**Decision.** `corpus_eligibility.eligible_unit_count` has four branches and
each one calls a frozen v0.1 function and does nothing else:
`is_eligible_lookahead_target`, `build_comparable_observations`,
`build_duplicate_groups`, `build_revision_history_units`. These are the same
functions `benchmark_dispatch.eligible_clean_denominator` uses to build a v0.1
clean control's false-positive denominator.

**Consequences.** A v0.2 denominator is the same quantity as a v0.1
denominator, not an analogue of one. Tests call the frozen functions directly
and compare, so a future divergence fails rather than drifts.

An unsupported fault profile raises rather than returning zero: an unmeasured
cell must never read as a measured empty one.

---

## ADR-V2-004 — Partition identity is corpus metadata and cannot reach a detector

**Status.** Accepted.

**Context.** Splitting a corpus into development, validation, and held-out
partitions introduces a failure mode v0.1 did not have: the split becoming a
feature a detector could key on.

**Decision.** Four mechanisms, in decreasing order of how much they rely on
anyone being careful:

1. **Structural.** `AuditInputRecord` has no partition field and drops
   `source_row_key`. There is nowhere to put it.
2. **Constructive.** Detector-visible naming (`source_name`, `source_locator`,
   `audit_dataset_name`) is an opaque hash-derived cohort code, checked by
   `check_detector_visible_naming` at construction. A cohort code is
   hexadecimal, and every partition token contains a non-hex character, so a
   derived code *cannot* spell one.
3. **Identity.** Entity ids are SHA-256 derived rather than allocated in a
   readable order, and are disjoint across partitions.
4. **Test.** Every detector-visible string value is either present in every
   partition or present in exactly one and hash-opaque.

**Consequences.** The leakage test is stated per *value*, not as a substring
search. The real `us-gaap` concept `ResearchAndDevelopmentExpense` contains the
word "development", appears identically in all three partitions, and therefore
carries no partition information. A naive substring test would have failed on
it, and the fix would have been to rename a real taxonomy concept — tuning data
to a test. The precise property is the one worth asserting.

---

## ADR-V2-005 — The held-out corpus gate blocks materialization, not description

**Status.** Accepted.

**Context.** ADR-010 froze this split for reserved final seeds: a reserved seed
may appear in a saved artifact, because released held-out evidence has to stay
readable by the surfaces built to present it, but it may not be *executed*
without authorization. The held-out corpus partition needs the same treatment
for the same reason — its identifiers, hashes, and eligibility counts are
exactly the committed evidence that proves the partition was settled before the
freeze.

**Decision.** `corpus_gate.held_out_corpus_units` is a `ContextVar`-scoped
context manager, standard-library only, importing nothing from `quantcheck`. It
authorizes **materializing records**. Describing a held-out unit needs nothing.
The registry additionally refuses an authorization that does not cover the
complete declared held-out partition, so opening the gate for one convenient
unit is useless.

**Consequences.** `corpus_freeze_v0_2.json` reads with no authorization; it is
rebuilt with one. Exactly one file outside the gate module opens it —
`scripts/corpus_freeze.py` — and a static test asserts that the CLI, the package
modules, and every other script do not.

The two gates are independent: a held-out corpus authorization does not unlock
reserved final seeds, and a final-seed authorization does not unlock corpus
units. Both directions are tested.

---

## ADR-V2-006 — The curated public source class ships a declared placeholder

**Status.** Accepted.

**Context.** The v0.2 mandate asks for curated public real financial-data
fixtures. Ordinary tests make no live network requests (hard invariant 11), and
current SEC guidance must be rechecked before any live run. Meanwhile, hard
invariant 13 requires synthetic, controlled, and real-data claims to stay
clearly distinguished.

**Decision.** Implement the source class by its *reading path*, not by who
authored its bytes: a `curated_public` unit is an SEC EDGAR Company Facts
envelope normalized by the frozen `normalize_companyfacts` under an explicit
allowlist. What ships today is a curated field-shape document in that real
contract — real `us-gaap` concept names, real unit and form vocabularies —
with **placeholder registrants and purpose-built values**.

The placeholder status is machine-readable, not prose:
`CURATED_PUBLIC_IS_PLACEHOLDER = True`, and every such unit's provenance carries
`verbatim_source=False`, `publisher="sec-edgar-companyfacts"`, and
`retrieval_method="in_package_curated_envelope"`.

**Consequences.** Admitting genuine public data later is a change of *bytes*:
replace `curated_public_envelope` with the saved response and re-run the freeze.
The allowlist, normalization path, contract, census, and every test stay as they
are.

The unit cannot support Revision Overwrite — a Company Facts response carries no
declared lineage marker — so the source class does not claim it. That is a
structural limit of the class, declared rather than worked around.

**Rejected.** Using real CIKs with invented values. It would make the unit read
as real company data, which is exactly the distinction invariant 13 exists to
protect.

**Rejected.** Serializing the envelope with `canonical_json_bytes`. The
canonical form encodes a `Decimal` as a JSON *string*, and the frozen adapter
correctly refuses a quoted financial value. `companyfacts_json_bytes` writes
real JSON numbers from canonical decimal text, constructing no binary float.

---

## ADR-V2-007 — External private data is referenced, never held

**Status.** Accepted.

**Context.** Externally supplied vendor or customer datasets are the strongest
external-validity evidence available and the one thing this repository must not
contain.

**Decision.** An `external_private` unit is addressed by a caller-supplied
directory or `QUANTCHECK_EXTERNAL_CORPUS_ROOT`; unset is the supported default
and never an error. Three guarantees are enforced by code rather than promised:

1. `CorpusUnitSpec` **rejects** an `external_private` unit that carries a
   `content_hash` or a diversity profile, because both are derived from record
   content. The validator is the mechanism that keeps licensed content out of a
   committed artifact.
2. `redacted_external_summary` returns identity, partition, and a record count.
   There is no code path that puts an external value, issuer, or row key into a
   repository artifact.
3. The declared SHA-256 is verified against the raw bytes *before* parsing.

**Consequences.** The committed corpus has zero external units, and every test,
gate, and command runs offline without one. The class is exercised against
synthetic external roots under `tmp_path`; no real vendor dataset has been used.

---

## ADR-V2-008 — v0.2 is additive; the v0.1 freeze is not reopened

**Status.** Accepted.

**Context.** `CHECKSUMS.md` freezes 88 files — 67 frozen source and lock files,
`release_freeze.json`, and 20 release documents including `docs/DECISIONS.md`,
`docs/LIMITATIONS.md`, and `docs/METHODOLOGY.md`. `v0.1.0` is an immutable tag.
Meanwhile `tests/test_release_freeze.py` asserted that *every*
`src/quantcheck/*.py` module is in `FROZEN_SOURCE_FILES`.

**Decision.** Every v0.2 module, test, and document is new. No frozen file is
edited, and no corpus module is added to `FROZEN_SOURCE_FILES` — doing so would
change the v0.1 release candidate identity and the checksum manifest, which is
precisely what the tag's immutability forbids. The v0.2 ADRs live in this
document; the v0.2 corpus description lives in `docs/CORPUS_V0_2.md`.

The one edit to an existing file is `tests/test_release_freeze.py` (not
checksum-covered), which now excludes `corpus_*` modules from its
must-be-frozen sweep **and asserts the exclusion is safe**: no frozen module may
contain the string `quantcheck.corpus`. The exclusion is a proof obligation, not
a waiver.

**Consequences.** `scripts/release_checksums.py --check` still reports 88 files
verified, `release_freeze.json` still verifies, and the reviewed fixture still
regenerates to its committed bytes.
`tests/test_corpus_v01_isolation.py` carries the whole guarantee as tests.

`corpus_freeze_v0_2.json` is deliberately outside `CHECKSUMS.md`, which is a
v0.1 release-surface manifest. It has its own verifier.

---

## ADR-V2-009 — Corpus partitions are separate from seed partitions

**Status.** Accepted.

**Context.** v0.1 already has a held-out concept: reserved final seeds
1000–1009, gated by `release_gate`. It would be natural to reuse it.

**Decision.** Do not. A *seed* partition holds out an injection draw; a *corpus*
partition holds out a set of clean sources. They answer different questions and
compose: a future v0.2 benchmark can run reserved seeds over development corpus
units during rehearsal, and reserved seeds over held-out corpus units only for a
release.

`release_gate.reserved_final_seeds` authorizes exactly the seed range
1000–1009 and cannot be widened, so reusing it for corpus units was not
available anyway without editing a frozen module.

**Consequences.** Two independent authorizations with two independent scopes,
neither implying the other. A v0.2 benchmark milestone must open both to produce
a held-out release.

---

## ADR-V2-010 — Selected execution and evaluation use two explicit views

**Status.** Accepted.

**Context.** v0.1 deliberately ran every detector over one sanitized audit
input and scored the resulting combined report against one primary injected
family. A correlated finding from another detector was therefore a strict false
positive even when it expressed a real rule violation on the injected record.
Dropping that finding would conceal evidence; relabeling it as another primary
true positive would inflate recall; changing v0.1 in place would invalidate the
released comparison point.

**Decision.** Add a versioned `quantcheck/benchmark/v2` path with one normalized
`DetectorExecutionConfigV2`. It selects one, several, or all frozen detectors
and nests the existing `BenchmarkDetectorConfigs`, so there is no second
threshold/configuration architecture. Every selected detector still receives
only `AuditInputSnapshot`; its v1 report, findings, provenance, and IDs are
embedded unchanged in a v2 execution envelope.

Evaluation happens only after the corrupted and mandatory paired-clean
executions are finalized. It has two explicit views:

1. `strict_primary_score` delegates to the frozen primary-family scorer over
   the frozen combined-report construction. With all four detectors it is
   byte-identical to the v0.1 report and score for the same input and manifest.
   A subset is marked not all-detector comparable.
2. `production_interpretation` is non-metric and preserves every finding. In
   precedence order, a finding is the exact primary match; an exact equivalent
   present in the paired clean control is independent/background; a non-primary
   finding that uniquely references one injected fault unit is
   secondary/corroborating; everything else is unmatched.

One finding has one category. The frozen scorer retains exact one-to-one recall,
and a secondary finding can attach to at most one fault unit and never affects
recall. A multi-unit relationship is left unmatched. `FaultUnitOutcomeV2`
records the primary finding, secondary findings, and violated rules per injected
unit, while unmatched IDs remain explicitly available as genuinely unexplained.

**Consequences.** Researchers can answer primary detection, other valid rules,
and unexplained findings separately without suppressing correlated evidence.
The production interpretation must not be reported as corrected benchmark
precision or recall. Exact paired-control equivalence is intentionally
conservative: evidence that cannot support a unique relationship stays
unmatched.

**Rejected.** Running only the primary detector by default would hide cross-rule
evidence. Treating every record intersection as corroboration would let one
finding attach to multiple fault units. Recomputing or amending released v0.1
metrics would destroy the comparison baseline.

---

## ADR-V2-011 — v0.2 envelopes are additive; migration is explicit re-execution

**Status.** Accepted.

**Context.** A new evaluation meaning needs new serialized identities, but the
scientific detector outputs inside it have not changed. The installed v0.1 CLI,
release documents, source surface, and checksum manifest are frozen.

**Decision.** Introduce new spec versions and stable-ID namespaces for v0.2
benchmark configs/cases, detector executions, finding interpretations, and
evaluations. Use the existing canonical serializer and atomic artifact store.
Keep nested v1 `AuditReport`, `Finding`, and `ScoreReport` objects byte-for-byte
and retain their original IDs.

There is no in-place or automatic v1-to-v2 migration. A v1 artifact remains v1.
Producing a v2 interpretation requires an explicit new run with a paired clean
control and the private manifest, and writes new v2 paths/IDs. Consumers
dispatch on `spec_version`. The additive CLI is invoked as
`python -m quantcheck.benchmark_v2_cli`; the checksum-frozen installed
`quantcheck` command is not changed or rerouted.

**Consequences.** `CHECKSUMS.md` and `release_freeze.json` remain current and no
v0.1 benchmark metric is retroactively recomputed. Development and validation
may exercise the new contract without authorizing held-out corpus materialization
or reserved final seeds. A future v0.2 release needs its own freeze, checksum
surface, and both authorizations.

---

## ADR-V2-012 — External production audits require an explicit mapping contract

**Status.** Accepted.

**Context.** The corpus substrate can load already-canonical private JSON, but
that is not a production ingestion contract. Customer Parquet, Arrow, CSV, and
Python tables carry source-specific names and—more importantly—source-specific
financial meanings. Guessing availability, revisions, units, periods, or row
identity would make a successful audit less trustworthy than a loud refusal.

**Decision.** Add the versioned `quantcheck/dataset-mapping/v1` contract and a
separate manifest-free audit workflow. Every canonical field is mapped from a
declared column, a declared constant, or (where the frozen schema permits null)
an explicit absent declaration. Availability is either a source date explicitly
meaning first researcher availability or evidenced equality to filing. Revision
lineage is either source-declared lineage plus positive sequence, with paired
nulls explicitly independent, or globally declared absent. Forms, accessions,
matching economic keys, values, and row position never infer lineage.

Values accept only `Decimal`, integer, or canonical fixed-point text. Float and
Arrow floating types are rejected before normalization. Every row has an
explicit source-row ID; deterministic canonical source coordinates are opaque,
while exact upstream row identity and lineage remain private provenance and are
removed by the unchanged audit boundary.

Files are format-declared, SHA-256 checked before parsing, read-only, and
rechecked for change after parsing. Dry-run diagnostics use fixed messages and
make explicit false audit/benchmark/network/manifest claims. Production audit
reuses the existing point-in-time builder, sanitizer, v0.2 selected-detector
execution, and unchanged v1 detector reports. It accepts no manifest, injector,
seed, severity, or fault profile and produces no score.

**Consequences.** Customer audits are operationally independent of benchmark
fault injection and private truth. Equivalent logical rows normalize
identically across supported formats and source order. Ambiguous source
semantics fail closed. The public report contains public detector evidence and
artifact identities, while raw source-row provenance and the full normalized
dataset stay on the private in-memory side.

**Rejected.** Mapping by common column-name aliases; treating filing as
availability by default; accepting floats and formatting them as decimals;
ordinalizing duplicate source IDs; deriving revision histories from accessions
or business keys; routing customer audits through benchmark cases; or calling a
dry-run profile an audit.

---

## ADR-V2-013 — PyArrow is lazy until v0.2 package metadata is frozen

**Status.** Accepted for the additive pre-release surface.

**Context.** Parquet and Arrow require PyArrow, but `pyproject.toml` and
`uv.lock` are in the immutable v0.1 release checksum and candidate. Editing
them now would falsify the released evidence. The repository environment
already locks and tests PyArrow through the dashboard dependency graph.

**Decision.** Import PyArrow only when a declared Parquet or Arrow input is
used. CSV/Python use needs no PyArrow, and importing the ingestion module does
not load it. A missing dependency returns the fixed machine-readable
`input.pyarrow_unavailable` diagnostic. Production and clean-wheel gates install
the wheel plus the tested locked PyArrow explicitly.

**Consequences.** The v0.1 checksum and package behavior remain unchanged while
the full format path is implemented and verifiable. A future v0.2 release must
declare PyArrow as a dependency or optional extra in its own package metadata;
until then, operators must install it explicitly. This is a packaging
limitation, not a silent fallback to a different Parquet reader.

---

## ADR-V2-014 — Production policies are versioned overlays, not benchmark truth

**Status.** Accepted.

**Context.** Organizations need different production actions, expected
concept/unit pairs, source-supported publication lags, reporting frequency,
and documented dataset exceptions. Putting those choices in detector globals
or benchmark configurations would make customer operations capable of changing
scientific benchmark truth and would leave audit provenance ambiguous.

**Decision.** Add strict `AuditPolicyV1` and `ExternalDatasetAuditReportV2`
contracts in dedicated namespaces. A policy explicitly configures every
detector as enabled or reasoned-disabled and assigns blocking, warning, or
informational action. Unit Drift alone admits an explicit ratio threshold,
because it is the only current detector contract with a configurable threshold;
the other scientific rules reject threshold fields. Concept/unit, publication-
lag, and reporting-frequency expectations are production-only rules evaluated
over the sanitized audit input.

Policy content is canonically normalized, SHA-256 hashed, and assigned a stable
identity. Every current production audit requires the policy as an argument and
records its ID, version, and hash. There is no global or environment fallback.
Benchmark configuration types, execution paths, detector defaults, scores,
manifests, and released v0.1/v0.2 scientific behavior remain unchanged.

Exceptions match exact datasets and enabled rule IDs, require reasons, and are
applied only after valid results exist. More exact scope predicates take
precedence; an equal-specificity tie fails closed. Waivers and action overrides
remain visible in the report. Structural validation and identity failures are
not policy results and cannot be excepted, so malformed input cannot disable a
rule by making it disappear.

**Consequences.** Policy changes create new identities and reports are exactly
attributable. Production action changes can never be described as benchmark
threshold, precision, recall, or scoring changes. The v1 external report type
remains parseable but no current audit entry point emits it; producing policy-
bearing evidence requires an explicit new audit.

**Rejected.** Process-wide mutable configuration; environment-selected
policies; extending `BenchmarkV2Config`; embedding manifests or fault labels;
silently using detector defaults for an enabled configurable threshold;
suppressing excepted findings; choosing the first matching exception; treating
malformed or insufficient input as a disabled rule; and inventing a customer-
specific default policy.

---

## ADR-V2-015 — Scale production audits with content-addressed local entity partitions

**Status.** Accepted.

**Context.** Pre-change profiling at 20,000 deterministic records measured
7.345 seconds for the existing all-detector audit after normalization and
154,250,416 bytes of traced peak Python allocation for the complete raw-row
workflow. Instrumented profiling attributed most cumulative time to canonical
conversion and repeated complete-input identity verification. The frozen
detectors' actual passes were substantially smaller. Weakening the identity
boundary would optimize the wrong contract; holding an arbitrarily large
customer dataset in one immutable tuple would leave memory unbounded.

**Decision.** Keep the frozen audit path and introduce the additive
`quantcheck/external-audit-execution/v1` local runner. It accepts explicit
file-backed partitions whose source contract declares complete, disjoint
entity histories. Partition identity covers source SHA-256/size, mapping,
policy, as-of date, expected count, and semantics. Run identity covers the
sorted partition identities. Neither covers paths, worker count, scheduling,
timestamps, or filesystem order.

Every current detector and policy rule is entity-local: the record rules are
per record, Duplicate and Unit Drift keys include entity, and reporting
frequency groups include entity. The runner validates entity disjointness and
rejects finalization on overlap. Supported worker counts are exactly 1, 2,
and 4 local spawned processes. Each worker holds one partition. Successful
case status and run finalization are written last through the existing atomic
store; immutable evidence is content-addressed; failed cases are retried;
unchanged hashes are verified and reused; changed hashes receive new case
identities; interruption leaves completed cases but no premature finalization.

Persist one full private normalized dataset plus a small private entity summary
per partition. Do not persist redundant full snapshot and audit-input copies.
The public report already records their identities/hashes and the normalized
dataset plus plan reproduces them. Structured operational logs contain fixed
codes and IDs only and are excluded from logical artifact identity.

**Consequences.** The 50,000-record reference run remains bounded by a 5,000-
record partition: 36,325,079 bytes of traced largest-partition allocation. One,
two, and four workers produced the identical logical artifact hash
`42f05328cdcda08e0882415197f8dde62bc71c591412e31e37abb6387c76203e`;
wall time was 17.916, 9.725, and 6.436 seconds. An unchanged rerun took 0.036
seconds; changing one of ten partitions took 1.802 seconds and reused nine.
These are machine-specific operational measurements, not scientific metrics or
portable SLAs.

Partition completeness remains an upstream source attestation; the runner can
prove disjointness but cannot prove that a source omitted nothing. A future
cross-entity rule cannot use this incremental contract without a new explicit
merge boundary. Memory is bounded by partition size, not out-of-core within a
partition. Spawned-worker callers need a normal guarded entry point.

**Rejected.** Caching away frozen identity checks; deriving identity from file
names or enumeration; splitting one entity across partitions; persisting three
full private representations; threads presented as CPU parallelism; unlimited
worker counts; a force-overwrite mode; Kubernetes; task queues; distributed
databases; microservices; and network orchestration.

---

## ADR-V2-016 — Self-hosting is a hardened batch image, not a service

**Status.** Accepted.

**Context.** A security-conscious firm must be able to evaluate QuantCheck on customer research
data without sending that data to external SaaS. The existing production runner is already local,
manifest-free, content-addressed, and data-free in its operational logs. Adding a web service,
identity layer, database, or remote control plane would enlarge the attack surface and exceed the
milestone.

**Decision.** Add a narrow `quantcheck/self-hosted-run/v1` operational config and the module entry
point `python -m quantcheck.external_dataset_self_hosted`. The config embeds the existing logical
plan and binds every partition ID to a confined relative file below one read-only input root. It
fixes telemetry and network requirements to false, rejects unknown/secret fields, accepts only the
existing worker counts, and calls the unchanged bounded audit runner. It emits only canonical,
fixed-code redacted status events. The checksum-frozen six-command root CLI is unchanged.

Distribute that entry point in a digest-pinned, two-stage Python 3.12 image. The runtime is numeric
UID/GID `65532`, exposes no port, declares no volume, and treats `/config`/`/input` as read-only and
`/output`/`/work` as the only writable roots. The supported invocation additionally disables the
network, makes the root filesystem read-only, drops capabilities, prevents privilege escalation,
and applies resource limits. The minimal image supports CSV because immutable v0.1 metadata does
not declare PyArrow; no implicit out-of-band install is hidden in the build.

Build inputs, workflow actions, Buildx, and BuildKit are version/digest pinned. CI scans secrets,
locked dependencies, and the final image; generates SPDX SBOMs; and compares two no-cache OCI
exports. A release workflow publishes packages and GHCR image by digest, attaches SBOM and
provenance attestations, then extracts a synthetic smoke bundle from the pulled image and runs the
normal mounted audit under `--network none`. Registry credentials remain in the CI/container
runtime mechanism and are never application config or build arguments.

**Consequences.** Scientific contracts, detector imports, policies, findings, benchmark truth, and
artifact identities are unchanged. A customer can use one verifiable batch artifact in an isolated
environment and delete its explicit output/work roots afterward. Container/runtime logs,
snapshots, backups, media sanitization, and host compromise remain operator boundaries. Provenance,
SBOMs, and scans are evidence, not a certification or security guarantee. Until the publishing
workflow actually succeeds for a new release, no new image, digest, or attestation is claimed.

**Rejected.** A network listener; authentication, SAML, RBAC, teams, billing, databases,
multi-tenancy, telemetry opt-out instead of telemetry-off, secret values in JSON/YAML config,
mutable base/action tags, root execution, implicit volumes, writable customer input, a hidden
PyArrow download, or claiming a SLSA/compliance level from workflow configuration alone.

---

## ADR-V2-017 — Shadow evaluation separates immutable evidence from supplied human outcomes

**Status.** Accepted.

**Context.** A real design-partner evaluation needs researcher review, dispositions, rerun
comparison, and aggregate pilot reporting. Those are human/product-evaluation concerns, not new
detector truth. Putting reviewer state inside a `Finding`, routing QuantCheck into the production
research path, or filling a report template with expected numbers would destroy the evidence
boundary and manufacture customer claims.

**Decision.** Start shadow packaging only from identity-verified public
`ExternalDatasetAuditReportV2` artifacts produced from a customer-controlled copy/snapshot. Bind
each package to the declared QuantCheck version and code/image revision, exact report hashes,
mapping/policy provenance, as-of context, normalized/snapshot/audit-input hashes, and optional
content-addressed execution finalization. Exclude runtime from the reproducible logical audit ID;
retain supplied measured runtime in the separately hashed finding bundle.

Embed the exact immutable `Finding` objects in a researcher bundle and link every later artifact to
their canonical hashes. Store dispositions in a complete sanitized adjudication export and free-
text notes in a distinct private artifact that pilot reporting never accepts. Dispositions are
`confirmed_issue`, `legitimate_data_condition`, `accepted_exception`,
`duplicate_correlated_signal`, or `unresolved`; investigation status remains independent so an
investigated finding may remain unresolved. Count research-decision impact only when a confirmed
issue is explicitly marked `customer_independently_confirmed`.

Compare versions with an exact evidence key only. Preserve context-match identity and classify
same-key full-hash equality/difference as unchanged/changed; classify unmatched keys as
added/removed. Never infer fuzzy equivalence or rewrite either run. Generate pilot metrics only
from exactly one complete, identity-verified adjudication export per finding bundle. The report is
aggregate-only and omits customer/dataset names, findings/evidence, record IDs, values, and notes.

**Consequences.** QuantCheck can support a factual external pilot while preserving detector and
policy evidence and without entering or blocking production. The package records datasets and
point-in-time records audited, supplied runtime, findings per detector, investigation and
disposition counts, independently customer-confirmed research-decision impacts, and supplied review
seconds. Stable IDs in a sanitized export remain linkable, and small aggregate counts remain
commercially sensitive; customer access/share/retention approval is still required. This repository
contains no pilot inputs or results.

**Rejected.** Editing findings to add reviewer conclusions; using reviewer notes as metric input;
automatic disposition; inferring customer impact; fuzzy rerun matching; silently comparing changed
data/policy/as-of context as a code-only change; source-data writes or remediation; production gate
integration; telemetry/SaaS; and pre-populated or synthetic pilot numbers.

---

## ADR-V2-018 — Missing Observations is the evidence-tie fallback and requires explicit expectations

**Status.** Accepted.

**Context.** Milestone H requires the next fault family to follow demonstrated customer pain and
names Missing Observations and Entity Identity as candidates. The design-partner workflow and
current handoff explicitly record that no real customer audit, adjudication, pilot result, or
discovery ranking exists. Historical documents merely propose both families. The evidence cannot
distinguish them, so the milestone's explicit fallback selects Missing Observations; this is not a
customer-demand claim.

Deleting rows is easy, but proving an absence is erroneous is not. A quarterly gap can be correct
because an issuer does not report that concept, its fiscal cadence differs, the series begins or
ends legitimately, the source lacks coverage, or a customer contract permits the condition.
Inference from adjacency alone would manufacture false certainty and would invite injector truth
across the audit boundary.

**Decision.** Add `quantcheck/missing-observation/v1` outside the frozen v0.1 surface. Require an
identity-bearing public detector configuration containing exact expected cells, `expected_by`
dates, and source/customer-contract evidence references. Expectations distinguish general required
cells, reporting schedules, entity coverage, concept coverage, survivorship cohorts, and source
feed coverage. A missing finding exists only for a due declared cell with zero exact matches; a
future expectation is explicitly not evaluated, and an undeclared gap is ignored.

Implement six private deterministic mechanisms: random cell selection, interior reporting gaps,
entity-group selection, concept-group selection, complete declared survivorship-entity filtering,
and complete declared source/window outages. Public context may correspond to a mechanism because
it is independently declared coverage evidence and is used unchanged on the clean control; seed,
selected cells, deleted rows/values, digest/rank, severity, and fault identity remain private.
Refuse partial survivorship/outage scope when a cap is too small.

Keep the frozen `AuditInputSnapshot` projection unchanged and define additive missingness finding,
report, manifest, score, research, and evaluation envelopes. Exact scoring starts only after audit
finalization, uses one-to-one complete-evidence equality, and gives no recall credit for duplicate
findings. Private replay reinserts exact deleted rows and must restore clean canonical identity.
The controlled research method is one Decimal mean over the declared expected cohort.

Freeze a six-mechanism development/validation/held-out synthetic configuration. A separate
standard-library gate authorizes only the complete held-out case set for the exact freeze identity.
Persist aggregate public evaluation evidence with clean-control, score, research-change, and exact
restoration counts, while excluding deleted-row/private research truth. Mark it synthetic contract
evidence and explicitly not customer evidence.

**Consequences.** QuantCheck can test six materially different missingness patterns without
assuming every absent quarter is wrong or weakening any manifest boundary. Detector performance is
conditional on correct explicit expectations. A bad expectation can still create a bad finding;
source-owner review remains mandatory. The synthetic held-out result cannot be generalized to a
vendor feed or used to retroactively claim customer pain.

**Rejected.** Selecting Entity Identity without distinguishing evidence; claiming the fallback as
customer demand; treating every quarterly gap as an error; inferring fiscal/reporting calendars;
passing deleted records, manifests, seeds, selected entities/concepts, outage windows, or
survivorship labels to the detector; detector-only imputation; partial complete-scope injection;
changing frozen v0.1 findings/scores; or presenting synthetic held-out evidence as a design-partner
pilot.
