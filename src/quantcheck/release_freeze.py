"""The QuantCheck 0.1 release-candidate freeze record.

A freeze record is the immutable statement of *what was frozen* before any
reserved final seed executed. It records the scientific configuration (fault
specifications, detector versions and configurations, severity definitions,
target rules, matching rules, false-positive denominator rules, research
configurations, replay method), the release matrix (fault profiles, severity
list, final seed list, clean-control policy), the normalized release benchmark
configuration and its canonical bytes hash, and the SHA-256 of every frozen
repository file.

The record is deliberately safe to commit and publish. It contains no secret,
no absolute or user path, no manifest, no fault target, no pre-corruption
value, and no answer-key relationship — only versions, thresholds that are
already public constants in the source, identifiers, and content hashes. A
test asserts that directly against the serialized bytes.

Verification is byte-level and refuses to repair: if any frozen file's SHA-256
no longer matches, or the release configuration no longer canonicalizes to the
recorded bytes, the candidate is invalid and the release path must refuse to
dispatch a final case until a new candidate is created.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BeforeValidator

from quantcheck.benchmark_expansion import expand_benchmark_cases
from quantcheck.benchmark_fixtures import REVIEWED_FIXTURE_ID
from quantcheck.duplicate_contract import (
    DUPLICATE_DETECTOR_ID,
    DUPLICATE_DETECTOR_VERSION,
    DUPLICATE_FAULT_SUBTYPE,
    DUPLICATE_FAULT_TYPE,
    DUPLICATE_SCORING_SPEC_VERSION,
    DUPLICATE_SPEC_VERSION,
    duplicate_severity_profile,
)
from quantcheck.fixtures import canonical_reviewed_fixture_bytes
from quantcheck.hashing import canonical_sha256, sha256_hex_of_bytes, stable_id
from quantcheck.lookahead_contract import (
    LOOKAHEAD_DETECTOR_ID,
    LOOKAHEAD_DETECTOR_VERSION,
    LOOKAHEAD_FAULT_SUBTYPE,
    LOOKAHEAD_FAULT_TYPE,
    LOOKAHEAD_SCORING_SPEC_VERSION,
    LOOKAHEAD_SPEC_VERSION,
    lookahead_severity_profile,
)
from quantcheck.release_config import RELEASE_BENCHMARK_NAME
from quantcheck.release_contract import (
    FROZEN_SOURCE_FILES,
    RELEASE_CLEAN_CONTROL_POLICY,
    RELEASE_CONTROL_CASE_COUNT,
    RELEASE_FAULT_CASE_COUNT,
    RELEASE_FAULT_PROFILES,
    RELEASE_SEEDS,
    RELEASE_SEVERITIES,
    RELEASE_SPEC_VERSION,
    RELEASE_TOTAL_CASE_COUNT,
)
from quantcheck.revision_overwrite_contract import (
    REVISION_OVERWRITE_DETECTOR_ID,
    REVISION_OVERWRITE_DETECTOR_VERSION,
    REVISION_OVERWRITE_FAULT_SUBTYPE,
    REVISION_OVERWRITE_FAULT_TYPE,
    REVISION_OVERWRITE_SCORING_SPEC_VERSION,
    REVISION_OVERWRITE_SPEC_VERSION,
    revision_overwrite_severity_profile,
)
from quantcheck.schemas import (
    BenchmarkConfig,
    CanonicalDecimal,
    CanonicalModel,
    ContentHash,
    NonNegativeInteger,
    Token,
)
from quantcheck.sec_fixture import (
    REVIEWED_SEC_FIXTURE_SPEC_VERSION,
    canonical_reviewed_sec_fixture_bytes,
)
from quantcheck.serialization import canonical_json_bytes, parse_canonical_json
from quantcheck.unit_drift_contract import (
    UNIT_DRIFT_DETECTOR_ID,
    UNIT_DRIFT_DETECTOR_VERSION,
    UNIT_DRIFT_FAULT_SUBTYPE,
    UNIT_DRIFT_FAULT_TYPE,
    UNIT_DRIFT_RATIO_THRESHOLD,
    UNIT_DRIFT_SCORING_SPEC_VERSION,
    UNIT_DRIFT_SPEC_VERSION,
    unit_drift_severity_profile,
)

__all__ = [
    "RELEASE_FREEZE_NAMESPACE",
    "FrozenFileHash",
    "FrozenSeverityProfile",
    "ReleaseFreezeError",
    "ReleaseFreezeRecord",
    "build_release_freeze_record",
    "read_release_freeze_record",
    "release_freeze_record_hash",
    "verify_release_freeze_record",
    "write_release_freeze_record",
]

RELEASE_FREEZE_NAMESPACE = "quantcheck/release-candidate/v1"

#: The false-positive denominator rule each family scores against, recorded so
#: the freeze states the rule rather than pointing at code that could change.
_DENOMINATOR_RULES: dict[str, str] = {
    "lookahead_timestamp": "eligible_clean_record_count",
    "unit_drift": "all_comparable_observation_count",
    "duplicate_observation": "eligible_record_count",
    "revision_overwrite": "eligible_revision_unit_count",
}

#: The exact matching rule each family's scorer applies.
_MATCHING_RULES: dict[str, str] = {
    "lookahead_timestamp": "exact_one_to_one_on_modified_record_id",
    "unit_drift": "exact_one_to_one_on_modified_record_id",
    "duplicate_observation": "exact_one_to_one_on_fingerprint_group",
    "revision_overwrite": "exact_one_to_one_on_modified_record_id",
}

#: The replay method for every family: private manifest-assisted exact
#: restoration, never detector-only repair.
_REPLAY_METHOD = "private_manifest_assisted_exact_replay"


def _to_tuple(value: object) -> object:
    """Accept a JSON array as a tuple on reload.

    ``CanonicalModel`` is strict, so a reloaded ``list`` would otherwise fail
    to validate against a ``tuple`` field. This mirrors the same before-
    validator the benchmark schemas already use for their sequence fields.
    """
    if isinstance(value, list):
        return tuple(value)
    return value


type _Tuple[ItemT] = Annotated[tuple[ItemT, ...], BeforeValidator(_to_tuple)]


class ReleaseFreezeError(RuntimeError):
    """Raised when a release candidate cannot be built or no longer verifies."""


class FrozenFileHash(CanonicalModel):
    """One frozen repository file and its content hash.

    ``path`` is always repository-relative POSIX, never an absolute or user
    path, so a freeze record stays publishable.
    """

    path: Token
    sha256: ContentHash


class FrozenSeverityProfile(CanonicalModel):
    """One fault family's frozen numeric definition of one severity.

    Field names are deliberately prefixed ``frozen_``. The underlying constants
    are public — they are documented in ``docs/faults/`` and live as module
    constants — but the *manifest* uses names like ``target_fraction`` for
    per-case injector truth. The release privacy scan matches exact object
    keys and cannot know which context it is in, so the freeze record avoids
    the collision rather than asking the scanner for an exemption. A scan with
    exemptions is a scan that eventually misses something.
    """

    fault_profile: Token
    severity: Token
    frozen_target_fraction: CanonicalDecimal
    #: The family's second severity parameter, named by the family: Look-Ahead's
    #: minimum natural filing lag in days, Unit Drift's value scale factor, or
    #: Revision Overwrite's minimum relative revision size. Duplicate
    #: Observations has no second parameter.
    frozen_parameter_name: Token | None = None
    frozen_parameter_value: CanonicalDecimal | None = None


class FrozenFaultSpecification(CanonicalModel):
    """One fault family's frozen scientific identity and rules."""

    fault_profile: Token
    fault_type: Token
    fault_subtype: Token
    injector_spec_version: Token
    detector_id: Token
    detector_version: Token
    scoring_spec_version: Token
    matching_rule: Token
    false_positive_denominator_rule: Token
    replay_method: Token


