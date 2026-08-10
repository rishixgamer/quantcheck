"""Security and deployment contract for the self-hosted batch entry point."""

from __future__ import annotations

import io
import json
import socket
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from quantcheck.external_dataset_execution_contract import (
    build_external_audit_execution_plan,
    build_external_audit_partition_spec,
)
from quantcheck.external_dataset_self_hosted import (
    SELF_HOSTED_CONFIG_SPEC_VERSION,
    SelfHostedConfigurationError,
    SelfHostedPartitionBindingV1,
    SelfHostedRunConfigV1,
    load_self_hosted_config,
    main,
    run_self_hosted_audit,
)
from quantcheck.serialization import canonical_json_bytes
from tests.external_dataset_support import (
    mapping,
    pinned_file_input,
    policy,
    reviewed_rows,
    write_csv,
)


def _config(input_root: Path) -> SelfHostedRunConfigV1:
    source = input_root / "partition.csv"
    write_csv(source, reviewed_rows())
    active_mapping = mapping()
    active_policy = policy()
    partition = build_external_audit_partition_spec(
        partition_key="customer-partition-001",
        source=pinned_file_input(source, "csv"),
        expected_record_count=3,
        mapping=active_mapping,
        policy=active_policy,
        as_of_date=date(2024, 12, 31),
    )
    plan = build_external_audit_execution_plan(
        mapping=active_mapping,
        policy=active_policy,
        as_of_date=date(2024, 12, 31),
        maximum_records_per_partition=10,
        partitions=(partition,),
    )
    return SelfHostedRunConfigV1(
        plan=plan,
        bindings=(
            SelfHostedPartitionBindingV1(
                partition_id=partition.partition_id,
                input_path="partition.csv",
            ),
        ),
    )


def test_self_hosted_audit_is_offline_and_emits_only_redacted_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    work_root = tmp_path / "work"
    work_root.mkdir()
    config = _config(input_root)
    config_path = tmp_path / "run.json"
    config_path.write_bytes(canonical_json_bytes(config))

    def deny_network(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("self-hosted audit attempted network access")

    monkeypatch.setattr(socket, "socket", deny_network)
    stdout = io.StringIO()
    exit_code = main(
        (),
        environ={
            "QUANTCHECK_CONFIG_PATH": str(config_path),
            "QUANTCHECK_INPUT_DIR": str(input_root),
            "QUANTCHECK_OUTPUT_DIR": str(output_root),
            "QUANTCHECK_WORK_DIR": str(work_root),
        },
        stdout=stdout,
    )

    assert exit_code == 0
    events = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [event["event"] for event in events] == ["audit_started", "audit_completed"]
    assert all(event["redacted"] is True for event in events)
    log_text = stdout.getvalue()
    for forbidden in (
        "100.25",
        "120.00",
        "130",
        "Example Customer Issuer",
        "customer-warehouse",
        "customer://",
        str(input_root),
        str(output_root),
    ):
        assert forbidden not in log_text
    assert (output_root / "public" / "runs" / config.plan.run_id / "finalization.json").is_file()


def test_config_rejects_secrets_telemetry_and_network_requests(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    config = _config(input_root)
    document = config.model_dump(mode="python")
    document["api_token"] = "do-not-accept-me"
    with pytest.raises(ValidationError):
        SelfHostedRunConfigV1.model_validate(document)

    for field in ("telemetry", "network_required"):
        document = config.model_dump(mode="python")
        document[field] = True
        with pytest.raises(ValidationError):
            SelfHostedRunConfigV1.model_validate(document)


@pytest.mark.parametrize(
    "path",
    ("/absolute.csv", "../escape.csv", "nested/../../escape.csv", r"windows\\path.csv", "~/.csv"),
)
def test_binding_rejects_paths_outside_the_input_mount(path: str) -> None:
    with pytest.raises(ValidationError):
        SelfHostedPartitionBindingV1(partition_id="xpart_0000000000000000", input_path=path)


def test_runtime_rejects_a_symlinked_input(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    input_root.mkdir()
    config = _config(input_root)
    target = input_root / "partition.csv"
    moved = tmp_path / "outside.csv"
    target.rename(moved)
    target.symlink_to(moved)
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(SelfHostedConfigurationError, match="partition input is invalid"):
        run_self_hosted_audit(config, input_root=input_root, output_root=output)


def test_failure_log_never_echoes_invalid_config_or_exception_details(tmp_path: Path) -> None:
    secret = "super-secret-financial-value-918273"
    config_path = tmp_path / "run.json"
    config_path.write_text('{"api_token":"' + secret + '"}', encoding="utf-8")
    stdout = io.StringIO()
    exit_code = main(
        (),
        environ={"QUANTCHECK_CONFIG_PATH": str(config_path)},
        stdout=stdout,
    )
    assert exit_code == 2
    assert secret not in stdout.getvalue()
    assert json.loads(stdout.getvalue()) == {
        "code": "configuration_invalid",
        "event": "audit_failed",
        "redacted": True,
        "spec_version": SELF_HOSTED_CONFIG_SPEC_VERSION,
    }


def test_environment_cannot_enable_telemetry() -> None:
    stdout = io.StringIO()
    exit_code = main((), environ={"QUANTCHECK_TELEMETRY": "1"}, stdout=stdout)
    assert exit_code == 2
    assert json.loads(stdout.getvalue())["code"] == "telemetry_must_remain_disabled"


def test_invalid_arguments_are_redacted() -> None:
    secret = "--password=never-echo-this"
    stdout = io.StringIO()
    exit_code = main((secret,), environ={}, stdout=stdout)
    assert exit_code == 2
    assert secret not in stdout.getvalue()
    assert json.loads(stdout.getvalue())["code"] == "arguments_invalid"


def test_module_entry_point_reads_process_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "argv", ["quantcheck-self-hosted", "--help"])
    assert main(None, environ={}, stdout=stdout) == 0
    assert stdout.getvalue().startswith("usage: quantcheck-self-hosted")


def test_load_rejects_non_file_and_oversized_configuration(tmp_path: Path) -> None:
    with pytest.raises(SelfHostedConfigurationError, match="deployment configuration is invalid"):
        load_self_hosted_config(tmp_path)

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (8 * 1024 * 1024 + 1))
    with pytest.raises(SelfHostedConfigurationError, match="deployment configuration is invalid"):
        load_self_hosted_config(oversized)
