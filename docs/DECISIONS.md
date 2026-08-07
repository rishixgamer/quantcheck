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
