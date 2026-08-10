# Performance and local execution

This document defines the additive
`quantcheck/external-audit-execution/v1` production execution contract and the
reproducible performance suite around it. It changes no detector, threshold,
finding, benchmark score, or v0.1 artifact.

## Profile first: measured pre-optimization behavior

The existing `audit_external_rows` implementation was profiled before this
layer was designed. The deterministic input used twenty duration observations
per entity, exact `Decimal` values, no injected faults, all four detectors, and
an as-of date after every observation. These are operational timings on macOS
arm64 / Python 3.12.13, not scientific metrics or cross-machine promises.

| Records | Normalize | Existing all-detector audit | Traced peak Python allocation | Normalized bytes | In-memory private serialization bytes |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 0.096 s | 0.255 s | 7,938,232 | 777,229 | 1,823,915 |
| 5,000 | 0.553 s | 1.336 s | 38,899,200 | 3,885,229 | 9,115,915 |
| 20,000 | 2.007 s | 7.345 s | 154,250,416 | 15,549,643 | 36,489,157 |

`tracemalloc` changes runtime substantially, so its elapsed times are not in
the table. It measures Python allocations, not native allocator or aggregate
multi-process RSS.

A separate `cProfile` run at 20,000 records took 16.6 s under instrumentation.
Canonical conversion accounted for 12.8 s cumulative. Repeated whole-snapshot
identity construction/checking accounted for most of that work. Direct
unprofiled detector passes over the already-sanitized input were:

| Detector | Runtime |
| --- | ---: |
| Look-Ahead | 0.394 s |
| Unit Drift | 0.700 s |
| Duplicate Observations | 1.026 s |
| Revision Overwrite | 0.396 s |

These results support bounded partitions and content-addressed reuse. They do
not justify weakening the frozen identity checks, changing detector science,
or introducing a service architecture.

## Evidence-backed implementation

Three optimizations were implemented:

1. **Complete-entity partitions.** A partition contains complete histories for
   its entities, and entity sets must be disjoint. The engine holds only one
   partition per sequential worker at a time. Each local process holds at most
   one partition at a time.
2. **Bounded local processes.** Supported worker counts are exactly `1`, `2`,
   and `4`. `spawn` is used so workers do not inherit caller threads or native
   library state. No queue service, database, scheduler, Kubernetes,
   microservice, or network transport exists.
3. **One full private representation.** Persistence keeps the normalized
   dataset and a small entity-set summary. It does not persist redundant full
   `DatasetSnapshot` and `AuditInputSnapshot` copies. The public report retains
   their deterministic IDs and hashes, so the normalized dataset plus the
   plan can reproduce them.

The frozen in-memory audit still constructs its snapshot and sanitized input;
the optimization bounds their lifetime and persistence rather than claiming an
unsupported out-of-core detector rewrite.

## Partition contract and scientific equivalence boundary

`complete_entity_histories_disjoint` is an explicit source contract. The
engine verifies that no successful partition shares an entity ID with another
successful partition. It cannot prove that an upstream source omitted a record;
source owners must attest that each supplied entity history is complete for the
run.

That boundary is sufficient for every current rule:

- Look-Ahead and Revision Overwrite evaluate each sanitized record.
- Duplicate Observations' exact fingerprint includes `entity_id`.
- Unit Drift's comparable-series key includes `entity_id`.
- production concept/unit and publication-lag rules evaluate each record.
- production reporting-frequency groups include `entity_id`.

Therefore no current finding can require records from two valid partitions.
Per-partition `AuditReport` IDs intentionally differ from a monolithic report
because each report names its own audit input. The logical finding objects are
unchanged. A future cross-entity rule must reject this incremental contract or
introduce its own explicit merge semantics; it must not silently reuse it.

Performance-corpus routing ranks complete entity IDs by SHA-256 and assigns
them round-robin. Python hash randomization, input enumeration, filenames,
directory order, and worker scheduling never participate.

## Persistence, resume, retry, and interruption recovery

The root is content-addressed:

```text
<root>/
  public/
    partitions/<partition-id>/
      partition_spec.json
      validation_profile.json
      audit_report.json
      status.json
    runs/<run-id>/
      plan.json
      finalization.json
  private/
    partitions/<partition-id>/
      normalized_dataset.json
      partition_summary.json
  operations/
    runs/<run-id>/latest.json
```

`partition-id` covers the source SHA-256/size, logical partition key, mapping,
policy, as-of date, expected count, and partition semantics. It excludes paths
and execution mechanics. `run-id` covers the normalized sorted partition set
and the same audit contract. Worker count is an operational option and is
absent from both identities.

All evidence writes use the existing canonical serializer, same-directory
temporary file, flush, `fsync`, and atomic `os.replace` path. A successful
partition status is written last. A run finalization is written only after
every partition has terminal state and entity disjointness succeeds. A retry
may atomically replace a `completed_with_failures` finalization after a
previously failed partition succeeds; it cannot replace conflicting immutable
case evidence or a different successful status.