class ReleaseFreezeRecord(CanonicalModel):
    """Everything frozen before the first reserved final seed executes."""

    release_candidate_id: Token
    spec_version: Literal["quantcheck/release/v1"] = RELEASE_SPEC_VERSION
    benchmark_spec_version: Token
    package_version: Token
    python_requirement: Token

    # Release matrix
    fault_profiles: _Tuple[Token]
    severities: _Tuple[Token]
    final_seeds: _Tuple[NonNegativeInteger]
    clean_control_policy: Token
    fault_case_count: NonNegativeInteger
    control_case_count: NonNegativeInteger
    total_case_count: NonNegativeInteger

    # Frozen science
    fault_specifications: _Tuple[FrozenFaultSpecification]
    severity_profiles: _Tuple[FrozenSeverityProfile]
    detector_configs_sha256: ContentHash
    unit_drift_ratio_threshold: CanonicalDecimal

    # Frozen inputs
    reviewed_fixture_id: Token
    reviewed_fixture_sha256: ContentHash
    sec_reviewed_fixture_id: Token
    sec_reviewed_fixture_sha256: ContentHash

    # Frozen configuration
    benchmark_id: Token
    release_config_sha256: ContentHash
    expanded_case_count: NonNegativeInteger
    case_matrix_sha256: ContentHash

    # Frozen repository state
    frozen_files: _Tuple[FrozenFileHash]
    lockfile_sha256: ContentHash


