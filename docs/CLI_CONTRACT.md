# CLI contract

This is the current authoritative contract for Recovery Phase 9. It defines
the rebuilt v1 Typer command surface, the saved-stage `inject`/`audit`/
`evaluate` workflow, the machine/human output shape, and the exit-code
taxonomy. It is a thin interface over existing implementation, described
elsewhere: this document adds no scientific behavior of its own.

The project scope fixes Phase 9's scope in one sentence and names no
concrete command, flag, or exit code. The lost historical release referenced
a `docs/CLI_CONTRACT.md`, but that file did not survive; historical evidence
The archived design describes a six-command Typer CLI with exit codes
`0/2/3/4/5/10`, used here as design inspiration only. No historical flag
syntax, JSON field name, or exit-code assignment is claimed to be
byte-identical to the lost release. The reconstruction decisions are recorded
in `docs/DECISIONS.md` (ADR-007); this document is the frozen result.

## Command surface

Six root commands, exactly:

```text
quantcheck ingest sec
quantcheck inject
quantcheck audit
quantcheck evaluate
quantcheck benchmark run
quantcheck benchmark smoke
quantcheck explain
```

`ingest` and `benchmark` are command groups with no behavior of their own;
running either with no subcommand prints its help. There is no `--version`
flag and no separate `python -m quantcheck` behavior (only the
`quantcheck.cli` module form, `python -m quantcheck.cli`, which is what the
installed console script itself runs). There is no `snapshot`, `score`,
`damage`, `run-case`, `demo`, dashboard, HTML, aggregate-rebuild, release, or
force-overwrite command, and no flag anywhere that authorizes a held-out or
final/release seed.

Every command accepts a command-local `--json` flag. Without it, output is
plain, stable, single-line-per-fact human text on stdout. With it, exactly
one canonical JSON object is written to stdout, using the project's own
canonical serializer (`canonical_json_bytes`) — the same encoding every
artifact on disk uses: sorted keys, exact Decimal strings, ISO dates,
preserved nulls, no floats, no ANSI.

## `ingest sec`

Wraps `SecCompanyFactsAdapter` exactly (`fetch`/`replay`/`normalize`/
`build_snapshot`). Never a generic ingestion framework, never a second
provider.

```text
quantcheck ingest sec
  --cik <CIK>
  --config <sec-normalization.json>
  --cache-dir <dir>
  --user-agent <contact-identified UA>
  --output <dir>
  --dataset-name <name>
  --as-of-date <ISO date>
  [--refresh]        # bypass a cached response and refetch over the network
  [--replay-only]     # never touch the network; require an already-cached response
  [--json]
```

`--config` is a JSON object with exactly the fields `cik`, `concepts`,
`forms`, `filed_from`, `filed_through` (each `concepts` entry has exactly
`taxonomy`, `concept`, `unit`, `period_type`) — the CLI-input shape of
`SecNormalizationConfig`, which is a plain dataclass rather than a Pydantic
schema and so is validated by an explicit exact-field-set check before
construction. `--refresh` and `--replay-only` are mutually exclusive.

Writes exactly one public artifact, `snapshot.json` (a `DatasetSnapshot`)
under `--output`. Never writes cache contents, raw SEC bytes, or the cache
directory path into any public artifact or stdout.

## Saved-stage workflow: `inject` / `audit` / `evaluate`

All three operate over the existing fully expanded `BenchmarkCaseConfig` —
the same case type `quantcheck.benchmark_expansion.expand_benchmark_cases`
produces — never a second, CLI-specific case format. A saved-stage output
root is laid out exactly like a benchmark run's output root:
`<output>/public/cases/<benchmark_case_id>/*.json` and
`<output>/private/cases/<benchmark_case_id>/*.json`, via the existing
`AtomicArtifactStore` (immutable case evidence, no force-overwrite option).

For the same fully expanded case, running `inject` then `audit` then
`evaluate` produces public and private artifacts byte-identical to a single
`dispatch_benchmark_case` call, for all four fault families.

### `inject`

```text
quantcheck inject --case <case-config.json> --output <dir> [--json]
```

Loads and strictly validates a `BenchmarkCaseConfig` (unknown fields,
invalid enums, duplicate or prohibited seeds, and broken identity
relationships are all rejected — final seeds `1000`–`1009` included, with no
override flag). Delegates to the matching fault family's injector. Writes the
public `case_config.json` and the private `clean_snapshot.json`; a fault case
additionally writes the private `corrupted_snapshot.json` and `manifest.json`.
Never runs detection, scoring, or replay.

### `audit`

```text
quantcheck audit --dir <dir> [--json]
# or, for an arbitrary canonical snapshot not produced by `inject`:
quantcheck audit --case <case-config.json> --snapshot <dataset-snapshot.json> --output <dir> [--json]
```

