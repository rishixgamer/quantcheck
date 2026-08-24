# QuantCheck status

Updated 2026-08-24 for the curated public tree.

## Current classification

QuantCheck is a deterministic research-integrity framework, not a trading
system. The current package is `0.2.0.dev0`. Its engineering state is a
design-partner beta candidate; it is **not production-ready**.

## Verified capabilities

- The rebuilt package preserves the four v0.1 fault families: Look-Ahead
  Timestamp, Unit Drift, Duplicate Observations, and Revision Overwrite.
- Detectors receive only a sanitized `AuditInputSnapshot`. Private manifests
  are used only after audit finalization for scoring, replay, and controlled
  research comparisons.
- The CLI, saved-stage workflow, public artifact reader, deterministic HTML
  summary, and read-only dashboard are implemented over the same artifact
  contracts.
- Additive post-MVP work includes selected-detector evaluation, production
  input/policy layers, bounded local execution, self-hosted packaging, and a
  Missing Observations vertical slice. Missing Observations is not part of the
  frozen v0.1 benchmark; Entity Identity remains unimplemented.
- Synthetic v0.2 development and validation evidence is saved separately:
  390 successful development cases and 390 successful validation cases, with
  clean controls. This is engineering evidence, not customer evidence.
- The observational SEC study processed 472 selected Company Facts records
  from five issuers. It demonstrates narrow real-source pipeline exposure;
  it is not broad natural-data detector validation.
- The real-source adversarial study used 120 manufactured fault instances on
  preserved SEC observations. Exact matching and four correlated Unit Drift
  warnings are reported as controlled evidence, not natural SEC defects.

## Open gates and limitations

- The cited candidate source commit `3b47da9` has a green Security workflow run
  `32693592309`, including exact two-build OCI manifest/config/layer identity,
  dependency, secret, image, and SBOM gates. There is still no published image
  digest or trusted release attestation for deployment.
- No held-out v0.2 execution, customer file, design-partner adjudication,
  pilot result, confirmed research impact, or production deployment exists.
- The SEC adapter is narrow: one CIK at a time, explicit concept/unit/form/date
  allowlists, day-level availability, and no universal statement reconstruction.
- Benchmark metrics are fixture- and denominator-specific. Controlled research
  comparisons are not returns, alpha, Sharpe ratios, portfolio results, or
  financial-loss estimates.
- Exact replay is private answer-key evidence, not detector-only remediation.
- The dashboard and HTML surface are local, read-only, and public-artifact
  only. They do not browse manifests or private values.

## Evidence map

- [Research and real-data studies](research/README.md)
- [Benchmark results](FINAL_BENCHMARK_RESULTS.md)
- [Limitations](LIMITATIONS.md)
- [Artifact and privacy contract](ARTIFACTS_AND_PRIVACY.md)
- [Archive and release-asset manifest](ARTIFACT_ARCHIVE.md)

Claims must remain scoped to the saved artifact, fixture, protocol, or run
that produced them. A new release must rerun the applicable quality,
serialization, privacy, security, and publication checks.
