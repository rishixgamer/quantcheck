"""The OCI reproducibility diagnostic compares every claimed identity."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSPECTOR = REPO_ROOT / "scripts/inspect_oci_layout.py"


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _oci_archive(path: Path, *, config_marker: str) -> None:
    config = _json({"marker": config_marker})
    layer = b"deterministic-layer"
    manifest = _json(
        {
            "schemaVersion": 2,
            "config": {"digest": _digest(config), "size": len(config)},
            "layers": ({"digest": _digest(layer), "size": len(layer)},),
        }
    )
    index = _json(
        {
            "schemaVersion": 2,
            "manifests": ({"digest": _digest(manifest), "size": len(manifest)},),
        }
    )
    members = {
        "index.json": index,
        f"blobs/sha256/{_digest(config).split(':')[1]}": config,
        f"blobs/sha256/{_digest(layer).split(':')[1]}": layer,
        f"blobs/sha256/{_digest(manifest).split(':')[1]}": manifest,
    }
    with tarfile.open(path, "w") as archive:
        for name, payload in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.mtime = 0
            info.mode = 0o644
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))


def test_identical_oci_archives_report_every_matching_identity(tmp_path: Path) -> None:
    first = tmp_path / "first.tar"
    second = tmp_path / "second.tar"
    _oci_archive(first, config_marker="same")
    second.write_bytes(first.read_bytes())
    completed = subprocess.run(
        (sys.executable, str(INSPECTOR), str(first), str(second)),
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert report["identical"] is True
    assert report["first"] == report["second"]
    assert report["first"]["archive_sha256"].startswith("sha256:")
    assert report["first"]["manifest_digest"].startswith("sha256:")
    assert report["first"]["config_digest"].startswith("sha256:")
    assert len(report["first"]["layer_digests"]) == 1


def test_changed_oci_config_is_a_nonzero_reproducibility_failure(tmp_path: Path) -> None:
    first = tmp_path / "first.tar"
    second = tmp_path / "second.tar"
    _oci_archive(first, config_marker="first")
    _oci_archive(second, config_marker="second")
    completed = subprocess.run(
        (sys.executable, str(INSPECTOR), str(first), str(second)),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert report["identical"] is False
    assert report["first"]["config_digest"] != report["second"]["config_digest"]
