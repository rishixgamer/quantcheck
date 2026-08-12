#!/bin/sh
set -eu

if ! command -v docker >/dev/null 2>&1; then
  echo "docker with buildx is required" >&2
  exit 2
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/quantcheck-repro.XXXXXX")
cleanup() {
  rm -rf -- "$build_dir"
}
trap cleanup EXIT HUP INT TERM

source_date_epoch=${SOURCE_DATE_EPOCH:-$(git -C "$repo_root" log -1 --format=%ct)}
vcs_ref=${VCS_REF:-$(git -C "$repo_root" rev-parse HEAD)}

build_once() {
  destination=$1
  docker buildx build \
    --platform linux/amd64 \
    --no-cache \
    --build-arg "SOURCE_DATE_EPOCH=$source_date_epoch" \
    --build-arg "VCS_REF=$vcs_ref" \
    --provenance=false \
    --sbom=false \
    --output "type=oci,dest=$destination,rewrite-timestamp=true" \
    "$repo_root"
}

build_once "$build_dir/first.oci.tar"
build_once "$build_dir/second.oci.tar"

digest() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

first=$(digest "$build_dir/first.oci.tar")
second=$(digest "$build_dir/second.oci.tar")
comparison="$build_dir/oci-comparison.json"
if ! python3 "$repo_root/scripts/inspect_oci_layout.py" \
  "$build_dir/first.oci.tar" "$build_dir/second.oci.tar" >"$comparison"
then
  cat "$comparison" >&2
  echo "container reproducibility check failed: OCI identities differ" >&2
  exit 1
fi
if [ "$first" != "$second" ]; then
  cat "$comparison" >&2
  echo "container reproducibility check failed: raw OCI archives differ" >&2
  exit 1
fi
cat "$comparison"
printf '%s  %s\n' "$first" "quantcheck-linux-amd64.oci.tar"
