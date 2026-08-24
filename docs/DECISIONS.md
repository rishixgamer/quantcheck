# Architecture decisions

## ADR-001 — Reconstructed Look-Ahead details missing from historical evidence

**Status:** accepted for Recovery Phase 3

**Context.** The historical release notes say the lost implementation used a
frozen Look-Ahead contract, period-end substitution, SHA-256 target ranking,
7/14/30-day lag thresholds, exact scoring, a clean point-in-time denominator,
`availability_count_v0_1`, and manifest-assisted replay. The referenced
`docs/faults/` file did not survive. Current higher-authority files require a
complete vertical slice but do not specify the selection ordinal base, cap,
identifier payloads, exact null formulas, or how to guarantee the controlled
research result changes when injection starts from the current Milestone 2
point-in-time `DatasetSnapshot`.

**Decision.** `docs/faults/LOOK_AHEAD.md` freezes the smallest deterministic
completion:

- zero-based target ranks;
- fixed 2%/5%/10% fractions and 7/14/30-day minimum natural filing lags;
- a strict positive `max_targets` with default 100;
- explicit `research_as_of_date` in injection configuration, with eligibility
  requiring `period_end <= research_as_of_date < available_on`;
- `available_on == filed_on` as the supported clean source semantic;
- standard ratio nulls: precision for no findings, recall for no faults, F1
  when either is null, and false-positive rate for a zero denominator;
- one dedicated versioned namespace per new identity and normal `rec_` prefixes
  for both source and modified records, preventing the record ID from acting as
  an injected-row flag;
- immutable audit reports are finalized by construction, so scoring receives
  an existing report and never invokes detection.

**Alternatives rejected.** Binary-float fractions would violate canonical
precision. Position-based selection would violate order independence. A
visible `mod_` prefix would leak injector role. Inferring true availability
for delayed-publication sources would guess unsupported semantics. Comparing
at the snapshot horizon would not guarantee controlled availability-count
damage. Reconstructing a general backtester, generic fault framework, or
historical artifact layouts would expand scope without authority.

**Compatibility.** These rules define rebuilt v1 artifact identities; they do
not reproduce historical IDs or bytes. Changing the ordinal base, cap,
eligibility window, record-prefix decision, identity payloads, or metric nulls
changes logical artifacts and requires a new specification/namespace version.

**Verification.** Focused contract, injection, isolation, exact-scoring,
research/replay, property, subprocess, and complete integration tests freeze
the decision.

## ADR-002 — Narrow SEC client, cache, and source-occurrence rules

**Status:** accepted for Recovery Phase 4