def _severity_profiles() -> tuple[FrozenSeverityProfile, ...]:
    """Record every family's numeric severity definition, from the contracts."""
    profiles: list[FrozenSeverityProfile] = []
    for severity in RELEASE_SEVERITIES:
        lookahead = lookahead_severity_profile(severity)  # type: ignore[arg-type]
        profiles.append(
            FrozenSeverityProfile(
                fault_profile="lookahead_timestamp",
                severity=severity,
                frozen_target_fraction=lookahead.target_fraction,
                frozen_parameter_name="minimum_lag_days",
                frozen_parameter_value=Decimal(lookahead.minimum_lag_days),
            )
        )
        drift = unit_drift_severity_profile(severity)  # type: ignore[arg-type]
        profiles.append(
            FrozenSeverityProfile(
                fault_profile="unit_drift",
                severity=severity,
                frozen_target_fraction=drift.target_fraction,
                frozen_parameter_name="scale_factor",
                frozen_parameter_value=drift.scale_factor,
            )
        )
        duplicate = duplicate_severity_profile(severity)  # type: ignore[arg-type]
        profiles.append(
            FrozenSeverityProfile(
                fault_profile="duplicate_observation",
                severity=severity,
                frozen_target_fraction=duplicate.target_fraction,
            )
        )
        revision = revision_overwrite_severity_profile(severity)  # type: ignore[arg-type]
        profiles.append(
            FrozenSeverityProfile(
                fault_profile="revision_overwrite",
                severity=severity,
                frozen_target_fraction=revision.target_fraction,
                frozen_parameter_name="minimum_relative_revision_size",
                frozen_parameter_value=revision.minimum_relative_revision_size,
            )
        )
    return tuple(profiles)


def _fault_specifications() -> tuple[FrozenFaultSpecification, ...]:
    """Record the four families' frozen identities and scoring rules."""
    return (
        FrozenFaultSpecification(
            fault_profile="lookahead_timestamp",
            fault_type=LOOKAHEAD_FAULT_TYPE,
            fault_subtype=LOOKAHEAD_FAULT_SUBTYPE,
            injector_spec_version=LOOKAHEAD_SPEC_VERSION,
            detector_id=LOOKAHEAD_DETECTOR_ID,
            detector_version=LOOKAHEAD_DETECTOR_VERSION,
            scoring_spec_version=LOOKAHEAD_SCORING_SPEC_VERSION,
            matching_rule=_MATCHING_RULES["lookahead_timestamp"],
            false_positive_denominator_rule=_DENOMINATOR_RULES["lookahead_timestamp"],
            replay_method=_REPLAY_METHOD,
        ),
        FrozenFaultSpecification(
            fault_profile="unit_drift",
            fault_type=UNIT_DRIFT_FAULT_TYPE,
            fault_subtype=UNIT_DRIFT_FAULT_SUBTYPE,
            injector_spec_version=UNIT_DRIFT_SPEC_VERSION,
            detector_id=UNIT_DRIFT_DETECTOR_ID,
            detector_version=UNIT_DRIFT_DETECTOR_VERSION,
            scoring_spec_version=UNIT_DRIFT_SCORING_SPEC_VERSION,
            matching_rule=_MATCHING_RULES["unit_drift"],
            false_positive_denominator_rule=_DENOMINATOR_RULES["unit_drift"],
            replay_method=_REPLAY_METHOD,
        ),
        FrozenFaultSpecification(
            fault_profile="duplicate_observation",
            fault_type=DUPLICATE_FAULT_TYPE,
            fault_subtype=DUPLICATE_FAULT_SUBTYPE,
            injector_spec_version=DUPLICATE_SPEC_VERSION,
            detector_id=DUPLICATE_DETECTOR_ID,
            detector_version=DUPLICATE_DETECTOR_VERSION,
            scoring_spec_version=DUPLICATE_SCORING_SPEC_VERSION,
            matching_rule=_MATCHING_RULES["duplicate_observation"],
            false_positive_denominator_rule=_DENOMINATOR_RULES["duplicate_observation"],
            replay_method=_REPLAY_METHOD,
        ),
        FrozenFaultSpecification(
            fault_profile="revision_overwrite",
            fault_type=REVISION_OVERWRITE_FAULT_TYPE,
            fault_subtype=REVISION_OVERWRITE_FAULT_SUBTYPE,
            injector_spec_version=REVISION_OVERWRITE_SPEC_VERSION,
            detector_id=REVISION_OVERWRITE_DETECTOR_ID,
            detector_version=REVISION_OVERWRITE_DETECTOR_VERSION,
            scoring_spec_version=REVISION_OVERWRITE_SCORING_SPEC_VERSION,
            matching_rule=_MATCHING_RULES["revision_overwrite"],
            false_positive_denominator_rule=_DENOMINATOR_RULES["revision_overwrite"],
            replay_method=_REPLAY_METHOD,
        ),
    )


