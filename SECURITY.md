# QuantCheck security policy

## Reporting a vulnerability

Report suspected vulnerabilities privately to the QuantCheck maintainers through
[GitHub private vulnerability reporting](https://github.com/rishixgamer/quantcheck/security/advisories/new).
Do not place customer data, credentials, exploit details, or an unpatched vulnerability in a public
issue.

Include, when safe:

- the affected release tag, package version, or container digest;
- the affected component and deployment mode;
- a minimal reproduction using synthetic data;
- the expected and observed security boundary;
- impact and any known workaround.

The maintainers target an acknowledgement within three business days and an initial triage within
seven business days. These are response targets, not contractual service levels. The reporter and
maintainers should agree on coordinated disclosure timing after impact and remediation are
understood.

If GitHub private vulnerability reporting is unavailable, contact the repository owner privately
through the contact mechanism on the repository profile and ask for a secure reporting channel.
Do not send the vulnerability details until that channel is established. QuantCheck does not
currently publish a PGP reporting key or operate a security bounty program.

## Supported versions

Security fixes are made on the latest published release line. A release is supported only when its
artifacts and provenance are available from the repository's GitHub Release and GHCR package.
The historical `v0.1.0` Python release predates the self-hosted container; do not infer that a
container exists until a later release workflow has actually published one.

## Disclosure and remediation

Confirmed issues are tracked privately until a fix or documented mitigation is ready. Remediation
uses a new immutable version and digest; published wheels, source distributions, container tags,
SBOMs, and attestations are never silently replaced. A security advisory records affected versions,
impact, mitigation, fixed versions, and credit when the reporter wants it.

The full dependency and patch process is in
[`docs/SUPPLY_CHAIN_SECURITY.md`](docs/SUPPLY_CHAIN_SECURITY.md).
