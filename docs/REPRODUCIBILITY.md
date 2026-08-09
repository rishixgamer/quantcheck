# Reproducibility guide

## What is guaranteed to be identical

Given the same clean snapshot, configuration, seed, and code version:

* every logical identifier (`bench_`, `bcase_`, `agg_`, `rec_`, `snap_`, …);
* every canonical public and private artifact's bytes;
* the rebuilt aggregate report;
* the presentation model's canonical bytes;
* the rendered HTML summary's bytes.

Independent of: output root, working directory, temporary directory, wall
clock, username, hostname, environment ordering, mapping insertion order,
configuration list ordering, and `PYTHONHASHSEED`.

## What is deliberately *not* identical

`runtime_metadata.json` records the wall clock, platform string, and
interpreter version. It is runtime-specific **by schema design** and never
enters any logical identity. `index.json` differs with it, because the index
embeds every artifact's content hash including that one.

Claiming these are byte-identical would be false, so this guide states plainly
that they are not, and every comparison below excludes them by name rather than
by hand-waving.

## Verified for the 0.1.0 release

All checks below were run against the released public-only evidence.

| Check | Result |
| --- | --- |
| `PYTHONHASHSEED=0` / `1` / `987654`, fresh subprocesses | identical model, HTML, and aggregate hashes |
| Canonical reload of all 595 public artifacts | every artifact round-trips byte-identically |
| HTML rendered to two different destinations | identical, SHA-256 `2ba3c7746e18df90699a99ddd4ce0e0dc100bb6fa2b0ead7f88e4887e52ac795` |
| Conflicting bytes at an existing HTML destination | rejected, no overwrite |
| Public-only aggregate rebuild vs saved aggregate | byte-identical |
| Resume of an identical successful run | 94 successful cases reused, 0 dispatched, same `agg_571aae0b7c60a4a5` |
| Independent output root | identical logical bytes; only runtime metadata and index differ |
| Normalised list reordering | identical `benchmark_id` |
| Candidate 1 vs candidate 2 public trees | 593 of 594 indexed artifacts byte-identical |

Presentation model SHA-256:
`2c2788ca2673f67f807c89760ddbc030ddde13b8395b65be9300af6566ef7f68`.

## Reproducing the release from a clean checkout

```bash
uv sync --frozen --all-groups

# 1. Confirm the frozen release candidate still matches this working tree.
#    This must pass before any reserved seed will run.
uv run python scripts/release_freeze.py --check

# 2. Run the held-out matrix. Reserved seeds 1000-1009 execute only here.
uv run python scripts/run_release_benchmark.py --output release_evidence/final

# 3. Build the public-only package and verify it with private data absent.
uv run python scripts/verify_release_evidence.py \
    --source release_evidence/final \
    --public-only release_evidence/public_only \
    --html release_evidence/public_only/summary.html

# 4. Confirm the committed release surface is unmodified.
uv run python scripts/release_checksums.py --check
```

## Reproducing the offline smoke benchmark

```bash
uv run quantcheck benchmark smoke --output /tmp/qc-smoke
uv run python scripts/render_html_summary.py /tmp/qc-smoke \
    --output /tmp/qc-smoke/summary.html
```

12 cases, entirely offline, no network.

## Checking determinism yourself

```bash
# Same configuration, two roots, compare logical bytes.
uv run quantcheck benchmark smoke --output /tmp/qc-a
uv run quantcheck benchmark smoke --output /tmp/qc-b
diff -r /tmp/qc-a/public /tmp/qc-b/public   # only runtime_metadata.json and index.json differ

# Across hash seeds.
PYTHONHASHSEED=1      uv run pytest -k determinism
PYTHONHASHSEED=987654 uv run pytest -k determinism
```

## Fixture integrity

```bash
uv run python scripts/generate_reviewed_fixture.py --check
uv run python scripts/generate_reviewed_sec_fixture.py --check
```

Both regenerate their fixture from code and compare against the checked-in
bytes. The reviewed fixture bytes are also reproducible from an installed wheel
via `quantcheck.fixtures.canonical_reviewed_fixture_bytes()`.

## Environment

Python 3.12 (`requires-python = ">=3.12,<3.13"`), `uv` 0.12.2, Hatchling. The
lockfile is authoritative; `uv lock --check` verifies it is current. The release
was produced on macOS (Darwin 25.5.0, arm64); no platform-specific behaviour is
relied on, but no other platform has been exercised.
