# QuantCheck v0.2 detector execution and finding evaluation

This document is the serialization, versioning, and migration contract for the
additive `quantcheck/benchmark/v2` development and validation path.

`v0.1.0` remains an immutable comparison point. Its detector implementations,
finding IDs, combined reports, score reports, benchmark artifacts, release
freeze, checksums, and published metrics are not rewritten or recomputed by
this contract.

## Contract boundary

The v0.2 path separates three stages:

1. A `BenchmarkV2Config` expands frozen corpus units into deterministic
   `BenchmarkV2CaseConfig` objects. Every fault case requires a paired clean
   control.
2. `run_selected_detectors_v2` receives exactly an `AuditInputSnapshot` and a
   `DetectorExecutionConfigV2`. It runs one, several, or all supported frozen
   detectors. It has no manifest, injector, target rank, pre-corruption value,
   or clean-snapshot parameter.
3. Only after the corrupted and clean-control executions are finalized does
   `evaluate_detector_execution_v2` receive the private manifest. It writes an
   unchanged strict primary-family score beside a non-metric production
   interpretation of every finding.

`AuditInputSnapshot` remains the detector trust boundary. Corpus partitions,
source revision markers, manifests, and injector metadata do not cross it.

## One configuration architecture

`DetectorExecutionConfigV2` is the single detector-execution configuration
used by the Python API, the benchmark case config, and the additive CLI. It
contains:

- `selected_detectors`: one normalized tuple in contract order;
- `detector_configs`: the existing frozen `BenchmarkDetectorConfigs`, not a
  parallel threshold schema.

The supported keys and canonical order are:

1. `duplicate_observation`
2. `lookahead_timestamp`
3. `revision_overwrite`
4. `unit_drift`

An empty selection, duplicate key, unknown key, or benchmark profile whose
primary detector is not selected is rejected. Logical reorderings normalize to
the same configuration, identifier, and bytes.

## Dual evaluation views

### Strict primary-family score

`BenchmarkV2Evaluation.strict_primary_audit_report` is built with the frozen
v0.1 combined-report function, and `strict_primary_score` is built by the
primary family's frozen exact one-to-one scorer. No scoring formula, matching
rule, denominator, null convention, threshold, or finding is changed.

With the exact all-detector selection, the strict report and score are
byte-identical to direct v0.1 dispatch for the same audit input and manifest;
`v0_1_all_detector_comparable` is `true`. A subset still has strict
primary-family semantics, but its smaller finding population is not the v0.1
all-detector benchmark population, so the flag is `false`.

The strict score is the only metric view. In particular, secondary findings do
not become true positives and do not change recall.

### Production finding interpretation

Every corrupted-execution finding is preserved in full and assigned exactly
one category, in this precedence order:

| Category | Evidence required | Metric effect |
| --- | --- | --- |
| `primary_matched` | The frozen primary scorer accepted an exact one-to-one finding/fault match. | Already counted by the unchanged strict score. |
| `independent_background` | The same detector/rule/evidence finding is present in the paired clean control after deterministic original/corrupted record-ID correspondence. | None. |
| `secondary_corroborating` | A non-primary detector's public affected-record/evidence references exactly one injected fault unit, and no clean-control equivalent exists. | None. |
| `unmatched` | No unique supported primary, clean-control, or causal relationship was established. | None; it remains explicitly unexplained. |

Clean-control equivalence excludes only `finding_id` and explanatory prose from
the comparison. It retains detector and rule identity, evidence, values, dates,
severity, confidence, and provenance. Corrupted record IDs are deterministically
mapped to their original clean IDs for that comparison. This lets legitimate
unusual observations remain visible and be called background only when the
paired control proves they pre-existed the injection.

For a secondary relationship, ordinary findings contribute their affected
record IDs and Unit Drift findings also contribute neighbor IDs carried in
public evidence. Duplicate injection's causal unit contains the source and
created-copy IDs. If a finding intersects zero or more than one fault unit, it
is `unmatched`, not guessed into a relationship.

`FaultUnitOutcomeV2` gives each injected unit its one primary finding, any
secondary findings, and the complete rule IDs those attached findings violated.
The schemas enforce all of the following:

- one primary exact match per finding and fault, as enforced by the frozen
  scorer;
- one category per finding;
- one fault-unit outcome per injected fault;
- one secondary finding may attach to at most one fault unit;
- production primary relationships exactly equal the strict scorer's matches;
- secondary findings never alter strict true-positive or recall counts.

## The three researcher questions

For one `BenchmarkV2Evaluation`:

- **Did the primary injected failure get detected?** Read
  `all_primary_faults_detected`, `primary_matched_fault_count`,
  `primary_missed_fault_count`, and each fault unit's `primary_finding_id`.
- **What other valid rules did the same record violate?** Read each fault
  unit's `secondary_finding_ids` and `violated_rule_ids`, then resolve those IDs
  in `production_interpretation.findings`.
- **Which findings remain genuinely unexplained?** Read
  `production_interpretation.genuinely_unexplained_finding_ids`; it is validated
  to equal exactly the `unmatched` category.

