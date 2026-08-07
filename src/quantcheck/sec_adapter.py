"""Narrow, cache-first SEC Company Facts retrieval and normalization.

This module deliberately supports one CIK and an explicit allowlist at a
time.  It is not a generic ingestion framework or a statement builder.
Network/cache types live here rather than in :mod:`quantcheck.schemas`, so the
canonical financial contract remains independent of HTTPX and filesystems.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlparse

import httpx

from quantcheck.hashing import sec_source_row_id, sha256_hex_of_bytes, source_record_id
from quantcheck.json_types import (
    CanonicalizationError,
    canonical_decimal_string,
    parse_canonical_date,
)
from quantcheck.point_in_time import build_dataset_snapshot
from quantcheck.schemas import DatasetSnapshot, FinancialFact, PeriodType, SourceReference
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json

__all__ = [
    "COMPANY_FACTS_CACHE_SCHEMA_VERSION",
    "COMPANY_FACTS_URL_PREFIX",
    "SEC_SOURCE_NAME",
    "InvalidAllowlistedFactError",
    "InvalidCikError",
    "InvalidCompanyFactsError",
    "SecAdapterError",
    "SecCacheIntegrityError",
    "SecCacheMissError",
    "SecClientConfig",
    "SecCompanyFactsAdapter",
    "SecConceptSpec",
    "SecConfigurationError",
    "SecExclusion",
    "SecFetchResult",
    "SecHttpError",
    "SecNormalizationConfig",
    "SecNormalizationResult",
    "SecRawCache",
    "SecRetryExhaustedError",
    "SecTransportError",
    "UnsupportedNormalizationInputError",
    "build_sec_snapshot",
    "companyfacts_url",
    "normalize_cik",
    "normalize_companyfacts",
    "parse_companyfacts_bytes",
]

COMPANY_FACTS_URL_PREFIX = "https://data.sec.gov/api/xbrl/companyfacts"
COMPANY_FACTS_CACHE_SCHEMA_VERSION = "quantcheck/sec-companyfacts-cache/v1"
SEC_SOURCE_NAME = "sec-companyfacts"

_CIK_PATTERN = re.compile(r"^[0-9]{1,10}$")
_CANONICAL_CIK_PATTERN = re.compile(r"^[0-9]{10}$")
_ACCESSION_PATTERN = re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")
_EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+"
)
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_ALLOWED_ENTRY_FIELDS = frozenset(
    {"start", "end", "val", "accn", "fy", "fp", "form", "filed", "frame"}
)
_REQUIRED_ENTRY_FIELDS = frozenset({"end", "val", "accn", "form", "filed"})
_ALLOWED_CONCEPT_FIELDS = frozenset({"label", "description", "units"})
_ACCEPTED_METADATA_FIELDS = frozenset(
    {"schema_version", "canonical_cik", "url", "raw_filename", "raw_sha256"}
)

type RawJson = None | bool | int | Decimal | str | list["RawJson"] | dict[str, "RawJson"]
type Sleep = Callable[[float], None]
type Monotonic = Callable[[], float]
type ExclusionReason = Literal[
    "taxonomy_not_allowlisted",
    "concept_not_allowlisted",
    "unit_not_allowlisted",
    "form_not_allowlisted",
    "filed_before_range",
    "filed_after_range",
    "period_shape_not_allowlisted",
]


class SecAdapterError(ValueError):
    """Base class for explicit SEC adapter failures."""


class SecConfigurationError(SecAdapterError):
    """Raised when SEC client configuration is missing or unsupported."""


class InvalidCikError(SecAdapterError):
    """Raised when a CIK cannot be normalized without guessing."""


class SecTransportError(SecAdapterError):
    """Raised after bounded retries of HTTP transport failures are exhausted."""


class SecHttpError(SecAdapterError):
    """Raised for a non-successful SEC HTTP response."""

    def __init__(self, status_code: int, *, attempts: int) -> None:
        self.status_code = status_code
        self.attempts = attempts
        super().__init__(f"SEC Company Facts request failed with HTTP {status_code}")


class SecRetryExhaustedError(SecHttpError):
    """Raised when a retryable SEC response remains unsuccessful."""


class SecCacheMissError(SecAdapterError):
    """Raised when no accepted offline Company Facts entry exists."""


class SecCacheIntegrityError(SecAdapterError):
    """Raised when accepted cache metadata or immutable content fails validation."""


class InvalidCompanyFactsError(SecAdapterError):
    """Raised when raw bytes are not the requested Company Facts envelope."""


class UnsupportedNormalizationInputError(SecAdapterError):
    """Raised when normalization configuration or source structure is unsupported."""


class InvalidAllowlistedFactError(SecAdapterError):
    """Raised when an entry claims an allowlisted category but is malformed."""


def _validate_seconds(name: str, value: object, *, positive: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SecConfigurationError(f"{name} must be a finite number of seconds")
    result = float(value)
    if not math.isfinite(result):
        raise SecConfigurationError(f"{name} must be finite")
    if positive and result <= 0:
        raise SecConfigurationError(f"{name} must be greater than zero")
    if not positive and result < 0:
        raise SecConfigurationError(f"{name} must not be negative")
    return result


def _contact_match(user_agent: str) -> re.Match[str] | None:
    email_match = _EMAIL_PATTERN.search(user_agent)
    if email_match is not None:
        return email_match
    return _URL_PATTERN.search(user_agent)


def _validate_user_agent(value: object) -> str:
    if not isinstance(value, str):
        raise SecConfigurationError("user_agent must be an explicit string")
    if not value or value != value.strip():
        raise SecConfigurationError("user_agent must be nonblank with no surrounding whitespace")
    if len(value) > 256 or any(ord(character) < 0x20 for character in value):
        raise SecConfigurationError("user_agent has an unsupported length or control character")

    lowered = value.casefold()
    placeholder_fragments = (
        "<",
        ">",
        "placeholder",
        "change-me",
        "changeme",
        "your-email",
        "sample company",
        "example.com",
        "example.org",
        "example.net",
        ".invalid",
        "localhost",
    )
    if any(fragment in lowered for fragment in placeholder_fragments):
        raise SecConfigurationError("user_agent must not contain placeholder contact information")

    contact = _contact_match(value)
    if contact is None:
        raise SecConfigurationError(
            "user_agent must include an email address or HTTP(S) contact URL"
        )
    contact_text = contact.group(0)
    if "://" in contact_text:
        parsed = urlparse(contact_text)
        if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
            raise SecConfigurationError("user_agent contact URL is malformed")
        if "." not in parsed.hostname or parsed.username is not None:
            raise SecConfigurationError("user_agent contact URL must have a public host")

    identity = (value[: contact.start()] + value[contact.end() :]).strip(" ()[]{};,/-")
    if len(identity) < 2 or not any(character.isalpha() for character in identity):
        raise SecConfigurationError(
            "user_agent must include an explicit organization or tool identity"
        )
    return value


@dataclass(frozen=True, slots=True)
class SecClientConfig:
    """Immutable settings for one synchronous, cache-first SEC client."""

    user_agent: str
    cache_dir: Path
    timeout_seconds: float = 10.0
    minimum_interval_seconds: float = 0.2
    max_retries: int = 2
    backoff_seconds: float = 0.5
    max_retry_after_seconds: float = 30.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_agent", _validate_user_agent(self.user_agent))
        if not isinstance(self.cache_dir, Path | str):
            raise SecConfigurationError("cache_dir must be a pathlib.Path or path string")
        cache_dir = Path(self.cache_dir)
        if not str(cache_dir):
            raise SecConfigurationError("cache_dir must not be empty")
        object.__setattr__(self, "cache_dir", cache_dir)
        object.__setattr__(
            self,
            "timeout_seconds",
            _validate_seconds("timeout_seconds", self.timeout_seconds, positive=True),
        )
        object.__setattr__(
            self,
            "minimum_interval_seconds",
            _validate_seconds(
                "minimum_interval_seconds", self.minimum_interval_seconds, positive=False
            ),
        )
        object.__setattr__(
            self,
            "backoff_seconds",
            _validate_seconds("backoff_seconds", self.backoff_seconds, positive=False),
        )
        object.__setattr__(
            self,
            "max_retry_after_seconds",
            _validate_seconds(
                "max_retry_after_seconds", self.max_retry_after_seconds, positive=False
            ),
        )
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int):
            raise SecConfigurationError("max_retries must be an integer")
        if not 0 <= self.max_retries <= 5:
            raise SecConfigurationError("max_retries must be between zero and five")


def _validate_name(name: str, value: object) -> str:
    if not isinstance(value, str) or _TOKEN_PATTERN.fullmatch(value) is None:
        raise UnsupportedNormalizationInputError(f"{name} is malformed")
    return value


@dataclass(frozen=True, slots=True)
class SecConceptSpec:
    """One exact taxonomy/concept/unit/period-shape normalization allowlist row."""

    taxonomy: str
    concept: str
    unit: str
    period_type: PeriodType

    def __post_init__(self) -> None:
        object.__setattr__(self, "taxonomy", _validate_name("taxonomy", self.taxonomy))
        object.__setattr__(self, "concept", _validate_name("concept", self.concept))
        object.__setattr__(self, "unit", _validate_name("unit", self.unit))
        if self.period_type not in {"instant", "duration"}:
            raise UnsupportedNormalizationInputError("period_type must be instant or duration")


@dataclass(frozen=True, slots=True)
class SecNormalizationConfig:
    """Immutable allowlists for one Company Facts response."""

    cik: str | int
    concepts: Sequence[SecConceptSpec]
    forms: Sequence[str]
    filed_from: date
    filed_through: date

    def __post_init__(self) -> None:
        object.__setattr__(self, "cik", normalize_cik(self.cik))
        if not isinstance(self.concepts, Sequence) or isinstance(self.concepts, str | bytes):
            raise UnsupportedNormalizationInputError("concepts must be a nonempty sequence")
        concepts = tuple(self.concepts)
        if not concepts or not all(isinstance(item, SecConceptSpec) for item in concepts):
            raise UnsupportedNormalizationInputError("concepts must contain SecConceptSpec values")
        concept_keys = {
            (item.taxonomy, item.concept, item.unit, item.period_type) for item in concepts
        }
        if len(concept_keys) != len(concepts):
            raise UnsupportedNormalizationInputError("concept allowlist rows must be unique")
        object.__setattr__(
            self,
            "concepts",
            tuple(
                sorted(
                    concepts,
                    key=lambda item: (
                        item.taxonomy,
                        item.concept,
                        item.unit,
                        item.period_type,
                    ),
                )
            ),
        )

        if not isinstance(self.forms, Sequence) or isinstance(self.forms, str | bytes):
            raise UnsupportedNormalizationInputError("forms must be a nonempty sequence")
        forms = tuple(_validate_name("form", form) for form in self.forms)
        if not forms:
            raise UnsupportedNormalizationInputError("forms must not be empty")
        object.__setattr__(self, "forms", tuple(sorted(set(forms))))

        for field_name in ("filed_from", "filed_through"):
            field_value = getattr(self, field_name)
            if isinstance(field_value, datetime) or not isinstance(field_value, date):
                raise UnsupportedNormalizationInputError(f"{field_name} must be a day-level date")
        if self.filed_from > self.filed_through:
            raise UnsupportedNormalizationInputError("filed_from must not be after filed_through")


@dataclass(frozen=True, slots=True)
class SecFetchResult:
    """Exact accepted response bytes and their raw-content identity."""

    canonical_cik: str
    url: str
    raw_sha256: str
    raw_bytes: bytes
    from_cache: bool


@dataclass(frozen=True, slots=True)
class SecExclusion:
    """One deterministic, explicit allowlist exclusion."""

    reason: ExclusionReason
    taxonomy: str
    concept: str
    unit: str
    source_row_key: str


@dataclass(frozen=True, slots=True)
class SecNormalizationResult:
    """Normalized facts plus the source occurrences excluded by configuration."""

    canonical_cik: str
    source_locator: str
    records: tuple[FinancialFact, ...]
    exclusions: tuple[SecExclusion, ...]


def normalize_cik(value: object) -> str:
    """Return a positive CIK as the SEC endpoint's ten-digit string."""
    if isinstance(value, bool):
        raise InvalidCikError("boolean is not a valid CIK")
    if isinstance(value, int):
        if value <= 0 or value > 9_999_999_999:
            raise InvalidCikError("CIK integer must be between 1 and 9999999999")
        return f"{value:010d}"
    if not isinstance(value, str) or _CIK_PATTERN.fullmatch(value) is None:
        raise InvalidCikError("CIK must contain one to ten ASCII digits")
    numeric = int(value)
    if numeric == 0:
        raise InvalidCikError("CIK must be positive")
    return f"{numeric:010d}"


