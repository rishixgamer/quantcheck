# QuantCheck 0.1.0 final held-out benchmark results

Every number on this page was read back out of the saved standalone summaries under
`evidence/v0_1_release/`, reproduced from the complete public evidence archive.
None is copied from the historical 0.1.0
documentation, and none was produced by tuning anything after the results were
seen.

## Release candidate

| Field | Value |
| --- | --- |
| Release candidate | `relc_2c6e945a71b85b39` |
| Freeze record SHA-256 | `7584be72c2fa3882c3a61c0ba47354cd3e45f53cd1f4d0bb70f9a012e59f42eb` |
| Package version | `0.1.0` |
| Benchmark id | `bench_403a85e506ff66ea` |
| Aggregate report id | `agg_571aae0b7c60a4a5` |
| Release configuration SHA-256 | `a29c131b83d85323b379436e674efbadff7e382f5e0ca09c7dd3e3bef46e6f3c` |
| Case matrix SHA-256 | `2a1ffbc7d2ff32a0965ccfea3076ac17f46a20d2de6c0d9fc6590799e629cc13` |
| Public summary HTML SHA-256 | `2ba3c7746e18df90699a99ddd4ce0e0dc100bb6fa2b0ead7f88e4887e52ac795` |
| Presentation model SHA-256 | `2c2788ca2673f67f807c89760ddbc030ddde13b8395b65be9300af6566ef7f68` |

### An earlier candidate was invalidated, and is preserved

`relc_a573d64b0345a5b5` produced a complete 124-case held-out run first. It was
then **invalidated by a release-plumbing defect, not by its detector
performance**: the schema refused to *deserialize* a reserved final seed at all,
which meant the strict public reader could not load the released
`benchmark_config.json`, and the public evidence package could not be
aggregated, presented, or rendered. The package was unreadable by the very
surfaces built to present it.

The fix draws the boundary at **execution** rather than **representation**
(`benchmark_contract.require_seed_execution_authorized`). It touches no
injector, detector, matcher, denominator, severity rule, or research
calculation. Because the three changed files are frozen inputs, the candidate
no longer verified and a new one had to be cut.

Both runs are preserved. `release_evidence/candidate_1_relc_a573d64b0345a5b5/`
holds the first run and its freeze record. Comparing the two public trees file
by file:

* 595 public files in each, identical file sets;
* **593 of 594 indexed artifacts are byte-identical**, including every case
  configuration, audit input, audit report, score, research summary, status,
  the benchmark configuration, the case matrix, and the aggregate report;
* the only differences are `runtime_metadata.json`, which the schema makes
  runtime-specific by design, and `index.json`, which embeds that file's hash.

The scientific result is therefore provably unchanged by the correction.

## Configuration

4 fault profiles × 3 severities × 10 reserved final seeds = **120 held-out
fault cases**, plus **4 clean controls** (one per fault profile) = **124 cases**.

The clean-control policy is one control per fault profile. This is derived from
the current contract, not from the historical target: `BenchmarkProfile.clean_control`
is a single optional `BenchmarkCleanControl`, so the Milestone 8 schema can
express at most one control per profile. The historical 0.1.0 documentation
implies twelve controls (132 cases); reproducing that count would require
widening a completed schema for presentation reasons, which this milestone must
not do. See ADR-009.

Per-profile fixtures, point-in-time horizons, research contexts, and detector
configuration are the already-reviewed smoke configuration reused verbatim.
Only the severity and seed dimensions were expanded. All inputs are the offline
reviewed synthetic fixtures; no live SEC call was made.

## Overall result

| Metric | Exact saved value |
| --- | --- |
| Configured cases | 124 |
| Successful | 94 |
| Failed | 30 |
| Incomplete | 0 |
| Injected fault units | 130 |
| Findings | 208 |
| True-positive faults | 130 |
| False-negative faults | 0 |
| True-positive findings | 130 |
| False-positive findings | 78 |
| Eligible clean denominator | 1070 |
| **Precision** | `0.625` |
| **Recall** | `1` |
| **F1** | `0.76923076923076923076923076923076923076923076923077` |
| **False-positive rate** | `0.072897196261682242990654205607476635514018691588785` |
| Research output changed | 90 of 90 |
| Exact replay restored | 90 of 90 |

## By fault profile

| Profile | Cases | OK | Failed | Faults | Findings | TP | FP | Denom | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `duplicate_observation` | 31 | 31 | 0 | 70 | 101 | 70 | 31 | 651 | `0.69306930693069306930693069306930693069306930693069` | `1` |
| `unit_drift` | 31 | 31 | 0 | 30 | 45 | 30 | 15 | 155 | `0.66666666666666666666666666666666666666666666666667` | `1` |
| `lookahead_timestamp` | 31 | 21 | 10 | 20 | 41 | 20 | 21 | 253 | `0.4878048780487804878048780487804878048780487804878` | `1` |
| `revision_overwrite` | 31 | 11 | 20 | 10 | 21 | 10 | 11 | 11 | `0.47619047619047619047619047619047619047619047619048` | `1` |

False-positive rate by profile: Duplicate `0.047619047619047619047619047619047619047619047619048`,
Unit Drift `0.096774193548387096774193548387096774193548387096774`,
Look-Ahead `0.08300395256916996047430830039525691699604743083004`,
Revision Overwrite `1`.

## By severity

