"""SHA-256 content hashes and deterministic stable identifiers."""

from __future__ import annotations

import ast
import hashlib
import inspect
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from types import ModuleType

import pytest

from quantcheck import hashing, json_types, schemas, serialization
from quantcheck.hashing import (
    AUDIT_INPUT_SNAPSHOT_NAMESPACE,
    DATASET_SNAPSHOT_NAMESPACE,
    SOURCE_RECORD_NAMESPACE,
    STABLE_ID_DIGEST_LENGTH,
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
from quantcheck.json_types import CanonicalizationError
from quantcheck.schemas import AuditInputSnapshot, CaseConfig, DatasetSnapshot, RuntimeMetadata
from tests.support import audit_input_record, financial_fact

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


# --- SHA-256 itself, against published vectors -------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        (b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
        (
            b"The quick brown fox jumps over the lazy dog",
            "d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592",
        ),
    ],
)
def test_sha256_matches_known_vectors(data: bytes, expected: str) -> None:
    assert sha256_hex_of_bytes(data) == expected


def test_sha256_hex_of_bytes_rejects_text() -> None:
    with pytest.raises(CanonicalizationError, match="expected bytes"):
        sha256_hex_of_bytes("abc")  # type: ignore[arg-type]


def test_canonical_sha256_is_sha256_of_the_canonical_bytes() -> None:
    from quantcheck.serialization import canonical_json_bytes

    fact = financial_fact()
    assert canonical_sha256(fact) == hashlib.sha256(canonical_json_bytes(fact)).hexdigest()
    assert _HEX_64.fullmatch(canonical_sha256(fact))


def test_canonical_sha256_rejects_unsupported_values() -> None:
    with pytest.raises(CanonicalizationError):
        canonical_sha256({"v": 1.5})


# --- stable_id format and framing --------------------------------------------


def test_stable_id_has_the_documented_prefix_and_length() -> None:
    identifier = stable_id(prefix="rec", namespace="ns/v1", payload={"a": 1})
    assert identifier.startswith("rec_")
    assert re.fullmatch(r"rec_[0-9a-f]{16}", identifier)
    assert len(identifier.split("_")[1]) == STABLE_ID_DIGEST_LENGTH


def test_stable_id_digest_is_a_prefix_of_the_full_digest() -> None:
    payload = {"a": 1}
    identifier = stable_id(prefix="x", namespace="ns/v1", payload=payload)
    envelope = {
        "id_scheme": hashing.STABLE_ID_SCHEME,
        "namespace": "ns/v1",
        "payload": payload,
    }
    assert identifier == f"x_{canonical_sha256(envelope)[:STABLE_ID_DIGEST_LENGTH]}"


def test_stable_id_honours_a_custom_digest_length() -> None:
    identifier = stable_id(prefix="x", namespace="ns/v1", payload={}, digest_length=32)
    assert re.fullmatch(r"x_[0-9a-f]{32}", identifier)


def test_the_namespace_separates_identical_payloads() -> None:
    payload = {"a": 1}
    left = stable_id(prefix="x", namespace="ns/one", payload=payload)
    right = stable_id(prefix="x", namespace="ns/two", payload=payload)
    assert left != right


@pytest.mark.parametrize("prefix", ["", "Rec", "1rec", "rec_", "rec-id", "a" * 17, "réc"])
def test_malformed_prefixes_are_rejected(prefix: str) -> None:
    with pytest.raises(CanonicalizationError, match="prefix"):
        stable_id(prefix=prefix, namespace="ns/v1", payload={})


def test_empty_namespace_is_rejected() -> None:
    with pytest.raises(CanonicalizationError, match="namespace"):
        stable_id(prefix="x", namespace="", payload={})


@pytest.mark.parametrize("length", [0, 7, 65, -1])
def test_out_of_range_digest_lengths_are_rejected(length: int) -> None:
    with pytest.raises(CanonicalizationError, match="digest_length"):
        stable_id(prefix="x", namespace="ns/v1", payload={}, digest_length=length)


def test_boolean_digest_length_is_rejected() -> None:
    with pytest.raises(CanonicalizationError, match="digest_length"):
        stable_id(prefix="x", namespace="ns/v1", payload={}, digest_length=True)


def test_stable_id_rejects_an_unsupported_payload() -> None:
    with pytest.raises(CanonicalizationError):
        stable_id(prefix="x", namespace="ns/v1", payload={"v": 1.5})


