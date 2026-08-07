"""QuantCheck: deterministic point-in-time financial data reliability auditing.

The canonical contract layer — strict JSON value types, immutable domain
schemas, one canonical serialization path, SHA-256 hashing, and deterministic
stable identifiers — is implemented. Fixtures, point-in-time snapshot
selection, the SEC adapter, fault injectors, detectors, scoring, benchmark
artifacts, and presentation are not.
"""

from quantcheck.hashing import (
    AUDIT_INPUT_SNAPSHOT_NAMESPACE,
    CASE_CONFIG_NAMESPACE,
    DATASET_SNAPSHOT_NAMESPACE,
    SOURCE_RECORD_NAMESPACE,
    STABLE_ID_DIGEST_LENGTH,
    STABLE_ID_SCHEME,
    audit_input_snapshot_id,
    audit_input_snapshot_identity_matches,
    build_artifact_identity,
    canonical_sha256,
    case_config_id,
    case_config_identity_matches,
    dataset_snapshot_id,
    dataset_snapshot_identity_matches,
    sha256_hex_of_bytes,
    source_record_id,
    stable_id,
)
from quantcheck.json_types import (
    CanonicalizationError,
    JsonValue,
    canonical_date_string,
    canonical_datetime_string,
    canonical_decimal_string,
    parse_canonical_date,
    parse_canonical_datetime,
    parse_canonical_decimal,
)
from quantcheck.schemas import (
    ArtifactIdentity,
    AuditInputRecord,
    AuditInputSnapshot,
    CanonicalModel,
    CaseConfig,
    DatasetSnapshot,
    Dimension,
    FinancialFact,
    PeriodType,
    RuntimeMetadata,
    SourceReference,
)
from quantcheck.serialization import (
    canonical_json_bytes,
    canonical_json_text,
    parse_canonical_json,
    to_canonical_json,
)

__version__ = "0.1.0.dev0"

__all__ = [
    "AUDIT_INPUT_SNAPSHOT_NAMESPACE",
    "CASE_CONFIG_NAMESPACE",
    "DATASET_SNAPSHOT_NAMESPACE",
    "SOURCE_RECORD_NAMESPACE",
    "STABLE_ID_DIGEST_LENGTH",
    "STABLE_ID_SCHEME",
    "ArtifactIdentity",
    "AuditInputRecord",
    "AuditInputSnapshot",
    "CanonicalModel",
    "CanonicalizationError",
    "CaseConfig",
    "DatasetSnapshot",
    "Dimension",
    "FinancialFact",
    "JsonValue",
    "PeriodType",
    "RuntimeMetadata",
    "SourceReference",
    "__version__",
    "audit_input_snapshot_id",
    "audit_input_snapshot_identity_matches",
    "build_artifact_identity",
    "canonical_date_string",
    "canonical_datetime_string",
    "canonical_decimal_string",
    "canonical_json_bytes",
    "canonical_json_text",
    "canonical_sha256",
    "case_config_id",
    "case_config_identity_matches",
    "dataset_snapshot_id",
    "dataset_snapshot_identity_matches",
    "parse_canonical_date",
    "parse_canonical_datetime",
    "parse_canonical_decimal",
    "parse_canonical_json",
    "sha256_hex_of_bytes",
    "source_record_id",
    "stable_id",
    "to_canonical_json",
]
