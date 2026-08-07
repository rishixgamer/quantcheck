"""Shared builders for QuantCheck contract-layer tests.

These are small hand-written examples, not fixture generation. Deterministic
fixture infrastructure belongs to a later milestone.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from quantcheck.schemas import (
    AuditInputRecord,
    Dimension,
    FinancialFact,
    SourceReference,
)


def source_reference(row_key: str = "row-1") -> SourceReference:
    return SourceReference(
        source_name="reviewed-fixture",
        source_locator="fixture-0001",
        source_row_key=row_key,
    )


def financial_fact(**overrides: Any) -> FinancialFact:
    """Build a valid duration-period fact, overriding any field by keyword."""
    fields: dict[str, Any] = {
        "record_id": "rec_0123456789abcdef",
        "entity_id": "CIK0000320193",
        "entity_name": "Example Corporation",
        "concept_namespace": "us-gaap",
        "concept": "Revenues",
        "value": Decimal("1234567.8900"),
        "unit": "USD",
        "dimensions": (
            Dimension(axis="Segment", member="Total"),
            Dimension(axis="Region", member="US"),
        ),
        "period_type": "duration",
        "period_start": date(2024, 1, 1),
        "period_end": date(2024, 3, 31),
        "filed_on": date(2024, 5, 2),
        "available_on": date(2024, 5, 2),
        "form": "10-Q",
        "accession_number": "0000320193-24-000069",
        "source": source_reference(),
    }
    fields.update(overrides)
    return FinancialFact(**fields)


def audit_input_record(**overrides: Any) -> AuditInputRecord:
    """Build a valid sanitized audit-input record."""
    fields: dict[str, Any] = {
        "record_id": "rec_0123456789abcdef",
        "entity_id": "CIK0000320193",
        "concept_namespace": "us-gaap",
        "concept": "Revenues",
        "value": Decimal("1234567.8900"),
        "unit": "USD",
        "dimensions": (Dimension(axis="Region", member="US"),),
        "period_type": "duration",
        "period_start": date(2024, 1, 1),
        "period_end": date(2024, 3, 31),
        "filed_on": date(2024, 5, 2),
        "available_on": date(2024, 5, 2),
        "form": "10-Q",
        "accession_number": "0000320193-24-000069",
        "source_name": "reviewed-fixture",
        "source_locator": "fixture-0001",
    }
    fields.update(overrides)
    return AuditInputRecord(**fields)
