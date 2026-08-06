# Rebuild QuantCheck — Recovery Milestone 0: Repository Bootstrap

You are in a new, mostly empty QuantCheck repository created after the original source folder was lost.

Historical documents under `reference/` describe the intended project and a prior 0.1.0 implementation. They are specifications and historical evidence only. Do not assume any historical code, test count, benchmark metric, artifact, or hash currently exists.

## Mandatory reading

Before editing:

1. Read `AGENTS.md`.
2. Read `IMPLEMENT.md`.
3. Read `docs/AUTHORITY_AND_READING_ORDER.md`.
4. Read `PROJECT_SCOPE.md` and `MVP_ACCEPTANCE_CRITERIA.md`.
5. Read only the toolchain/repository-bootstrap portions of:
   - `reference/AGENTS_ORIGINAL.md`
   - `reference/IMPLEMENT_RELEASE_0.1.0.md`
   - `reference/DEVELOPMENT_MILESTONES.txt`
6. Inspect the actual repository tree and Git status.

Then restate:

- current factual repository state;
- applicable fixed choices;
- Milestone 0 acceptance criteria;
- smallest proposed diff;
- tests and commands you will run.

Do not merely plan. Implement Milestone 0 after the inspection.

## Scope

Create only the reproducible repository foundation:

- Python `>=3.12,<3.13`
- package name `quantcheck`
- `src/quantcheck/` layout
- `uv` project and lockfile
- Hatchling build backend
- Ruff linting and formatting
- MyPy strict or near-strict configuration
- pytest
- Hypothesis plugin available to tests
- minimal package metadata
- installed `quantcheck` console entry point with stable `--help`
- minimal typed implementation with no financial behavior
- baseline unit/smoke tests
- GitHub Actions workflow that runs the baseline quality gates
- `.gitignore`
- concise developer setup instructions

Use the minimum dependencies needed for this milestone. Do not add HTTPX, pandas, PyArrow, or Streamlit yet. Typer may be added now only if it is the smallest clean way to satisfy the installed help-only CLI entry point; otherwise implement a standard-library entry point and record the temporary choice without creating a competing long-term CLI architecture.

## Do not implement

- financial schemas
- canonical financial serialization beyond what bootstrap itself requires
- point-in-time logic
- fixtures
- SEC access
- fault injectors
- detectors
- manifests
- scoring
- benchmark artifacts
- dashboard or HTML
- historical benchmark values or hashes
- placeholder scientific results

Do not create fake modules containing `pass`, fake implementations, or TODO claims that imply completed behavior.

## Required commands

Run the repository's exact equivalents of:

```bash
uv sync --all-groups
uv sync --frozen --all-groups
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
uv lock --check
uv run quantcheck --help
uv build --offline
```

If the local environment requires a writable `UV_CACHE_DIR`, use one and record it as an environment workaround rather than modifying project semantics.

## Acceptance criteria

Milestone 0 passes only when:

1. A clean environment can install from the lockfile.
2. The package imports successfully.
3. The installed `quantcheck --help` command exits successfully.
4. Lint, format check, type check, tests, and lock verification pass.
5. Wheel and sdist build locally.
6. No financial behavior is falsely claimed or stubbed.
7. CI runs the same baseline commands.
8. `IMPLEMENT.md` is updated with factual files changed, commands and outcomes, decisions, limitations, and exact next task.

The exact next task should be the canonical schemas/serialization/hashing milestone, not another bootstrap task.

## Final response

Report:

- implementation status;
- files changed and purpose;
- dependencies selected;
- tests added;
- exact commands and outcomes;
- any environmental retries;
- decisions made;
- known limitations;
- `IMPLEMENT.md` update;
- exact next task.

Do not claim historical 0.1.0 completion.