def companyfacts_url(cik: object) -> str:
    """Construct the sole endpoint supported by this adapter."""
    return f"{COMPANY_FACTS_URL_PREFIX}/CIK{normalize_cik(cik)}.json"


def _reject_json_constant(text: str) -> RawJson:
    raise ValueError(f"unsupported JSON constant {text!r}")


def _parse_source_json(raw_bytes: bytes) -> RawJson:
    if not isinstance(raw_bytes, bytes):
        raise InvalidCompanyFactsError("Company Facts content must be bytes")
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidCompanyFactsError("Company Facts content must be valid UTF-8") from exc
    try:
        parsed = json.loads(
            text,
            parse_int=int,
            parse_float=Decimal,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise InvalidCompanyFactsError("Company Facts content is not valid finite JSON") from exc
    return cast(RawJson, parsed)


def _mapping(value: RawJson, *, label: str, allowlisted: bool = False) -> dict[str, RawJson]:
    if not isinstance(value, dict):
        error_type = InvalidAllowlistedFactError if allowlisted else InvalidCompanyFactsError
        raise error_type(f"{label} must be a JSON object")
    return value


def _string(value: RawJson, *, label: str, allowlisted: bool = False) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        error_type = InvalidAllowlistedFactError if allowlisted else InvalidCompanyFactsError
        raise error_type(f"{label} must be a nonblank string")
    return value


def parse_companyfacts_bytes(raw_bytes: bytes, *, expected_cik: object) -> dict[str, RawJson]:
    """Parse exact source bytes and validate the narrow top-level envelope."""
    canonical_cik = normalize_cik(expected_cik)
    parsed = _parse_source_json(raw_bytes)
    envelope = _mapping(parsed, label="Company Facts envelope")
    expected_fields = {"cik", "entityName", "facts"}
    if set(envelope) != expected_fields:
        raise InvalidCompanyFactsError(
            "Company Facts envelope must contain exactly cik, entityName, and facts"
        )
    try:
        source_cik = normalize_cik(envelope["cik"])
    except InvalidCikError as exc:
        raise InvalidCompanyFactsError("Company Facts envelope contains an invalid CIK") from exc
    if source_cik != canonical_cik:
        raise InvalidCompanyFactsError("Company Facts envelope CIK does not match the request")
    _string(envelope["entityName"], label="entityName")
    _mapping(envelope["facts"], label="facts")
    return envelope


def _safe_child(root: Path, *parts: str) -> Path:
    root_resolved = root.resolve(strict=False)
    candidate = root.joinpath(*parts)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root_resolved):
        raise SecCacheIntegrityError("cache path escapes the configured cache root")
    return candidate


