# Secure development and release checklist

This checklist is an implementation-oriented alignment with established secure-software and
software-supply-chain practices. It is not a certification checklist and passing it does not create
a compliance claim.

## Prepare and protect

- [ ] Security requirements, assets, trust boundaries, abuse cases, and non-goals are current in
  `SELF_HOSTED_THREAT_MODEL.md`.
- [ ] The change stays single-tenant/local and adds no authentication, SAML, RBAC, database,
  billing, hosted control plane, or remote telemetry.
- [ ] Repository and release-workflow permissions are least privilege; every action uses a reviewed
  full commit SHA.
- [ ] Base/builder images use reviewed immutable digests; Python dependencies remain locked with
  hashes.
- [ ] No secret is accepted in ordinary app config or a Docker build argument; external credentials
  use the platform's secret/credential mechanism.
- [ ] Private vulnerability reports use `SECURITY.md`; public issues contain no unpatched exploit,
  customer data, or credentials.

## Produce and verify

- [ ] Detector manifest blindness, audit sanitization, exact financial values, deterministic IDs,
  non-mutation, and clean-control invariants remain green.
- [ ] New/changed code has positive, negative, edge, redaction, traversal, offline, and regression
  tests.
- [ ] Structured logs expose no financial values, source credentials, raw exceptions, or local
  paths by default.
- [ ] Container runs as non-root with no port, no implicit volume, a read-only root, no network,
  dropped capabilities, `no-new-privileges`, and explicit read-only/writable mounts.
- [ ] `uv sync --frozen --all-groups`, Ruff, strict MyPy, pytest, lock check, installed CLI help,
  `uv build --offline`, and `git diff --check` pass on Python 3.12.
- [ ] Wheel and sdist are inspected separately; clean Python 3.12 installation works from the wheel.
- [ ] Secret scanning, locked-dependency scanning, final-image scanning, and SBOM generation pass.
  Any exception is explicit, owned, expiring, and justified by reachability/mitigation evidence.
- [ ] Two fixed-input Linux/amd64 BuildKit exports are byte-identical.
- [ ] A pulled image digest runs the synthetic audit with outbound networking disabled, read-only
  config/input mounts, writable output/work mounts, a read-only root, and non-root user.
- [ ] All generated customer data can be enumerated below the declared mounts and removed; runtime
  log, snapshot, and backup retention are documented as operator responsibilities.

## Release and respond

- [ ] Version/tag/source revision agree; mutable tags are never the verification identity.
- [ ] Wheel, sdist, checksums, package/container SPDX SBOMs, and image digest are published.
- [ ] Package and image provenance plus SBOM attestations verify against the expected repository and
  signer workflow.
- [ ] Release notes state security-relevant changes, limitations, known vulnerabilities/exceptions,
  migration needs, and exact fixed digests without claiming an unearned certification.
- [ ] Patch instructions and customer retirement/deletion steps are current.
- [ ] `docs/STATUS.md` records factual local/CI evidence and explicitly separates configured gates
  from gates actually observed green.

References: [NIST SP 800-218 SSDF](https://csrc.nist.gov/pubs/sp/800/218/final),
[SLSA specification](https://slsa.dev/spec/),
[GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations),
and [Docker build attestations](https://docs.docker.com/build/metadata/attestations/).
