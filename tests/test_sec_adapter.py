"""CIK/configuration, normalization, provenance, fixture, and integration tests."""

from __future__ import annotations

import importlib.util
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

import quantcheck as q

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_FILE = REPO_ROOT / "tests" / "fixtures" / "sec_companyfacts_curated.json"
SCRIPT_FILE = REPO_ROOT / "scripts" / "generate_reviewed_sec_fixture.py"
TEST_EMAIL = "ops" + "@quantcheck.dev"
TEST_CONTACT_URL = "https:" + "//quantcheck.dev/contact"
USER_AGENT = f"QuantCheck Research {TEST_EMAIL}"


def _payload() -> dict[str, Any]:
    return cast(dict[str, Any], q.reviewed_sec_fixture_payload())


def _bytes(payload: dict[str, Any]) -> bytes:
    return q.canonical_json_bytes(payload)


def _asset_usd_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        payload["facts"]["us-gaap"]["Assets"]["units"]["USD"],
    )


def _revenue_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        payload["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"][
            "USD"
        ],
    )


def _result(raw: bytes | None = None) -> q.SecNormalizationResult:
    return q.normalize_companyfacts(
        raw if raw is not None else q.canonical_reviewed_sec_fixture_bytes(),
        q.reviewed_sec_normalization_config(),
    )


def _fetch_result(raw: bytes | None = None, *, from_cache: bool = False) -> q.SecFetchResult:
    content = raw if raw is not None else q.canonical_reviewed_sec_fixture_bytes()
    return q.SecFetchResult(
        canonical_cik=q.REVIEWED_SEC_CIK,
        url=q.companyfacts_url(q.REVIEWED_SEC_CIK),
        raw_sha256=q.sha256_hex_of_bytes(content),
        raw_bytes=content,
        from_cache=from_cache,
    )


# --- Client configuration and CIK --------------------------------------------


def test_valid_user_agent_with_email_or_url_is_accepted(tmp_path: Path) -> None:
    email = q.SecClientConfig(user_agent=USER_AGENT, cache_dir=tmp_path)
    url = q.SecClientConfig(
        user_agent=f"QuantCheck Research {TEST_CONTACT_URL}",
        cache_dir=tmp_path,
    )
    assert email.user_agent == USER_AGENT
    assert url.user_agent.endswith("/contact")


@pytest.mark.parametrize(
    "user_agent",
    [
        "",
        "   ",
        "QuantCheck",
        TEST_EMAIL,
        "Sample Company Name AdminContact" + "@example.com",
        "QuantCheck <your-email" + "@company.com>",
        "QuantCheck http:" + "//localhost/contact",
    ],
)
def test_missing_blank_placeholder_or_identity_free_user_agent_is_rejected(
    user_agent: str,
    tmp_path: Path,
) -> None:
    with pytest.raises(q.SecConfigurationError):
        q.SecClientConfig(user_agent=user_agent, cache_dir=tmp_path)


def test_client_config_is_frozen(tmp_path: Path) -> None:
    config = q.SecClientConfig(user_agent=USER_AGENT, cache_dir=tmp_path)
    with pytest.raises(FrozenInstanceError):
        config.max_retries = 4  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeout_seconds", 0),
        ("timeout_seconds", float("inf")),
        ("minimum_interval_seconds", -0.1),
        ("backoff_seconds", -1),
        ("max_retry_after_seconds", -1),
        ("max_retries", -1),
        ("max_retries", 6),
        ("max_retries", True),
    ],
)
def test_timeout_pacing_and_retry_bounds_are_strict(
    field: str,
    value: object,
    tmp_path: Path,
) -> None:
    fields: dict[str, Any] = {
        "user_agent": USER_AGENT,
        "cache_dir": tmp_path,
        field: value,
    }
    with pytest.raises(q.SecConfigurationError):
        q.SecClientConfig(**fields)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (320193, "0000320193"),
        ("320193", "0000320193"),
        ("0000320193", "0000320193"),
        (1, "0000000001"),
    ],
)
def test_cik_normalization_is_canonical(source: object, expected: str) -> None:
    assert q.normalize_cik(source) == expected


@pytest.mark.parametrize(
    "source",
    [None, True, False, 0, -1, 10_000_000_000, "", "0", "-1", "+1", "1.0", " 1", "١"],
)
def test_malformed_zero_negative_overlong_or_ambiguous_cik_is_rejected(source: object) -> None:
    with pytest.raises(q.InvalidCikError):
        q.normalize_cik(source)