Resume does not trust file existence. It verifies:

- source bytes against the declared SHA-256 and size;
- partition, mapping, policy, and as-of linkages;
- canonical public schemas and artifact hashes;
- public report identity;
- private normalized-dataset hash; and
- the private entity-set summary.

An unchanged partition is reused. A changed source hash produces a new
partition identity, so only that partition executes and prior immutable
evidence remains available. A failed partition is retried without rerunning
valid successes. One failure does not stop other partitions. `KeyboardInterrupt`
propagates; already-completed statuses remain, no premature finalization is
written, and the next run resumes them.

Operational logs are strict canonical records containing only run/partition
IDs, fixed event/failure codes, worker count, and `redacted=true`. They contain
no timestamps, paths, values, source rows, exception text, or stack traces.
They are operational rather than logical artifacts and are excluded from the
worker-count equality hash.

## Reproducible benchmark suite

Run:

```bash
uv run python scripts/run_performance_benchmarks.py \
  --output performance_baseline_v1.json
```

The script generates exact CSV corpora, excludes generation time from audit
runtime, executes each envelope sequentially, measures detectors separately on
the same bounded partitions, measures unchanged and one-changed-partition
reruns, and runs the large corpus in fresh roots with worker counts `1`, `2`,
and `4`. It refuses the report if any logical artifact-tree hash differs.

The checked-in `performance_baseline_v1.json` is 3,386 bytes, SHA-256
`0ed3fe5cb5e3b2c466208503ab2abe5c25c8e14f7a8d75614ddaa70235ebf70e`.
It records macOS 26.5.2 arm64, Python 3.12.13. Durations below are rounded from
the canonical nanosecond fields; sizes are exact bytes.

| Envelope | Records / partitions | Detector runtimes: Duplicate / Look-Ahead / Revision / Unit | Total | Peak Python allocation | Normalized | Public | Private | Unchanged rerun | One changed partition |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Small | 1,000 / 2 x 500 | 0.035 / 0.014 / 0.014 / 0.022 s | 0.350 s | 3,704,317 | 801,494 | 18,892 | 802,702 | 0.004 s | 0.176 s; 1 reused, 1 executed |
| Medium | 10,000 / 4 x 2,500 | 0.388 / 0.139 / 0.139 / 0.226 s | 3.435 s | 18,297,232 | 8,010,992 | 34,280 | 8,019,008 | 0.010 s | 0.865 s; 3 reused, 1 executed |
| Large | 50,000 / 10 x 5,000 | 1.884 / 0.734 / 0.767 / 1.247 s | 17.916 s | 36,325,079 | 40,091,893 | 80,332 | 40,129,433 | 0.036 s | 1.802 s; 9 reused, 1 executed |

The large logical artifact hash is
`42f05328cdcda08e0882415197f8dde62bc71c591412e31e37abb6387c76203e`
for all supported worker counts:

| Workers | Runtime | Speedup vs 1 | Conservative peak upper bound |
| ---: | ---: | ---: | ---: |
| 1 | 17.916 s | 1.00x | 36,325,079 bytes |
| 2 | 9.725 s | 1.84x | 72,650,158 bytes |
| 4 | 6.436 s | 2.78x | 145,300,316 bytes |

The upper bound multiplies the measured largest-partition traced allocation by
worker count; it is not measured aggregate RSS.

## Documented envelopes

These are local operating envelopes with deliberate headroom, not CI timing
assertions or guarantees on other hardware:

| Envelope | Corpus contract | Sequential target | Peak Python allocation target | Incremental target |
| --- | --- | ---: | ---: | ---: |
| Small | <= 1,000 records; <= 500/partition | <= 1 s | <= 8 MiB/worker | unchanged <= 0.25 s |
| Medium | <= 10,000 records; <= 2,500/partition | <= 6 s | <= 24 MiB/worker | one changed <= 2 s |
| Large | <= 50,000 records; <= 5,000/partition | <= 30 s sequential; <= 12 s at 4 workers | <= 48 MiB/worker; <= 192 MiB conservative at 4 workers | unchanged <= 0.25 s; one changed <= 4 s |

Operators should rerun the suite on their target machine and choose a worker
count from measured wall-time/memory tradeoffs. Larger-than-envelope inputs
must be split into more complete-entity partitions; increasing the per-worker
partition cap without measurement is not a supported optimization.

## Deliberate limits

- Memory is bounded by partition size, not fully out-of-core within one
  partition; frozen models still require immutable complete tuples.
- File hashing is intentionally repeated on resume to prove unchanged bytes.
- Peak allocation excludes native PyArrow memory and aggregate worker RSS.
- Runtime and operational logs are machine/attempt evidence, not canonical
  scientific artifacts.
- Only file-backed CSV/Parquet/Arrow partitions use this engine. In-memory
  Python iterables retain the direct single-audit API because they have no
  immutable raw-byte identity for safe cross-run reuse.
- Local process callers must use a normal guarded Python entry point because
  workers use `spawn`; the supplied script does.
