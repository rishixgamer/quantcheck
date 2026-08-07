"""Exact Decimal arithmetic shared by Unit Drift contracts and detectors."""

from __future__ import annotations

from decimal import Decimal, localcontext

__all__ = ["decimal_divide", "symmetric_absolute_ratio"]


def decimal_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Divide with the project-wide deterministic 50-digit working precision."""
    if denominator == 0:
        raise ZeroDivisionError("Unit Drift ratios require a nonzero denominator")
    with localcontext() as context:
        context.prec = 50
        return numerator / denominator


def symmetric_absolute_ratio(left: Decimal, right: Decimal) -> Decimal:
    """Return ``max(abs(left/right), abs(right/left))`` for nonzero values."""
    if left == 0 or right == 0:
        raise ZeroDivisionError("Unit Drift ratios require two nonzero values")
    absolute_left = abs(left)
    absolute_right = abs(right)
    return max(
        decimal_divide(absolute_left, absolute_right),
        decimal_divide(absolute_right, absolute_left),
    )
