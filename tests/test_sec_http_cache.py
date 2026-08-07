"""Hermetic HTTPX request, retry, pacing, and exact-byte cache tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import httpx
import pytest

import quantcheck as q

USER_AGENT = "QuantCheck Research " + "ops" + "@quantcheck.dev"


def _config(cache_dir: Path, **overrides: Any) -> q.SecClientConfig:
    fields: dict[str, Any] = {
        "user_agent": USER_AGENT,
        "cache_dir": cache_dir,
        "timeout_seconds": 2.5,
        "minimum_interval_seconds": 0.2,
        "max_retries": 2,
        "backoff_seconds": 0.5,
        "max_retry_after_seconds": 5,
    }
    fields.update(overrides)
    return q.SecClientConfig(**fields)


def _adapter(
    cache_dir: Path,
    handler: Callable[[httpx.Request], httpx.Response],
    **kwargs: Any,
) -> q.SecCompanyFactsAdapter:
    return q.SecCompanyFactsAdapter(
        _config(cache_dir, **kwargs.pop("config_overrides", {})),
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def _accepted_path(cache_dir: Path) -> Path:
    return cache_dir / "companyfacts" / "CIK0000320193" / "accepted.json"


def _metadata(cache_dir: Path) -> dict[str, str]:
    parsed = q.parse_canonical_json(_accepted_path(cache_dir).read_bytes())
    assert isinstance(parsed, dict)
    assert all(isinstance(value, str) for value in parsed.values())
    return dict(cast(dict[str, str], parsed))


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


# --- HTTP requests, retry, and pacing ----------------------------------------


def test_success_uses_exact_url_user_agent_accept_header_and_timeout(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=q.canonical_reviewed_sec_fixture_bytes())

    result = _adapter(tmp_path, handler).fetch(320193)
    assert len(seen) == 1
    request = seen[0]
    assert str(request.url) == q.companyfacts_url(320193)
    assert request.headers["User-Agent"] == USER_AGENT
    assert request.headers["Accept"] == "application/json"
    assert request.extensions["timeout"] == {
        "connect": 2.5,
        "read": 2.5,
        "write": 2.5,
        "pool": 2.5,
    }
    assert result.raw_bytes == q.canonical_reviewed_sec_fixture_bytes()
    assert not result.from_cache


def test_transport_failure_retries_are_bounded_and_preserve_cause(tmp_path: Path) -> None:
    requests = 0
    clock = _Clock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        raise httpx.ConnectError("offline", request=request)

    adapter = _adapter(tmp_path, handler, sleeper=clock.sleep, monotonic=clock.monotonic)
    with pytest.raises(q.SecTransportError) as raised:
        adapter.fetch(320193)
    assert requests == 3
    assert isinstance(raised.value.__cause__, httpx.ConnectError)
    assert clock.sleeps == [0.5, 1.0]


def test_nonretryable_http_response_fails_once_with_http_cause(tmp_path: Path) -> None:
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(404)

    with pytest.raises(q.SecHttpError) as raised:
        _adapter(tmp_path, handler).fetch(320193)
    assert requests == 1
    assert raised.value.status_code == 404
    assert raised.value.attempts == 1
    assert isinstance(raised.value.__cause__, httpx.HTTPStatusError)


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_approved_transient_responses_retry_then_succeed(status: int, tmp_path: Path) -> None:
    responses = 0
    clock = _Clock()

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal responses
        responses += 1
        if responses == 1:
            return httpx.Response(status, headers={"Retry-After": "1"})
        return httpx.Response(200, content=q.canonical_reviewed_sec_fixture_bytes())

    result = _adapter(
        tmp_path,
        handler,
        sleeper=clock.sleep,
        monotonic=clock.monotonic,
    ).fetch(320193)
    assert responses == 2
    assert clock.sleeps == [1.0]
    assert result.raw_bytes == q.canonical_reviewed_sec_fixture_bytes()


def test_retry_exhaustion_reports_attempt_count_and_preserves_cause(tmp_path: Path) -> None:
    requests = 0
    clock = _Clock()

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(503)

    with pytest.raises(q.SecRetryExhaustedError) as raised:
        _adapter(
            tmp_path,
            handler,
            sleeper=clock.sleep,
            monotonic=clock.monotonic,
        ).fetch(320193)
    assert requests == 3
    assert raised.value.attempts == 3
    assert isinstance(raised.value.__cause__, httpx.HTTPStatusError)


@pytest.mark.parametrize("retry_after", ["Wed, 21 Oct 2015 07:28:00 GMT", "1.5", "-1", "6"])
def test_invalid_or_unsupported_retry_after_uses_deterministic_backoff(
    retry_after: str,
    tmp_path: Path,
) -> None:
    requests = 0
    clock = _Clock()

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(429, headers={"Retry-After": retry_after})
        return httpx.Response(200, content=q.canonical_reviewed_sec_fixture_bytes())

    _adapter(
        tmp_path,
        handler,
        sleeper=clock.sleep,
        monotonic=clock.monotonic,
    ).fetch(320193)
    assert clock.sleeps == [0.5]


def test_zero_retry_after_is_a_valid_delay_seconds_form(tmp_path: Path) -> None:
    requests = 0
    clock = _Clock()

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, content=q.canonical_reviewed_sec_fixture_bytes())

    _adapter(
        tmp_path,
        handler,
        sleeper=clock.sleep,
        monotonic=clock.monotonic,
    ).fetch(320193)
    assert clock.sleeps == [0.2]


def test_sequential_refreshes_are_paced_with_injected_clock(tmp_path: Path) -> None:
    requests = 0
    clock = _Clock()

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, content=q.canonical_reviewed_sec_fixture_bytes())

    adapter = _adapter(tmp_path, handler, sleeper=clock.sleep, monotonic=clock.monotonic)
    adapter.fetch(320193, refresh=True)
    adapter.fetch(320193, refresh=True)
    assert requests == 2
    assert clock.sleeps == [0.2]


def test_malformed_successful_body_is_not_retried(tmp_path: Path) -> None:
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, content=b"not-json")

    with pytest.raises(q.InvalidCompanyFactsError):
        _adapter(tmp_path, handler).fetch(320193)
    assert requests == 1


# --- Cache-first and offline replay ------------------------------------------


def test_exact_raw_bytes_determine_digest_filename_and_accepted_pointer(tmp_path: Path) -> None:
    raw = q.canonical_reviewed_sec_fixture_bytes()
    result = q.SecRawCache(tmp_path).accept(320193, url=q.companyfacts_url(320193), raw_bytes=raw)
    digest = q.sha256_hex_of_bytes(raw)
    metadata = _metadata(tmp_path)
    assert result.raw_sha256 == digest
    assert metadata == {
        "canonical_cik": "0000320193",
        "raw_filename": f"raw-{digest}.json",
        "raw_sha256": digest,
        "schema_version": q.COMPANY_FACTS_CACHE_SCHEMA_VERSION,
        "url": q.companyfacts_url(320193),
    }
    raw_path = _accepted_path(tmp_path).parent / f"raw-{digest}.json"
    assert raw_path.read_bytes() == raw


def test_cache_hit_avoids_a_redundant_request(tmp_path: Path) -> None:
    requests = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, content=q.canonical_reviewed_sec_fixture_bytes())

    adapter = _adapter(tmp_path, handler)
    first = adapter.fetch(320193)
    second = adapter.fetch(320193)
    assert requests == 1
    assert not first.from_cache and second.from_cache
    assert first.raw_bytes == second.raw_bytes


def test_offline_replay_makes_no_network_call(tmp_path: Path) -> None:
    cache = q.SecRawCache(tmp_path)
    cache.accept(
        320193,
        url=q.companyfacts_url(320193),
        raw_bytes=q.canonical_reviewed_sec_fixture_bytes(),
    )

    def forbidden(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("offline replay attempted network access")

    replayed = _adapter(tmp_path, forbidden).replay(320193)
    assert replayed.from_cache


def test_missing_offline_cache_is_explicit(tmp_path: Path) -> None:
    with pytest.raises(q.SecCacheMissError):
        q.SecRawCache(tmp_path).load(320193)


def test_identical_cache_write_is_idempotent(tmp_path: Path) -> None:
    cache = q.SecRawCache(tmp_path)
    raw = q.canonical_reviewed_sec_fixture_bytes()
    cache.accept(320193, url=q.companyfacts_url(320193), raw_bytes=raw)
    pointer_before = _accepted_path(tmp_path).read_bytes()
    cache.accept(320193, url=q.companyfacts_url(320193), raw_bytes=raw)
    assert _accepted_path(tmp_path).read_bytes() == pointer_before
    assert len(list(_accepted_path(tmp_path).parent.glob("raw-*.json"))) == 1


def test_missing_raw_file_and_hash_mismatch_are_rejected(tmp_path: Path) -> None:
    cache = q.SecRawCache(tmp_path)
    raw = q.canonical_reviewed_sec_fixture_bytes()
    cache.accept(320193, url=q.companyfacts_url(320193), raw_bytes=raw)
    raw_path = _accepted_path(tmp_path).parent / _metadata(tmp_path)["raw_filename"]
    raw_path.unlink()
    with pytest.raises(q.SecCacheIntegrityError, match="missing"):
        cache.load(320193)

    cache.accept(320193, url=q.companyfacts_url(320193), raw_bytes=raw)
    raw_path.write_bytes(b"corrupted")
    with pytest.raises(q.SecCacheIntegrityError, match="hash"):
        cache.load(320193)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "other", "schema"),
        ("canonical_cik", "0000789019", "wrong CIK"),
        ("url", "https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json", "wrong"),
        ("raw_sha256", "z" * 64, "digest"),
        ("raw_filename", "../../escape.json", "filename"),
    ],
)
def test_invalid_accepted_metadata_is_rejected(
    field: str,
    value: str,
    message: str,
    tmp_path: Path,
) -> None:
    cache = q.SecRawCache(tmp_path)
    cache.accept(
        320193,
        url=q.companyfacts_url(320193),
        raw_bytes=q.canonical_reviewed_sec_fixture_bytes(),
    )
    metadata = _metadata(tmp_path)
    metadata[field] = value
    _accepted_path(tmp_path).write_bytes(q.canonical_json_bytes(metadata))
    with pytest.raises(q.SecCacheIntegrityError, match=message):
        cache.load(320193)


def test_extra_noncanonical_or_invalid_json_pointer_is_rejected(tmp_path: Path) -> None:
    cache = q.SecRawCache(tmp_path)
    cache.accept(
        320193,
        url=q.companyfacts_url(320193),
        raw_bytes=q.canonical_reviewed_sec_fixture_bytes(),
    )
    metadata = _metadata(tmp_path)
    metadata["extra"] = "no"
    _accepted_path(tmp_path).write_bytes(q.canonical_json_bytes(metadata))
    with pytest.raises(q.SecCacheIntegrityError, match="fields"):
        cache.load(320193)
    _accepted_path(tmp_path).write_bytes(b"not-json")
    with pytest.raises(q.SecCacheIntegrityError, match="canonical JSON"):
        cache.load(320193)


def test_invalid_json_or_wrong_envelope_with_matching_digest_is_rejected(tmp_path: Path) -> None:
    entity_dir = _accepted_path(tmp_path).parent
    entity_dir.mkdir(parents=True)
    for raw in (b"not-json", b'{"cik":320193,"entityName":"Apple Inc.","facts":[],"x":1}'):
        digest = q.sha256_hex_of_bytes(raw)
        filename = f"raw-{digest}.json"
        (entity_dir / filename).write_bytes(raw)
        _accepted_path(tmp_path).write_bytes(
            q.canonical_json_bytes(
                {
                    "canonical_cik": "0000320193",
                    "raw_filename": filename,
                    "raw_sha256": digest,
                    "schema_version": q.COMPANY_FACTS_CACHE_SCHEMA_VERSION,
                    "url": q.companyfacts_url(320193),
                }
            )
        )
        with pytest.raises(q.SecCacheIntegrityError, match="Company Facts"):
            q.SecRawCache(tmp_path).load(320193)


def test_conflicting_immutable_content_is_never_overwritten(tmp_path: Path) -> None:
    raw = q.canonical_reviewed_sec_fixture_bytes()
    digest = q.sha256_hex_of_bytes(raw)
    entity_dir = _accepted_path(tmp_path).parent
    entity_dir.mkdir(parents=True)
    target = entity_dir / f"raw-{digest}.json"
    target.write_bytes(b"conflict")
    with pytest.raises(q.SecCacheIntegrityError, match="conflicting"):
        q.SecRawCache(tmp_path).accept(320193, url=q.companyfacts_url(320193), raw_bytes=raw)
    assert target.read_bytes() == b"conflict"
    assert not _accepted_path(tmp_path).exists()


def test_failed_pointer_replace_preserves_previous_accepted_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = q.SecRawCache(tmp_path)
    original = q.canonical_reviewed_sec_fixture_bytes()
    cache.accept(320193, url=q.companyfacts_url(320193), raw_bytes=original)
    changed = original.replace(b"Apple Inc.", b"Apple Incorporated", 1)

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("simulated interruption")

    monkeypatch.setattr("quantcheck.sec_adapter.os.replace", fail_replace)
    with pytest.raises(q.SecCacheIntegrityError, match="atomically"):
        cache.accept(320193, url=q.companyfacts_url(320193), raw_bytes=changed)
    assert cache.load(320193).raw_bytes == original


def test_failed_malformed_refresh_preserves_previous_accepted_entry(tmp_path: Path) -> None:
    cache = q.SecRawCache(tmp_path)
    original = q.canonical_reviewed_sec_fixture_bytes()
    cache.accept(320193, url=q.companyfacts_url(320193), raw_bytes=original)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"malformed")

    with pytest.raises(q.InvalidCompanyFactsError):
        _adapter(tmp_path, handler).fetch(320193, refresh=True)
    assert cache.load(320193).raw_bytes == original


def test_raw_whitespace_changes_raw_identity_but_not_normalized_logic(tmp_path: Path) -> None:
    compact = q.canonical_reviewed_sec_fixture_bytes()
    spaced = json.dumps(q.reviewed_sec_fixture_payload(), indent=2).encode()
    assert q.sha256_hex_of_bytes(compact) != q.sha256_hex_of_bytes(spaced)
    first = q.SecRawCache(tmp_path / "a").accept(
        320193, url=q.companyfacts_url(320193), raw_bytes=compact
    )
    second = q.SecRawCache(tmp_path / "b").accept(
        320193, url=q.companyfacts_url(320193), raw_bytes=spaced
    )
    config = q.reviewed_sec_normalization_config()
    assert first.raw_sha256 != second.raw_sha256
    assert q.canonical_json_bytes(q.normalize_companyfacts(first.raw_bytes, config).records) == (
        q.canonical_json_bytes(q.normalize_companyfacts(second.raw_bytes, config).records)
    )


def test_mock_online_and_offline_replay_normalize_to_identical_records(tmp_path: Path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=q.canonical_reviewed_sec_fixture_bytes())

    adapter = _adapter(tmp_path, handler)
    online = adapter.fetch(320193)
    offline = adapter.replay(320193)
    config = q.reviewed_sec_normalization_config()
    assert q.canonical_json_bytes(adapter.normalize(online, config).records) == (
        q.canonical_json_bytes(adapter.normalize(offline, config).records)
    )
