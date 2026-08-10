# External dataset audit contract

## Status and boundary

This document defines the additive production input path for customer-supplied
financial facts. Its serialized contracts are:

| Artifact | Version | Identifier |
| --- | --- | --- |
| Mapping | `quantcheck/dataset-mapping/v1` | `dmap_` |
| Dry-run profile | `quantcheck/dataset-validation-profile/v1` | `dprof_` |
| Normalized dataset | `quantcheck/normalized-dataset/v1` | `ndset_` |
| Production policy | `quantcheck/audit-policy/v1` | `apol_` |
| Public audit report | `quantcheck/external-audit/v2` | `xaudit2_` |

The path is additive. It does not change the frozen `FinancialFact`,
`DatasetSnapshot`, `AuditInputSnapshot`, detector, benchmark, scoring, release,
or CLI contracts. It never invokes fault injection, never constructs or reads a
benchmark manifest, never scores against private truth, and makes no network
request.

This is a production data audit, not a benchmark. A dry-run profile is not an
audit, and neither result is a claim about detector recall, precision, financial
performance, or data correctness beyond the rules actually run.

## Supported inputs

- Parquet;
- Arrow IPC file and Arrow IPC stream;
- CSV as an explicit interoperability fallback;
- Python `Iterable[Mapping[str, object]]` input.

The file format is always declared by the caller. File extensions and CSV
dialects are not sniffed. CSV syntax, encoding, delimiter, quote character, and
null tokens are explicit. Parquet and Arrow are read with PyArrow in batches;
PyArrow is imported only when one of those formats is used.

The immutable v0.1 wheel metadata cannot be changed without invalidating the
released checksum surface. Consequently this additive, pre-v0.2-release module
does not yet advertise a wheel extra. Operators using Parquet or Arrow must
install a compatible PyArrow explicitly (the repository lock currently tests
PyArrow 24.0.0). Absence produces the data-free diagnostic
`input.pyarrow_unavailable`; importing QuantCheck or using CSV/Python input does
not import or require PyArrow. A future v0.2 release must declare the dependency
or extra in its own package metadata and freeze.

## Mapping contract

`DatasetMappingV1` resolves every canonical meaning. Unknown mapping fields are
rejected. Required source columns must exist. Unmapped source columns are either
rejected or allowed by the explicit `unmapped_columns` policy; they are never
silently normalized.

| Canonical meaning | Mapping requirement |
| --- | --- |
| Dataset identity | Explicit stable `dataset_name` |
| Entity identifier | Required column or declared constant |
| Entity display name | Column, constant, or explicit absent declaration |
| Concept namespace and concept | Each is a column or constant |
| Value | Required column with `decimal_integer_or_canonical_text_only` |
| Unit | Required column or declared constant |
| Dimensions | Explicit axis/member-column pairs; `()` means dimension-free |
| Period type | Constant `instant`/`duration`, or explicit source label mapping |
| Period start/end | Day-level column/constant; start may be explicitly absent |
| Filing date | Explicit day-level column/constant |
| Availability date | Source column meaning first researcher availability, or evidenced equality to filing |
| Form | Column, constant, or explicit absent declaration |
| Accession/equivalent | Column, constant, or explicit absent declaration; source-row ID remains required |
| Source name/locator | Explicit public-audit provenance column or constant |
| Source row identity | Required source-defined column, never input row position |
| Revision lineage | Source-declared lineage/sequence columns, or explicit independent declaration |

Availability has two admitted forms only:

1. a source date whose declared meaning is
   `first_available_to_researcher_end_of_day`, with an evidence reference; or
2. `same_as_filing`, with the exact basis
   `source_contract_confirms_filing_date_equals_availability_date` and an
   evidence reference.

No fallback sets availability equal to filing. No timestamp is truncated to a
date. Sources with timestamp-level semantics must provide an explicitly derived
day-level field under a separately reviewed mapping.

Revision columns may be null only as a pair, explicitly meaning an independent
occurrence. A non-null pair is converted to the existing opaque
`xline_<digest>#r<n>` declaration. QuantCheck validates unique positive
sequences, one economic identity per lineage, and monotonic filing and
availability dates with the existing point-in-time engine. Accessions, forms,
matching business keys, values, or row adjacency never create a lineage.

## Exact values and source identity

Accepted financial values are `Decimal`, non-boolean integer, or canonical
fixed-point decimal text. Python `float`, Arrow float/double, exponent text,
boolean, non-finite values, and implicit string conversion are rejected. No
accepted value passes through binary floating point.

Every row must supply a source-defined row identifier. Independent occurrences
receive an opaque stable source coordinate derived from public source
provenance plus that identifier. Declared revisions use source lineage plus
positive sequence. The original source row identifier and raw lineage are
preserved exactly in private `NormalizedRowProvenanceV1`; the sanitized detector
input structurally omits both.

Normalized facts and provenance links are sorted by deterministic record ID.
Input row order, Python hash seed, current directory, temporary directory, user,
and file format do not affect normalized logical bytes. Equivalent CSV,
Parquet, Arrow, and Python rows therefore produce the same `NormalizedDatasetV1`.

## File integrity and non-mutation

Production normalization and audit require `expected_sha256`; optional
`expected_size_bytes` provides a second check. The raw digest is computed before
parsing. The same read-only file handle is used for parsing, and device, inode,
size, and nanosecond modification time are checked again afterward. Missing,
symlinked, drifted, malformed, truncated, invalid-UTF-8, wrong-width CSV, and
wrong-container inputs are rejected.

