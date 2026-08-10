# Self-hosted security threat model

## Scope and relation to the v0.1 model

This is the additive threat model for the self-hosted production distribution. The frozen v0.1
benchmark model in `THREAT_MODEL.md` remains historically accurate for the tagged benchmark
release, where network and supply-chain threats were explicitly out of scope. This document brings
artifact provenance, dependency risk, container isolation, customer-data handling, and operational
deletion into scope without changing any scientific or detector trust boundary.

The deployment is one customer, one local batch job, and one operator-controlled host. QuantCheck
does not provide identity, authorization, tenant isolation, a database, a network service, or a
remote management plane.

## Assets and trust boundaries

Assets:

- raw customer financial inputs and their mappings/policies;
- private normalized records and source provenance;
- public findings and finalization evidence;
- release artifacts, SBOMs, provenance attestations, and dependency locks;
- redacted operational logs.

Trust boundaries:

1. the release repository/workflow to the package registry and GHCR;
2. the container runtime to the non-root batch process;
3. read-only `/config` and `/input` mounts to the normalization boundary;
4. the sanitized `AuditInputSnapshot` to manifest-blind detectors;
5. the process to writable `/output` and `/work` mounts;
6. the output root and container log driver to the customer's retention controls.

## Threats and controls

### S1 — An artifact cannot be traced to reviewed source

**Threat.** A tag is moved, a registry artifact is substituted, or a customer installs an artifact
whose source/build instructions are unknown.

**Controls.** Release assets carry SHA-256 checksums and GitHub/Sigstore build-provenance
attestations. Images are consumed by digest. BuildKit also attaches max-mode SLSA-format provenance
and an SBOM to the OCI image. Every GitHub Action is pinned to a full commit SHA, and base/builder
images are pinned to OCI digests. Verification instructions bind the subject to the exact
`rishixgamer/quantcheck` repository and publishing workflow.

**Residual risk.** Provenance proves origin and build context, not that source is safe. A compromised
repository, privileged workflow, GitHub-hosted runner, upstream action at the pinned commit, or
registry remains material. No SLSA level or certification is claimed.

### S2 — A vulnerable or malicious dependency enters the release

**Threat.** Python, OS, base-image, scanner, or workflow dependencies contain a known or newly
discovered vulnerability.

**Controls.** Python resolution is frozen in `uv.lock`; base and builder images use digests;
Trivy scans locked dependencies and the final image; Syft/BuildKit produce SPDX SBOMs; weekly CI
rescans current vulnerability data; the documented patch process issues a new immutable release.
Fixable high/critical findings block CI and publication.

**Residual risk.** Scanners can miss vulnerabilities, databases can lag, unfixed findings need risk
decisions, and an SBOM can be incomplete. Findings below the gate still require review appropriate
to the firm's risk tolerance.

### S3 — A secret is committed, built, or copied into config

**Threat.** Source credentials or registry tokens leak through Git, config, image layers,
provenance, or logs.

**Controls.** Trivy runs a dedicated repository secret scan. The application config has no secret
field and rejects unknown keys. The build accepts no secret build argument. Registry login uses the
runtime/CI credential mechanism. Logs use fixed redacted codes and no exception text.

**Residual risk.** A user can misuse a non-secret provenance string as a place to paste sensitive
text. Review mappings and policies as customer data, and never place credentials in them. Host
shell history and external log drivers are outside the application boundary.

### S4 — Customer data leaves the isolated environment

**Threat.** Telemetry, a remote dependency, or an accidental adapter call sends financial data out.

**Controls.** The self-hosted entry point imports and calls the local external-audit execution path,
which declares `network_used=false`; telemetry/network config can only be `false`; telemetry
environment values that request enablement are rejected. The supported invocation uses `--network
none`, and release smoke verification runs a real audit under that restriction.

**Residual risk.** A hostile or compromised container runtime/host can observe mounted data and
process memory. Network namespaces do not mitigate host compromise or local side channels.

### S5 — The process writes outside declared customer-data roots

**Threat.** A path traversal, symlink, temp file, implicit volume, or writable root filesystem leaves
data somewhere the operator does not delete.

**Controls.** Input bindings allow safe relative POSIX paths only and are confined below the input
root; symlinked inputs are rejected. Customer mounts are read-only. The root filesystem is run
read-only. `TMPDIR` is `/work`; persistent artifacts are rooted under `/output`; no OCI `VOLUME` is
declared. The artifact store independently refuses traversal and writes atomically in-root.

**Residual risk.** The container runtime can retain stdout/stderr, overlay data, or snapshots.
Operator-owned mounts, log drivers, backups, crash dumps, and storage media require separate
retention and sanitization controls.

### S6 — Excess container privilege expands impact

**Threat.** Malformed customer input exploits the parser or package and reaches the host.

**Controls.** The image runs as numeric non-root UID/GID `65532`, exposes no port, requires no
capability, and is documented with a read-only root, `no-new-privileges`, dropped capabilities,
PID/CPU/memory limits, and no network. Inputs/configs are read-only.

**Residual risk.** Containers are not virtual machines. Kernel, runtime, Python, and parser
vulnerabilities remain. Higher-assurance deployments may add an approved sandbox or VM without
changing QuantCheck's artifact contract.

### S7 — Diagnostic output exposes values or credentials

**Threat.** A parse error or exception copies a financial value, entity name, path, source locator,
or credential to logs.

**Controls.** Public validation diagnostics use a fixed catalogue. The bounded runner persists
fixed operational events/failure codes. The container boundary catches errors and emits canonical
JSON with a fixed code, never exception text or tracebacks. Focused tests place distinctive values
and secrets in failing inputs and assert their absence.

**Residual risk.** Public findings intentionally contain detector evidence defined by their frozen
contracts and may be sensitive to the customer. Audit artifacts are not diagnostic logs and must be
retained as customer data.

### S8 — One customer's data or output is reused for another

**Threat.** Resume semantics or a shared mount causes cross-engagement retention.

**Controls.** The distribution is single-tenant. Operators must use a fresh input, output, and work
root per engagement. Resume reuses only identity- and hash-verified partition evidence. There is no
shared database or service cache.

**Residual risk.** QuantCheck cannot enforce the operator's host-directory allocation or backup
policy. Multi-tenant scheduling is explicitly unsupported.

### S9 — Resource exhaustion prevents completion

**Threat.** A large or malformed dataset consumes memory, CPU, disk, PIDs, or diagnostic capacity.

**Controls.** Inputs are size/digest pinned, diagnostics are bounded, complete-entity partitions
have an explicit record cap, workers are limited to 1/2/4, and deployment examples apply CPU,
memory, and PID limits. Failures are isolated per partition and resumable.

**Residual risk.** One entity history cannot be split without changing detector semantics; native
parser memory and decompression behavior can exceed Python allocation evidence. Operators must
validate capacity before production use.

## Explicit non-goals

- authentication, authorization, SAML, RBAC, accounts, teams, or billing;
- a multi-tenant or hosted service, database, message queue, or remote control plane;
- protection from a compromised host, kernel, container runtime, CI administrator, or repository
  administrator;
- side-channel resistance, malware scanning of customer inputs, or guaranteed secure erasure;
- certification against NIST, ISO, SOC, PCI DSS, FedRAMP, or another scheme;
- a claim that provenance, an SBOM, or a vulnerability scan makes an artifact secure.
