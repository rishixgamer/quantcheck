# Software supply chain, provenance, and patch process

## What is implemented

The self-hosted release workflow publishes these versioned artifacts from one release tag:

- wheel and source distribution;
- SHA-256 `SHA256SUMS` for the package artifacts and downloadable SBOMs;
- a GHCR image addressed by immutable digest and version/source-SHA tags;
- SPDX 2.3 JSON SBOMs for packages and the final container;
- GitHub/Sigstore SLSA-provenance attestations for packages and the image;
- GitHub/Sigstore SPDX SBOM attestations for packages and the image;
- BuildKit max-mode provenance and an SBOM attached to the OCI image.

Python dependencies are resolved through the checked-in `uv.lock`. The build uses Python 3.12,
Hatchling, a digest-pinned Python base, a digest-pinned `uv` builder, a fixed Buildx version, and a
digest-pinned BuildKit worker. `SOURCE_DATE_EPOCH` is the source commit time; the reproducibility
gate performs two no-cache BuildKit exports with timestamp rewriting and requires byte-identical OCI
archives. This is a scoped Linux/amd64 reproducibility claim for the same source, build arguments,
BuildKit behavior, and reachable locked dependencies, not a claim that arbitrary builders or
platforms produce the same digest.

All workflow actions are pinned to full commit SHAs. CI separately scans repository content for
secrets, scans locked library dependencies, scans the built image, generates an SBOM, and reruns the
container reproducibility check. The release path repeats the final image vulnerability scan before
publishing. Fixable high/critical findings fail the gate; lower-severity and currently unfixed
findings remain inputs to maintainer/customer risk review, not proof of absence.

## Verify a downloaded package

On a connected verification host, download the release asset, `SHA256SUMS`, and SBOM. Verify the
digest first, then bind the artifact to this repository and the publishing workflow:

```bash
sha256sum --check SHA256SUMS

gh attestation verify quantcheck-<version>-py3-none-any.whl \
  --repo rishixgamer/quantcheck \
  --signer-workflow rishixgamer/quantcheck/.github/workflows/publish-self-hosted.yml

gh attestation verify quantcheck-<version>-py3-none-any.whl \
  --repo rishixgamer/quantcheck \
  --signer-workflow rishixgamer/quantcheck/.github/workflows/publish-self-hosted.yml \
  --predicate-type https://spdx.dev/Document/v2.3
```

Inspect the verification JSON and confirm `sourceRepository`, `sourceDigest`, workflow path, subject
name/digest, and expected tag/ref satisfy the firm's policy. An attestation is evidence of origin;
it is not a vulnerability-free or certification statement.

## Verify a container

Resolve and record the immutable digest before transfer:

```bash
qc_image='ghcr.io/rishixgamer/quantcheck-self-hosted@sha256:<digest>'

gh attestation verify "oci://$qc_image" \
  --repo rishixgamer/quantcheck \
  --signer-workflow rishixgamer/quantcheck/.github/workflows/publish-self-hosted.yml

gh attestation verify "oci://$qc_image" \
  --repo rishixgamer/quantcheck \
  --signer-workflow rishixgamer/quantcheck/.github/workflows/publish-self-hosted.yml \
  --predicate-type https://spdx.dev/Document/v2.3

docker buildx imagetools inspect "$qc_image" --format '{{ json .Provenance.SLSA }}'
docker buildx imagetools inspect "$qc_image" --format '{{ json .SBOM.SPDX }}'
```

Check that the OCI label revision, provenance source digest, release tag, and expected repository
agree. Review both the downloadable SBOM and attached SBOM because each is produced by a distinct
tool/boundary. Pull or save the image by digest only after the checks pass.

## Offline attestation verification

Before crossing an air gap, obtain the artifact, its attestation bundle, and a fresh trusted-root
set on an online verification host:

```bash
gh attestation download quantcheck-<version>-py3-none-any.whl \
  --repo rishixgamer/quantcheck
gh attestation trusted-root > trusted_root.jsonl
```

Transfer those files through the firm's approved channel. Offline:

```bash
gh attestation verify quantcheck-<version>-py3-none-any.whl \
  --repo rishixgamer/quantcheck \
  --bundle sha256:<artifact-digest>.jsonl \
  --custom-trusted-root trusted_root.jsonl \
  --signer-workflow rishixgamer/quantcheck/.github/workflows/publish-self-hosted.yml
```

Import a refreshed trusted root whenever new signed material is introduced. A stale root can miss
later key revocations or rotations.

## Dependency and security-update process

1. **Detect.** Weekly scheduled CI refreshes Trivy vulnerability data and scans source dependencies
   and the container. Maintainers also monitor upstream Python/base-image/action advisories and
   private reports under `SECURITY.md`.
2. **Triage.** Confirm the affected component, reachable code path, affected artifact digests,
   exploit preconditions, fixed version, and any customer mitigation. Never paste customer data or
   a live secret into the issue or scanner exception.
3. **Patch narrowly.** Use `uv lock --upgrade-package <name>` for one Python dependency where
   possible. For a base or builder image, resolve the reviewed tag to its OCI digest and update the
   digest and comment together. For an action, review the upstream release and pin its full commit
   SHA. Do not use moving tags in release workflows.
4. **Verify.** Run focused regression tests, the complete Python 3.12 gates, offline wheel/sdist
   build and archive inspection, container build/reproducibility/offline smoke, secret scan,
   dependency scan, image scan, and SBOM review. Confirm no scientific frozen file or result changed
   unless the release explicitly authorizes that change.
5. **Release immutably.** Increment the version, create a reviewed tag/release, let the publishing
   workflow build from that tag, and verify the new package/image attestations. Never overwrite an
   existing digest or release asset. Publish an advisory with affected and fixed versions when the
   change is security-relevant.
6. **Customer action.** Tell customers which digest is fixed, how to verify it, whether config/data
   migration is needed, and how to retire old local images and generated data under their retention
   process.

If no fixed upstream version exists, record a time-bounded exception with the CVE/advisory,
affected artifact, reachability evidence, compensating control, owner, review date, and removal
condition. The current workflows intentionally have no blanket ignore file.

## Practice alignment and claims

The checklist is informed by NIST SP 800-218 SSDF outcomes: documented security requirements and
decisions, protected and reproducible build inputs, provenance for released components, automated
verification, vulnerability intake, triage, and remediation. OCI provenance uses the SLSA v1
predicate format, and GitHub-hosted signing uses Sigstore identities. These are implementation
choices, not audit results.

QuantCheck has not obtained NIST, SLSA, ISO 27001, SOC 2, PCI DSS, FedRAMP, or other certification.
It has not undergone an independent penetration test or third-party supply-chain audit. SBOMs,
scans, signatures, and attestations reduce specific risks; none establishes that the software is
secure or suitable for a firm's obligations.