def _frozen_file_hashes(repo_root: Path) -> tuple[FrozenFileHash, ...]:
    """Hash every frozen repository file, refusing a missing one."""
    hashes: list[FrozenFileHash] = []
    for relative in FROZEN_SOURCE_FILES:
        path = repo_root / relative
        if not path.is_file():
            raise ReleaseFreezeError(f"frozen release input is missing: {relative}")
        hashes.append(FrozenFileHash(path=relative, sha256=sha256_hex_of_bytes(path.read_bytes())))
    return tuple(hashes)


def _record_body(record: ReleaseFreezeRecord) -> dict[str, object]:
    return {
        name: getattr(record, name)
        for name in ReleaseFreezeRecord.model_fields
        if name != "release_candidate_id"
    }


def build_release_freeze_record(
    *,
    repo_root: Path,
    package_version: str,
    python_requirement: str,
    config: BenchmarkConfig,
) -> ReleaseFreezeRecord:
    """Freeze one release candidate from the current repository state.

    ``config`` is the normalized release benchmark configuration, which the
    caller builds under an active final-seed authorization. The record's
    identity is the stable ID of everything else in it, so any change to a
    frozen file, a threshold, the matrix, or the configuration produces a
    different ``release_candidate_id``.
    """
    if config.benchmark_name != RELEASE_BENCHMARK_NAME:
        raise ReleaseFreezeError(
            "a release candidate may only freeze the release benchmark configuration"
        )
    matrix = expand_benchmark_cases(config)
    if matrix.case_count != RELEASE_TOTAL_CASE_COUNT:
        raise ReleaseFreezeError(
            f"the release matrix must expand to {RELEASE_TOTAL_CASE_COUNT} cases, "
            f"got {matrix.case_count}"
        )
    frozen_files = _frozen_file_hashes(repo_root)
    lockfile = next((entry for entry in frozen_files if entry.path == "uv.lock"), None)
    if lockfile is None:  # pragma: no cover - FROZEN_SOURCE_FILES always lists it
        raise ReleaseFreezeError("the frozen file list must include uv.lock")

    body: dict[str, object] = {
        "spec_version": RELEASE_SPEC_VERSION,
        "benchmark_spec_version": config.spec_version,
        "package_version": package_version,
        "python_requirement": python_requirement,
        "fault_profiles": RELEASE_FAULT_PROFILES,
        "severities": RELEASE_SEVERITIES,
        "final_seeds": RELEASE_SEEDS,
        "clean_control_policy": RELEASE_CLEAN_CONTROL_POLICY,
        "fault_case_count": RELEASE_FAULT_CASE_COUNT,
        "control_case_count": RELEASE_CONTROL_CASE_COUNT,
        "total_case_count": RELEASE_TOTAL_CASE_COUNT,
        "fault_specifications": _fault_specifications(),
        "severity_profiles": _severity_profiles(),
        "detector_configs_sha256": canonical_sha256(config.detector_configs),
        "unit_drift_ratio_threshold": UNIT_DRIFT_RATIO_THRESHOLD,
        "reviewed_fixture_id": REVIEWED_FIXTURE_ID,
        "reviewed_fixture_sha256": sha256_hex_of_bytes(canonical_reviewed_fixture_bytes()),
        "sec_reviewed_fixture_id": REVIEWED_SEC_FIXTURE_SPEC_VERSION,
        "sec_reviewed_fixture_sha256": sha256_hex_of_bytes(canonical_reviewed_sec_fixture_bytes()),
        "benchmark_id": config.benchmark_id,
        "release_config_sha256": canonical_sha256(config),
        "expanded_case_count": matrix.case_count,
        "case_matrix_sha256": canonical_sha256(matrix),
        "frozen_files": frozen_files,
        "lockfile_sha256": lockfile.sha256,
    }
    candidate_id = stable_id(
        prefix="relc",
        namespace=RELEASE_FREEZE_NAMESPACE,
        payload=body,
    )
    return ReleaseFreezeRecord.model_validate({"release_candidate_id": candidate_id, **body})