def _fsync_directory(directory: Path) -> None:
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError as exc:
        raise SecCacheIntegrityError("unable to open cache directory for synchronization") from exc
    try:
        os.fsync(descriptor)
    except OSError as exc:
        raise SecCacheIntegrityError("unable to synchronize cache directory") from exc
    finally:
        os.close(descriptor)


def _write_temp_file(directory: Path, data: bytes) -> Path:
    descriptor, raw_path = tempfile.mkstemp(prefix=".quantcheck-sec-", suffix=".tmp", dir=directory)
    temp_path = Path(raw_path)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


class SecRawCache:
    """Integrity-checked immutable raw files plus one atomic accepted pointer."""

    def __init__(self, root: Path | str) -> None:
        if not isinstance(root, Path | str):
            raise SecConfigurationError("cache root must be a pathlib.Path or path string")
        self._root = Path(root)

    def _entity_dir(self, canonical_cik: str) -> Path:
        return _safe_child(self._root, "companyfacts", f"CIK{canonical_cik}")

    def _accepted_path(self, canonical_cik: str) -> Path:
        return _safe_child(self._entity_dir(canonical_cik), "accepted.json")

    def _raw_path(self, canonical_cik: str, filename: str) -> Path:
        if Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise SecCacheIntegrityError("accepted raw filename is not a single safe filename")
        return _safe_child(self._entity_dir(canonical_cik), filename)

    def load(self, cik: object) -> SecFetchResult:
        """Load and revalidate the accepted entry without network access."""
        canonical_cik = normalize_cik(cik)
        accepted_path = self._accepted_path(canonical_cik)
        if accepted_path.is_symlink():
            raise SecCacheIntegrityError("accepted cache pointer must not be a symbolic link")
        if not accepted_path.exists():
            raise SecCacheMissError("no accepted Company Facts cache entry exists")
        try:
            metadata_bytes = accepted_path.read_bytes()
        except OSError as exc:
            raise SecCacheIntegrityError("accepted cache pointer cannot be read") from exc
        try:
            parsed = parse_canonical_json(metadata_bytes)
        except CanonicalizationError as exc:
            raise SecCacheIntegrityError(
                "accepted cache pointer is not valid canonical JSON"
            ) from exc
        if not isinstance(parsed, dict) or set(parsed) != _ACCEPTED_METADATA_FIELDS:
            raise SecCacheIntegrityError("accepted cache pointer has invalid metadata fields")
        if canonical_json_bytes(parsed) != metadata_bytes:
            raise SecCacheIntegrityError("accepted cache pointer is not canonical JSON")
        if not all(isinstance(value, str) for value in parsed.values()):
            raise SecCacheIntegrityError("accepted cache pointer metadata must be strings")

        metadata = cast(dict[str, str], parsed)
        expected_url = companyfacts_url(canonical_cik)
        if metadata["schema_version"] != COMPANY_FACTS_CACHE_SCHEMA_VERSION:
            raise SecCacheIntegrityError("accepted cache pointer has an unsupported schema version")
        if metadata["canonical_cik"] != canonical_cik:
            raise SecCacheIntegrityError("accepted cache pointer has the wrong CIK")
        if metadata["url"] != expected_url:
            raise SecCacheIntegrityError("accepted cache pointer has the wrong Company Facts URL")
        digest = metadata["raw_sha256"]
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise SecCacheIntegrityError("accepted cache pointer has an invalid raw digest")
        expected_filename = f"raw-{digest}.json"
        if metadata["raw_filename"] != expected_filename:
            raise SecCacheIntegrityError("accepted raw filename does not match its digest")

        raw_path = self._raw_path(canonical_cik, expected_filename)
        if raw_path.is_symlink():
            raise SecCacheIntegrityError("immutable raw cache content must not be a symbolic link")
        if not raw_path.exists():
            raise SecCacheIntegrityError("accepted immutable raw cache content is missing")
        try:
            raw_bytes = raw_path.read_bytes()
        except OSError as exc:
            raise SecCacheIntegrityError("immutable raw cache content cannot be read") from exc
        if sha256_hex_of_bytes(raw_bytes) != digest:
            raise SecCacheIntegrityError("immutable raw cache content hash does not match metadata")
        try:
            parse_companyfacts_bytes(raw_bytes, expected_cik=canonical_cik)
        except InvalidCompanyFactsError as exc:
            raise SecCacheIntegrityError(
                "accepted raw content is not valid Company Facts data"
            ) from exc
        return SecFetchResult(
            canonical_cik=canonical_cik,
            url=expected_url,
            raw_sha256=digest,
            raw_bytes=raw_bytes,
            from_cache=True,
        )

    def _write_immutable(self, target: Path, data: bytes) -> None:
        if target.is_symlink():
            raise SecCacheIntegrityError("immutable raw cache target must not be a symbolic link")
        if target.exists():
            try:
                current = target.read_bytes()
            except OSError as exc:
                raise SecCacheIntegrityError("immutable raw cache target cannot be read") from exc
            if current != data:
                raise SecCacheIntegrityError(
                    "immutable raw cache filename contains conflicting data"
                )
            return

        temp_path = _write_temp_file(target.parent, data)
        try:
            try:
                os.link(temp_path, target)
            except FileExistsError:
                if target.is_symlink() or target.read_bytes() != data:
                    raise SecCacheIntegrityError(
                        "immutable raw cache filename contains conflicting data"
                    ) from None
            _fsync_directory(target.parent)
        except OSError as exc:
            raise SecCacheIntegrityError(
                "immutable raw cache content cannot be established"
            ) from exc
        finally:
            temp_path.unlink(missing_ok=True)

    def _replace_pointer(self, target: Path, data: bytes) -> None:
        if target.is_symlink():
            raise SecCacheIntegrityError("accepted cache pointer must not be a symbolic link")
        if target.exists():
            try:
                if target.read_bytes() == data:
                    return
            except OSError as exc:
                raise SecCacheIntegrityError("accepted cache pointer cannot be read") from exc
        temp_path = _write_temp_file(target.parent, data)
        try:
            os.replace(temp_path, target)
            _fsync_directory(target.parent)
        except OSError as exc:
            raise SecCacheIntegrityError(
                "accepted cache pointer cannot be replaced atomically"
            ) from exc
        finally:
            temp_path.unlink(missing_ok=True)

    def accept(self, cik: object, *, url: str, raw_bytes: bytes) -> SecFetchResult:
        """Validate and atomically accept exact response bytes."""
        canonical_cik = normalize_cik(cik)
        expected_url = companyfacts_url(canonical_cik)
        if url != expected_url:
            raise SecCacheIntegrityError(
                "response URL does not match the requested Company Facts URL"
            )
        parse_companyfacts_bytes(raw_bytes, expected_cik=canonical_cik)
        digest = sha256_hex_of_bytes(raw_bytes)
        filename = f"raw-{digest}.json"
        metadata = {
            "schema_version": COMPANY_FACTS_CACHE_SCHEMA_VERSION,
            "canonical_cik": canonical_cik,
            "url": expected_url,
            "raw_filename": filename,
            "raw_sha256": digest,
        }
        metadata_bytes = canonical_json_bytes(metadata)

        entity_dir = self._entity_dir(canonical_cik)
        try:
            entity_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise SecCacheIntegrityError("Company Facts cache directory cannot be created") from exc
        # Re-resolve after creation to catch a pre-existing symlinked component.
        _safe_child(self._root, "companyfacts", f"CIK{canonical_cik}")
        raw_path = self._raw_path(canonical_cik, filename)
        accepted_path = self._accepted_path(canonical_cik)
        self._write_immutable(raw_path, raw_bytes)
        self._replace_pointer(accepted_path, metadata_bytes)
        return SecFetchResult(
            canonical_cik=canonical_cik,
            url=expected_url,
            raw_sha256=digest,
            raw_bytes=raw_bytes,
            from_cache=False,
        )