**Context.** Current contracts require HTTPX, exact raw-byte identity,
cache-first/offline replay, day-level SEC availability, and explicit narrow
normalization, but they do not define the accepted-pointer layout, retry
statuses, source-row payload, or numeric JSON parsing. The SEC's current
[Company Facts documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
fixes the ten-digit CIK endpoint, while its
[developer guidance](https://www.sec.gov/about/developer-resources) limits
automated access to 10 requests per second and the Developer FAQ shows a
declared organization/contact user-agent. Historical Milestone 4 output is
evidence only and does not establish current bytes or identities.

**Decision.** The rebuilt adapter freezes these v1 choices:

- HTTPX is the sole added runtime capability (`httpx>=0.28,<1`; the current
  lock resolves 0.28.1). No retry, cache, tabular, or database package is
  added.
- A user-agent must contain an explicit organization/tool identity plus a
  non-placeholder email address or HTTP(S) contact URL. It is never read from
  Git, machine identity, paths, or environment variables.
- Sequential network attempts have a configurable 0.2-second default minimum
  interval. Two retries are the default; only HTTPX transport failures and
  HTTP 429/500/502/503/504 retry. Backoff is deterministic (`0.5 * 2^n`
  seconds by default). `Retry-After` accepts only non-negative integer
  delay-seconds within a configured 30-second default bound. HTTP-date forms
  are ignored in favor of deterministic backoff because interpreting them
  would depend on wall-clock time.
- Cache entries live under `companyfacts/CIK##########/`. Exact response bytes
  are immutable `raw-<sha256>.json` files. Canonical `accepted.json` contains
  only schema version, canonical CIK, canonical endpoint URL, raw filename,
  and raw SHA-256. Raw creation and pointer replacement are same-directory,
  flushed atomic operations; rejected refreshes never replace the accepted
  pointer. No retrieval timestamp or cache path is recorded.
- The supported envelope contains exactly `cik`, `entityName`, and `facts`.
  JSON integers parse as exact integers and JSON fractional/exponent numbers
  parse directly to `Decimal`; `float`, Boolean values, strings, nulls, and
  non-finite constants are never accepted as financial values.
- `sec_source_row_id` uses the dedicated
  `quantcheck/sec-companyfacts-source-row/v1` namespace over canonical CIK,
  taxonomy, concept, unit, the complete parsed source entry, and a positive
  equivalence-class duplicate ordinal. This preserves identical-occurrence
  multiplicity without source-list position. SEC fiscal/frame metadata
  affects the opaque row identity but receives no new canonical schema field.
- No SEC Company Facts field is treated as a source-declared revision marker.
  Every occurrence remains independent, and no `#r<n>` suffix is invented.
- The only supported availability rule is `available_on == filed_on`.
  Retrieval and execution time never affect financial availability.

**Alternatives rejected.** Hashing parsed/reserialized JSON would lose raw
identity. Mutable filename-based caching, automatic expiration, and fallback
network access during offline replay would weaken reproducibility. Source-list
indices would make IDs order-dependent. Treating accession, amendment form,
frame, or matching business keys as revision truth would guess semantics.
Binary-float JSON parsing would corrupt exact financial values. Retrying every
4xx or malformed successful response would hide distinct failure categories.

**Compatibility.** The cache schema and SEC source-row namespace are rebuilt
v1 contracts, not historical recovery. A change to their payloads, retry
classification, numeric parsing, or availability rule requires a new version.
The existing `FinancialFact`, snapshot, audit, and Look-Ahead contracts are
unchanged.

**Verification.** Hermetic HTTPX mock-transport tests, cache fault-injection
tests, reviewed-fixture checks, bounded properties, subprocess hash-seed and
environment comparisons, point-in-time/audit integration, and packaging
inspection freeze these choices.

## ADR-003 — Reconstructed Unit Drift series, evidence, and metric details

**Status:** accepted for Recovery Phase 5

**Context.** Historical evidence fixes the
`unit_drift` / `value_scaled_unit_unchanged` labels, rule
`value.scale_discontinuity`, factor/fraction profiles, three-observation
minimum, immediate nonzero neighbor method, threshold 50, approved factors,
confidence labels, exact matching, aggregate comparison, and manifest-assisted
replay. The original Unit Drift contract and implementation did not survive.
Current schemas also have no historical `source_status` field, and the rebuilt
26-record fixture has only two periods in each exact series rather than the
historically claimed 17 eligible observations. Surviving evidence does not fix
the precise duration-shape key, chronology tie behavior, cap/ordinal,
multi-correction tie-breaker, rebuilt IDs, denominator treatment of selected
targets, or zero-baseline relative-change policy.

**Decision.** `docs/faults/UNIT_DRIFT.md` freezes the smallest deterministic
rebuilt-v1 completion:

- exact series keys contain entity, namespace/concept, unit, dimensions,
  period type, and inclusive duration length;
- duplicate period coordinates exclude the whole ambiguous series, while
  zero observations remain in chronology and neighbor search uses the nearest
  nonzero value on each side;
- the positive cap defaults to 100 and target ranks are zero-based;
- candidate corrections test both multiplication and division, requiring all
  before-ratios to meet the threshold and all after-ratios to fall below it;
  qualifying corrections minimize maximum after-ratio, then ratio sum, factor,
  and operation order;
- factor 100/1,000/1,000,000 maps to low/medium/high finding severity; one
  usable neighbor is `suspicious` and two are `strong`;
- the false-positive denominator is every clean observation meeting the
  comparability prerequisites, including selected targets;
- relative aggregate change is signed change divided by the absolute clean
  aggregate, and is null for a zero clean aggregate;
- fault-specific manifest and identity namespaces are used because the
  existing Look-Ahead manifest/schema versions are not generic; generic
  `Finding`, `AuditReport`, `DetectionMetrics`, `ExactFindingMatch`, and
  `ScoreReport` envelopes are reused without changing existing serialized
  field sets; and
- no `source_status` or other detector-visible exemption is invented. The
  existing reviewed fixture remains a clean control; focused synthetic series
  provide positive/impact evidence without rewriting its historical rebuild
  bytes.

During verification, 50-digit repeating Decimal ratios exposed that
`canonical_decimal_string` used `Decimal.normalize()`, which applies the
ambient 28-digit context and could round a value during serialization. Exact
fixed-point formatting followed by removal of insignificant fractional zeroes
now preserves the complete finite coefficient while keeping numeric rather
than declared-scale identity. Existing golden vectors are unchanged.

**Alternatives rejected.** Entity-wide/global ratios would compare unrelated
facts. Position ordering would be nondeterministic. Guessing between duplicate
period coordinates would hide ambiguity. A `source_status` field would alter
the frozen audit schema solely for an historical exception mechanism. Binary
float/logarithmic scoring would violate financial precision. Rewriting the
reviewed fixture to imitate a historical eligibility count would invalidate a
completed rebuilt artifact without current authority.

**Compatibility.** These are rebuilt v1 identities and behavior, not recovered
historical artifacts. Changing the exact key, chronology exclusion,
eligibility, correction ordering, denominator, or aggregate zero policy
requires a new specification/namespace version. Existing Look-Ahead IDs,
canonical fields, fixture bytes, and golden vectors remain unchanged.

**Verification.** Strict contract, injection, isolation, hard-negative,
matching, replay, aggregate, property, subprocess, full regression, packaging,
and clean-wheel tests freeze the decision.

## ADR-004 — Reconstructed Duplicate Observations fingerprint, severity, and denominator

**Status:** accepted for Recovery Phase 6

**Context.** Historical evidence fixes the `exact_occurrence_copy` subtype,
rule `occurrence.exact_duplicate`, SHA-256 target ranking, one created copy
per fault, and manifest-assisted replay. It also names a fingerprint field
list including "source row," "revision," `record_id`, `form`, and non-semantic
notes, but the original fault document and exact field contract did not
survive. Current `AuditInputRecord` has no `source_row_key` or revision field
at all — Milestone 2 deliberately drops both at the audit boundary — so a
literal reading of "source row"/"revision" as fingerprint fields cannot be
implemented without either breaching the audit boundary or building an
injector-only fingerprint the detector could never reproduce, which would
break the invariant that injection eligibility must match detector
visibility.

**Decision.** `docs/faults/DUPLICATE_OBSERVATIONS.md` freezes the smallest
deterministic completion:

- `DuplicateFingerprint` contains exactly the fields present on both
  `FinancialFact` and `AuditInputRecord` after excluding `record_id` (so a
  generated copy always groups with its source) and `form`/`entity_name`
  (non-semantic/already-boundary-excluded). `source_name`/`source_locator`
  serve as the public "source row" stand-in; no revision/source-row-key
  field is invented, because none exists at the sanitized boundary.
- One consequence, accepted deliberately: the checked-in reviewed fixture's
  Milestone-2 "independent-occurrence pair" (entity 3, Q1 `Assets`) is
  byte-identical in every `AuditInputRecord` field, so the detector
  legitimately proves it as one natural exact group even with zero faults
  injected. Milestone 6's own scope note treats injection eligibility and
  detector visibility as separate concepts, so this is a positive proof of
  correct natural-duplicate detection, not a spurious finding — and
  injection eligibility correctly excludes this pre-existing group as a
  source.
- fixed fractions `0.01`/`0.05`/`0.15` for low/medium/high, with the
  established Decimal-ceiling/minimum-one/cap target-count rule;
- zero-based target ranks and a strict positive `max_targets` defaulting to
  100, identical in shape to Look-Ahead and Unit Drift;
- injection **appends** one created copy per selected source rather than
  replacing a record, because the fault is additive by nature; the created
  record's ID uses a dedicated `quantcheck/duplicate-created-record/v1`
  namespace over `(original_record_id, spec_version, copy_ordinal=1)`, but
  keeps the ordinary `rec_` prefix so it cannot act as an injected-row flag;
- public finding severity is fixed at `medium`, because the specification
  assigns no severity-bearing signal to a duplicate finding comparable to
  Look-Ahead's leaked days or Unit Drift's scale factor;
- the false-positive denominator is `eligible_record_count` — every
  clean singleton-fingerprint record, including selected targets — matching
  Unit Drift's convention rather than Look-Ahead's eligible-minus-target
  convention, per the historical evidence that the denominator equals the
  full eligible/singleton-fingerprint count, not that count minus targets;
- one new controlled research method, `record_count_v0_1` (plus
  `RecordCountResult`/`RecordCountImpact`), reports total occurrence and
  duplicate-group counts across clean/corrupted/repaired snapshots; and
- the existing `aggregate_value_v0_1`/`compare_unit_drift_research` pure
  functions are reused unmodified for the double-counting demonstration
  rather than duplicating that calculation, because an injected copy shares
  its original's `ComparableSeriesKey` and the existing method is already
  fault-family-agnostic.
- `Finding.evidence` gains a `DuplicateEvidence` branch (`record_ids` plural,
  `fingerprint_hash`, `group_size`, plus the shared fingerprint fields) and
  `Finding._check_affected_record` is extended to require
  `affected_record_ids == evidence.record_ids` for that branch, while every
  existing Look-Ahead/Unit Drift finding shape is unchanged.
  `ScoreReport.scoring_spec_version` gains
  `"quantcheck/duplicate-scoring/v1"` alongside the two existing values.

**Alternatives rejected.** Treating `source_row_key` as a fingerprint field
would either leak private lineage across the audit boundary (if read from
`FinancialFact` inside the detector, which is impossible since the detector
only ever sees `AuditInputSnapshot`) or make injector eligibility diverge
from detector-visible grouping (if computed only on the private side).
Replacing the clean fixture's independent-occurrence pair to force zero
findings on an uninjected clean run would invalidate a completed Milestone 2
artifact without current authority, and would remove the one piece of real
data proving the detector's natural-group behavior. A visible `dup_` or
`copy_` record prefix was rejected for the same anti-leakage reason as
Look-Ahead's/Unit Drift's modified-record prefixes. Replacing a record
in-place instead of appending would misrepresent the additive nature of
double-counting and would break the "original occurrence is never altered"
requirement.

**Compatibility.** These are rebuilt v1 identities and behavior, not
recovered historical artifacts. Changing the fingerprint field list, severity
value, denominator, append-vs-replace injection shape, or created-record
namespace requires a new specification/namespace version. Existing Look-Ahead
and Unit Drift contracts, IDs, and fixture bytes are unchanged.

**Verification.** Strict contract, injection, isolation, hard-negative
(including the natural-group positive case and its independent-filing
negative counterpart), matching, replay, record-count/aggregate-reuse,
property, subprocess, full regression, packaging, and clean-wheel tests
freeze the decision.

## ADR-005 — Rebuilt Revision Overwrite provenance and frozen-vintage research

**Status:** accepted for Recovery Phase 7

**Context.** Surviving evidence fixes the narrow `revision_overwrite` /
`later_vintage_in_earlier_state` family, explicit source-supported adjacent
histories, relative revision-size thresholds, SHA-256 selection, strict
matching, exact replay, and a cross-sectional growth-ranking sensitivity
demonstration. It does not define rebuilt v1 history-unit payloads, caps,
public finding severity, public provenance fields, or how a later comparison
period may be used without contaminating an earlier audit snapshot. The
existing audit boundary intentionally removes `source_row_key`, so source
lineage and derived revision IDs cannot truthfully appear in a manifest-blind
detector's evidence.

**Decision.** `docs/faults/REVISION_OVERWRITE.md` freezes the smallest
deterministic rebuilt-v1 completion:

- an eligible unit is the latest explicit historical revision visible at the
  clean cutoff plus its immediate next unavailable sequence; both must have
  `available_on == filed_on`, distinct non-null accessions/source rows/revision
  identities, unchanged controlled context, a changed nonzero historical
  value, and exact relative size meeting low/medium/high
  `0.01`/`0.05`/`0.20` thresholds;
- low/medium/high use target fractions `0.02`/`0.05`/`0.10`, a positive
  default cap of 100, Decimal ceiling/minimum-one target count, and zero-based
  ordering by full SHA-256 selection digest plus history-unit ID;
- injection replaces the historical occurrence with a newly identified record
  carrying the later value, filing/form/accession, and source provenance while
  retaining historical availability. The full later record remains only in the
  supplied source history; normal `rec_` prefixes remain mandatory so the
  audit input does not disclose injected-row role;
- the public detector proves only `available_on <= audit_as_of_date <
  filed_on` with `available_on < filed_on` and non-null accession provenance.
  Its public high severity derives from that direct temporal contradiction,
  not private injection severity. A public provenance hash covers only fields
  at the sanitized boundary. Source-row/revision conflicts are private
  manifest-integrity failures, not fabricated public evidence;
- the Revision Overwrite false-positive denominator is the full eligible
  history-unit count, including selected units. Valid Look-Ahead findings on
  the same corrupted row remain cross-detector signals and unmatched primary
  false positives; and
- the growth demonstration uses a pure frozen-vintage construction: preserve
  each historical clean/corrupted/repaired state, independently select the
  later current period from the full clean source history at an explicit
  research cutoff, add that identical current-period set to every branch, and
  run the same exact Decimal growth ranking. This leaves detector inputs
  unchanged and makes no backtest or trading-performance claim.

**Alternatives rejected.** Treating matching business keys, amended forms, or
accessions as a revision lineage would guess source semantics. Exposing a
source row key/revision ID to allow literal public matching would breach the
audit boundary. Replacing the frozen historical prior value with a later
revision during research would erase the corruption under study. Extending the
historical audit snapshot's as-of date to manufacture Q2 would make the
historical audit claim temporally dishonest. A generic vintage/research
framework is unnecessary for this narrow controlled case.

**Compatibility.** Revision Overwrite history-unit, modified-record, fault,
manifest, finding, report, score, research-result, and impact namespaces are
rebuilt v1 contracts, not historical recovery. Changing eligibility, public
evidence, selection, denominator, or frozen-vintage method requires a new
specification/namespace version. Existing fixture bytes, point-in-time
selection, audit fields, identifiers, and prior fault-family behavior remain
unchanged.

**Verification.** Focused contract, eligibility/injection, clean and hard
negative, audit-isolation, exact scoring/cross-detector, replay/research,
reviewed integration, bounded property, subprocess, full regression,
packaging, and clean-wheel tests freeze the decision.

## ADR-006 — Benchmark identity, artifact tree, resume, and aggregate conventions

**Status:** accepted for Recovery Phase 8

**Context.** Recovery Phase 8 requires deterministic benchmark configuration and
expansion, four-family/all-detector dispatch, public/private atomic artifact
persistence, structured failures, safe resume, and public-only aggregation.
Surviving evidence fixes the seed partitions, the twelve-case offline smoke
shape, and the requirement that a benchmark identity exclude runtime facts. It
does not define the rebuilt v1 benchmark identity payloads, the combined
report's identity, the artifact tree, resume validation, the failure taxonomy,
or the aggregate-level null conventions. Two facts about the *current* rebuilt
implementation also force configuration choices that no historical document
anticipated, and both are recorded here rather than resolved by changing
science.

**Decision.** The smallest deterministic rebuilt-v1 completion:

- **Identity.** `benchmark_id` (`bench_`, namespace
  `quantcheck/benchmark-config/v1`) is the SHA-256 stable ID of the fully
  normalized logical configuration. Expanded cases use `bcase_` with two
  namespaces — `quantcheck/benchmark-fault-case/v1` and
  `quantcheck/benchmark-clean-control-case/v1` — so a control can never collide
  with its fault sibling. The aggregate uses `agg_` /
  `quantcheck/benchmark-aggregate-report/v1`. A case identity covers the
  benchmark, fixture configuration, injector and detector *component* versions,
  detector configuration, severity, seed, seed class, target cap, and research
  configuration. The package version is deliberately **not** in any identity: it
  is an execution fact and lives in `RuntimeMetadata`, consistent with hard
  invariant 3, which already treats code version as separate from configuration.
- **Normalization.** Severities sort by `low < medium < high`, seeds sort
  ascending, profiles sort by fault profile, and duplicates in any dimension are
  rejected. Cases execute in lexicographic `benchmark_case_id` order.
- **Combined report identity.** Every case runs all four detectors on one
  sanitized input and finalizes exactly one `AuditReport` carrying the *primary*
  family's `detector_id`, `detector_version`, and audit-report namespace. This
  is what lets the existing family scorers — three of which assert the report's
  detector identity — accept the combined report with no change to their code.
  Findings from the other three detectors are retained verbatim and are counted
  as false positives under strict primary-class precision.
- **Clean controls carry their sibling's full configuration.** A control is the
  same logical case with injection omitted, so its eligible-clean denominator is
  computed by the *same* frozen eligibility function the injector uses and is
  directly comparable. A control has no manifest, so it has no `ScoreReport`;
  `BenchmarkCaseScore` carries the identical `DetectionMetrics` for both kinds
  and embeds the untouched family `ScoreReport` for fault cases only.
- **Artifact tree.** `public/` holds the configuration, case matrix, runtime
  metadata, aggregate report, public index, and per-case configuration,
  sanitized audit input, audit report, score, sanitized research summary, and
  terminal status. `private/` holds the clean snapshot, corrupted snapshot,
  manifest, repaired snapshot, full research impact, a private index, and
  failure diagnostics. A public artifact reference is a validated relative POSIX
  path whose segment grammar cannot express `..`, a leading `/`, a backslash, or
  `~`, and which rejects `private` as a segment — so a public index is
  structurally incapable of addressing private storage.
- **Persistence.** Writes are canonical, then temp-file/flush/`fsync`/
  `os.replace` in the destination directory. Case artifacts are immutable:
  identical bytes are reused, conflicting bytes raise an integrity error, and no
  force-overwrite option exists. Runtime metadata, the aggregate report, and the
  public index are per-run derived artifacts and are replaced, because they are
  rebuilt from immutable evidence rather than being evidence. The terminal
  status is written last and is never written over a prior *successful* status.
- **Resume.** A prior success is reused only after revalidating the status
  schema, case identity, every referenced path and content hash, the stored case
  configuration's bytes, the audit-input/report/score linkage, the research
  summary, and the private index's artifacts and hashes. A prior failure is
  retried; a case that never reached terminal success is completed; a success
  whose evidence does not support it becomes an integrity failure and its
  conflicting artifacts are left untouched.
- **Failures.** Stages are fixture load, expansion, dispatch, injection, audit
  sanitization, detection, scoring, repair, research, serialization,
  persistence, and aggregation. Categories are configuration, no-eligible-
  targets, integrity, persistence, and internal. Public failures carry a stage,
  a category, a normalized code, and a **fixed constant** message per category,
  so no exception text, value, or path can reach a public artifact through
  formatting. Private diagnostics keep the exception class and a
  whitespace-collapsed message and no stack trace.
- **Aggregate null conventions.** Counts micro-sum; metrics are computed once
  from the summed counts and are never macro-averaged. Precision is
  `TP / findings`; with no findings it is `1` for a successful fault-free group
  and null for a fault-bearing group. Recall is null with no injected faults.
  F1 is null whenever precision or recall is null. False-positive rate is null
  with no eligible-clean denominator. Failed and incomplete cases stay in the
  status totals and are excluded from pooled detection metrics.
- **Sanitized public research summary.** Only the research method, whether the
  controlled output changed, and whether exact replay restored it. Controlled
  counts and deltas stay private, because a Look-Ahead availability delta or a
  Duplicate record-count delta *is* the injected target count.
- **A second benchmark fixture exists, and Revision Overwrite runs at `low`.**
  Unit Drift eligibility requires a comparable series of at least three
  observations; the reviewed fixture has two periods per series and is a
  documented insufficient-history control with no eligible Unit Drift target at
  any severity or horizon. The benchmark therefore adds one deterministic
  offline five-observation series fixture
  (`quantcheck/benchmark-unit-drift-series/v1`) and refuses any other
  profile/fixture pairing. Separately, the reviewed fixture's only
  source-supported adjacent history has a 2% relative revision, which clears
  `low` (1%) but not `medium` (5%), so the smoke's Revision Overwrite profile
  runs at `low` while the other three run at `medium`.

**Rejected alternatives.** Relaxing the Unit Drift three-observation
comparability rule, or the Revision Overwrite relative-size thresholds, to make
one fixture and one severity cover everything would retune completed science to
suit orchestration. Suppressing cross-detector findings would inflate precision
by hiding real detector behavior. Publishing controlled research counts would
disclose target counts. Minting the combined report in a new benchmark namespace
would force edits to three completed scorers. Reusing `CaseConfig` for expanded
benchmark cases would have required adding fields to a Milestone 1 schema frozen
by golden vectors. Treating file existence as proof of success, or overwriting a
conflicting prior success, would destroy evidence. A generic plugin registry was
rejected in favor of an explicit closed four-family dispatcher.

**Compatibility.** Benchmark configuration, case, and aggregate namespaces are
rebuilt v1 contracts, not historical recovery. Changing identity payloads,
normalization, the artifact layout, resume validation, the failure taxonomy, or
the null conventions requires a new specification version. No injector,
detector, matcher, scorer, replay rule, research calculation, existing schema
field, identifier, reviewed fixture byte, or golden vector changed; the
Milestone 8 diff to pre-existing source files is purely additive.

**Verification.** Configuration/expansion, seed-class, dispatch/all-detector,
cross-detector, artifact/privacy, failure/resume, aggregation, offline smoke,
property, and subprocess hash-seed tests freeze the decision.

## ADR-007 — CLI command surface, saved-stage workflow, JSON envelope, and exit codes

**Status:** accepted for Recovery Phase 9

**Context.** The project scope fixes Phase 9's scope in one sentence —
"Add the contracted command surface and saved-stage workflow with canonical
JSON output, stable exit codes, and privacy-safe rendering" — and names no
concrete command, flag, or exit code. No current `docs/CLI_CONTRACT.md`
exists, and none of `PROJECT_SCOPE.md`, `MVP_ACCEPTANCE_CRITERIA.md`, or the
prior ADRs fixes CLI syntax. Archived historical evidence describes
a lost six-command Typer CLI (`ingest`, `inject`, `audit`, `evaluate`,
`benchmark`, `explain`) with exit codes `0/2/3/4/5/10`, but per the repo's
authority order this is evidence of scale and intent only, not a byte- or
syntax-identity target. This ADR freezes the rebuilt v1 CLI contract,
recorded in full in `docs/CLI_CONTRACT.md`.

**Decision.** The smallest deliberate completion of the one-sentence contract:

- **Command surface.** Six root commands: `ingest sec`, `inject`, `audit`,
  `evaluate`, `benchmark run`, `benchmark smoke`, plus `explain`. No other
  root command, no `--version` flag, and no separate `python -m quantcheck`
  behavior — v0.1 does not need them and the historical release's inclusion of
  a `--version` flag is not itself authority to add one now. The installed
  console script keeps pointing at `quantcheck.cli:main`, a plain function
  (unchanged from the Milestone 0 placeholder's entry point), which now wraps
  a Typer `app` object rather than `argparse`.
- **Saved-stage workflow.** `inject`/`audit`/`evaluate` operate over the
  existing `BenchmarkCaseConfig` — the same fully expanded case type
  `expand_benchmark_cases` already produces — rather than a second,
  CLI-specific case-definition schema. `quantcheck.saved_case_workflow` is new
  glue, not new science: it calls the exact functions
  `dispatch_benchmark_case` calls (`clean_snapshot_for_case`,
  `inject_for_case`, `sanitize_for_audit`, `run_all_detectors`,
  `combined_audit_report`, `score_for_case`, `replay_for_case`,
  `research_for_case`, `fault_score`, `research_summary_for_case`) in the same
  order over the same persisted evidence, so a staged
  `inject -> audit -> evaluate` run and one `dispatch_benchmark_case` call
  produce byte-identical public and private artifacts for all four fault
  families (verified directly by test). `benchmark_dispatch`'s five
  single-case helper functions (`_clean_snapshot`, `_inject`, `_score`,
  `_replay`, `_research`, plus `_eligible_clean_denominator`,
  `_control_score`, `_fault_score`, `_research_summary`,
  `_lookahead_research_date`) were renamed to their public forms (dropping the
  leading underscore, no behavior change) and `run_all_detectors` now takes
  `detector_configs` directly instead of a full case, specifically so this
  reuse would not require a second implementation or reaching into another
  module's private names. `audit` additionally accepts a standalone
  `--case`/`--snapshot`/`--output` form for auditing an arbitrary canonical
  `DatasetSnapshot` (for example one built by `ingest sec`) that was never
  produced by `inject`. A clean control has no manifest and therefore no
  `evaluate` stage: its `audit` stage is terminal, matching
  `dispatch_benchmark_case`'s own clean-control branch, which never touches a
  manifest either.
- **Artifact layout.** Saved-stage output reuses the exact
  `public/`/`private/` `AtomicArtifactStore` split and the
  `cases/<benchmark_case_id>/<artifact>.json` relative path convention the
  benchmark runner already uses, so a saved-stage tree and a benchmark-run
  tree are laid out identically and existing artifact-name constants
  (`PUBLIC_CASE_ARTIFACT_NAMES`, `PRIVATE_CASE_ARTIFACT_NAMES`,
  `public_case_directory`) are reused rather than duplicated.
- **SEC ingestion.** `ingest sec` wraps `SecCompanyFactsAdapter` exactly:
  `fetch`/`replay`/`normalize`/`build_snapshot`, unchanged. `SecNormalizationConfig`
  is a plain dataclass, not a Pydantic schema, so its CLI-input JSON shape is
  validated by an explicit exact-field-set check before construction — this
  is the one place the CLI enforces strictness itself rather than delegating
  to a schema, and it widens nothing the adapter did not already accept.
  `--replay-only` is a thin, explicit wrapper over the adapter's own
  `.replay()`, added so a test (or an operator) can assert zero network
  access at the CLI boundary without relying on cache-hit behavior alone.
- **Machine output.** Exactly one `canonical_json_bytes(payload)` call per
  command, where `payload` is a plain `dict[str, object]` of primitives, IDs,
  and (for `audit`) public `Finding` models — reusing the single canonical
  serializer rather than `json.dumps`. Every payload is an explicit finite
  allowlist of fields (verified by test for `inject` and `evaluate`); nothing
  a command did not explicitly choose to include can appear.
- **Exit codes.** `0` success; `2` user/configuration input (bad path, bad
  JSON, schema/enum/seed rejection, broken artifact identity); `3`
  saved-artifact/integrity/persistence problems
  (`SavedStageError`/`ArtifactIntegrityError`/`ArtifactPersistenceError`); `4`
  SEC source/cache/normalization (`SecAdapterError` and its subclasses); `5`
  a structured failed-or-incomplete benchmark outcome (`benchmark run`/
  `benchmark smoke` only, decided from the returned aggregate's counts, never
  from a raised exception); `10` an unexpected internal error, reported with
  the fixed generic sentence "an unexpected internal error occurred" and never
  the exception's own message. This mirrors the shape of the historical
  evidence's `0/2/3/4/5/10` mapping because it is a reasonable, complete
  partition of the failure categories Recovery Phase 9 itself lists, not
  because the historical numbers are binding.
- **No-argument and help behavior.** `--help` exits `0`. Invoking any command
  group with no subcommand (including bare `quantcheck`) shows the same help
  text but exits `2` — this is Click/Typer's own `no_args_is_help` semantics,
  a missing-command usage error, not a bespoke choice, and is recorded here so
  it is not mistaken for an inconsistency.
- **Privacy.** `audit` (both the `--dir` and `--snapshot` forms) calls only
  `sanitize_for_audit` plus the four manifest-blind `detect_*` functions and
  never imports or constructs a manifest type; `evaluate` is the first CLI
  stage that reads a manifest, and only after a finalized public
  `AuditReport` already exists on disk. `explain` reads only `public/`,
  never `private/`, and never reruns a detector.

**Rejected alternatives.** A second, CLI-only case-configuration format was
rejected because `BenchmarkCaseConfig` already is a fully expanded, strictly
validated, identity-checked case — inventing another one would duplicate
Milestone 8's schema for no gain. Reaching into `benchmark_dispatch`'s
underscore-prefixed helpers from `saved_case_workflow` (instead of renaming
them to public names) was rejected as an avoidable code smell once the same
functions were going to be called from two modules. A generic `--config`
positional-JSON-blob CLI parser (accepting arbitrary loosely-typed dictionaries)
was rejected in favor of handing parsed JSON straight to the existing strict
Pydantic models, per the hard invariant that CLI parsing must not weaken
schema validation. `--held-out`, `--release`, `--force`, and any other
seed-authorization or overwrite bypass flag were rejected outright: Milestone
8 deliberately has no override path for final seeds or for `write_immutable`,
and the CLI must not become the place one is quietly added.

**Compatibility.** This is a rebuilt v1 CLI contract, not a recovery of the
lost historical one: command names happen to match historical evidence where
that evidence was a reasonable design, but no flag syntax, exit-code
assignment, or JSON field name is claimed to be byte- or behavior-identical to
the lost release. Changing the command surface, the JSON envelope shape, or
the exit-code mapping requires a new specification version recorded here. No
injector, detector, matcher, scorer, replay rule, research calculation,
existing schema field, identifier, benchmark runner/aggregator/store behavior,
or SEC adapter behavior changed; the `benchmark_dispatch` diff is a
behavior-preserving rename plus one signature widening
(`run_all_detectors(audit_input, detector_configs)` instead of
`run_all_detectors(audit_input, case)`), and every other Milestone 0–8 file is
either unchanged or additive.

**Verification.** Saved-stage equivalence (all four fault families, byte-for-
byte against `dispatch_benchmark_case`), strict config loading (malformed
JSON, invalid UTF-8, wrong suffix, unknown fields, invalid enums, broken
identity, every reserved final seed 1000–1009), exit-code taxonomy (every
class, human and `--json`), benchmark run/smoke (including resume and a
tampered-prior-success exit-5 case), hermetic offline SEC ingestion, `explain`
public-only boundary, adversarial privacy scans (manifest field names,
manifest IDs, pre-injection record identity, local paths), subprocess
execution (console script and `python -m`), and `PYTHONHASHSEED`
determinism across the full saved-stage workflow all freeze the decision.

## ADR-008 — Public-only presentation: reader boundary, shared model, HTML determinism, and the Streamlit dependency

**Status:** accepted for Recovery Phase 10

**Context.** The project scope fixes Phase 10's scope in one sentence —
"Add a strict public reader, shared immutable presentation model, read-only
Streamlit app, and deterministic self-contained HTML" — and names no artifact
format, path rule, null policy, or launch command. `PROJECT_SCOPE.md` lists
the dashboard and HTML summary as v0.1 surfaces, and
`MVP_ACCEPTANCE_CRITERIA.md` item 10 requires that both "read public artifacts
only and do not execute scientific logic". Historical evidence under
Archived historical notes describe a lost `public_artifact_reader.py` /
`presentation.py` / `html_summary.py` / `dashboard/app.py` set keyed on a
`public/artifact_index.json` entry point and a `streamlit>=1.60,<2` runtime
range. Per the repository's authority order that is evidence of shape and
intent only: the rebuilt public tree's actual index is `public/index.json`
(`benchmark_runner.BENCHMARK_INDEX_PATH`), and no historical byte, hash,
metric, or dependency version is claimed. This ADR freezes the rebuilt v1
presentation contract, recorded in full in `docs/DASHBOARD_AND_HTML.md`.

**Decision.**

- **One reader, reusing the existing artifact contract.** `public_artifact_reader`
  reads the public tree the benchmark already writes, through the existing
  `AtomicArtifactStore`, the existing canonical parser, the existing Pydantic
  schemas, and the existing SHA-256 identity. It defines no second artifact
  format and no loose-dictionary path. Root artifact filenames moved into
  `benchmark_contract.PUBLIC_ROOT_ARTIFACT_NAMES` so the runner and the reader
  share one mapping; `benchmark_runner`'s five `BENCHMARK_*_PATH` constants now
  reference it, a behaviour-preserving change.
- **Role allowlist.** Exactly the keys of `PUBLIC_ROOT_ARTIFACT_NAMES` and
  `PUBLIC_CASE_ARTIFACT_NAMES` are readable. An unknown role is rejected, never
  skipped or guessed, so a future private artifact kind cannot become readable
  merely by being named in an index.
- **Path security is layered, and never repairs.** The existing
  `PUBLIC_RELATIVE_PATH_PATTERN` supplies the grammar, which makes `..`, a
  leading `/`, a backslash, a drive letter, and `~` *unrepresentable*; a
  `private` segment is refused separately; and the resolved location must stay
  under the resolved root, which is what catches symlink escapes and symlinks
  into the private tree. An unsafe path is rejected, never normalized into a
  safe-looking one.
- **Tree-level integrity is strict; case-level outcome mirrors aggregation.**
  A missing/malformed root artifact, a bad index hash, a missing indexed
  artifact, an unknown role, a cross-case reference, an unsafe path, a
  benchmark-identity disagreement, or a status naming a different case raises
  `PublicArtifactError`. A case whose *success claim* is unsubstantiated
  becomes `incomplete`, which is exactly what `benchmark_aggregate` already
  does independently — so the reader can never contradict the saved aggregate
  about a case's outcome. A case is never dropped and never inferred
  successful.
- **The saved aggregate must describe the saved statuses.** The reader refuses
  a tree whose `aggregate_report.json` status counts disagree with its case
  statuses, because a rendered page built from a stale aggregate would be
  quietly self-contradictory.
- **The reader result carries no filesystem path.** A path that is never
  carried cannot later be rendered.
- **One shared immutable model.** `presentation.BenchmarkPresentation` is the
  single interpretation both surfaces render. Overall and grouped metrics are
  the saved aggregate's own numbers copied across, never recomputed. Case
  order follows the saved matrix. Finding evidence is flattened through the
  existing `to_canonical_json`, so exposing it introduces no new judgment about
  what is publishable — the evidence models are already public artifacts.
- **Decimal and null semantics are exact.** Metrics stay `Decimal | None` end
  to end and never pass through binary `float`. An undefined metric stays
  `None` in the model; only rendered text says `n/a`. It is never turned into
  `0`, `NaN`, or an empty string inside the model.
- **Deterministic HTML.** UTF-8, embedded CSS only, no JavaScript, no remote
  resource, no render timestamp, no random identifier, no environment path;
  every artifact-derived string escaped. Identical logical artifacts render
  byte-identical output regardless of destination, process, or
  `PYTHONHASHSEED`. Output reuses the existing persistence conventions:
  atomic write, identical existing bytes reused untouched, conflicting bytes
  rejected as `ArtifactIntegrityError`. There is no force-overwrite option,
  matching the rest of the repository.
- **The dashboard is standalone and read-only.** It lives in `dashboard/`,
  outside the package, so ordinary `import quantcheck` can never import
  Streamlit. It requires an explicit `--artifacts` root, uses Streamlit-native
  components only, adds no CLI command, and every case filter defaults to
  showing everything — a default that hid failures, incomplete cases, clean
  controls, or weak results would make a broken benchmark look healthy.
- **Streamlit is a `dashboard` dependency group, not a runtime dependency.**
  Range `streamlit>=1.40,<2`; the lock selects `1.61.1` plus its transitive
  packages, and no previously locked package was upgraded or removed. The
  dashboard is a repository-local surface: `dashboard/` is excluded from the
  wheel and sdist under the same rule already documented for `scripts/`, so
  declaring Streamlit as a runtime dependency would burden every consumer of
  the distribution with ~35 packages (including pandas, NumPy, and PyArrow) for
  code the distribution does not ship. This deliberately diverges from the
  historical release's direct runtime range; the divergence is recorded rather
  than hidden. A clean wheel install therefore has no Streamlit at all and the
  reader, model, and HTML renderer still work.

**Consequences.** Presentation cannot become a second access path into private
truth: its transitive `quantcheck` import closure is exactly
`benchmark_contract`, `benchmark_store`, `hashing`, `json_types`, `schemas`,
`serialization`, and `unit_drift_math` — no manifest, injector, detector,
scorer, replay, or research module — and that closure is pinned by test. No
fault family, detector, threshold, matching rule, denominator, severity,
research calculation, replay rule, benchmark identity, expansion, aggregation
semantic, or CLI root command changed. The six-command CLI surface is
unchanged and reserved final seeds `1000–1009` remain prohibited.

**Verification.** Strict-reader positive/negative/adversarial cases (unsafe
paths of every documented shape, symlink escapes into and out of the tree, bad
hashes, malformed and schema-invalid JSON, wrong benchmark and case identity,
unknown and mispathed roles, cross-case references, missing indexed artifacts,
unindexed extras, hostile working directory); exact-aggregate,
Decimal-precision, null-preservation, group-preservation, and ordering checks
on the model; HTML determinism across two destinations, three
`PYTHONHASHSEED` values, a fresh subprocess, and a separate output root;
escaping of `<`, `>`, `&`, `"`, and `'`; no-JavaScript, no-remote-resource,
no-timestamp, no-local-path, and no-answer-key scans; output reuse,
conflict rejection, invalid destinations, and no-partial-file-on-failure;
official Streamlit `AppTest` startup, overview, counts, metrics, filtering,
findings, failed/incomplete/null rendering, sanitized errors, and read-only
verification; and end-to-end runs of reader, model, HTML, and dashboard
against a copied public tree with the entire private tree absent.

## ADR-009 — Release matrix, clean-control policy, and the freeze record

**Status.** Accepted (Recovery Phase 11).

**Context.** Milestone 11 must execute a held-out benchmark over reserved final
seeds `1000–1009` and freeze what produced it. Three details were genuinely
unspecified by current contracts: how many clean controls the release runs, what
a freeze record contains, and where release evidence lives. The historical
0.1.0 documentation implies twelve controls for 132 total cases, but historical
material cannot override the rebuilt repository's own schemas.

**Decision.**

*Clean-control policy: one control per fault profile — four controls, 124 total
cases.* This is derived, not chosen. `schemas.BenchmarkProfile.clean_control` is
a single optional `BenchmarkCleanControl` carrying one severity and one seed, so
the completed Milestone 8 contract can express at most one control per profile.
Reaching twelve would require widening a completed schema for presentation
reasons, which this milestone must not do. The divergence from the historical
target is recorded rather than hidden. Controls are pinned to the lowest
reserved seed, because a control injects nothing and so selects no target.

*Release matrix: the reviewed smoke configuration, expanded in exactly two
dimensions.* Per-profile fixtures, point-in-time horizons, research contexts,
and detector configuration are reused verbatim from the already-reviewed smoke
benchmark; only severity (all three) and seed (the ten reserved) change.
Searching over horizons or research cutoffs for a release matrix with better
numbers is exactly what a held-out benchmark exists to prevent. A consequence is
that three profile/severity cells have no eligible target on the reviewed
fixture and fail every seed with `no_eligible_targets`; those failures are kept
visible rather than configured away.

*Freeze record.* A canonical JSON `ReleaseFreezeRecord` (`release_freeze.json`,
identity prefix `relc_`, namespace `quantcheck/release-candidate/v1`) pinning the
package version, Python requirement, benchmark spec version, release matrix,
four fault specifications, twelve severity definitions, detector
versions/configuration/threshold, matching rules, false-positive denominator
rules, replay method, both reviewed fixture hashes, the normalized release
configuration and its canonical hash, the expanded matrix hash, and the SHA-256
of an explicit list of 67 frozen repository files. Verification is byte-level
and refuses to repair. The record is publishable: it carries no secret, path,
manifest, fault target, or answer-key relationship. Severity fields are prefixed
`frozen_` so that public constants never collide with private manifest key names
in the context-free privacy scan — a scan with exemptions is a scan that
eventually misses something.

*`CHECKSUMS.md`.* No historical format survived and no current contract defined
one, so the smallest deterministic format is used: a Markdown document whose
body is a fenced block of `<sha256>  <path>` lines, sorted by path, over the
committed release surface. Generated benchmark artifacts are deliberately
excluded; they are reproduced, not committed.

*Evidence location.* Release output lives under the gitignored
`release_evidence/`. Only the freeze record, the checksums, and the documented
metrics are committed, so no generated artifact tree or private manifest enters
version control.

**Consequences.** The release reports 124 cases rather than the historical 132,
and 30 of its 120 fault cases fail for a documented structural reason. Both are
stated prominently rather than smoothed over.

## ADR-010 — Final-seed authorization gates execution, not representation

**Status.** Accepted (Recovery Phase 11). Supersedes the initial Milestone 11
draft, which gated representation.

**Context.** Reserved final seeds must be unusable through every ordinary
interface. The first implementation enforced this in `schemas.py`, refusing to
*construct or deserialize* any model carrying a reserved seed without an active
authorization.

That was over-broad, and the release itself proved it. After the first candidate
(`relc_a573d64b0345a5b5`) produced a complete 124-case held-out run, the strict
public reader could not load the released `public/benchmark_config.json`: the
schema refused to deserialize it. The public evidence package — the thing the
whole public/private boundary exists to make shareable — was unreadable by the
reader, the aggregator, the presentation model, the HTML renderer, and the
dashboard.

**Decision.** The security property is that a reserved seed must never be
**executed** without authorization. It is not that a reserved seed must never
**exist**. Authorization is therefore decided in exactly one place,
`benchmark_contract.require_seed_execution_authorized`, called by benchmark
configuration building, expansion (via `classify_benchmark_seed`), the case
dispatcher, and all three saved-stage workflow functions. `schemas.py` keeps
only the coherence rules: a seed must fall in a known partition, a case's
declared `seed_class` must match its seed, and a profile may not mix final seeds
with ordinary ones.

Reading a saved held-out artifact is permitted. Reading is not running, and the
presentation layer executes nothing.

**Consequences.** Candidate `relc_a573d64b0345a5b5` was invalidated — by a
release-plumbing defect, not by its detector performance — and is preserved
under `release_evidence/candidate_1_relc_a573d64b0345a5b5/` with its own freeze
record. Candidate `relc_2c6e945a71b85b39` was frozen after the fix and re-ran
the matrix. Of 594 indexed artifacts, 593 are byte-identical between the two
runs; only `runtime_metadata.json` (runtime-specific by schema design) and
`index.json` (which embeds its hash) differ, so the correction provably changed
no science.

**Verification.** Every reserved seed refused at every execution entry point and
through every CLI command; near-miss seeds refused with *and* without an
authorization; mixed partitions refused; static AST checks that only
`release_gate` and `release_run` open an authorization and that `cli.py` never
references the gate; a fresh-subprocess check that the gate starts closed; and
`test_a_released_case_config_stays_readable_with_the_gate_closed` plus
`test_the_released_public_evidence_loads_with_the_gate_closed`, the regression
tests for the defect above.
