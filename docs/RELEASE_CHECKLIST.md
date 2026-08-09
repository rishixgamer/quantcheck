# QuantCheck 0.1.0 release checklist

Status recorded against release candidate `relc_2c6e945a71b85b39`.

## Locally controllable gates

| # | Gate | Status |
| --- | --- | --- |
| 1 | Full validation rehearsal completed **before** any final seed | PASS — 244-case release-shaped rehearsal on development seeds `0-9` and validation seeds `100-109` |
| 2 | Release candidate frozen **before** the first final seed | PASS — freeze precedes every dispatch; verification runs before the run loop |
| 3 | Freeze covers the scientific configuration | PASS — 4 fault specs, 12 severity definitions, detector versions/config/threshold, matching rules, denominator rules, replay method, both fixture hashes, 67 frozen files |
| 4 | Ordinary interfaces reject final seeds | PASS — config building, expansion, dispatcher, `run_benchmark`, all three saved-stage functions, all CLI commands |
| 5 | Release-only authorization is narrow and tested | PASS — complete-partition-only, scoped, non-nesting, non-anonymous, stdlib-only, statically confined to two modules |
| 6 | Frozen inputs verified before final dispatch | PASS — a drifted input refuses the run with no output tree created |
| 7 | 120 held-out fault cases executed | PASS |
| 8 | Required clean controls executed | PASS — 4, one per fault profile (ADR-009) |
| 9 | Failures and incompletes honestly preserved | PASS — 30 failed, 0 incomplete, all visible in matrix, statuses, and aggregate |
| 10 | Final aggregate generated from saved evidence | PASS — `agg_571aae0b7c60a4a5` |
| 11 | Public-only aggregate reconstruction succeeds | PASS — byte-identical to saved |
| 12 | Public presentation works with `private/` absent | PASS — reader, model, HTML, AppTest, headless health |
| 13 | Metrics come from saved artifacts | PASS |
| 14 | README / results / release notes / HTML / dashboard agree | PASS |
| 15 | Privacy scan passes | PASS — no private key, local path, secret, traceback, or symlink |
| 16 | Determinism and reproducibility checks pass | PASS — see REPRODUCIBILITY.md |
| 17 | Package build passes | PASS — wheel and sdist, offline |
| 18 | Package contents clean | PASS — no artifacts, manifests, caches, reference material, or real paths |
| 19 | Fresh wheel installation works | PASS — Python 3.12 clean venv, CLI, smoke, HTML, no Streamlit |
| 20 | Prior completed behaviour remains green | PASS — full suite |
| 21 | `IMPLEMENT.md` updated factually | PASS |
| 22 | Release checksums current | PASS — `scripts/release_checksums.py --check` |

## External gates — NOT satisfied, and not claimed

These cannot be performed from this environment. None is simulated, and no
evidence for any of them is fabricated.

| Gate | Status |
| --- | --- |
| GitHub Actions CI | **NOT RUN.** The workflow was validated only by running its constituent commands locally. |
| Git tag `v0.1.0` | **NOT CREATED.** No tag exists. |
| GitHub release | **NOT CREATED.** |
| PyPI / registry publication | **NOT PUBLISHED.** No upload was attempted or authorized. |
| Hosted dashboard / public URL | **DOES NOT EXIST.** |
| DOI | **DOES NOT EXIST.** |
| Recorded demonstration video | **NOT RECORDED.** A storyboard is below; no recording was made. |
| Third-party attestation / security audit | **NONE.** |
| Cross-platform verification (Linux, Windows) | **NOT PERFORMED.** Released from macOS arm64 only. |

## Commit and publication

Nothing has been committed, staged, tagged, pushed, or published. The working
tree holds the release for review. `git diff --check` is clean and no generated
artifact tree, cache, or secret is staged — `release_evidence/` is gitignored.

## Three-minute demonstration storyboard

Written for a future recording. **No video has been recorded.**

| Time | Beat |
| --- | --- |
| 0:00–0:20 | The problem: a dataset that leaks future information, corrupts scale, double-counts, or substitutes a later revision can make research look convincing. |
| 0:20–0:45 | `uv run quantcheck benchmark smoke --output /tmp/qc` — 12 offline cases, four fault families, four detectors on every case. |
| 0:45–1:15 | Show the artifact tree: `public/` vs `private/`. Open `manifest.json` and note that no detector ever sees it. |
| 1:15–1:45 | `scripts/render_html_summary.py` on the public tree only; open the HTML. Delete `private/` and render again — identical bytes. |
| 1:45–2:20 | The held-out release: freeze record, `--check`, then 124 cases at reserved seeds `1000-1009`. Precision `0.625`, recall `1`. |
| 2:20–2:50 | The honest part: 30 cases failed with `no_eligible_targets`, and all 78 false positives are cross-detector findings under strict primary scoring. Neither was tuned away. |
| 2:50–3:00 | Limitations: synthetic fixture, four narrow subtypes, controlled comparisons — not a backtest, not production certification. |