def _retry_after_delay(value: str | None, *, maximum: float) -> float | None:
    # HTTP-date parsing would make retry behavior depend on wall-clock time.
    # The rebuild therefore accepts only the unambiguous delay-seconds form.
    if value is None or re.fullmatch(r"[0-9]+", value) is None:
        return None
    delay = float(int(value))
    if delay > maximum:
        return None
    return delay


class SecCompanyFactsAdapter:
    """One-company synchronous retrieval, replay, and normalization."""

    def __init__(
        self,
        config: SecClientConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        sleeper: Sleep = time.sleep,
        monotonic: Monotonic = time.monotonic,
    ) -> None:
        if not isinstance(config, SecClientConfig):
            raise SecConfigurationError("config must be a SecClientConfig")
        self._config = config
        self._cache = SecRawCache(config.cache_dir)
        self._transport = transport
        self._sleeper = sleeper
        self._monotonic = monotonic
        self._last_request_started: float | None = None

    def _pace(self) -> None:
        now = self._monotonic()
        if self._last_request_started is not None:
            remaining = self._config.minimum_interval_seconds - (now - self._last_request_started)
            if remaining > 0:
                self._sleeper(remaining)
                now = self._monotonic()
        self._last_request_started = now

    def _retry_sleep(self, response: httpx.Response | None, retry_index: int) -> None:
        retry_after = None
        if response is not None:
            retry_after = _retry_after_delay(
                response.headers.get("Retry-After"),
                maximum=self._config.max_retry_after_seconds,
            )
        delay = (
            retry_after
            if retry_after is not None
            else self._config.backoff_seconds * (2**retry_index)
        )
        if delay > 0:
            self._sleeper(delay)

    def _download(self, canonical_cik: str) -> SecFetchResult:
        url = companyfacts_url(canonical_cik)
        attempts = self._config.max_retries + 1
        with httpx.Client(transport=self._transport, follow_redirects=False) as client:
            for attempt_index in range(attempts):
                self._pace()
                try:
                    response = client.get(
                        url,
                        headers={
                            "User-Agent": self._config.user_agent,
                            "Accept": "application/json",
                        },
                        timeout=self._config.timeout_seconds,
                    )
                except httpx.TransportError as exc:
                    if attempt_index == attempts - 1:
                        raise SecTransportError(
                            f"SEC transport failed after {attempts} attempt(s)"
                        ) from exc
                    self._retry_sleep(None, attempt_index)
                    continue

                if response.is_success:
                    return self._cache.accept(
                        canonical_cik,
                        url=url,
                        raw_bytes=response.content,
                    )

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as cause:
                    if response.status_code not in _RETRYABLE_STATUS_CODES:
                        raise SecHttpError(
                            response.status_code, attempts=attempt_index + 1
                        ) from cause
                    if attempt_index == attempts - 1:
                        raise SecRetryExhaustedError(
                            response.status_code,
                            attempts=attempts,
                        ) from cause
                self._retry_sleep(response, attempt_index)
        raise AssertionError("bounded SEC request loop exited unexpectedly")

    def fetch(self, cik: object, *, refresh: bool = False) -> SecFetchResult:
        """Use valid accepted content first, unless an explicit refresh is requested."""
        canonical_cik = normalize_cik(cik)
        if not refresh:
            try:
                return self._cache.load(canonical_cik)
            except SecCacheMissError:
                pass
        return self._download(canonical_cik)

    def replay(self, cik: object) -> SecFetchResult:
        """Return accepted bytes entirely offline."""
        return self._cache.load(cik)

    def normalize(
        self,
        fetched: SecFetchResult,
        normalization: SecNormalizationConfig,
    ) -> SecNormalizationResult:
        """Normalize a validated fetch result under an explicit allowlist."""
        if fetched.canonical_cik != normalization.cik:
            raise UnsupportedNormalizationInputError(
                "fetch result CIK does not match normalization configuration"
            )
        if fetched.url != companyfacts_url(fetched.canonical_cik):
            raise InvalidCompanyFactsError("fetch result URL is not the canonical endpoint")
        if sha256_hex_of_bytes(fetched.raw_bytes) != fetched.raw_sha256:
            raise InvalidCompanyFactsError("fetch result raw digest does not match its bytes")
        return normalize_companyfacts(fetched.raw_bytes, normalization)

    def build_snapshot(
        self,
        fetched: SecFetchResult,
        normalization: SecNormalizationConfig,
        *,
        dataset_name: str,
        as_of_date: date,
    ) -> DatasetSnapshot:
        """Normalize, then call the existing point-in-time snapshot engine."""
        result = self.normalize(fetched, normalization)
        return build_sec_snapshot(
            result,
            dataset_name=dataset_name,
            as_of_date=as_of_date,
        )


