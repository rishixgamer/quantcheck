# Self-hosted deployment and data lifecycle

## Distribution boundary

The self-hosted distribution is a local, single-tenant batch container over the existing bounded
external-dataset audit engine. It does not add a server, listening port, authentication, SAML,
RBAC, teams, billing, a database, or a hosted control plane. The normal audit path uses local files
and processes only and requires no outbound network access.

The container entry point is:

```text
python -m quantcheck.external_dataset_self_hosted
```

Its config is `quantcheck/self-hosted-run/v1`. The config embeds one existing
`ExternalAuditExecutionPlanV1`, binds each partition ID to one relative file below the input mount,
and fixes both `telemetry` and `network_required` to `false`. Unknown fields are rejected. There is
no credential, token, password, API-key, connection-string, or remote-source field in this config.
Registry credentials belong in the container runtime's credential store; they must not be placed in
the QuantCheck config or passed as Docker build arguments.

## Prepare an audit

First build the reviewed `DatasetMappingV1`, `AuditPolicyV1`, integrity-pinned partition specs, and
execution plan described in [`EXTERNAL_DATASETS.md`](EXTERNAL_DATASETS.md). Then serialize the
deployment binding with QuantCheck's canonical serializer:

```python
from pathlib import Path

from quantcheck.external_dataset_self_hosted import (
    SelfHostedPartitionBindingV1,
    SelfHostedRunConfigV1,
)
from quantcheck.serialization import canonical_json_bytes

config = SelfHostedRunConfigV1(
    plan=reviewed_plan,
    bindings=(
        SelfHostedPartitionBindingV1(
            partition_id=reviewed_plan.partitions[0].partition_id,
            input_path="partition-001.csv",
        ),
    ),
    worker_count=1,
)
Path("run.json").write_bytes(canonical_json_bytes(config))
```

Every input path is relative, cannot contain `..`, a backslash, a home-directory marker, or an
absolute root, and must resolve to a regular non-symlink file below the input mount. The existing
ingestion layer then verifies its declared SHA-256 and byte size before parsing and checks for file
replacement during parsing.

The beta-candidate image installs the `0.2.0.dev0` package's declared runtime dependencies,
including locked PyArrow 24.0.0. CSV, Parquet, Arrow IPC file, and Arrow IPC stream inputs therefore
use the same supported clean-install surface. This changes package/image size and vulnerability
surface, so the clean-wheel format tests, locked-dependency scan, image scan, SBOM review, and
resource-bounded smoke run are required before distribution. The immutable v0.1 wheel and image
claims remain unchanged.

## Verify before running

Use a digest, never a floating tag. Verify package/container provenance and the SBOM as described in
[`SUPPLY_CHAIN_SECURITY.md`](SUPPLY_CHAIN_SECURITY.md) while still on a connected staging system.
Transfer the verified digest or saved OCI image, the reviewed config, and the integrity-pinned input
files into the isolated environment through the firm's approved process.

## Hardened offline invocation

The image declares numeric user `65532:65532`, no ports, and no automatic volumes. `/config` and
`/input` are read-only mounts. `/output` and `/work` are the only intended writable mounts. The
root filesystem is read-only, all Linux capabilities are dropped, privilege escalation is disabled,
and networking is disabled in the recommended invocation:

```bash
qc_image='ghcr.io/rishixgamer/quantcheck-self-hosted@sha256:<verified-digest>'
qc_config_dir='/approved/quantcheck/config'
qc_input_dir='/approved/quantcheck/input'
qc_output_dir='/approved/quantcheck/output'
qc_work_dir='/approved/quantcheck/work'

install -d -m 0750 "$qc_output_dir" "$qc_work_dir"

docker run --rm \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 128 \
  --memory 4g \
  --cpus 4 \
  --mount "type=bind,src=$qc_config_dir,dst=/config,readonly" \
  --mount "type=bind,src=$qc_input_dir,dst=/input,readonly" \
  --mount "type=bind,src=$qc_output_dir,dst=/output" \
  --mount "type=bind,src=$qc_work_dir,dst=/work" \
  "$qc_image"
```

Set ownership or an ACL that lets UID/GID `65532` write only the two writable host directories.
Size CPU and memory against the reviewed partition cap and
[`PERFORMANCE_AND_EXECUTION.md`](PERFORMANCE_AND_EXECUTION.md). Worker counts are fixed to 1, 2,
or 4 and do not enter logical artifact identity.

The process writes canonical JSON status records to standard output. Success records contain only
the logical run/finalization IDs and status. Failure records contain a fixed code. Financial values,
entity names, source locators, source credentials, local paths, raw exceptions, and tracebacks are
not included. Container-runtime log drivers can retain these redacted records independently, so the
operator must apply its normal log-retention policy.

Telemetry is absent and explicitly disabled (`DO_NOT_TRACK=1`, `QUANTCHECK_TELEMETRY=0`, and
`telemetry=false`). An attempt to enable QuantCheck telemetry is rejected. The Python package still
contains the separate SEC adapter, but the self-hosted entry point does not call it; `--network
none` is the enforcement boundary for an isolated deployment.

## Outputs, retention, and deletion

QuantCheck has no background service, database, remote object store, or automatic retention job.
Generated audit data persists until the operator deletes it:

```text
/output/public/      audit reports, statuses, plans, and finalization evidence
/output/private/     normalized customer records and private partition summaries
/output/operations/  redacted operational event records
/work/               temporary runtime files, if any
container logs       retained by the operator's container runtime, outside QuantCheck
```

Treat the entire output root as customer data. The public/private naming is an audit boundary, not
a data-classification decision for the customer. Use a fresh output and work root per customer or
engagement; never reuse one root across tenants.

After exporting any approved evidence, stop the container and delete the exact output and work
roots using the firm's approved media-sanitization procedure. Also delete copied configs, input
staging files, container-runtime logs, snapshots, and backups according to the firm's retention
schedule. QuantCheck cannot erase filesystem snapshots, storage-controller remaps, backups, or log
driver copies. Ordinary file deletion is therefore a logical-deletion claim, not a cryptographic or
physical-erasure claim.

The release workflow verifies the deletion boundary by running the pulled image digest with
networking disabled and a read-only root, confirming all audit artifacts live below the mounted
output root, then removing the mounted output and work trees and checking that neither remains.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All partitions succeeded and finalization was written. |
| `2` | Config, mount binding, or telemetry setting was invalid. |
| `3` | The run finalized with one or more isolated partition failures. |
| `4` | Artifact integrity, persistence, or execution failed. |
| `130` | The process was interrupted. |

Inspect canonical evidence under `/output`; do not rely on log text as the audit result.