Dry-run may omit the expected digest so the operator can obtain the observed
SHA-256 and size, review diagnostics, then pin the exact bytes for a production
run. QuantCheck never writes, renames, repairs, or changes permissions on the
customer source file. Python mappings are copied before use and never modified.

## Dry-run profile and diagnostics

Use `profile_external_file` or `profile_external_rows`. The profile reports
only format, source digest/size where applicable, counts, validity, and bounded
machine-readable diagnostics. It contains these literal boundary declarations:

- `audit_claim=false`;
- `benchmark_claim=false`;
- `network_used=false`;
- `manifest_used=false`.

Diagnostic codes, stages, fields, row numbers, and messages are deterministic.
Messages come from a fixed catalogue. Raw financial values, source-row values,
upstream exception text, and local paths are never copied into diagnostics or
exception messages. `max_diagnostics` bounds visible output while exact total
and omitted counts remain available.

## Production workflow

The Python API is intentionally direct:

```python
from datetime import date
from pathlib import Path

from quantcheck.external_dataset_audit import audit_external_file
from quantcheck.external_dataset_contract import ExternalDatasetFileInputV1
from quantcheck.external_dataset_policy_examples import monitoring_policy_v1

artifacts = audit_external_file(
    Path("customer-facts.parquet"),
    mapping=reviewed_mapping,
    file_input=ExternalDatasetFileInputV1(
        input_format="parquet",
        expected_sha256="<reviewed lowercase SHA-256>",
        expected_size_bytes=123456,
    ),
    as_of_date=date(2024, 6, 30),
    policy=monitoring_policy_v1(),
)
public_report = artifacts.public_report
```

The implemented order is exactly:

```text
customer dataset
  -> validate mapping and raw integrity
  -> normalize to FinancialFact
  -> build end-of-day point-in-time DatasetSnapshot
  -> sanitize to AuditInputSnapshot
  -> validate and resolve the explicitly supplied production policy
  -> run its enabled frozen detectors and production-only expectation rules
  -> apply explicit dataset-exception precedence without suppressing results
  -> ExternalDatasetAuditReportV2
```

`ExternalDatasetAuditReportV2` contains normalized/snapshot/audit identities and
hashes, the exact policy ID/version/content hash, counts, explicit resolved
detector configuration, the selected detectors' unchanged public `AuditReport`
objects, every rule's evaluated/disabled/not-evaluated status, policy results,
applied exception reasons, action counts, and disposition. It contains no full
normalized record set, entity name, source row key, raw revision lineage,
private provenance link, manifest, fault injection result, benchmark score,
local path, or runtime metadata. Findings may contain the public evidence
defined by their frozen detector contracts; the workflow does not log the
report automatically.

`ExternalDatasetAuditReportV1` (`quantcheck/external-audit/v1`) remains
parseable for pre-policy artifacts, but no current production entry point emits
it. See
`docs/PRODUCTION_AUDIT_POLICIES.md` for the exact policy, exception, threshold,
and precedence contracts.

## Bounded local execution

File-backed production audits may be supplied as deterministic, integrity-
pinned partitions through `quantcheck.external_dataset_execution`. The exact
partition contract is `complete_entity_histories_disjoint`: every entity's
complete history for the run lives in exactly one partition. The engine
validates entity disjointness, caps records per partition, supports local
worker counts `1`, `2`, and `4`, writes terminal case state and finalization
atomically, isolates failures, resumes interrupted work, retries failed cases,
and reuses only hash-verified unchanged partition identities.

Paths, worker scheduling, worker count, timestamps, and filesystem order do
not enter logical identity. Operational logs use fixed redacted codes. The
engine persists one private normalized dataset per partition and does not
duplicate full private snapshot/audit-input representations. See
`docs/PERFORMANCE_AND_EXECUTION.md` for the artifact tree, incremental boundary,
measured bottlenecks, performance envelopes, and reproducible benchmark.

The smallest hardened container binding over this engine is documented in
`docs/SELF_HOSTED_DEPLOYMENT.md`. It adds confined read-only input bindings, explicit writable
directories, non-root/read-only-root operation, telemetry-disabled configuration, and fixed-code
structured logs without changing this production audit contract.

## Deliberate limitations

The optional design-partner packaging and adjudication workflow is documented separately in
`docs/DESIGN_PARTNER_SHADOW_MODE.md`. It starts from finalized public
`ExternalDatasetAuditReportV2` artifacts, never from source rows, and does not change this mapping,
normalization, audit, or policy contract.

- No vendor-specific adapter, taxonomy harmonization, currency conversion,
  scale inference, identifier lookup, statement reconstruction, or timestamp
  truncation is implemented.
- Wide dimensions require one reviewed axis/member-column pair per axis.
- CSV supports one explicit RFC-style delimiter/quote configuration and UTF-8;
  it does not sniff dialects or locale-specific numbers/dates.
- Each execution partition holds normalized canonical facts in memory because
  the frozen point-in-time and detector contracts consume immutable snapshots.
  Memory is bounded by the reviewed partition cap rather than by the full
  multi-partition corpus; execution is not out-of-core within one partition.
- This path emits manifest-free detector evidence. It cannot produce benchmark
  precision/recall without controlled private truth, and does not claim to.
- Reporting-frequency expectations detect adjacent internal period-end gaps;
  without an explicit reporting window they make no claim about a missing first
  or last expected report.