def _concept_units(
    concept_body: RawJson,
    *,
    allowlisted: bool,
) -> dict[str, RawJson]:
    body = _mapping(concept_body, label="concept body", allowlisted=allowlisted)
    if "units" not in body:
        error_type = InvalidAllowlistedFactError if allowlisted else InvalidCompanyFactsError
        raise error_type("concept body is missing units")
    if allowlisted:
        unknown = set(body) - _ALLOWED_CONCEPT_FIELDS
        if unknown:
            raise InvalidAllowlistedFactError("allowlisted concept body has unknown fields")
        for field in ("label", "description"):
            if field in body:
                _string(body[field], label=field, allowlisted=True)
    return _mapping(body["units"], label="concept units", allowlisted=allowlisted)


def _ordered_occurrences(entries_value: RawJson) -> list[tuple[RawJson, int]]:
    if not isinstance(entries_value, list):
        raise InvalidCompanyFactsError("a Company Facts unit must contain a JSON array")
    decorated: list[tuple[bytes, RawJson]] = []
    for entry in entries_value:
        try:
            identity_bytes = canonical_json_bytes(entry)
        except CanonicalizationError as exc:
            raise InvalidCompanyFactsError(
                "source entry is outside the supported JSON domain"
            ) from exc
        decorated.append((identity_bytes, entry))
    decorated.sort(key=lambda item: item[0])
    counts: dict[bytes, int] = {}
    ordered: list[tuple[RawJson, int]] = []
    for identity_bytes, entry in decorated:
        ordinal = counts.get(identity_bytes, 0) + 1
        counts[identity_bytes] = ordinal
        ordered.append((entry, ordinal))
    return ordered


