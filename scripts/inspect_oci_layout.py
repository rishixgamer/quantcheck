#!/usr/bin/env python3
"""Inspect and compare reproducible OCI-layout archives without extra packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Any


def _sha256(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON semantics independently of object-key or whitespace order."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _member_bytes(archive: tarfile.TarFile, name: str) -> bytes:
    member = archive.getmember(name)
    extracted = archive.extractfile(member)
    if extracted is None:
        raise ValueError(f"OCI member is not a regular file: {name}")
    return extracted.read()


def _blob_bytes(archive: tarfile.TarFile, digest: str) -> bytes:
    algorithm, value = digest.split(":", 1)
    if algorithm != "sha256":
        raise ValueError(f"unsupported OCI digest algorithm: {algorithm}")
    payload = _member_bytes(archive, f"blobs/{algorithm}/{value}")
    if _sha256(payload) != digest:
        raise ValueError(f"OCI blob content does not match descriptor {digest}")
    return payload


def inspect(path: Path) -> dict[str, Any]:
    archive_sha256 = _sha256(path.read_bytes())
    with tarfile.open(path, mode="r:*") as archive:
        index_bytes = _member_bytes(archive, "index.json")
        index = json.loads(index_bytes)
        manifests = index.get("manifests", [])
        if len(manifests) != 1:
            raise ValueError("expected exactly one platform manifest in the OCI index")
        manifest_digest = manifests[0]["digest"]
        manifest = json.loads(_blob_bytes(archive, manifest_digest))
        config_digest = manifest["config"]["digest"]
        _blob_bytes(archive, config_digest)
        layer_digests = [layer["digest"] for layer in manifest.get("layers", [])]
        for digest in layer_digests:
            _blob_bytes(archive, digest)
    canonical_identity = {
        # The raw archive and index hashes remain useful diagnostics, but the
        # OCI layout tar can legitimately vary in member order/header bytes.
        # Digest-addressed manifest/config/layer content is the image identity.
        "config_digest": config_digest,
        "index_canonical_sha256": _sha256(_canonical_json_bytes(index)),
        "layer_digests": layer_digests,
        "manifest_digest": manifest_digest,
    }
    return {
        "archive_sha256": archive_sha256,
        "canonical_identity": canonical_identity,
        "config_digest": config_digest,
        "index_sha256": _sha256(index_bytes),
        "layer_digests": layer_digests,
        "manifest_digest": manifest_digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", nargs="?", type=Path)
    args = parser.parse_args()

    first = inspect(args.first)
    if args.second is None:
        print(json.dumps(first, indent=2, sort_keys=True))
        return 0

    second = inspect(args.second)
    raw_archive_identical = first["archive_sha256"] == second["archive_sha256"]
    report = {
        "first": first,
        "identical": (first["canonical_identity"] == second["canonical_identity"]),
        "raw_archive_identical": raw_archive_identical,
        "second": second,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