# --- determinism and sensitivity ---------------------------------------------


def test_identical_logical_input_gives_identical_ids() -> None:
    kwargs = {
        "source_name": "reviewed-fixture",
        "source_locator": "fixture-0001",
        "source_row_key": "row-1",
    }
    assert len({source_record_id(**kwargs) for _ in range(20)}) == 1


def test_a_meaningful_change_changes_the_id() -> None:
    base = source_record_id(
        source_name="reviewed-fixture", source_locator="fixture-0001", source_row_key="row-1"
    )
    assert base != source_record_id(
        source_name="reviewed-fixture", source_locator="fixture-0001", source_row_key="row-2"
    )
    assert base != source_record_id(
        source_name="reviewed-fixture", source_locator="fixture-0002", source_row_key="row-1"
    )
    assert base != source_record_id(
        source_name="other-fixture", source_locator="fixture-0001", source_row_key="row-1"
    )


def test_mapping_insertion_order_does_not_affect_the_hash() -> None:
    forward = {"alpha": 1, "beta": {"x": 1, "y": 2}}
    backward = {"beta": {"y": 2, "x": 1}, "alpha": 1}
    assert canonical_sha256(forward) == canonical_sha256(backward)
    assert stable_id(prefix="x", namespace="ns/v1", payload=forward) == stable_id(
        prefix="x", namespace="ns/v1", payload=backward
    )


def test_snapshot_id_ignores_record_order() -> None:
    first = financial_fact(record_id="rec_aaaaaaaaaaaaaaaa")
    second = financial_fact(record_id="rec_bbbbbbbbbbbbbbbb")
    forward = dataset_snapshot_id(
        dataset_name="demo", as_of_date=date(2024, 6, 30), records=[first, second]
    )
    backward = dataset_snapshot_id(
        dataset_name="demo", as_of_date=date(2024, 6, 30), records=[second, first]
    )
    assert forward == backward


def test_snapshot_id_changes_when_a_record_value_changes() -> None:
    base = dataset_snapshot_id(
        dataset_name="demo", as_of_date=date(2024, 6, 30), records=[financial_fact()]
    )
    changed = dataset_snapshot_id(
        dataset_name="demo",
        as_of_date=date(2024, 6, 30),
        records=[financial_fact(value=Decimal("1"))],
    )
    assert base != changed


def test_snapshot_id_changes_when_the_as_of_date_changes() -> None:
    base = dataset_snapshot_id(
        dataset_name="demo", as_of_date=date(2024, 6, 30), records=[financial_fact()]
    )
    changed = dataset_snapshot_id(
        dataset_name="demo", as_of_date=date(2024, 7, 1), records=[financial_fact()]
    )
    assert base != changed


def test_dataset_and_audit_snapshot_ids_use_distinct_prefixes_and_namespaces() -> None:
    assert dataset_snapshot_id(
        dataset_name="demo", as_of_date=date(2024, 6, 30), records=[]
    ).startswith("snap_")
    assert audit_input_snapshot_id(
        dataset_name="demo", as_of_date=date(2024, 6, 30), records=[]
    ).startswith("audit_")
    assert DATASET_SNAPSHOT_NAMESPACE != AUDIT_INPUT_SNAPSHOT_NAMESPACE
    assert SOURCE_RECORD_NAMESPACE not in (
        DATASET_SNAPSHOT_NAMESPACE,
        AUDIT_INPUT_SNAPSHOT_NAMESPACE,
    )


def test_audit_input_snapshot_id_ignores_record_order() -> None:
    first = audit_input_record(record_id="rec_aaaaaaaaaaaaaaaa")
    second = audit_input_record(record_id="rec_bbbbbbbbbbbbbbbb")
    forward = audit_input_snapshot_id(
        dataset_name="demo", as_of_date=date(2024, 6, 30), records=[first, second]
    )
    backward = audit_input_snapshot_id(
        dataset_name="demo", as_of_date=date(2024, 6, 30), records=[second, first]
    )
    assert forward == backward