No correlated finding is dropped from either the strict report or the
production interpretation.

## Serialization and identities

All v0.2 artifacts use the existing `canonical_json_bytes` and
`parse_canonical_json` functions. There is no second serializer. Decimal values
remain canonical JSON strings, object keys are canonical, tuples serialize as
arrays, and day-level dates use the existing canonical date form.

| Artifact | `spec_version` | ID prefix | Stable-ID namespace |
| --- | --- | --- | --- |
| `BenchmarkV2Config` | `quantcheck/benchmark/v2` | `bench2_` | `quantcheck/benchmark-config/v2` |
| `BenchmarkV2CaseConfig` | `quantcheck/benchmark/v2` | `bcase2_` | `quantcheck/benchmark-case/v2` |
| `DetectorExecutionV2` | `quantcheck/detector-execution/v2` | `dexec2_` | `quantcheck/detector-execution/v2` |
| `ProductionFindingInterpretationV2` | `quantcheck/finding-evaluation/v2` | `fint2_` | `quantcheck/finding-interpretation/v2` |
| `BenchmarkV2Evaluation` | `quantcheck/finding-evaluation/v2` | `eval2_` | `quantcheck/evaluation/v2` |

Each identifier hashes the complete canonical artifact body except its own ID.
The v0.2 execution embeds the exact sanitized audit input and records its
canonical SHA-256. The contained detector `AuditReport` and `Finding` objects
remain the frozen v1 schemas with their original detector IDs, detector
versions, rule IDs, provenance, finding IDs, and identity namespaces. Wrapping
them in v0.2 never re-identifies them.

Cross-process tests compare complete canonical bytes under three
`PYTHONHASHSEED` values and different working directories.

## Python API

Selected execution uses the same config model used by benchmark cases:

```python
from quantcheck.benchmark_v2_execution import run_selected_detectors_v2
from quantcheck.benchmark_v2_schemas import DetectorExecutionConfigV2

config = DetectorExecutionConfigV2(
    selected_detectors=("lookahead_timestamp", "revision_overwrite"),
)
execution = run_selected_detectors_v2(audit_input, config)
```

Corpus-backed cases use `build_benchmark_v2_config`,
`expand_benchmark_v2_cases`, and `run_benchmark_v2_case`. Development seeds
`0`–`9` and validation seeds `100`–`109` are admitted. This milestone rejects
held-out corpus units and reserved final seeds before execution.

## Additive CLI

The installed `quantcheck` command is a checksum-frozen v0.1 surface. It is not
rerouted. The v0.2 module CLI is additive and uses the exact Python schemas and
artifact store above:

```bash
# One detector
uv run python -m quantcheck.benchmark_v2_cli audit \
  --audit-input audit_input.json \
  --output detector_execution.json \
  --detectors lookahead_timestamp

# An explicit pair; use --detectors all for all supported detectors
uv run python -m quantcheck.benchmark_v2_cli audit \
  --audit-input audit_input.json \
  --output detector_execution.json \
  --detectors lookahead_timestamp,revision_overwrite

# One expanded corpus case and its mandatory paired control
uv run python -m quantcheck.benchmark_v2_cli run-case \
  --case benchmark_v2_case.json \
  --output case_artifacts
```

`run-case` writes public `case_config.json`,
`clean_control_execution.json`, `corrupted_execution.json`, and
`evaluation.json`. Private `clean_snapshot.json`, `corrupted_snapshot.json`,
and `manifest.json` are written under a separate `private/` root.

## Migration and compatibility

There is deliberately no in-place migration:

- v0.1 artifacts stay v0.1 artifacts and continue to validate against their
  frozen schemas;
- v0.1 benchmark metrics and held-out evidence are never retroactively
  categorized, rewritten, or recomputed;
- a v0.2 interpretation may be produced only by an explicit new run that has
  both finalized selected-detector executions, its paired clean control, and
  the corresponding private manifest;
- that new output receives new v0.2 container IDs while preserving every
  nested v1 finding/report/score byte that is reused;
- consumers dispatch on `spec_version`; they must not coerce a v1 artifact into
  a v2 schema or overwrite an existing v1 path with v2 bytes.

The v0.1 `CHECKSUMS.md` is intentionally unchanged because v0.2 files are
outside the v0.1 release surface. A future v0.2 release candidate must define
its own freeze and checksums after development and validation rehearsal. This
milestone does not authorize a held-out execution and does not claim v0.2
aggregate metrics.

## Current limitations

- Production categories are evidence interpretations, not revised precision,
  recall, or false-positive metrics.
- `independent_background` requires exact paired-control equivalence. A valid
  background finding whose evidence naturally changes between snapshots may
  remain `unmatched`; the contract prefers an explicit unknown over a guess.
- `secondary_corroborating` proves a unique record-level relationship to an
  injected unit, not that the secondary rule was the injector's intended
  failure family.
- Only development and validation single-case execution is implemented here.
  Aggregate reporting, a v0.2 release freeze, and held-out execution remain
  later gated work.
