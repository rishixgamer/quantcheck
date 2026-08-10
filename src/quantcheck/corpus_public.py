"""The curated public source class for the v0.2 corpus.

A ``curated_public`` corpus unit is defined by *how it is read*, not by who
authored its bytes: it is an SEC EDGAR Company Facts envelope normalized by the
frozen :func:`quantcheck.sec_adapter.normalize_companyfacts`, under an explicit
taxonomy/concept/unit/form/date allowlist. That is the whole point of the source
class — the path from public disclosure bytes to canonical
:class:`~quantcheck.schemas.FinancialFact` records already exists and is frozen,
so admitting genuine public data later is a change of *bytes*, not of code.

**What ships today is a placeholder, and says so.** The envelope below is a
curated field-shape document in the real Company Facts contract, using real
``us-gaap`` concept names and real unit and form vocabularies, with placeholder
registrants and purpose-built values. No live SEC request has been made, and no
saved response is reproduced. :data:`CURATED_PUBLIC_IS_PLACEHOLDER` records this
in machine-readable form, every unit's
:class:`~quantcheck.corpus_schemas.CorpusProvenance` carries
``verbatim_source=False``, and the substitution procedure is documented in
``docs/CORPUS_V0_2.md``.

Substituting genuine bytes requires no change to this module beyond replacing
:func:`curated_public_envelope` with the saved response and updating the corpus
freeze record: the allowlist, the normalization path, the corpus contract, the
census, and every test stay exactly as they are.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext

from quantcheck.corpus_synthetic import cohort_entity_id
from quantcheck.json_types import canonical_decimal_string
from quantcheck.schemas import FinancialFact
from quantcheck.sec_adapter import (
    SecConceptSpec,
    SecNormalizationConfig,
    normalize_companyfacts,
)

__all__ = [
    "CURATED_PUBLIC_CONCEPTS",
    "CURATED_PUBLIC_IS_PLACEHOLDER",
    "CURATED_PUBLIC_PUBLISHER",
    "CURATED_PUBLIC_RETRIEVAL_METHOD",
    "CuratedPublicSpec",
    "companyfacts_json_bytes",
    "curated_public_cik",
    "curated_public_config",
    "curated_public_envelope",
    "curated_public_records",
]

#: ``True`` while the shipped envelope is a curated field-shape placeholder
#: rather than a saved live response. Provenance, the freeze record, and the
#: corpus documentation all read this rather than restating it in prose.
CURATED_PUBLIC_IS_PLACEHOLDER = True

CURATED_PUBLIC_PUBLISHER = "sec-edgar-companyfacts"
CURATED_PUBLIC_RETRIEVAL_METHOD = "in_package_curated_envelope"

#: The reviewed allowlist: real ``us-gaap`` concepts, real units, real period
#: shapes. Anything outside it is excluded by the frozen adapter rather than
#: guessed at.
CURATED_PUBLIC_CONCEPTS: tuple[tuple[str, str, str], ...] = (
    ("Assets", "USD", "instant"),
    ("Liabilities", "USD", "instant"),
    ("StockholdersEquity", "USD", "instant"),
    ("RevenueFromContractWithCustomerExcludingAssessedTax", "USD", "duration"),
    ("NetIncomeLoss", "USD", "duration"),
    ("EarningsPerShareDiluted", "USD/shares", "duration"),
)

_FORMS: tuple[str, ...] = ("10-K", "10-Q")
_FILED_FROM = date(2021, 1, 1)
_FILED_THROUGH = date(2025, 12, 31)
_PERIOD_COUNT = 12
_LAST_PERIOD_END = date(2024, 6, 30)


@dataclass(frozen=True, slots=True)
class CuratedPublicSpec:
    """One curated public document: a registrant, a lag, and a value scale."""

    registrant_key: str
    entity_name: str
    filing_lag_days: int
    scale: str

    def __post_init__(self) -> None:
        if self.filing_lag_days < 0:
            raise ValueError("a filing lag must not be negative")


def curated_public_cik(registrant_key: str) -> int:
    """A ten-digit CIK-shaped integer derived from the registrant key.

    Derived rather than chosen, for the same reason synthetic entity ids are:
    a hash carries no ordering a reader could decode back into a partition.
    """
    return int(cohort_entity_id(registrant_key).removeprefix("CIK"))


def _quarter_ends() -> tuple[date, ...]:
    """The twelve calendar-quarter ends up to :data:`_LAST_PERIOD_END`, oldest first."""
    ends: list[date] = []
    year, month = _LAST_PERIOD_END.year, _LAST_PERIOD_END.month
    for _ in range(_PERIOD_COUNT):
        ends.append(
            date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        )
        total = year * 12 + (month - 1) - 3
        year, month = total // 12, total % 12 + 1
    return tuple(reversed(ends))


def _quarter_start(period_end: date) -> date:
    total = period_end.year * 12 + (period_end.month - 1) - 2
    return date(total // 12, total % 12 + 1, 1)


_BASE_VALUES: dict[str, str] = {
    "Assets": "3120000000.00",
    "Liabilities": "1740000000.00",
    "StockholdersEquity": "1380000000.00",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "612000000.00",
    "NetIncomeLoss": "74500000.00",
    "EarningsPerShareDiluted": "0.91",
}
_GROWTH: dict[str, str] = {
    "Assets": "0.011",
    "Liabilities": "0.009",
    "StockholdersEquity": "0.013",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "0.023",
    "NetIncomeLoss": "0.018",
    "EarningsPerShareDiluted": "0.017",
}


def _value(concept: str, index: int, scale: Decimal) -> Decimal:
    quantum = Decimal("0.01")
    with localcontext() as context:
        context.prec = 50
        raw = (
            Decimal(_BASE_VALUES[concept])
            * scale
            * (Decimal(1) + Decimal(_GROWTH[concept])) ** index
        )
    value = raw.quantize(quantum)
    return value if value != 0 else quantum


def curated_public_config(spec: CuratedPublicSpec) -> SecNormalizationConfig:
    """The reviewed normalization allowlist for one curated public document."""
    return SecNormalizationConfig(
        cik=curated_public_cik(spec.registrant_key),
        concepts=tuple(
            SecConceptSpec(
                taxonomy="us-gaap",
                concept=concept,
                unit=unit,
                period_type=period_type,  # type: ignore[arg-type]
            )
            for concept, unit, period_type in CURATED_PUBLIC_CONCEPTS
        ),
        forms=_FORMS,
        filed_from=_FILED_FROM,
        filed_through=_FILED_THROUGH,
    )


def curated_public_envelope(spec: CuratedPublicSpec) -> dict[str, object]:
    """Build one curated Company Facts envelope.

    The document deliberately includes one ``dei`` concept and one unallowlisted
    ``us-gaap`` concept, so the frozen adapter's exclusion path is exercised by
    the corpus rather than only by the v0.1 adapter tests.
    """
    cik = curated_public_cik(spec.registrant_key)
    scale = Decimal(spec.scale)
    ends = _quarter_ends()
    us_gaap: dict[str, object] = {}
    for concept, unit, period_type in CURATED_PUBLIC_CONCEPTS:
        entries: list[dict[str, object]] = []
        for index, period_end in enumerate(ends):
            filed_on = period_end + timedelta(days=spec.filing_lag_days)
            entry: dict[str, object] = {
                "accn": f"{cik:010d}-{filed_on.year % 100:02d}-{index + 1:06d}",
                "end": period_end.isoformat(),
                "filed": filed_on.isoformat(),
                "form": "10-K" if (len(ends) - 1 - index) % 4 == 0 else "10-Q",
                "fy": period_end.year,
                "fp": f"Q{((period_end.month - 1) // 3) + 1}",
                "val": _value(concept, index, scale),
            }
            if period_type == "duration":
                entry["start"] = _quarter_start(period_end).isoformat()
            entries.append(entry)
        us_gaap[concept] = {
            "label": concept,
            "description": "Curated public field-shape entry; not a saved live response.",
            "units": {unit: entries},
        }

    us_gaap["OtherNonoperatingIncomeExpense"] = {
        "label": "Other Nonoperating Income (Expense)",
        "description": "Present but not allowlisted; the adapter must exclude it.",
        "units": {
            "USD": [
                {
                    "accn": f"{cik:010d}-24-000900",
                    "start": "2024-04-01",
                    "end": "2024-06-30",
                    "filed": "2024-08-05",
                    "form": "10-Q",
                    "val": Decimal("1250000.00"),
                }
            ]
        },
    }
    return {
        "cik": cik,
        "entityName": spec.entity_name,
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "label": "Entity Common Stock, Shares Outstanding",
                    "description": "Unsupported taxonomy; the adapter must exclude it.",
                    "units": {
                        "shares": [
                            {
                                "accn": f"{cik:010d}-24-000901",
                                "end": "2024-06-30",
                                "filed": "2024-08-05",
                                "form": "10-Q",
                                "val": 91000000,
                            }
                        ]
                    },
                }
            },
            "us-gaap": us_gaap,
        },
    }


def companyfacts_json_bytes(payload: object) -> bytes:
    """Serialize a Company Facts envelope the way SEC EDGAR actually emits one.

    This cannot use :func:`~quantcheck.serialization.canonical_json_bytes`: the
    canonical form encodes a ``Decimal`` as a JSON *string*, and the frozen
    adapter — correctly — refuses a quoted financial value. So the envelope is
    written with real JSON numbers, and the ``Decimal`` text is emitted exactly
    as its canonical string with no quotes and no float ever constructed.

    Object keys are sorted, so the bytes are deterministic.
    """
    if isinstance(payload, Mapping):
        members = ", ".join(
            f"{json.dumps(str(key))}: {companyfacts_json_bytes(item).decode()}"
            for key, item in sorted(payload.items(), key=lambda entry: str(entry[0]))
        )
        return f"{{{members}}}".encode()
    if isinstance(payload, bool):
        raise TypeError("a Company Facts envelope carries no boolean")
    if isinstance(payload, int):
        return str(payload).encode()
    if isinstance(payload, Decimal):
        return canonical_decimal_string(payload).encode()
    if isinstance(payload, str):
        return json.dumps(payload).encode()
    if isinstance(payload, Sequence):
        members = ", ".join(companyfacts_json_bytes(item).decode() for item in payload)
        return f"[{members}]".encode()
    raise TypeError(f"unsupported Company Facts value of type {type(payload).__name__}")


def curated_public_records(spec: CuratedPublicSpec) -> tuple[FinancialFact, ...]:
    """Normalize one curated public document through the frozen SEC adapter.

    Every record therefore carries ``available_on == filed_on``, no dimensions,
    a real Company Facts source locator, and a source row key minted by the
    frozen adapter — the same shape a genuine saved response would produce.
    """
    raw_bytes = companyfacts_json_bytes(curated_public_envelope(spec))
    result = normalize_companyfacts(raw_bytes, curated_public_config(spec))
    return result.records