def test_companyfacts_endpoint_is_exact_and_deterministic() -> None:
    assert q.companyfacts_url(320193) == (
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"
    )
    assert q.companyfacts_url("0000320193") == q.companyfacts_url(320193)


def test_normalization_config_rejects_unknown_fields_and_duplicate_specs() -> None:
    with pytest.raises(TypeError):
        q.SecNormalizationConfig(  # type: ignore[call-arg]
            cik=320193,
            concepts=(),
            forms=("10-Q",),
            filed_from=date(2024, 1, 1),
            filed_through=date(2024, 12, 31),
            unknown=True,
        )
    spec = q.SecConceptSpec("us-gaap", "Assets", "USD", "instant")
    with pytest.raises(q.UnsupportedNormalizationInputError, match="unique"):
        q.SecNormalizationConfig(
            cik=320193,
            concepts=(spec, spec),
            forms=("10-Q",),
            filed_from=date(2024, 1, 1),
            filed_through=date(2024, 12, 31),
        )


def test_normalization_config_copies_and_canonicalizes_caller_sequences() -> None:
    concepts = [
        q.SecConceptSpec("us-gaap", "SalesRevenueNet", "USD", "duration"),
        q.SecConceptSpec("us-gaap", "Assets", "USD", "instant"),
    ]
    forms = ["10-Q", "10-K"]
    config = q.SecNormalizationConfig(
        cik=320193,
        concepts=concepts,
        forms=forms,
        filed_from=date(2022, 1, 1),
        filed_through=date(2024, 12, 31),
    )
    assert concepts[0].concept == "SalesRevenueNet"
    assert forms == ["10-Q", "10-K"]
    assert config.forms == ("10-K", "10-Q")
    assert config.concepts[0].concept == "Assets"


# --- Reviewed fixture and successful normalization ---------------------------


def test_checked_in_sec_fixture_matches_the_pure_factory() -> None:
    assert FIXTURE_FILE.read_bytes() == q.canonical_reviewed_sec_fixture_bytes()
    assert q.sha256_hex_of_bytes(FIXTURE_FILE.read_bytes()) == (
        "332a506af4ceef5cd9ebb17cb0c1f9f04805ca1535c44f0083e019992f73c2d9"
    )


def test_reviewed_fixture_has_seven_records_and_five_explicit_exclusions() -> None:
    result = _result()
    assert len(result.records) == q.EXPECTED_SEC_NORMALIZED_RECORD_COUNT == 7
    assert len(result.exclusions) == q.EXPECTED_SEC_EXCLUSION_COUNT == 5
    assert {item.reason for item in result.exclusions} == {
        "taxonomy_not_allowlisted",
        "concept_not_allowlisted",
        "unit_not_allowlisted",
        "form_not_allowlisted",
        "filed_before_range",
    }


def test_supported_instant_and_duration_facts_keep_exact_fields() -> None:
    result = _result()
    instant = next(record for record in result.records if record.concept == "Assets")
    duration = next(
        record
        for record in result.records
        if record.concept == "RevenueFromContractWithCustomerExcludingAssessedTax"
        and record.value < 0
    )
    assert instant.period_type == "instant" and instant.period_start is None
    assert duration.period_type == "duration"
    assert duration.period_start == date(2023, 12, 31)
    assert duration.period_end == date(2024, 3, 30)
    assert duration.value == Decimal("-25")
    assert duration.entity_id == "CIK0000320193"
    assert duration.entity_name == "Apple Inc."
    assert duration.concept_namespace == "us-gaap"
    assert duration.unit == "USD"
    assert duration.form == "10-Q"
    assert duration.accession_number == "0000320193-24-000069"


def test_json_decimal_lexeme_never_passes_through_binary_float() -> None:
    raw = q.canonical_reviewed_sec_fixture_bytes().replace(
        b"89498000000",
        b"89498000000.1250",
        1,
    )
    record = next(
        item for item in _result(raw).records if item.value == Decimal("89498000000.1250")
    )
    assert isinstance(record.value, Decimal)
    assert '"value":"89498000000.125"' in q.canonical_json_text(record)


