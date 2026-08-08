# Public-only presentation: dashboard and HTML summary

The presentation layer turns saved **public** benchmark artifacts into something
a human can read. It is deliberately incapable of doing anything else: it runs
no science, writes no artifact, and cannot address the private tree.

The decisions behind this document are frozen in ADR-008 (`docs/DECISIONS.md`).

## Architecture

```text
public/ artifact tree
        |
        v
public_artifact_reader   strict trust boundary: role allowlist, path security,
        |                schema validation, SHA-256 verification
        v
presentation             one immutable shared model (Decimal-exact, null-preserving)
        |
        +---------------------------+
        v                           v
html_summary                 dashboard/app.py
(deterministic offline HTML)  (read-only Streamlit)
```

Both surfaces consume the **same** model. Neither reads artifacts on its own,
and neither reimplements a benchmark rule. There is exactly one place where
"what a saved benchmark means to a human" is decided.

| Module | Role |
| --- | --- |
| `src/quantcheck/public_artifact_reader.py` | Strict public-only reader |
| `src/quantcheck/presentation.py` | The shared immutable model |
| `src/quantcheck/html_summary.py` | Deterministic self-contained HTML |
| `dashboard/app.py` | Standalone read-only Streamlit app |
| `scripts/render_html_summary.py` | Thin HTML render entry point |

## Artifact-root expectations

Both surfaces accept either form, matching `aggregate_from_public_root`:

- a benchmark **output root** containing `public/` (and possibly `private/`); or
- a copied-out **public tree** itself.

The tree must contain `benchmark_config.json`, `case_matrix.json`,
`aggregate_report.json`, and `index.json`. `runtime_metadata.json` is read if
present. Per-case artifacts live under `cases/<benchmark_case_id>/`.

## Commands

Neither surface is a `quantcheck` CLI command. The contracted root command
surface stays exactly six (`docs/CLI_CONTRACT.md`), and no dashboard, HTML,
aggregate-rebuild, or force-overwrite command was added.

Produce artifacts with the existing CLI:

```bash
uv run quantcheck benchmark smoke --output artifacts/smoke
```

Launch the read-only dashboard:

```bash
uv run --group dashboard streamlit run dashboard/app.py -- --artifacts artifacts/smoke
```

The `--` separator is required: everything after it goes to the app rather than
to Streamlit. `--artifacts` is mandatory; without it the app reports a sanitized
error instead of guessing a root.

Render the deterministic HTML summary:

```bash
uv run python scripts/render_html_summary.py artifacts/smoke --output artifacts/smoke/summary.html
```

Exit codes: `0` success, `2` the public artifacts were rejected, `3` the summary
could not be written.

## The reader's trust boundary

For every artifact presentation uses, the reader:

- validates the relative path;
- reads only from the selected public root;
- validates the expected Pydantic schema;
- verifies the recorded SHA-256 content hash;
- validates benchmark-identity and case-identity relationships; and
- rejects unknown artifact roles rather than guessing.

### Path security

These are rejected, never repaired into something safe-looking:

| Rejected | Why it cannot appear |
| --- | --- |
| `/etc/passwd` | absolute POSIX path |
| `C:\Windows\...`, `C:/Windows` | Windows/drive-letter path |
| `..`, `cases/../../private/x.json` | traversal |
| `private/manifest.json` | addresses private storage |
| `cases/<other-case>/score.json` | cross-case reference |
| a symlink pointing outside the root | resolves outside the public root |
| a symlink into `private/` | resolves outside the public root |
| an unknown `kind` in the index | outside the role allowlist |

The grammar (`PUBLIC_RELATIVE_PATH_PATTERN`) makes most of these
*unrepresentable* rather than merely filtered, because every path segment must
start with an alphanumeric character. Symlinks are caught by resolution.

### Strict rejection vs. preserved incompleteness

The reader distinguishes two kinds of problem:

- **Tree-level integrity** — a missing or malformed root artifact, a bad index
  hash, a missing indexed artifact, an unknown or mispathed role, a cross-case
  reference, a benchmark-identity disagreement, a status naming a different
  case, or an `aggregate_report.json` whose status counts contradict the saved
  case statuses. These raise `PublicArtifactError`.
- **Case-level evidence** — a case whose *success claim* is not substantiated
  becomes `incomplete`. This is exactly what `benchmark_aggregate` already does
  independently, so the reader can never contradict the saved aggregate about a
  case's outcome.

## Privacy guarantees

The presentation layer never needs, and never opens, a manifest, an original or
pre-corruption value, a clean/corrupted/repaired snapshot, a private research
value or delta, an injector selection digest or target rank, an expected finding
count, or a private failure diagnostic. Deleting the entire `private/` tree
changes no result.

