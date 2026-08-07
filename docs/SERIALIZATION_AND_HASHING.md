# Canonical serialization, hashing, and identifiers

This is the **current** contract for QuantCheck's deterministic layer. It is
authoritative for the rebuilt repository.

## Provenance of this document

`reference/AGENTS_ORIGINAL.md` invariant 8 points at a file of this name in
the lost repository. That file did **not** survive; no copy exists under
`reference/`. The surviving historical documents state only that Decimal is
serialized as a JSON string and that hashes are SHA-256. Everything more
specific below — trailing-zero handling, exponent form, negative zero, key
ordering, identifier prefixes, and digest truncation — is **defined here for
the rebuild**, not recovered. No historical hash or identifier can therefore
be reproduced, and none is treated as a compatibility target.

## Value domain

Canonicalization accepts exactly:

| Input | Canonical JSON form |
| --- | --- |
| `None` | `null` |
| `bool` | `true` / `false` |
| `int` | JSON integer (arbitrary precision) |
| `str` | JSON string |
| `Decimal` | JSON string, see below |
| `date` | JSON string, `YYYY-MM-DD` |
| `datetime` (aware) | JSON string, `YYYY-MM-DDTHH:MM:SS.ffffffZ` |
| `CanonicalModel` | JSON object over its declared fields |
| `Mapping[str, ...]` | JSON object |
| non-string `Sequence` | JSON array, order preserved |

Everything else is rejected with `CanonicalizationError`. In particular
`float`, `bytes`, `set`, `complex`, non-string mapping keys, naive
`datetime`, and arbitrary objects are rejected. There is no `str(value)`
fallback, so no object address, repr, or local path can ever reach an
artifact.

`bool` is checked before `int` and `datetime` before `date`, because each is a
subclass of the other in Python. A `datetime` is never accepted where a
day-level financial `date` is required.

Nesting deeper than 64 levels is rejected.

## Decimal encoding

* Plain fixed-point notation only. Exponent notation never appears in output.
* The exponent is normalized away, so the encoding depends only on the
  **numeric value**: `Decimal("1.50")`, `Decimal("1.5")`, and
  `Decimal("150E-2")` all encode as `"1.5"`. Declared scale is deliberately
  *not* part of identity.

  This is a correctness requirement, not a convenience. Python's `Decimal`
  equality is numeric, so `Decimal("1.50") == Decimal("1.5")`. If the encoding
  kept scale, two models that compare equal would hash differently — and the
  same economic fact reported as `1234567` in one filing and `1234567.00` in
  the next would look like two distinct facts to duplicate-observation and
  revision analysis. Values that compare equal always produce equal bytes.
  Encoding uses exact fixed-point formatting and removes insignificant
  fractional zeroes textually; it never performs a Decimal arithmetic
  operation that could round through the ambient context. Coefficients longer
  than the default 28-digit context therefore round-trip exactly, including
  Unit Drift ratio evidence computed at 50-digit working precision.
* Zero is written without a sign: `Decimal("-0.00")` encodes as `"0"`.
  A negative zero carries no financial meaning, and preserving it would give
  two logically equal values two different hashes.

Callers that need to retain a source's declared precision must carry it as
separate explicit metadata; it must not ride along inside the value.
* `NaN`, `sNaN`, `Infinity`, and `-Infinity` are rejected.

On input, a Decimal field accepts a `Decimal`, an `int`, or a string matching
`^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$`. Leading `+`, leading zeros, a bare
trailing `.`, exponent notation, whitespace, underscores, `NaN`, and
`Infinity` are rejected rather than guessed at. `float` and `bool` are
rejected outright: a `float` cannot represent a decimal financial value
exactly, and a `bool` is not a quantity.

Because every emitted string matches the accepted input pattern, the round
trip is closed.

## JSON text and bytes

* Object keys are sorted by Unicode code point.
* Sequence order is preserved; sequence order is meaningful.
* Separators are `,` and `:` with no whitespace.
* `ensure_ascii=False`: non-ASCII characters are written as themselves and
  the result is encoded UTF-8.
* No trailing newline.
* Strings are preserved code point for code point. No Unicode normalization
  is applied, so NFC and NFD spellings of the same grapheme are distinct
  logical values. Producers must normalize upstream if they need them equal.

