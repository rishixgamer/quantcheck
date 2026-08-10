# Self-hosted distribution

`Dockerfile` is the production image definition. `smoke/` contains only a synthetic, integrity-
pinned three-row audit used to verify a pulled published image with networking disabled. It is not
customer data, benchmark evidence, or a detector-performance claim.

Read, in order:

1. [`docs/SELF_HOSTED_DEPLOYMENT.md`](../docs/SELF_HOSTED_DEPLOYMENT.md)
2. [`docs/SELF_HOSTED_THREAT_MODEL.md`](../docs/SELF_HOSTED_THREAT_MODEL.md)
3. [`docs/SUPPLY_CHAIN_SECURITY.md`](../docs/SUPPLY_CHAIN_SECURITY.md)
4. [`SECURITY.md`](../SECURITY.md)

The image deliberately has no server, exposed port, automatic volume, database, authentication, or
remote service. `/config` and `/input` are read-only; `/output` and `/work` are operator-owned
writable mounts.
