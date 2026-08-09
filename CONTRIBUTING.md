# Contributing to QuantCheck

## Setup

```bash
uv sync --all-groups
uv run pytest
```

Python 3.12 only (`requires-python = ">=3.12,<3.13"`). `uv` manages the
environment; the lockfile is authoritative.

## Quality gates

Every one of these must exit 0 before a change is complete:

```bash
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
MYPYPATH=src uv run mypy --explicit-package-bases dashboard scripts
uv run pytest
uv lock --check
uv run quantcheck --help
uv build --offline
git diff --check
uv run python scripts/generate_reviewed_fixture.py --check
uv run python scripts/generate_reviewed_sec_fixture.py --check
uv run python scripts/release_checksums.py --check
```

MyPy runs in strict mode. Ruff enforces `E`, `F`, `I`, `UP`, `B`, `SIM` at a
100-column line length.

## Non-negotiable invariants

These are the rules the design exists to protect. A change that breaks one is
wrong even if the tests pass.

1. Detectors never receive manifests, pre-corruption values, injected-row flags,
   or injector-only metadata.
2. Detectors receive a sanitized `AuditInputSnapshot`, not unrestricted
   canonical records.
3. The same clean snapshot, configuration, seed, and code version produce the
   same logical corruption and the same artifact bytes.
4. Caller-owned inputs are never modified in place.
5. Period, filing, availability, as-of, and runtime dates stay distinct.
6. Financial values use `Decimal`; public JSON encodes them as canonical
   strings. Nothing passes through binary float.
7. Identifiers and hashes never depend on row position or `PYTHONHASHSEED`.
8. Every detector is evaluated against clean controls.
9. Scoring reads the private manifest only after the audit report is finalized.
10. Ordinary tests make no live network requests.
11. Unsupported source semantics are rejected or explicitly recorded, never
    guessed.
12. Synthetic, controlled, and real-data claims stay clearly distinguished.
13. Historical metrics and hashes are never copied into new output unless
    reproduced by the current implementation.

## Reserved final seeds

Seeds `1000`–`1009` are held-out release evidence. **Do not use them for
development, debugging, or new tests.** They are executable only through
`quantcheck.release_run` under a verified frozen release candidate. Adding any
flag, parameter, environment variable, or helper that widens that access is a
change to the project's core claim and will be rejected. See
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## Scope discipline

Not accepted during v0.1: new fault families, missing-observation or entity-swap
faults, machine learning, additional data vendors, authentication, accounts,
databases, hosted infrastructure, parallel or distributed execution, a second
frontend, new root CLI commands, a general `--force`, unrestricted held-out
flags, automatic detector-only remediation, or any alpha/Sharpe/loss-prevention
claim the research contracts do not support.

## Scientific changes

Detector thresholds, injector target rules, target fractions, matching rules,
false-positive denominators, severity definitions, research formulas, fault
selection, and case selection are **frozen** by the release candidate.

Changing any of them:

* invalidates the current release candidate and requires a new freeze;
* requires an ADR in `docs/DECISIONS.md` stating what changed and why;
* must never be motivated by a benchmark score. A poor result is not a defect.
  Honest false positives and false negatives are evidence and must be preserved.

## Tests

Add positive, negative, edge, and regression tests. Do not weaken or delete an
existing test to make a change pass — if a test's assertion has genuinely moved,
move it to where the behaviour now lives and say why in the test's docstring.

Privacy scans must never pass vacuously: if you assert something is absent from
public bytes, also assert it is present in the private tree.

## Handoff

`IMPLEMENT.md` is the operational source of truth between sessions. Record the
milestone completed, files changed, commands run with exact outcomes, decisions
added, known limitations, and the exact next task.