Pydantic's own `model_dump_json` is never used. Models are converted field by
field from `model_fields`, then key-sorted, so the output depends on the
declared contract rather than on Pydantic's serializer defaults.

## Hashing

`canonical_sha256(value)` is `sha256(canonical_json_bytes(value)).hexdigest()`
— 64 lowercase hex characters. A *content hash* is always the digest of the
complete canonical form of the artifact.

SEC Company Facts raw-content identity is deliberately different:
`sha256_hex_of_bytes(response.content)` hashes the exact bytes supplied by the
HTTPX response layer, before JSON parsing or normalization. Whitespace, key
order, and numeric lexical changes therefore change the raw digest even when
they normalize to the same canonical financial records. Cache location,
retrieval time, runtime user, hostname, and working directory do not
participate. The cache filename is `raw-<64-lowercase-hex>.json`.

## Stable identifiers

```text
stable_id = "<prefix>_" + sha256(canonical_bytes(envelope))[:16]

envelope = {
  "id_scheme": "quantcheck/stable-id/v1",
  "namespace": "<versioned namespace>",
  "payload":   <canonical form of the logical identity>
}
```

* Prefixes match `^[a-z][a-z0-9]{0,15}$`.
* The default truncation is 16 hex characters (64 bits).
* The namespace is inside the hashed envelope, so two kinds of artifact can
  never collide by sharing a payload shape.
* No identifier uses `uuid4`, `id()`, or Python's built-in `hash()`.
* No identifier payload contains a runtime timestamp, an output directory, a
  temporary directory, a working directory, an absolute path, a username, or
  a DataFrame row position.

### Assigned namespaces and prefixes

| Helper | Prefix | Namespace | Payload |
| --- | --- | --- | --- |
| `source_record_id` | `rec` | `quantcheck/source-record/v1` | source name, locator, and the source's own row key |
| `dataset_snapshot_id` | `snap` | `quantcheck/dataset-snapshot/v1` | dataset name, as-of date, records sorted by `record_id` |
| `audit_input_snapshot_id` | `audit` | `quantcheck/audit-input-snapshot/v1` | dataset name, as-of date, records sorted by `record_id` |
| `case_config_id` | `case` | `quantcheck/case-config/v1` | case name, dataset name, as-of date, seed, spec version |
| `revision_id` | `rev` | `quantcheck/revision/v1` | a declared revision lineage's id and its sequence number |
| `sec_source_row_id` | `srow` | `quantcheck/sec-companyfacts-source-row/v1` | canonical CIK, taxonomy, concept, unit, complete parsed SEC entry, and deterministic duplicate ordinal |
| `lookahead_modified_record_id` | `rec` | `quantcheck/lookahead-modified-record/v1` | original record id, Look-Ahead spec, and exact original/corrupted availability mutation |
| `lookahead_fault_id` | `fault` | `quantcheck/lookahead-fault/v1` | clean snapshot id, original/corrupted record ids, seed, and spec version |
| `fault_manifest_id` | `man` | `quantcheck/lookahead-manifest/v1` | complete manifest body excluding `manifest_id` |
| `lookahead_finding_id` | `find` | `quantcheck/lookahead-finding/v1` | complete finding body excluding `finding_id` |
| `lookahead_audit_report_id` | `arep` | `quantcheck/lookahead-audit-report/v1` | complete audit-report body excluding `audit_report_id` |
| `lookahead_score_report_id` | `score` | `quantcheck/lookahead-score-report/v1` | complete score-report body excluding `score_report_id` |
| `lookahead_research_result_id` | `rsch` | `quantcheck/lookahead-research-result/v1` | complete availability-count result body excluding `research_result_id` |
| `lookahead_impact_id` | `impact` | `quantcheck/lookahead-impact/v1` | complete research-impact body excluding `impact_id` |
| `unit_drift_modified_record_id` | `rec` | `quantcheck/unit-drift-modified-record/v1` | original record id, Unit Drift spec, and exact original/corrupted value mutation plus factor |
| `unit_drift_fault_id` | `fault` | `quantcheck/unit-drift-fault/v1` | clean snapshot id, original/corrupted record ids, seed, and spec version |
| `unit_drift_manifest_id` | `man` | `quantcheck/unit-drift-manifest/v1` | complete Unit Drift manifest body excluding `manifest_id` |
| `unit_drift_finding_id` | `find` | `quantcheck/unit-drift-finding/v1` | complete Unit Drift finding body excluding `finding_id` |
| `unit_drift_audit_report_id` | `arep` | `quantcheck/unit-drift-audit-report/v1` | complete Unit Drift audit-report body excluding `audit_report_id` |
| `unit_drift_score_report_id` | `score` | `quantcheck/unit-drift-score-report/v1` | complete Unit Drift score-report body excluding `score_report_id` |
| `unit_drift_research_result_id` | `rsch` | `quantcheck/unit-drift-research-result/v1` | complete aggregate-value result body excluding `research_result_id` |
| `unit_drift_impact_id` | `impact` | `quantcheck/unit-drift-impact/v1` | complete aggregate-value impact body excluding `impact_id` |

