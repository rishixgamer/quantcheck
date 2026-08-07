"""Pure reviewed field-shape fixture for the narrow SEC adapter.

The fixture is a curated public-shape example, not a verbatim response and
not evidence of a live SEC request.  It uses the public Apple CIK and standard
taxonomy names solely to exercise the documented Company Facts envelope.
"""

from __future__ import annotations

from datetime import date

from quantcheck.sec_adapter import SecConceptSpec, SecNormalizationConfig
from quantcheck.serialization import canonical_json_bytes

__all__ = [
    "EXPECTED_SEC_EXCLUSION_COUNT",
    "EXPECTED_SEC_NORMALIZED_RECORD_COUNT",
    "EXPECTED_SEC_RAW_ENTRY_COUNT",
    "REVIEWED_SEC_CIK",
    "REVIEWED_SEC_FIXTURE_NAME",
    "REVIEWED_SEC_FIXTURE_SPEC_VERSION",
    "canonical_reviewed_sec_fixture_bytes",
    "reviewed_sec_fixture_payload",
    "reviewed_sec_normalization_config",
]

REVIEWED_SEC_CIK = "0000320193"
REVIEWED_SEC_FIXTURE_NAME = "quantcheck-curated-sec-companyfacts-field-shapes"
REVIEWED_SEC_FIXTURE_SPEC_VERSION = "quantcheck/sec-companyfacts-fixture/v1"
EXPECTED_SEC_RAW_ENTRY_COUNT = 12
EXPECTED_SEC_NORMALIZED_RECORD_COUNT = 7
EXPECTED_SEC_EXCLUSION_COUNT = 5


def reviewed_sec_fixture_payload() -> dict[str, object]:
    """Return the deterministic 12-entry curated Company Facts envelope."""
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "dei": {
                "EntityPublicFloat": {
                    "description": "Unsupported taxonomy example.",
                    "label": "Entity Public Float",
                    "units": {
                        "USD": [
                            {
                                "accn": "0000320193-23-000077",
                                "end": "2023-09-30",
                                "filed": "2023-11-03",
                                "form": "10-Q",
                                "fp": "Q3",
                                "fy": 2023,
                                "val": 1,
                            }
                        ]
                    },
                }
            },
            "us-gaap": {
                "Assets": {
                    "description": "Instant fact examples and filter controls.",
                    "label": "Assets",
                    "units": {
                        "EUR": [
                            {
                                "accn": "0000320193-23-000106",
                                "end": "2023-12-31",
                                "filed": "2024-02-02",
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2023,
                                "val": 3,
                            }
                        ],
                        "USD": [
                            {
                                "accn": "0000320193-23-000077",
                                "end": "2023-09-30",
                                "filed": "2023-11-03",
                                "form": "10-Q",
                                "fp": "Q3",
                                "frame": "CY2023Q3I",
                                "fy": 2023,
                                "val": 0,
                            },
                            {
                                "accn": "0000320193-23-000106",
                                "end": "2023-12-31",
                                "filed": "2024-02-02",
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2023,
                                "val": 352583000000,
                            },
                            {
                                "accn": "0000320193-23-000106",
                                "end": "2023-12-31",
                                "filed": "2024-02-02",
                                "form": "10-K",
                                "fp": "FY",
                                "frame": "CY2023Q4I",
                                "fy": 2023,
                                "val": 352583000000,
                            },
                            {
                                "accn": "0000320193-24-000001",
                                "end": "2024-01-15",
                                "filed": "2024-01-16",
                                "form": "8-K",
                                "fp": "Q1",
                                "fy": 2024,
                                "val": 4,
                            },
                            {
                                "accn": "0000320193-21-000105",
                                "end": "2021-09-25",
                                "filed": "2021-10-29",
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2021,
                                "val": 5,
                            },
                        ],
                    },
                },
                "GrossProfit": {
                    "description": "Unsupported concept example.",
                    "label": "Gross Profit",
                    "units": {
                        "USD": [
                            {
                                "accn": "0000320193-23-000077",
                                "end": "2023-09-30",
                                "filed": "2023-11-03",
                                "form": "10-Q",
                                "fp": "Q3",
                                "fy": 2023,
                                "start": "2023-07-02",
                                "val": 6,
                            }
                        ]
                    },
                },
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "description": "Duration examples including zero and negative values.",
                    "label": "Revenue",
                    "units": {
                        "USD": [
                            {
                                "accn": "0000320193-23-000077",
                                "end": "2023-09-30",
                                "filed": "2023-11-03",
                                "form": "10-Q",
                                "fp": "Q3",
                                "frame": "CY2023Q3",
                                "fy": 2023,
                                "start": "2023-07-02",
                                "val": 89498000000,
                            },
                            {
                                "accn": "0000320193-23-000106",
                                "end": "2023-12-31",
                                "filed": "2024-02-02",
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2023,
                                "start": "2023-10-01",
                                "val": 0,
                            },
                            {
                                "accn": "0000320193-24-000069",
                                "end": "2024-03-30",
                                "filed": "2024-05-03",
                                "form": "10-Q",
                                "fp": "Q2",
                                "fy": 2024,
                                "start": "2023-12-31",
                                "val": -25,
                            },
                        ]
                    },
                },
                "SalesRevenueNet": {
                    "description": "Alternative explicitly allowlisted revenue concept.",
                    "label": "Sales Revenue Net",
                    "units": {
                        "USD": [
                            {
                                "accn": "0000320193-22-000108",
                                "end": "2022-09-24",
                                "filed": "2022-10-28",
                                "form": "10-K",
                                "fp": "FY",
                                "fy": 2022,
                                "start": "2021-09-26",
                                "val": 394328000000,
                            }
                        ]
                    },
                },
            },
        },
    }


def canonical_reviewed_sec_fixture_bytes() -> bytes:
    """Return the exact checked-in curated response bytes."""
    return canonical_json_bytes(reviewed_sec_fixture_payload())


def reviewed_sec_normalization_config() -> SecNormalizationConfig:
    """Return the exact allowlist reviewed with this field-shape fixture."""
    return SecNormalizationConfig(
        cik=REVIEWED_SEC_CIK,
        concepts=(
            SecConceptSpec("us-gaap", "Assets", "USD", "instant"),
            SecConceptSpec(
                "us-gaap",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "USD",
                "duration",
            ),
            SecConceptSpec("us-gaap", "SalesRevenueNet", "USD", "duration"),
        ),
        forms=("10-K", "10-Q"),
        filed_from=date(2022, 1, 1),
        filed_through=date(2024, 12, 31),
    )
