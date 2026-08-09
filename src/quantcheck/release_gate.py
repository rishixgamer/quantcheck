"""The single, narrow authorization primitive for reserved final seeds.

Reserved final seeds ``1000-1009`` are held-out release evidence. Every
ordinary interface rejects them, and this module is the only thing in the
package that can lift that rejection.

The design goals, in order:

1. **It cannot authorize an arbitrary seed.** :func:`reserved_final_seeds`
   accepts exactly one seed set — the complete reserved partition — and
   nothing else. A subset, a superset, a duplicate, a re-ordered mix with a
   development seed, or a seed one past either end is refused.
2. **It cannot be entered by accident.** Activation is a context manager, so
   the permission is scoped to a ``with`` block and is removed on the way out
   even if the block raises.
3. **It cannot leak into ordinary execution.** The permission lives in a
   :class:`~contextvars.ContextVar`, so it is per-context and never a global
   flag another thread, task, or later call can observe.
4. **It cannot be reached from the CLI.** No command, flag, or environment
   variable references this module; ``scripts/`` and the release modules are
   the only callers, and a static test asserts that.

This module deliberately imports nothing from ``quantcheck``. ``schemas.py``
consults :func:`final_seed_authorized`, so the dependency has to point this
way to stay acyclic, and keeping it standard-library-only means the gate has
no way to be influenced by anything the rest of the package does.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

__all__ = [
    "RESERVED_FINAL_SEEDS",
    "FinalSeedAuthorization",
    "FinalSeedAuthorizationError",
    "active_final_seed_authorization",
    "final_seed_authorized",
    "reserved_final_seeds",
]

#: The complete reserved final/release seed partition, in ascending order.
#: This is the *only* seed set :func:`reserved_final_seeds` will authorize.
#: It duplicates no value: ``schemas.FINAL_SEED_RANGE`` is built from it.
RESERVED_FINAL_SEEDS: tuple[int, ...] = tuple(range(1000, 1010))

_RESERVED_SET = frozenset(RESERVED_FINAL_SEEDS)


class FinalSeedAuthorizationError(RuntimeError):
    """Raised when final-seed authorization is requested incorrectly."""


@dataclass(frozen=True, slots=True)
class FinalSeedAuthorization:
    """One active authorization to construct reserved-final-seed cases.

    ``release_candidate_id`` records *which* frozen release candidate the
    permission was opened for, so an authorization can never be anonymous.
    ``seeds`` is always the complete reserved partition; it is stored rather
    than assumed so a caller reading the active authorization sees the exact
    set that was permitted.
    """

    release_candidate_id: str
    seeds: tuple[int, ...]

    def permits(self, seed: int) -> bool:
        """Report whether this authorization covers one seed."""
        return seed in self.seeds


_ACTIVE: ContextVar[FinalSeedAuthorization | None] = ContextVar(
    "quantcheck_final_seed_authorization", default=None
)


def active_final_seed_authorization() -> FinalSeedAuthorization | None:
    """Return the authorization active in this context, if any."""
    return _ACTIVE.get()


def final_seed_authorized(seed: int) -> bool:
    """Report whether one reserved final seed is authorized right now.

    ``schemas.py`` calls this, and only this, to decide whether a reserved
    seed may be represented. With no active authorization it always answers
    ``False``, which is what keeps every ordinary interface closed.
    """
    authorization = _ACTIVE.get()
    if authorization is None:
        return False
    return authorization.permits(seed)


def _validate_partition(seeds: Sequence[int]) -> tuple[int, ...]:
    """Accept exactly the complete reserved partition, or refuse.

    Every rejection below is a distinct way a caller could try to smuggle a
    seed through, so each is checked separately rather than collapsed into one
    set comparison — a set comparison alone would silently accept duplicates.
    """
    if isinstance(seeds, (str, bytes)):
        raise FinalSeedAuthorizationError("final seeds must be a sequence of integers")
    values = tuple(seeds)
    for seed in values:
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise FinalSeedAuthorizationError(
                f"final seeds must be integers, got {type(seed).__name__}"
            )
    if len(set(values)) != len(values):
        raise FinalSeedAuthorizationError("the final seed partition must not contain duplicates")
    unreserved = sorted(set(values) - _RESERVED_SET)
    if unreserved:
        raise FinalSeedAuthorizationError(
            f"only reserved final seeds may be authorized; refused: {unreserved}"
        )
    missing = sorted(_RESERVED_SET - set(values))
    if missing:
        raise FinalSeedAuthorizationError(
            "the complete reserved final seed partition must be authorized at once; "
            f"missing: {missing}"
        )
    return tuple(sorted(values))


@contextmanager
def reserved_final_seeds(
    *,
    release_candidate_id: str,
    seeds: Sequence[int],
) -> Iterator[FinalSeedAuthorization]:
    """Authorize the complete reserved final seed partition for this block.

    This lifts the reserved-seed rejection in ``schemas.py`` for the duration
    of the ``with`` block, and for nothing else. It grants no other permission:
    unclassified seeds stay unclassified, immutable artifacts stay immutable,
    and no detector gains manifest access.

    Nesting is refused rather than counted, because a nested authorization
    would mean two release candidates are open at once and the inner one would
    silently win.
    """
    if not isinstance(release_candidate_id, str) or not release_candidate_id:
        raise FinalSeedAuthorizationError(
            "final-seed authorization requires a frozen release candidate identifier"
        )
    if _ACTIVE.get() is not None:
        raise FinalSeedAuthorizationError("final-seed authorization is already active")
    authorization = FinalSeedAuthorization(
        release_candidate_id=release_candidate_id,
        seeds=_validate_partition(seeds),
    )
    token = _ACTIVE.set(authorization)
    try:
        yield authorization
    finally:
        _ACTIVE.reset(token)