def _source_row_key(
    *,
    canonical_cik: str,
    taxonomy: str,
    concept: str,
    unit: str,
    entry: RawJson,
    duplicate_ordinal: int,
) -> str:
    return sec_source_row_id(
        canonical_cik=canonical_cik,
        taxonomy=taxonomy,
        concept=concept,
        unit=unit,
        source_entry=entry,
        duplicate_ordinal=duplicate_ordinal,
    )


def _append_exclusions(
    exclusions: list[SecExclusion],
    *,
    canonical_cik: str,
    taxonomy: str,
    concept: str,
    units: Mapping[str, RawJson],
    reason: ExclusionReason,
) -> None:
    for unit in sorted(units):
        entries = _ordered_occurrences(units[unit])
        for entry, ordinal in entries:
            exclusions.append(
                SecExclusion(
                    reason=reason,
                    taxonomy=taxonomy,
                    concept=concept,
                    unit=unit,
                    source_row_key=_source_row_key(
                        canonical_cik=canonical_cik,
                        taxonomy=taxonomy,
                        concept=concept,
                        unit=unit,
                        entry=entry,
                        duplicate_ordinal=ordinal,
                    ),
                )
            )


def _entry_period_type(entry: Mapping[str, RawJson]) -> PeriodType:
    if "start" not in entry:
        return "instant"
    if entry["start"] is None:
        raise InvalidAllowlistedFactError("duration start must not be null")
    return "duration"


