"""Single authorization primitive for the complete Missing Observations holdout."""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

__all__ = [
    "MissingObservationHeldoutAuthorization",
    "MissingObservationHeldoutAuthorizationError",
    "active_missing_observation_heldout_authorization",
    "heldout_missing_observation_cases",
    "missing_observation_heldout_case_authorized",
]

_FREEZE_ID_PATTERN = re.compile(r"^mefreeze_[0-9a-f]{16}$")
_CASE_ID_PATTERN = re.compile(r"^mcase_[0-9a-f]{16}$")


class MissingObservationHeldoutAuthorizationError(RuntimeError):
    """Raised when held-out authorization is malformed or nested."""


@dataclass(frozen=True, slots=True)
class MissingObservationHeldoutAuthorization:
    freeze_id: str
    case_ids: tuple[str, ...]

    def permits(self, case_id: str) -> bool:
        return case_id in self.case_ids


_ACTIVE: ContextVar[MissingObservationHeldoutAuthorization | None] = ContextVar(
    "quantcheck_missing_observation_heldout_authorization", default=None
)


def active_missing_observation_heldout_authorization() -> (
    MissingObservationHeldoutAuthorization | None
):
    return _ACTIVE.get()


def missing_observation_heldout_case_authorized(case_id: str) -> bool:
    authorization = _ACTIVE.get()
    return authorization is not None and authorization.permits(case_id)


def _validate_case_ids(case_ids: Sequence[str]) -> tuple[str, ...]:
    if isinstance(case_ids, str | bytes):
        raise MissingObservationHeldoutAuthorizationError(
            "held-out case ids must be a sequence of strings"
        )
    values = tuple(case_ids)
    if not values:
        raise MissingObservationHeldoutAuthorizationError("the held-out case set must not be empty")
    if any(
        not isinstance(value, str) or _CASE_ID_PATTERN.fullmatch(value) is None for value in values
    ):
        raise MissingObservationHeldoutAuthorizationError("malformed held-out case id")
    if len(set(values)) != len(values):
        raise MissingObservationHeldoutAuthorizationError(
            "held-out case ids must not contain duplicates"
        )
    return tuple(sorted(values))


@contextmanager
def heldout_missing_observation_cases(
    *, freeze_id: str, case_ids: Sequence[str]
) -> Iterator[MissingObservationHeldoutAuthorization]:
    """Authorize exactly one declared complete holdout for one scoped block."""
    if not isinstance(freeze_id, str) or _FREEZE_ID_PATTERN.fullmatch(freeze_id) is None:
        raise MissingObservationHeldoutAuthorizationError(
            "held-out evaluation requires a frozen configuration identity"
        )
    if _ACTIVE.get() is not None:
        raise MissingObservationHeldoutAuthorizationError(
            "held-out Missing Observations authorization is already active"
        )
    authorization = MissingObservationHeldoutAuthorization(
        freeze_id=freeze_id,
        case_ids=_validate_case_ids(case_ids),
    )
    token = _ACTIVE.set(authorization)
    try:
        yield authorization
    finally:
        _ACTIVE.reset(token)
