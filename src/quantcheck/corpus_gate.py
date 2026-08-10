"""The single, narrow authorization primitive for held-out corpus units.

The v0.2 corpus reserves a whole partition of clean sources as held-out
evidence. Ordinary code may *describe* a held-out unit — its identifier,
partition, provenance, record count, content hash, and eligibility counts are
all committed evidence, and the freeze record would be unreadable if naming one
were forbidden. What ordinary code may not do is **materialize its records**,
because that is the step that lets a detector see it.

This is deliberately the same shape as ``quantcheck.release_gate``, which
ADR-010 froze for reserved final seeds, and for the same reason: the boundary
that matters is execution, not representation.

The design goals, in order:

1. **It cannot authorize a subset.** The registry hands this module the
   complete declared held-out unit set and refuses anything narrower, so a
   caller cannot open the gate for one convenient unit.
2. **It cannot be entered by accident.** Activation is a context manager, so
   the permission is scoped to a ``with`` block and is removed on the way out
   even if the block raises.
3. **It cannot leak into ordinary execution.** The permission lives in a
   :class:`~contextvars.ContextVar`, so it is per-context and never a global
   flag another thread, task, or later call can observe.
4. **It cannot be reached from the CLI.** No command, flag, or environment
   variable references this module; ``scripts/`` is the only caller outside
   tests, and a static test asserts that.

This module imports nothing from ``quantcheck``, so the gate has no way to be
influenced by anything the rest of the package does.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

__all__ = [
    "HeldOutCorpusAuthorization",
    "HeldOutCorpusAuthorizationError",
    "active_held_out_corpus_authorization",
    "held_out_corpus_units",
    "held_out_unit_authorized",
]

_UNIT_ID_PATTERN = re.compile(r"^cunit_[0-9a-f]{16}$")
_CORPUS_ID_PATTERN = re.compile(r"^corp_[0-9a-f]{16}$")


class HeldOutCorpusAuthorizationError(RuntimeError):
    """Raised when held-out corpus authorization is requested incorrectly."""


@dataclass(frozen=True, slots=True)
class HeldOutCorpusAuthorization:
    """One active authorization to materialize held-out corpus records.

    ``corpus_id`` records *which* frozen corpus the permission was opened for,
    so an authorization can never be anonymous. ``unit_ids`` is stored rather
    than assumed, so a caller reading the active authorization sees the exact
    set that was permitted.
    """

    corpus_id: str
    unit_ids: tuple[str, ...]

    def permits(self, unit_id: str) -> bool:
        """Report whether this authorization covers one corpus unit."""
        return unit_id in self.unit_ids


_ACTIVE: ContextVar[HeldOutCorpusAuthorization | None] = ContextVar(
    "quantcheck_held_out_corpus_authorization", default=None
)


def active_held_out_corpus_authorization() -> HeldOutCorpusAuthorization | None:
    """Return the authorization active in this context, if any."""
    return _ACTIVE.get()


def held_out_unit_authorized(unit_id: str) -> bool:
    """Report whether one held-out corpus unit is authorized right now.

    With no active authorization this always answers ``False``, which is what
    keeps every ordinary interface closed.
    """
    authorization = _ACTIVE.get()
    if authorization is None:
        return False
    return authorization.permits(unit_id)


def _validate_unit_ids(unit_ids: Sequence[str]) -> tuple[str, ...]:
    """Accept a nonempty, unique, well-formed set of corpus unit identifiers.

    Every rejection below is a distinct way a caller could try to smuggle
    something through, so each is checked separately rather than collapsed
    into one set comparison — a set comparison alone would silently accept
    duplicates.
    """
    if isinstance(unit_ids, str | bytes):
        raise HeldOutCorpusAuthorizationError("held-out unit ids must be a sequence of strings")
    values = tuple(unit_ids)
    if not values:
        raise HeldOutCorpusAuthorizationError("the held-out partition must not be empty")
    for unit_id in values:
        if not isinstance(unit_id, str) or _UNIT_ID_PATTERN.fullmatch(unit_id) is None:
            raise HeldOutCorpusAuthorizationError(f"malformed corpus unit id: {unit_id!r}")
    if len(set(values)) != len(values):
        raise HeldOutCorpusAuthorizationError("the held-out partition must not contain duplicates")
    return tuple(sorted(values))


@contextmanager
def held_out_corpus_units(
    *,
    corpus_id: str,
    unit_ids: Sequence[str],
) -> Iterator[HeldOutCorpusAuthorization]:
    """Authorize materializing the held-out corpus partition for this block.

    This lifts the held-out rejection in ``quantcheck.corpus_registry`` for the
    duration of the ``with`` block, and for nothing else. It grants no other
    permission: reserved final seeds stay reserved, immutable artifacts stay
    immutable, and no detector gains manifest access.

    The registry — which is the only thing that knows the declared held-out
    partition — additionally refuses an authorization that does not cover that
    partition exactly, so an authorization opened for a convenient subset is
    useless.

    Nesting is refused rather than counted, because a nested authorization
    would mean two corpora are open at once and the inner one would silently
    win.
    """
    if not isinstance(corpus_id, str) or _CORPUS_ID_PATTERN.fullmatch(corpus_id) is None:
        raise HeldOutCorpusAuthorizationError(
            "held-out corpus authorization requires a frozen corpus identifier"
        )
    if _ACTIVE.get() is not None:
        raise HeldOutCorpusAuthorizationError("held-out corpus authorization is already active")
    authorization = HeldOutCorpusAuthorization(
        corpus_id=corpus_id,
        unit_ids=_validate_unit_ids(unit_ids),
    )
    token = _ACTIVE.set(authorization)
    try:
        yield authorization
    finally:
        _ACTIVE.reset(token)