def _entry_date(entry: Mapping[str, RawJson], field: str) -> date:
    text = _string(entry[field], label=field, allowlisted=True)
    try:
        return parse_canonical_date(text)
    except CanonicalizationError as exc:
        raise InvalidAllowlistedFactError(f"{field} is not a valid calendar date") from exc


def _entry_decimal(entry: Mapping[str, RawJson]) -> Decimal:
    value = entry["val"]
    if isinstance(value, bool):
        raise InvalidAllowlistedFactError("boolean is not a financial value")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        try:
            canonical_decimal_string(value)
        except CanonicalizationError as exc:
            raise InvalidAllowlistedFactError("non-finite financial value is unsupported") from exc
        return value
    raise InvalidAllowlistedFactError("financial value must be a JSON integer or decimal number")


def _validate_optional_source_metadata(entry: Mapping[str, RawJson]) -> None:
    if "fy" in entry and (isinstance(entry["fy"], bool) or not isinstance(entry["fy"], int)):
        raise InvalidAllowlistedFactError("fy must be an integer when present")
    for field in ("fp", "frame"):
        if field in entry:
            _string(entry[field], label=field, allowlisted=True)


def _normalize_allowed_entry(
    *,
    entry_value: RawJson,
    duplicate_ordinal: int,
    canonical_cik: str,
    entity_name: str,
    taxonomy: str,
    concept: str,
    unit: str,
    allowed_period_types: frozenset[PeriodType],
    config: SecNormalizationConfig,
    records: list[FinancialFact],
    exclusions: list[SecExclusion],
) -> None:
    entry = _mapping(entry_value, label="allowlisted fact", allowlisted=True)
    unknown_fields = set(entry) - _ALLOWED_ENTRY_FIELDS
    if unknown_fields:
        raise InvalidAllowlistedFactError("allowlisted fact has unsupported fields or dimensions")
    missing_fields = _REQUIRED_ENTRY_FIELDS - set(entry)
    if missing_fields:
        raise InvalidAllowlistedFactError("allowlisted fact is missing required fields")

    row_key = _source_row_key(
        canonical_cik=canonical_cik,
        taxonomy=taxonomy,
        concept=concept,
        unit=unit,
        entry=entry_value,
        duplicate_ordinal=duplicate_ordinal,
    )
    form = _string(entry["form"], label="form", allowlisted=True)
    if form not in config.forms:
        exclusions.append(SecExclusion("form_not_allowlisted", taxonomy, concept, unit, row_key))
        return
    filed_on = _entry_date(entry, "filed")
    if filed_on < config.filed_from:
        exclusions.append(SecExclusion("filed_before_range", taxonomy, concept, unit, row_key))
        return
    if filed_on > config.filed_through:
        exclusions.append(SecExclusion("filed_after_range", taxonomy, concept, unit, row_key))
        return

    period_type = _entry_period_type(entry)
    if period_type not in allowed_period_types:
        exclusions.append(
            SecExclusion("period_shape_not_allowlisted", taxonomy, concept, unit, row_key)
        )
        return

    period_end = _entry_date(entry, "end")
    period_start = _entry_date(entry, "start") if period_type == "duration" else None
    if period_start is not None and period_start > period_end:
        raise InvalidAllowlistedFactError("duration start must not follow end")
    accession = _string(entry["accn"], label="accn", allowlisted=True)
    if _ACCESSION_PATTERN.fullmatch(accession) is None:
        raise InvalidAllowlistedFactError("accn is not a supported accession number")
    _validate_optional_source_metadata(entry)
    value = _entry_decimal(entry)

    locator = companyfacts_url(canonical_cik)
    source = SourceReference(
        source_name=SEC_SOURCE_NAME,
        source_locator=locator,
        source_row_key=row_key,
    )
    records.append(
        FinancialFact(
            record_id=source_record_id(
                source_name=source.source_name,
                source_locator=source.source_locator,
                source_row_key=source.source_row_key,
            ),
            entity_id=f"CIK{canonical_cik}",
            entity_name=entity_name,
            concept_namespace=taxonomy,
            concept=concept,
            value=value,
            unit=unit,
            dimensions=(),
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            filed_on=filed_on,
            available_on=filed_on,
            form=form,
            accession_number=accession,
            source=source,
        )
    )


