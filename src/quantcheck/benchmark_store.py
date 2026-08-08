"""Canonical, atomic, immutable-by-default benchmark artifact persistence.

Every write goes through one path: validate the model, serialize it with the
project's single canonical serializer, write a temporary file *in the
destination directory*, flush it, ``fsync`` it, and ``os.replace`` it into
place. There is no second JSON representation and no force-overwrite option.

Immutable semantics are the point of this module. A logical artifact is
addressed by a path derived from identities, so re-writing it with identical
bytes is a safe no-op, and re-writing it with different bytes means two runs
disagree about the same logical evidence — which is reported as an integrity
error rather than resolved by overwriting one of them.

Three artifacts are deliberately *not* immutable: runtime metadata, the
aggregate report, and the public index. None of them is case evidence; each is
a derived record of the most recent run over the same immutable case
artifacts, and a resumed run legitimately rewrites all three.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

__all__ = [
    "ArtifactIntegrityError",
    "ArtifactPersistenceError",
    "AtomicArtifactStore",
    "atomic_write_bytes",
]


class ArtifactPersistenceError(OSError):
    """Raised when an artifact cannot be written safely."""


class ArtifactIntegrityError(ValueError):
    """Raised when stored bytes conflict with the artifact being written."""


def atomic_write_bytes(destination: Path, payload: bytes) -> None:
    """Write bytes so a reader never observes a partial artifact.

    The temporary file is created in the destination's own directory so that
    ``os.replace`` is a same-filesystem rename and therefore atomic. The file
    is flushed and ``fsync``-ed before the rename, so a crash after the rename
    cannot leave a named-but-empty artifact behind.
    """
    directory = destination.parent
    directory.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(  # noqa: SIM115 - closed explicitly below
        mode="wb",
        dir=directory,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except OSError as exc:  # pragma: no cover - filesystem failure path
        temporary.unlink(missing_ok=True)
        raise ArtifactPersistenceError(f"could not persist {destination.name}") from exc
    finally:
        if temporary.exists():  # pragma: no cover - only after a failed replace
            temporary.unlink(missing_ok=True)


class AtomicArtifactStore:
    """A rooted, canonical, atomic artifact store for one benchmark run."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def path_for(self, relative_path: str) -> Path:
        """Resolve one store-relative path, refusing to escape the root."""
        candidate = self._root / relative_path
        try:
            resolved = candidate.resolve().relative_to(self._root.resolve())
        except ValueError as exc:
            raise ArtifactIntegrityError(
                f"artifact path {relative_path!r} escapes the store root"
            ) from exc
        return self._root / resolved

    def exists(self, relative_path: str) -> bool:
        return self.path_for(relative_path).is_file()

    def read_bytes(self, relative_path: str) -> bytes:
        destination = self.path_for(relative_path)
        try:
            return destination.read_bytes()
        except OSError as exc:
            raise ArtifactPersistenceError(f"could not read {relative_path}") from exc

    def read_canonical(self, relative_path: str) -> object:
        """Read and re-parse one artifact, rejecting non-canonical bytes."""
        return parse_canonical_json(self.read_bytes(relative_path))

    def write_immutable(self, relative_path: str, artifact: object) -> bytes:
        """Persist one immutable logical artifact and return its exact bytes.

        Identical existing bytes are reused untouched. Conflicting existing
        bytes raise :class:`ArtifactIntegrityError`: the stored evidence is
        never silently replaced, and there is no option that would allow it.
        """
        payload = canonical_json_bytes(artifact)
        destination = self.path_for(relative_path)
        if destination.is_file():
            existing = destination.read_bytes()
            if existing == payload:
                return payload
            raise ArtifactIntegrityError(
                f"immutable artifact {relative_path} already exists with different content"
            )
        atomic_write_bytes(destination, payload)
        return payload

    def write_run_artifact(self, relative_path: str, artifact: object) -> bytes:
        """Persist one derived per-run artifact, replacing any prior version.

        Restricted by policy to runtime metadata, the aggregate report, and the
        public index. These are rebuilt from immutable evidence on every run,
        so replacing them is not a loss of evidence.
        """
        payload = canonical_json_bytes(artifact)
        atomic_write_bytes(self.path_for(relative_path), payload)
        return payload