`revision_id` (Milestone 2) is not stored on any schema field: `FinancialFact`
is frozen by the Milestone 1 golden vectors below, so adding a field to it
would change every fact's canonical bytes. A record's membership in a
revision lineage is instead declared directly inside its own
`SourceReference.source_row_key`, using the `"<lineage_id>#r<sequence>"`
marker documented in `quantcheck.point_in_time`. `revision_id` gives that
declared `(lineage_id, sequence)` pair its own stable, testable identity —
it is used for identifier-stability tests, not persisted in any artifact.
Because `AuditInputRecord` never carries `source_row_key`, this marker (and
therefore the revision lineage and sequence) never crosses the
`sanitize_for_audit` boundary.

`sec_source_row_id` preserves one Company Facts occurrence without using its
position in a source list. Entries are canonically sorted first; occurrences
whose complete parsed entries compare byte-equivalent receive positive
ordinals within that equivalence class. Reordering the SEC list therefore
cannot change the resulting set of source rows, while exact multiplicity is
preserved. Fiscal-period and frame fields participate in this opaque source
identity because the frozen `FinancialFact` schema has no dedicated fields
for them. The SEC adapter never appends `#r<n>` and never infers a revision
lineage from similar economic fields.

Source records and Look-Ahead modified records deliberately share the `rec_`
prefix because both are record identities. Their namespaces still collision-
separate them. A visible `mod_` prefix was rejected because it would act as an
injected-row flag at the sanitized detector boundary. The private manifest is
the only artifact that assigns original/corrupted roles.

Unit Drift modified records follow the same anti-leakage rule: they use a
dedicated hashed namespace while retaining the ordinary `rec_` prefix. Unit
Drift artifacts do not borrow Look-Ahead namespaces even where their generic
envelope field sets are shared; the fault family and version remain part of
identity.

| `duplicate_created_record_id` | `rec` | `quantcheck/duplicate-created-record/v1` | original record id, Duplicate spec, and copy ordinal (fixed `1` in v0.1) |
| `duplicate_fault_id` | `fault` | `quantcheck/duplicate-fault/v1` | clean snapshot id, original/created record ids, seed, and spec version |
| `duplicate_manifest_id` | `man` | `quantcheck/duplicate-manifest/v1` | complete Duplicate manifest body excluding `manifest_id` |
| `duplicate_finding_id` | `find` | `quantcheck/duplicate-finding/v1` | complete Duplicate finding body excluding `finding_id` |
| `duplicate_audit_report_id` | `arep` | `quantcheck/duplicate-audit-report/v1` | complete Duplicate audit-report body excluding `audit_report_id` |
| `duplicate_score_report_id` | `score` | `quantcheck/duplicate-score-report/v1` | complete Duplicate score-report body excluding `score_report_id` |
| `duplicate_research_result_id` | `rsch` | `quantcheck/duplicate-research-result/v1` | complete record-count result body excluding `research_result_id` |
| `duplicate_impact_id` | `impact` | `quantcheck/duplicate-impact/v1` | complete record-count impact body excluding `impact_id` |

Duplicate Observations reuses the existing `aggregate_value_v0_1` /
`unit_drift_research_result_id` / `unit_drift_impact_id` identities unmodified
for its double-counting demonstration (see ADR-004); it does not mint a
parallel identity for that specific calculation, only for the new
`record_count_v0_1` method above.

