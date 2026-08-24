# QuantCheck limitations

This is the authoritative public limitations list; current release posture is
summarized in [STATUS.md](STATUS.md). Anything here is stated for users of the
release.

The immutable v0.1 limitations below remain historical truth. The current
`0.2.0.dev0` worktree adds synthetic development/validation evidence,
production-input and self-hosted engineering, but still has no completed
design-partner pilot, customer adjudication, production deployment, signed
candidate attestation, or held-out v0.2 result.

## Scientific scope

* **Four narrow fault subtypes only.** Look-Ahead `period_end_substitution`,
  Unit Drift `value_scaled_unit_unchanged`, Duplicate Observations
  `exact_occurrence_copy`, Revision Overwrite `later_vintage_in_earlier_state`.
  Missing-observation faults and entity swaps are explicitly out of scope for
  v0.1.
* **Synthetic reviewed fixtures.** The final benchmark runs on a 26-record
  reviewed synthetic fixture and a five-observation Unit Drift series. Results
  characterise this framework on this data, not real vendor feeds.
* **Small denominators.** `revision_overwrite`'s eligible-clean denominator over
  the whole 124-case matrix is 11, because the reviewed fixture contains one
  source-supported adjacent revision history. Its false-positive rate of `1` is
  arithmetically correct and statistically thin. Compare rates only alongside
  their denominators.
* **Three profile/severity cells have no eligible target** on this fixture and
  fail every seed with `no_eligible_targets`: Look-Ahead at `high` (needs a
  30-day filing lag), Revision Overwrite at `medium` and `high` (need 5% and 20%
  relative revisions against a 2% history). These are kept visible rather than
  configured away.
* **Recall of `1`** in the held-out matrix is a real measurement on this
  fixture, not a general sensitivity claim.
* **Unit Drift uses immediate local Decimal ratios only.** Simultaneously scaled
  adjacent observations can mask each other, and a one-neighbour endpoint can
  attribute a discontinuity to the clean neighbour.
* **Duplicate Observations is exact-copy only.** Not fuzzy deduplication,
  near-duplicate detection, amended-filing interpretation, restatement
  detection, or entity resolution. It cannot infer which member of a duplicate
  group is the bad row; that is private manifest truth.
* **Revision Overwrite requires an explicit declared lineage marker.** It cannot
  infer that two records are revisions from matching values alone, interpret
  amendments, or reconstruct statements.
* **Controlled research comparisons, not backtests.** `availability_count_v0_1`,
  `aggregate_value_v0_1`, `record_count_v0_1`, and `growth_ranking_v0_1` are
  narrow sensitivity demonstrations. They are not returns, alpha, Sharpe
  ratios, portfolio results, or financial-loss estimates.
* **Exact replay is manifest-assisted answer-key evidence.** It does not
  establish automatic or detector-only repair. Public findings intentionally
  cannot reconstruct the hidden true record.
* **Cross-detector findings count against strict primary precision.** All four
  detectors run on every case and every finding is retained, but a case is
  scored only against its own family. This depresses precision by design and is
  not tuned away.

## Data source scope

* **SEC adapter is one CIK at a time**, one Company Facts endpoint, entity-wide
  facts with no segments, explicit concept/unit/form/date allowlists, and
  `available_on == filed_on`. No statement reconstruction, scale or currency
  normalisation, concept harmonisation, filing-HTML parsing, cache expiry,
  parallel download, or intraday semantics.
* **The checked-in SEC fixture is a curated field-shape excerpt**, not a saved
  live response. Live download behaviour has only been exercised through HTTPX
  mock transports. No live-network attestation is made, and current SEC guidance
  must be rechecked before any live run.
* **Day-level availability semantics** only. No intraday claims.
* **No Unicode normalisation.** Canonical strings compare code point for code
  point, so NFC and NFD spellings are distinct logical values.

## Implementation scope

* **Sequential and local by design.** No parallelism, database, cloud
  persistence, scheduler, or hosted deployment.
* **No force-overwrite path anywhere**, including through the CLI. One output
  root holds exactly one logical benchmark.
* **The dashboard is local, read-only, and single-user.** No authentication,
  accounts, web backend, general artifact browser, manifest browsing, or
  private-value browsing.
* **`dashboard/` and `scripts/` ship in neither the wheel nor the sdist**, so an
  installed distribution provides the reader, presentation model, and HTML
  renderer but not the dashboard or Streamlit.
* **No benchmark truth is committed to the repository.** Both presentation
  surfaces require artifacts produced locally.
* **Runtime metadata is deliberately not reproducible.** `runtime_metadata.json`
  records the wall clock, platform, and interpreter version, so it differs
  between runs, and `index.json` differs with it because it embeds its hash.
  Every other logical artifact is byte-identical across runs, roots, and hash
  seeds.
* **No historical 0.1.0 metric, hash, identifier, or test count is reproduced or
  claimed.** The lost `docs/SERIALIZATION_AND_HASHING.md` was reconstructed, not
  recovered, and the reviewed fixture is newly authored.

## Release and external gates

* **The current beta candidate is not a published release.** Its local SPDX
  SBOM and in-toto/SLSA provenance statement are machine-readable and
  hash-bound to package artifacts, but the provenance uses an untrusted local
  builder identity and is unsigned. The cited candidate commit `3b47da9` has
  green Security workflow run `32693592309`, including identical
  digest-addressed OCI manifest/config/layer identity and dependency, secret,
  image, and SBOM gates. A published image digest and trusted CI attestations
  remain absent and must be verified before deployment-grade release claims.
* **The design-partner workflow is a protocol, not completed evidence.** No
  customer input, disposition, confirmed research impact, pilot metric, or
  testimonial is present. Synthetic development/validation performance cannot
  fill that gap.

* **GitHub Actions has run once, on the release source tree.** Run
  `31293937904` executed every workflow step against commit
  `5e02c9f84dafbe49f1f57c30d776d3a46576a9fe` and succeeded. Only Ubuntu
  `x86_64` is covered; the release was produced on macOS `arm64`.
* **Published only as source and a GitHub release.** The `v0.1.0` tag has a
  GitHub release with the wheel and sdist attached. There is no package-index
  upload, so `pip install quantcheck` does not resolve; install from the
  attached wheel or from source. No hosted dashboard, public URL, DOI,
  recorded demonstration video, or external attestation exists.