The model and both surfaces contain no manifest, hidden record role,
source-to-created relationship, target record id, private exception message or
traceback, filesystem path, output root, temporary directory, home path, or
credential.

This is structural, not aspirational: the presentation code's transitive
`quantcheck` import closure is exactly `benchmark_contract`, `benchmark_store`,
`hashing`, `json_types`, `schemas`, `serialization`, and `unit_drift_math`. No
manifest, injector, detector, scorer, replay, or research module is reachable,
and that closure is pinned by a test.

Two documented, deliberate non-secrets:

- A `duplicate_observation` case's *original* record identity legitimately
  appears in public detector evidence, because its injector **adds** a copy
  rather than replacing the original — the original is one half of the real
  duplicate pair (same rule as `docs/CLI_CONTRACT.md`).
- A clean record targeted in one case is ordinary public data in a clean control
  and in another seed's case, where it was never a target. A hidden identity is
  private *relative to its own case*, and that is how it is tested.

## Determinism guarantees

Given logically identical public artifacts, `render_html_summary` produces
byte-identical output across destination directories, output roots, processes,
working directories, and `PYTHONHASHSEED` values. Ordering comes from the saved
artifacts, which the benchmark already sorted; nothing consults the clock, the
environment, the filesystem, or a random source.

The HTML contains no render timestamp, no random identifier, and no
environment-specific path, so re-rendering an unchanged benchmark is a no-op.

## Output behaviour

`write_html_summary` uses the repository's existing persistence conventions:

- identical existing bytes are **reused untouched**;
- conflicting existing bytes raise `ArtifactIntegrityError` and are **never**
  overwritten (there is no force option anywhere in this repository);
- a non-`.html` destination, a directory in place of the file, or an impossible
  destination raises `HtmlSummaryError`; and
- a failed write leaves no partial or temporary file behind.

## Null-metric display policy

An undefined metric stays `None` in the model — never `0`, `NaN`, `""`, or the
string `"n/a"`. Only the rendering layer chooses text for it: both surfaces show
`n/a`. A metric is genuinely undefined when its population does not support it
(for example a false-positive rate with no eligible clean denominator, or recall
with nothing injected); it is not a failure and not a zero.

## Failed and incomplete cases

Failed cases, incomplete cases, and clean controls are all preserved and shown.

- A **failed** case shows its stage, category, error code, and the benchmark's
  own fixed public sentence. No exception message or stack trace is public.
- An **incomplete** case is one with no terminal status artifact, or whose
  success claim its own saved evidence does not support. It is displayed as
  incomplete and is **never** inferred to have succeeded or silently dropped.
- **Clean controls** appear with their metrics and no injected faults.
- No metric is fabricated for a case without a valid score artifact.

Every dashboard filter defaults to showing everything. A default that hid
failures, incomplete cases, clean controls, or weak results would make a broken
benchmark look healthy.

## Offline behaviour

Both surfaces are fully offline. The HTML embeds its CSS, uses no JavaScript, no
CDN, and no remote resource of any kind. The dashboard makes no network request,
uses only Streamlit-native components, and adds no analytics, tracking, or
authentication; `.streamlit/config.toml` disables Streamlit usage telemetry for
repository-local runs.

## Dependency

Streamlit is a **`dashboard` dependency group**, not a runtime dependency
(`streamlit>=1.40,<2`, locked at `1.61.1`). `dashboard/` is excluded from the
wheel and sdist under the same rule already documented for `scripts/`, so a
runtime dependency would burden every consumer of the distribution with ~35
packages for code the distribution does not ship. A clean wheel install has no
Streamlit at all, and the reader, model, and HTML renderer still work.

Ordinary `import quantcheck` never imports Streamlit, and the core package is
usable without importing any dashboard code.

## Known limitations

- The dashboard is a local, read-only, single-user Streamlit app. There is no
  authentication, no accounts, no web backend, no hosted deployment, and no
  browser-level automation beyond Streamlit's official `AppTest` and a local
  headless health startup.
- There is no general artifact browser, no manifest browsing, and no
  private-value browsing. Presentation shows what the saved public artifacts
  contain and nothing else.
- The reader deliberately raises on a status file that exists but does not
  validate, where `benchmark_aggregate` would record the case as incomplete.
  Aggregation must never crash mid-run; the reader is a verification tool and is
  loud instead. The two agree on every non-tampered tree.
- Case filters use only the public dimensions the saved artifacts already carry
  (fault profile, severity, status, seed class). No new scientific category was
  invented for the UI.
- No benchmark truth is committed to the repository for the UI to display; both
  surfaces require artifacts you produced yourself.
- No final held-out benchmark, release evidence, or `CHECKSUMS.md` exists. Seeds
  `1000–1009` remain prohibited and no historical 0.1.0 metric or hash is
  reproduced or claimed.
