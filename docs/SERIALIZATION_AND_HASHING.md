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

Later milestones will need further identifiers (modified records, duplicate
occurrences, manifests, findings, reports). Their payloads are **not**
specified here and must not be improvised: they get dedicated helpers when
their artifact contracts are written. Until then, callers use the generic
`stable_id` with an explicit new namespace.

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