`duplicate_fingerprint_hash` is **not** a `stable_id`-prefixed identifier —
it is a full 64-character content hash (`ContentHash`), computed by
`canonical_sha256` over an explicit envelope naming the dedicated
`quantcheck/duplicate-fingerprint/v1` namespace and the current
`quantcheck/duplicate-exact-occurrence-copy/v1` spec version, wrapping one
canonical `DuplicateFingerprint`. It intentionally excludes `record_id`,
`form`, and `entity_name` — see `docs/faults/DUPLICATE_OBSERVATIONS.md` and
ADR-004 for the exact field list and the reasoning.

Duplicate created records deliberately share the `rec_` prefix with every
other record identity, for the same anti-leakage reason as Look-Ahead's and
Unit Drift's modified-record identities: a visible role-specific prefix
would act as an injected-row flag at the sanitized detector boundary. Unlike
Look-Ahead/Unit Drift, Duplicate injection **appends** the created record to
the snapshot instead of replacing the original, because exact-occurrence-copy
corruption is additive.

### Revision Overwrite identifiers

| Helper | Prefix | Namespace | Payload |
| --- | --- | --- | --- |
| `revision_history_unit_id` | `runit` | `quantcheck/revision-overwrite-history-unit/v1` | complete explicit adjacent historical/later revision unit, including source-supported lineage, records, cutoff, and exact relative size |
| `revision_overwrite_modified_record_id` | `rec` | `quantcheck/revision-overwrite-modified-record/v1` | historical/later record IDs, Revision Overwrite specification, retained historical availability, and every later-vintage field substituted into the corrupted record |
| `revision_overwrite_fault_id` | `fault` | `quantcheck/revision-overwrite-fault/v1` | clean snapshot ID, eligible history-unit ID, corrupted record ID, seed, and specification |
| `revision_overwrite_manifest_id` | `man` | `quantcheck/revision-overwrite-manifest/v1` | complete private Revision Overwrite manifest body excluding `manifest_id` |
| `revision_overwrite_finding_id` | `find` | `quantcheck/revision-overwrite-finding/v1` | complete public Revision Overwrite finding body excluding `finding_id` |
| `revision_overwrite_audit_report_id` | `arep` | `quantcheck/revision-overwrite-audit-report/v1` | complete Revision Overwrite audit-report body excluding `audit_report_id` |
| `revision_overwrite_score_report_id` | `score` | `quantcheck/revision-overwrite-score-report/v1` | complete Revision Overwrite score-report body excluding `score_report_id` |
| `revision_overwrite_research_result_id` | `rsch` | `quantcheck/revision-overwrite-research-result/v1` | complete `growth_ranking_v0_1` result body excluding `research_result_id` |
| `revision_overwrite_impact_id` | `impact` | `quantcheck/revision-overwrite-impact/v1` | complete `growth_ranking_v0_1` impact body excluding `impact_id` |

Revision Overwrite uses a dedicated `runit_` identity because an economic key
alone does not identify a historical-state corruption: the adjacent declared
lineage sequences, source records, cutoff, and relative-size proof also
matter. Its modified records retain the ordinary `rec_` prefix even though
they use their own namespace; a visible revision-overwrite prefix would leak
injector role through `AuditInputSnapshot`. Private history/source-row/revision
metadata participates in private history-unit and manifest identities only.
Public finding identities cover only evidence that survives the audit boundary.

Later milestones will still need further identifiers (for example the full
benchmark framework). Their payloads are **not** specified here and must not
be improvised: they get dedicated helpers when their artifact contracts are
written. Until then, callers use the generic `stable_id` only with an
explicit new namespace.

## Order independence

Two constructs make identity independent of input order:

* `DatasetSnapshot.records` and `AuditInputSnapshot.records` are sorted by
  `record_id` during validation, and duplicate `record_id`s are rejected.
* `dimensions` are sorted by axis during validation, and duplicate axes are
  rejected.

Sorting produces a new tuple; caller-owned inputs are never mutated.

## Logical identity versus runtime metadata

`CaseConfig` carries only what changes the meaning of a case. `RuntimeMetadata`
carries when and where it ran. Runtime metadata is never an argument to any
identifier helper, so re-running the same logical case on a different day, in
a different directory, or under a different `PYTHONHASHSEED` yields the same
identifiers and the same bytes.