def test_zero_negative_and_duplicate_looking_occurrences_are_preserved() -> None:
    records = _result().records
    assert any(record.value == 0 for record in records)
    assert any(record.value < 0 for record in records)
    duplicates = [
        record
        for record in records
        if record.concept == "Assets"
        and record.period_end == date(2023, 12, 31)
        and record.value == Decimal("352583000000")
    ]
    assert len(duplicates) == 2
    assert len({record.record_id for record in duplicates}) == 2
    assert len({record.source.source_row_key for record in duplicates}) == 2


def test_source_row_and_record_identities_are_exact_rebuild_values() -> None:
    records = _result().records
    assert [record.record_id for record in records] == [
        "rec_1218a57fee03e429",
        "rec_1be49369f852d1f0",
        "rec_323c5244eb16bc7f",
        "rec_423d02514b8d5133",
        "rec_4fc9ff4459f1bffe",
        "rec_7aa4be505e41ed38",
        "rec_94c49c529abf3634",
    ]
    assert [record.source.source_row_key for record in records] == [
        "srow_ba7e32a9c5ca64f1",
        "srow_9ec0cbb21a07aaeb",
        "srow_156e220cea0ae9a7",
        "srow_ca613dc2217fdf6e",
        "srow_7d9c859f47607ed4",
        "srow_d2bfc4a6ad277d29",
        "srow_02dcee3e2b7986b7",
    ]


def test_provenance_uses_endpoint_not_cache_or_runtime_paths() -> None:
    result = _result()
    expected_url = q.companyfacts_url(q.REVIEWED_SEC_CIK)
    for record in result.records:
        assert record.source.source_name == q.SEC_SOURCE_NAME
        assert record.source.source_locator == expected_url
        assert record.source.source_row_key.startswith("srow_")
        assert q.parse_declared_revision_lineage(record.source.source_row_key) is None
        assert record.available_on == record.filed_on
        assert record.dimensions == ()


def test_source_entry_and_mapping_reordering_do_not_change_logical_records() -> None:
    payload = _payload()
    entries = _asset_usd_entries(payload)
    entries.reverse()
    facts = payload["facts"]
    payload["facts"] = {key: facts[key] for key in reversed(tuple(facts))}
    reordered = _result(_bytes(payload))
    assert q.canonical_json_bytes(reordered.records) == q.canonical_json_bytes(_result().records)
    assert reordered.exclusions == _result().exclusions


def test_normalization_does_not_mutate_caller_owned_content() -> None:
    payload = _payload()
    before = q.canonical_json_bytes(payload)
    raw = _bytes(payload)
    _result(raw)
    assert q.canonical_json_bytes(payload) == before
    assert raw == before


# --- Explicit rejection of malformed allowlisted source data -----------------


@pytest.mark.parametrize("bad_value", [True, "1", None, [1]])
def test_boolean_string_null_or_collection_financial_value_is_rejected(
    bad_value: object,
) -> None:
    payload = _payload()
    _revenue_entries(payload)[0]["val"] = bad_value
    with pytest.raises(q.InvalidAllowlistedFactError, match="financial value|boolean"):
        _result(_bytes(payload))


def test_non_finite_json_value_is_rejected_before_normalization() -> None:
    raw = q.canonical_reviewed_sec_fixture_bytes().replace(b"89498000000", b"NaN", 1)
    with pytest.raises(q.InvalidCompanyFactsError, match="finite JSON"):
        _result(raw)


def test_missing_required_field_is_rejected_not_skipped() -> None:
    payload = _payload()
    del _revenue_entries(payload)[0]["end"]
    with pytest.raises(q.InvalidAllowlistedFactError, match="missing required"):
        _result(_bytes(payload))


def test_invalid_duration_order_is_rejected() -> None:
    payload = _payload()
    _revenue_entries(payload)[0]["start"] = "2024-01-01"
    _revenue_entries(payload)[0]["end"] = "2023-12-31"
    with pytest.raises(q.InvalidAllowlistedFactError, match="must not follow"):
        _result(_bytes(payload))


@pytest.mark.parametrize("field", ["segment", "dimensions", "custom"])
def test_unsupported_dimensions_segments_or_unknown_fields_are_rejected(field: str) -> None:
    payload = _payload()
    _revenue_entries(payload)[0][field] = {"axis": "Product", "member": "Phone"}
    with pytest.raises(q.InvalidAllowlistedFactError, match="unsupported fields"):
        _result(_bytes(payload))