| Severity | Cases | OK | Failed | Faults | Findings | TP | FP | Denom | Precision | Recall |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `high` | 40 | 20 | 20 | 50 | 65 | 50 | 15 | 260 | `0.76923076923076923076923076923076923076923076923077` | `1` |
| `medium` | 43 | 33 | 10 | 40 | 67 | 40 | 27 | 419 | `0.59701492537313432835820895522388059701492537313433` | `1` |
| `low` | 41 | 41 | 0 | 40 | 76 | 40 | 36 | 391 | `0.52631578947368421052631578947368421052631578947368` | `1` |

## By final seed

Every one of the ten reserved seeds `1000` to `1009` ran. Nine of the ten produced
12 configured cases; seed `1000` produced 16, because the four clean controls
are pinned to the lowest reserved seed. Recall is `1` at every seed. Per-seed
precision ranges from `0.52` (seed `1000`) to
`0.68421052631578947368421052631578947368421052631579` (seeds `1001`, `1002`,
`1007`, `1008`, `1009`), with seeds `1003` to `1006` at
`0.59090909090909090909090909090909090909090909090909`. Full per-seed counts are
in `evidence/v0_1_release/aggregate_report.json` under `by_seed`.

## Honest failure analysis

### The 30 failed cases are structural ineligibility, not crashes

All 30 failures are `stage=injection`, `category=no_eligible_targets`,
`code=no_eligible_targets`, in exactly three profile/severity cells, ten seeds
each:

| Cell | Why no target exists |
| --- | --- |
| `lookahead_timestamp` / `high` | requires a 30-day natural filing lag; the reviewed fixture has none |
| `revision_overwrite` / `medium` | requires a 5% relative revision; the fixture's only adjacent history revises by 2% |
| `revision_overwrite` / `high` | requires a 20% relative revision; same 2% history |

These are frozen fault-family thresholds meeting a small reviewed synthetic
fixture. They were **not** configured away: the cells stay in the release
matrix and their failures stay visible in the matrix, the status files, and the
aggregate. Relaxing a threshold or shopping for a fixture horizon to make them
pass would have been exactly the score tuning this milestone forbids.

### Best and worst

* **Best precision:** `duplicate_observation` (`0.693…`). **Worst:**
  `revision_overwrite` (`0.476…`).
* **Recall is `1` everywhere**, at every profile, every severity, and every seed. There
  is not a single false negative in the held-out matrix. This is a real result,
  but read it with the fixture's small size in mind, not as evidence of general
  detector sensitivity.
* **Severity effect:** precision rises monotonically with severity
  (`0.526` low → `0.597` medium → `0.769` high). Larger corruptions are easier to
  separate from the fixed background of cross-detector findings; the background
  count is roughly constant while true positives grow.

### Where the false positives come from

All 78 false positives are **cross-detector findings under strict primary-label
scoring**, not detector malfunctions. A case is scored only against its own
fault family, but all four detectors run on every case and every finding is
retained. Public findings by rule across the matrix: `occurrence.exact_duplicate`
133, `value.scale_discontinuity` 45,
`temporal.period_end_available_before_filing` 20,
`revision.later_vintage_in_earlier_state` 10.

The dominant contributor is the reviewed fixture's documented natural
independent-occurrence pair, which the Duplicate detector correctly reports on
every reviewed-fixture case. ADR-004 already records that as legitimate
behaviour on clean data. A Revision Overwrite corruption also produces a valid
Duplicate signal, which strict primary scoring counts against Revision
Overwrite.

`revision_overwrite`'s false-positive rate of exactly `1` deserves its caveat:
its eligible-clean denominator is **11** across the whole matrix, because the
reviewed fixture contains a single source-supported adjacent revision history.
A rate computed over 11 units is not comparable to one computed over 651. The
number is reported as saved rather than suppressed or footnoted away.

### Research impact and replay

All 90 successful fault cases changed their controlled research output (90/90),
and manifest-assisted exact replay restored the clean result in all 90 (90/90).
No fault family produced a legitimate zero research impact in this matrix. The
30 ineligible cases have no research summary because nothing was injected.

### Clean-control behaviour

| Control | Findings | FP | Denominator | FPR |
| --- | --- | --- | --- | --- |
| `unit_drift` | 0 | 0 | 5 | `0` |
| `lookahead_timestamp` | 1 | 1 | 13 | `0.076923076923076923076923076923076923076923076923077` |
| `duplicate_observation` | 1 | 1 | 21 | `0.047619047619047619047619047619047619047619047619048` |
| `revision_overwrite` | 1 | 1 | 1 | `1` |

Every control finding is the same documented natural exact-duplicate pair. No
control had a fault injected (`injected_faults=0` for all four), and the
controls are scored with the same `DetectionMetrics` contract as fault cases.

## What these numbers are not

They are measured on a 26-record reviewed synthetic fixture plus a
five-observation Unit Drift series, across four narrow fault subtypes, offline.
They are not a claim of production readiness, general financial-data
certification, automated repair, loss prevention, trading alpha, universal SEC
coverage, statement reconstruction, universal restatement detection, or
vendor-wide reliability. See [LIMITATIONS.md](LIMITATIONS.md).

## Reproducing this

```bash
uv run python scripts/release_freeze.py --check
uv run python scripts/run_release_benchmark.py --output release_evidence/final
uv run python scripts/verify_release_evidence.py \
    --source release_evidence/final \
    --public-only release_evidence/public_only \
    --html release_evidence/public_only/summary.html
```

The freeze check must pass before the benchmark will dispatch a single case.