def test_case_config_id_is_sensitive_to_every_logical_field() -> None:
    base_kwargs = {
        "case_name": "look-ahead-medium",
        "dataset_name": "reviewed-demo",
        "as_of_date": date(2024, 6, 30),
        "seed": 42,
        "spec_version": "v0.1",
    }
    base = case_config_id(**base_kwargs)  # type: ignore[arg-type]
    for field, replacement in [
        ("case_name", "look-ahead-high"),
        ("dataset_name", "other"),
        ("as_of_date", date(2024, 7, 1)),
        ("seed", 43),
        ("spec_version", "v0.2"),
    ]:
        changed = dict(base_kwargs)
        changed[field] = replacement
        assert case_config_id(**changed) != base  # type: ignore[arg-type]


# --- runtime independence -----------------------------------------------------


def test_runtime_metadata_does_not_change_logical_identity() -> None:
    config = CaseConfig(
        case_id=case_config_id(
            case_name="c",
            dataset_name="d",
            as_of_date=date(2024, 6, 30),
            seed=1,
            spec_version="v0.1",
        ),
        case_name="c",
        dataset_name="d",
        as_of_date=date(2024, 6, 30),
        seed=1,
        spec_version="v0.1",
    )
    early = RuntimeMetadata(
        code_version="quantcheck-0.1.0.dev0",
        python_version="3.12.13",
        platform="darwin-arm64",
        generated_at=datetime(2026, 8, 6, 1, 0, 0, tzinfo=UTC),
    )
    later = RuntimeMetadata(
        code_version="quantcheck-0.1.0.dev0",
        python_version="3.12.13",
        platform="linux-x86_64",
        generated_at=datetime(2027, 1, 1, 23, 59, 59, tzinfo=UTC),
    )
    assert early != later
    assert case_config_identity_matches(config)
    assert canonical_sha256(config) == canonical_sha256(config)
    # The identity helper has no runtime parameter at all.
    assert "runtime" not in inspect.signature(case_config_id).parameters
    assert "generated_at" not in inspect.signature(case_config_id).parameters


def test_no_identity_helper_accepts_a_path_or_output_directory() -> None:
    path_like = {"path", "output_dir", "output_root", "directory", "tmpdir", "cwd", "filename"}
    for name in (
        "source_record_id",
        "dataset_snapshot_id",
        "audit_input_snapshot_id",
        "case_config_id",
    ):
        parameters = set(inspect.signature(getattr(hashing, name)).parameters)
        assert path_like.isdisjoint(parameters), name


@pytest.mark.parametrize("module", [hashing, schemas, serialization, json_types])
def test_no_module_calls_uuid_builtin_hash_or_id(module: ModuleType) -> None:
    """Checked against the parsed syntax tree, not the prose, so docstrings
    that merely *mention* uuid4 cannot make this pass or fail spuriously."""
    tree = ast.parse(inspect.getsource(module))

    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                called.add(node.func.attr)

    assert "uuid" not in imported
    assert {"hash", "id", "uuid1", "uuid4", "getrandbits", "random"}.isdisjoint(called)


# --- identity verifiers -------------------------------------------------------


def test_dataset_snapshot_identity_verifier_accepts_a_consistent_snapshot() -> None:
    records = (financial_fact(),)
    snapshot = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name="demo", as_of_date=date(2024, 6, 30), records=records
        ),
        dataset_name="demo",
        as_of_date=date(2024, 6, 30),
        records=records,
    )
    assert dataset_snapshot_identity_matches(snapshot)


def test_dataset_snapshot_identity_verifier_rejects_a_mismatched_id() -> None:
    snapshot = DatasetSnapshot(
        snapshot_id="snap_0123456789abcdef",
        dataset_name="demo",
        as_of_date=date(2024, 6, 30),
        records=(financial_fact(),),
    )
    assert not dataset_snapshot_identity_matches(snapshot)


def test_audit_input_snapshot_identity_verifier_round_trips() -> None:
    records = (audit_input_record(),)
    snapshot = AuditInputSnapshot(
        audit_input_id=audit_input_snapshot_id(
            dataset_name="demo", as_of_date=date(2024, 6, 30), records=records
        ),
        dataset_name="demo",
        as_of_date=date(2024, 6, 30),
        records=records,
    )
    assert audit_input_snapshot_identity_matches(snapshot)


def test_build_artifact_identity_pairs_id_with_content_hash() -> None:
    fact = financial_fact()
    identity = build_artifact_identity(
        kind="financial-fact", stable_identifier=fact.record_id, content=fact
    )
    assert identity.kind == "financial-fact"
    assert identity.stable_id == fact.record_id
    assert identity.content_hash == canonical_sha256(fact)