def test_wrong_envelope_cik_and_unknown_top_level_fields_are_rejected() -> None:
    wrong = _payload()
    wrong["cik"] = 789019
    with pytest.raises(q.InvalidCompanyFactsError, match="does not match"):
        _result(_bytes(wrong))
    extra = _payload()
    extra["retrievedAt"] = "2026-08-06"
    with pytest.raises(q.InvalidCompanyFactsError, match="exactly"):
        _result(_bytes(extra))


def test_period_shape_outside_allowlist_is_explicitly_excluded() -> None:
    payload = _payload()
    _asset_usd_entries(payload)[0]["start"] = "2023-07-02"
    result = _result(_bytes(payload))
    assert "period_shape_not_allowlisted" in {item.reason for item in result.exclusions}
    assert len(result.records) == 6


# --- Existing point-in-time and audit integration ----------------------------


def test_normalized_facts_build_the_reviewed_snapshot_with_rebuild_identity() -> None:
    result = _result()
    assert q.canonical_sha256(result.records) == (
        "bc8e4c09c6421409a20f323ce4219f6a8b4ccf1bfa9db11f98e8ca3ac1a43bf2"
    )
    snapshot = q.build_sec_snapshot(
        result,
        dataset_name="sec-reviewed",
        as_of_date=date(2024, 12, 31),
    )
    assert len(snapshot.records) == 7
    assert snapshot.snapshot_id == "snap_1695316352716659"
    assert q.canonical_sha256(snapshot) == (
        "79dbe97de337d64ed9be1ee670e1bfea702d03ef7a6f3bca15f825106f17a68a"
    )
    assert q.dataset_snapshot_identity_matches(snapshot)


def test_filing_day_is_the_exact_existing_point_in_time_boundary() -> None:
    result = _result()
    target = next(record for record in result.records if record.filed_on == date(2024, 5, 3))
    before = q.build_sec_snapshot(
        result,
        dataset_name="sec-reviewed",
        as_of_date=date(2024, 5, 2),
    )
    same_day = q.build_sec_snapshot(
        result,
        dataset_name="sec-reviewed",
        as_of_date=date(2024, 5, 3),
    )
    assert target.record_id not in {record.record_id for record in before.records}
    assert target.record_id in {record.record_id for record in same_day.records}


def test_audit_boundary_retains_safe_sec_provenance_and_drops_source_rows() -> None:
    snapshot = q.build_sec_snapshot(
        _result(),
        dataset_name="sec-reviewed",
        as_of_date=date(2024, 12, 31),
    )
    audit = q.sanitize_for_audit(snapshot)
    assert all(record.source_name == q.SEC_SOURCE_NAME for record in audit.records)
    assert all(record.source_locator == q.companyfacts_url(320193) for record in audit.records)
    data = q.canonical_json_bytes(audit)
    assert b"source_row_key" not in data
    assert b"srow_" not in data
    assert b"frame" not in data and b'"fy"' not in data and b'"fp"' not in data
    assert audit.audit_input_id == "audit_2076ec17a9143e61"
    assert q.canonical_sha256(audit) == (
        "b251d53bd880cf8b80c554fdb0879304f3f3cb5ff1232698b9ff5b082201435b"
    )
    assert q.audit_input_snapshot_identity_matches(audit)


def test_adapter_build_snapshot_uses_the_same_normalization_and_engine(tmp_path: Path) -> None:
    adapter = q.SecCompanyFactsAdapter(q.SecClientConfig(user_agent=USER_AGENT, cache_dir=tmp_path))
    snapshot = adapter.build_snapshot(
        _fetch_result(),
        q.reviewed_sec_normalization_config(),
        dataset_name="sec-reviewed",
        as_of_date=date(2024, 12, 31),
    )
    assert snapshot == q.build_sec_snapshot(
        _result(), dataset_name="sec-reviewed", as_of_date=date(2024, 12, 31)
    )


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sec_fixture_script", SCRIPT_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sec_fixture_script_check_and_write_modes(tmp_path: Path) -> None:
    module = _load_script()
    assert module.main(["--check"]) == 0
    module.FIXTURE_PATH = tmp_path / "nested" / "sec.json"  # type: ignore[attr-defined]
    assert module.main(["--check"]) == 1
    assert module.main([]) == 0
    assert module.main(["--check"]) == 0
    assert module.FIXTURE_PATH.read_bytes() == q.canonical_reviewed_sec_fixture_bytes()