`--dir` continues a saved `inject` stage in that same output root. The
`--case`/`--snapshot`/`--output` form audits any canonical `DatasetSnapshot`
directly — for example one built by `ingest sec` — using the given case's
`fault_profile` (to brand the combined report's identity) and
`detector_configs`. Either form: sanitizes the snapshot exactly once via
`sanitize_for_audit`, runs the manifest-blind detector tuple
(`detect_lookahead`, `detect_unit_drift`, `detect_duplicate_observations`,
`detect_revision_overwrite`), and finalizes one combined `AuditReport`. Writes
the public `audit_input.json` and `audit_report.json`. **Never reads or
constructs a manifest**, even when one already exists on disk from a prior
`inject`.

### `evaluate`

```text
quantcheck evaluate --dir <dir> [--json]
```

Requires a finalized public `audit_report.json` already in `<dir>` (from
`audit`). This is the first saved-stage command that reads the private
manifest. Delegates to the matching fault family's scorer, exact
manifest-assisted replay, and configured research comparison. Writes the
public `score.json` and `research_summary.json`, and the private
`repaired_snapshot.json` and `research_impact.json`. Rejects a clean-control
case outright: it has no manifest, so its terminal saved-stage artifact is its
own `audit` output, not an `evaluate` output.

## `benchmark run` / `benchmark smoke`

Thin wrappers over the existing Milestone 8 runner.

```text
quantcheck benchmark run --config <benchmark-config.json> --output <dir> [--resume/--no-resume] [--json]
quantcheck benchmark smoke --output <dir> [--resume/--no-resume] [--json]
```

`run` strictly loads and identity-checks a `BenchmarkConfig`, then calls
`run_benchmark(config, output_root=..., runtime=..., resume=...)` unchanged.
`smoke` calls the existing `smoke_benchmark_config()` — there is no committed
`configs/smoke.json`; the smoke configuration is a pure in-code builder, and
this command constructs nothing else. `--resume` defaults to on, matching the
library default. Both preserve every existing resume/revalidation, failure,
and public/private separation rule. Both exit `5` (a structured
failed-or-incomplete outcome) whenever the resulting aggregate's
`failed_case_count + incomplete_case_count > 0`, decided from the returned
aggregate's own counts, never from a raised exception.

## `explain`

```text
quantcheck explain --dir <dir> [--finding <finding_id>] [--case-id <id>] [--json]
```

Reads only `public/` under `--dir`. With `--finding`, prints that finding's
public fields (`rule_id`, `severity`, `confidence`, `explanation`,
`affected_record_ids`) from the saved audit report. Without it, prints the
case's fault profile, finding count and IDs, and (for a benchmark-run tree)
its terminal `status.json` outcome. `--case-id` selects among multiple saved
cases (as in a benchmark run's output tree); a saved-stage `inject` output
root holds exactly one case and needs no `--case-id`. Never loads a manifest,
never reveals a pre-corruption or hidden-role value, never reruns a detector,
and never reruns the benchmark.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | success |
| `2` | user/configuration input rejected (missing/malformed file, invalid JSON, unknown field, invalid enum, prohibited/duplicate seed, broken artifact identity) |
| `3` | saved-artifact/integrity/persistence problem (missing prior stage, conflicting immutable artifact, unreadable store) |
| `4` | SEC source/cache/normalization rejected |
| `5` | a `benchmark run`/`benchmark smoke` outcome contains a failed or incomplete case |
| `10` | unexpected internal error — reported with the fixed sentence "an unexpected internal error occurred", never the exception's own message |

`--help` on any command or group exits `0`. Running a command group with no
subcommand (including bare `quantcheck`) prints the same help but exits `2`:
standard Click/Typer `no_args_is_help` semantics (a missing-command usage
error), not a bespoke choice.

## Privacy rules

- `audit` (both forms) never imports or constructs a manifest type.
- `evaluate` is the first CLI stage permitted to read a manifest, and only
  after a finalized public `AuditReport` already exists.
- `explain` reads only `public/`.
- No command's `--json` payload or human text includes: a manifest, a
  pre-injection record identity for a family whose injector replaces the
  original record (Look-Ahead, Unit Drift, Revision Overwrite), a target rank
  or selection digest, private research counts or deltas (only the
  `changed`/`exact_restoration` booleans and the method name are public), a
  local absolute path, a cache directory path, or a credential.
- `Duplicate Observations` is a documented exception to the
  "original record identity never appears publicly" rule: its injector *adds*
  a copy rather than replacing the original, so the original record's own
  `record_id` legitimately remains visible as one half of the real duplicate
  pair in public detector evidence.

## Configuration ownership

Every command hands parsed JSON straight to an existing strict Pydantic model
(`BenchmarkCaseConfig`, `BenchmarkConfig`) or, for `SecNormalizationConfig`
(a plain dataclass), to an explicit exact-field-set check before
construction. There is no loose-dictionary configuration path, no silent
default substitution for an invalid value, and CLI parsing never widens what
the underlying schema accepts.