def normalize_companyfacts(
    raw_bytes: bytes,
    config: SecNormalizationConfig,
) -> SecNormalizationResult:
    """Normalize only explicitly allowlisted, entity-wide Company Facts entries."""
    if not isinstance(config, SecNormalizationConfig):
        raise UnsupportedNormalizationInputError(
            "normalization config must be a SecNormalizationConfig"
        )
    envelope = parse_companyfacts_bytes(raw_bytes, expected_cik=config.cik)
    entity_name = _string(envelope["entityName"], label="entityName")
    facts = _mapping(envelope["facts"], label="facts")
    allowed_concepts = {(spec.taxonomy, spec.concept) for spec in config.concepts}
    allowed_units = {(spec.taxonomy, spec.concept, spec.unit) for spec in config.concepts}
    allowed_period_types: dict[tuple[str, str, str], frozenset[PeriodType]] = {}
    for taxonomy, concept, unit in sorted(allowed_units):
        allowed_period_types[(taxonomy, concept, unit)] = frozenset(
            spec.period_type
            for spec in config.concepts
            if (spec.taxonomy, spec.concept, spec.unit) == (taxonomy, concept, unit)
        )

    records: list[FinancialFact] = []
    exclusions: list[SecExclusion] = []
    for taxonomy in sorted(facts):
        taxonomy_body = _mapping(facts[taxonomy], label="taxonomy facts")
        for concept in sorted(taxonomy_body):
            allowlisted_concept = (taxonomy, concept) in allowed_concepts
            units = _concept_units(
                taxonomy_body[concept],
                allowlisted=allowlisted_concept,
            )
            if taxonomy not in {spec.taxonomy for spec in config.concepts}:
                _append_exclusions(
                    exclusions,
                    canonical_cik=cast(str, config.cik),
                    taxonomy=taxonomy,
                    concept=concept,
                    units=units,
                    reason="taxonomy_not_allowlisted",
                )
                continue
            if not allowlisted_concept:
                _append_exclusions(
                    exclusions,
                    canonical_cik=cast(str, config.cik),
                    taxonomy=taxonomy,
                    concept=concept,
                    units=units,
                    reason="concept_not_allowlisted",
                )
                continue
            for unit in sorted(units):
                occurrences = _ordered_occurrences(units[unit])
                key = (taxonomy, concept, unit)
                if key not in allowed_units:
                    _append_exclusions(
                        exclusions,
                        canonical_cik=cast(str, config.cik),
                        taxonomy=taxonomy,
                        concept=concept,
                        units={unit: units[unit]},
                        reason="unit_not_allowlisted",
                    )
                    continue
                for entry, ordinal in occurrences:
                    _normalize_allowed_entry(
                        entry_value=entry,
                        duplicate_ordinal=ordinal,
                        canonical_cik=cast(str, config.cik),
                        entity_name=entity_name,
                        taxonomy=taxonomy,
                        concept=concept,
                        unit=unit,
                        allowed_period_types=allowed_period_types[key],
                        config=config,
                        records=records,
                        exclusions=exclusions,
                    )

    ordered_records = tuple(sorted(records, key=lambda record: record.record_id))
    ordered_exclusions = tuple(
        sorted(
            exclusions,
            key=lambda item: (
                item.reason,
                item.taxonomy,
                item.concept,
                item.unit,
                item.source_row_key,
            ),
        )
    )
    return SecNormalizationResult(
        canonical_cik=cast(str, config.cik),
        source_locator=companyfacts_url(config.cik),
        records=ordered_records,
        exclusions=ordered_exclusions,
    )


def build_sec_snapshot(
    result: SecNormalizationResult,
    *,
    dataset_name: str,
    as_of_date: date,
) -> DatasetSnapshot:
    """Feed normalized SEC facts into the existing point-in-time engine."""
    if not isinstance(result, SecNormalizationResult):
        raise UnsupportedNormalizationInputError("result must be a SecNormalizationResult")
    return build_dataset_snapshot(
        result.records,
        dataset_name=dataset_name,
        as_of_date=as_of_date,
    )
