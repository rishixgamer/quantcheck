# Artifact tree and the public/private contract

## Layout

One benchmark run writes one output root containing two separately rooted
stores:

```
<output_root>/
  public/
    benchmark_config.json      normalized logical configuration
    case_matrix.json           deterministic expansion, execution order
    runtime_metadata.json      clock/platform/interpreter (runtime-specific)
    aggregate_report.json      rebuilt from public case artifacts only
    index.json                 every public artifact, role, path, SHA-256
    cases/<benchmark_case_id>/
      case_config.json         the case's full scientific configuration
      audit_input.json         exactly sanitize_for_audit(corrupted snapshot)
      audit_report.json        finalised findings from all four detectors
      score.json               exact matching outcome and metrics
      research_summary.json    method, changed?, replay restored? (fault only)
      status.json              terminal outcome, written last
  private/
    cases/<benchmark_case_id>/
      clean_snapshot.json      pre-injection truth
      corrupted_snapshot.json  post-injection state
      manifest.json            the answer key
      repaired_snapshot.json   manifest-assisted exact replay result
      research_impact.json     controlled counts and deltas
      private_index.json       private artifacts and hashes
      diagnostics.json         exception class and message, on failure
```

A clean control's private tree holds only its clean snapshot and private index,
because the clean snapshot still carries `entity_name` and `source_row_key`.

## What may never appear in `public/`

Manifests; fault target answer keys; hidden role relationships; pre-corruption
values; original or reference private values; private research values and
deltas; private exception diagnostics; unapproved target identifiers or counts;
local absolute paths; user or home paths; temporary paths; output roots; cache
paths; credentials, tokens, or secrets; raw SEC cache; any reference into
`private/`; symlink escapes; path traversal; cross-case references.

This is enforced three ways:

1. **Structurally.** A public artifact reference is a validated relative POSIX
   path. `PUBLIC_RELATIVE_PATH_PATTERN` makes `..`, absolute paths, backslashes,
   drive letters, and `~` *unrepresentable* rather than merely rejected; a
   `private` segment is refused separately; and the resolved location must stay
   under the resolved root, which catches symlink escapes.
2. **By construction.** Public failures carry a stage, a category, a normalised
   code, and a **fixed constant sentence per category**, so no exception text,
   value, or path can reach a public artifact through string formatting.
   Research summaries expose only method, changed, and restored.
3. **By scanning the bytes on disk.** `quantcheck.release_evidence` defines
   `PRIVATE_ONLY_ARTIFACT_KEYS` (matched as exact JSON object keys, never
   substrings, so a legitimately public detector-derived
   `candidate_scale_factor` is not confused with the manifest's private
   `scale_factor`), plus `LOCAL_PATH_MARKERS` and `SECRET_MARKERS`. A companion
   test asserts those names *are* present in the private tree, so the scan
   cannot pass vacuously.

## Persistence guarantees

* One canonical serializer, no second JSON representation.
* Write to a temporary file in the destination directory, flush, `fsync`,
  atomic `os.replace`. No temporary file survives a run.
* Case artifacts are **immutable**: identical bytes are reused untouched,
  conflicting bytes raise `ArtifactIntegrityError`, and **no force-overwrite
  option exists anywhere** — asserted by signature inspection.
* `status.json` is written last, after every required artifact is persisted, and
  is never written over a prior *successful* status. File existence alone is
  never treated as success.
* Runtime metadata, the aggregate report, and the public index are per-run
  derived artifacts and are replaced, because they are rebuilt from immutable
  evidence.

## Resume

Resume revalidates before reusing: status schema, case identity, every
referenced path and content hash, the stored configuration's exact bytes,
audit-input/report/score linkage, the research summary, and the private index.
An invalid prior success is classified as an integrity failure whose conflicting
artifacts are left untouched, while aggregation independently downgrades the
case to `incomplete`. The two views deliberately disagree, because overwriting
the conflicting status would destroy the evidence the failure exists to
preserve.

## Public-only usability

The aggregate report, the presentation model, the HTML summary, and the
dashboard are all rebuilt from `public/` alone. Copying only `public/` to a
fresh location with no `private/` directory at all reproduces the saved
aggregate byte for byte and renders identical HTML. This is verified for the
0.1.0 release in [FINAL_BENCHMARK_RESULTS.md](FINAL_BENCHMARK_RESULTS.md).

A released held-out artifact must therefore stay **readable** with no release
authorization open. Reading is not running: reserved final seeds are gated at
execution (`benchmark_contract.require_seed_execution_authorized`), never at
deserialization. See [THREAT_MODEL.md](THREAT_MODEL.md).