def release_freeze_record_hash(record: ReleaseFreezeRecord) -> str:
    """Return the SHA-256 of a freeze record's canonical bytes."""
    return canonical_sha256(record)


def verify_release_freeze_record(
    record: ReleaseFreezeRecord,
    *,
    repo_root: Path,
    config: BenchmarkConfig,
) -> None:
    """Refuse the candidate unless every frozen input still matches exactly.

    This is the check the release path runs before dispatching any final case.
    It never repairs and never warns: a single drifted byte invalidates the
    candidate, and a new candidate must be frozen instead.
    """
    if record.release_candidate_id != stable_id(
        prefix="relc",
        namespace=RELEASE_FREEZE_NAMESPACE,
        payload=_record_body(record),
    ):
        raise ReleaseFreezeError(
            "the release candidate identity does not match its own frozen content"
        )
    if record.benchmark_id != config.benchmark_id:
        raise ReleaseFreezeError("the release configuration is not the frozen one")
    if record.release_config_sha256 != canonical_sha256(config):
        raise ReleaseFreezeError("the release configuration bytes have drifted since the freeze")
    if tuple(record.final_seeds) != RELEASE_SEEDS:
        raise ReleaseFreezeError("the frozen final seed partition has changed")
    if tuple(record.severities) != RELEASE_SEVERITIES:
        raise ReleaseFreezeError("the frozen severity list has changed")
    if tuple(record.fault_profiles) != RELEASE_FAULT_PROFILES:
        raise ReleaseFreezeError("the frozen fault profile list has changed")
    if record.clean_control_policy != RELEASE_CLEAN_CONTROL_POLICY:
        raise ReleaseFreezeError("the frozen clean-control policy has changed")
    if record.severity_profiles != _severity_profiles():
        raise ReleaseFreezeError("a frozen severity definition has changed since the freeze")
    if record.fault_specifications != _fault_specifications():
        raise ReleaseFreezeError("a frozen fault specification has changed since the freeze")
    if record.unit_drift_ratio_threshold != UNIT_DRIFT_RATIO_THRESHOLD:
        raise ReleaseFreezeError("the frozen Unit Drift detector threshold has changed")
    if record.reviewed_fixture_sha256 != sha256_hex_of_bytes(canonical_reviewed_fixture_bytes()):
        raise ReleaseFreezeError("the reviewed fixture bytes have drifted since the freeze")
    if record.sec_reviewed_fixture_sha256 != sha256_hex_of_bytes(
        canonical_reviewed_sec_fixture_bytes()
    ):
        raise ReleaseFreezeError("the reviewed SEC fixture bytes have drifted since the freeze")

    current = {entry.path: entry.sha256 for entry in _frozen_file_hashes(repo_root)}
    frozen = {entry.path: entry.sha256 for entry in record.frozen_files}
    if set(current) != set(frozen):
        raise ReleaseFreezeError("the frozen file list no longer matches the repository")
    drifted = sorted(path for path, digest in frozen.items() if current[path] != digest)
    if drifted:
        raise ReleaseFreezeError(f"frozen release inputs have drifted: {drifted}")


def write_release_freeze_record(record: ReleaseFreezeRecord, *, destination: Path) -> bytes:
    """Write a freeze record's canonical bytes, refusing to overwrite a different one."""
    payload = canonical_json_bytes(record)
    if destination.exists():
        existing = destination.read_bytes()
        if existing != payload:
            raise ReleaseFreezeError(
                "a different release freeze record already exists at that destination"
            )
        return payload
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return payload


def read_release_freeze_record(path: Path) -> ReleaseFreezeRecord:
    """Load and strictly validate a saved freeze record."""
    if not path.is_file():
        raise ReleaseFreezeError("no release freeze record exists at that path")
    return ReleaseFreezeRecord.model_validate(parse_canonical_json(path.read_bytes()))
