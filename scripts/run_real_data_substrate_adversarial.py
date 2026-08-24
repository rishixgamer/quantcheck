"""Execute the prospectively frozen real-data-substrate adversarial study.

This is evaluation orchestration only. It uses existing QuantCheck snapshots,
injectors, sanitized detectors, and exact scorers without changing them.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from quantcheck.audit_boundary import sanitize_for_audit
from quantcheck.duplicate_detection import detect_duplicate_observations
from quantcheck.duplicate_injection import inject_duplicate_observations
from quantcheck.duplicate_scoring import score_duplicate_observations
from quantcheck.hashing import canonical_sha256, dataset_snapshot_id
from quantcheck.lookahead_contract import is_eligible_lookahead_target
from quantcheck.lookahead_detection import detect_lookahead
from quantcheck.lookahead_injection import inject_lookahead
from quantcheck.lookahead_scoring import score_lookahead
from quantcheck.schemas import (
    DatasetSnapshot,
    DuplicateInjectionConfig,
    LookAheadInjectionConfig,
    UnitDriftDetectorConfig,
    UnitDriftInjectionConfig,
)
from quantcheck.serialization import canonical_json_bytes
from quantcheck.unit_drift_detection import detect_unit_drift
from quantcheck.unit_drift_injection import inject_unit_drift
from quantcheck.unit_drift_scoring import score_unit_drift
from quantcheck.unit_drift_series import (
    build_comparable_observations,
    comparable_series_key,
)

PROTOCOL = Path("docs/research/REAL_DATA_SUBSTRATE_ADVERSARIAL_PROTOCOL.md")
FREEZE = Path("evidence/real_data_substrate_adversarial_protocol_freeze.json")
SOURCE_ROOT = Path("evidence/real_data_study/companies")
OUTPUT_ROOT = Path("evidence/real_data_substrate_adversarial")
AS_OF_DATE = date(2024, 12, 31)
RESEARCH_AS_OF_DATE = date(2023, 12, 31)
SEEDS = (101, 202, 303)
EXPECTED_SOURCE_HASHES = {
    "alphabet": "d328647f09c8a3f099eeaabc87fba11af07e01c9f209b92f150f87de38a0b872",
    "amazon": "d1e041a5b72dd12629076d5336a8c4230ea3e203e7823903f6aece592a842c56",
    "apple": "7b332134aca42263b55835d825394b5d236c86a6afed2386eb8b33ed6e47ca88",
    "jpmorgan": "75410508de281e20eb343f071fba7a72075c17eb198262632bf2cb76094af55c",
    "microsoft": "eec8bd268fcf01d0716dc785dbd64321cc778ad8016517bcf1740097aa445183",
}
EXPECTED_FULL_ID = "snap_5eee9e1e6a6613f2"
EXPECTED_FULL_HASH = "efebaf6fc7204bf570f9f50b7332c4a062fb3297858f390dce80620627b80203"
EXPECTED_UNIT_ID = "snap_875bba34e465d51f"
EXPECTED_UNIT_HASH = "5ba093bd607568b4d6097259ae99e5ee95f7640b31b6178666957e64290dd0b6"


def write_canonical(path: Path, value: object) -> None:
    content = canonical_json_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise SystemExit(f"refusing to overwrite study artifact: {path}")
    path.write_bytes(content)


def load_sources() -> tuple[DatasetSnapshot, ...]:
    snapshots: list[DatasetSnapshot] = []
    for slug, expected_hash in EXPECTED_SOURCE_HASHES.items():
        path = SOURCE_ROOT / slug / "snapshot.json"
        snapshot = DatasetSnapshot.model_validate_json(path.read_bytes())
        actual_hash = canonical_sha256(snapshot)
        if actual_hash != expected_hash:
            raise SystemExit(f"source snapshot hash mismatch for {slug}: {actual_hash}")
        snapshots.append(snapshot)
    return tuple(snapshots)


def build_full_snapshot(snapshots: tuple[DatasetSnapshot, ...]) -> DatasetSnapshot:
    records = tuple(record for snapshot in snapshots for record in snapshot.records)
    snapshot = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name="real-data-substrate-all-issuers",
            as_of_date=AS_OF_DATE,
            records=records,
        ),
        dataset_name="real-data-substrate-all-issuers",
        as_of_date=AS_OF_DATE,
        records=records,
    )
    if snapshot.snapshot_id != EXPECTED_FULL_ID or canonical_sha256(snapshot) != EXPECTED_FULL_HASH:
        raise SystemExit("combined source substrate does not match the frozen identity")
    return snapshot


def build_unit_snapshot(full: DatasetSnapshot) -> tuple[DatasetSnapshot, dict[str, int]]:
    coordinate_groups: dict[tuple[object, date, date], list[Any]] = defaultdict(list)
    for record in full.records:
        coordinate_groups[
            (
                comparable_series_key(record),
                record.period_end,
                record.period_start or record.period_end,
            )
        ].append(record)

    selected = []
    collapsed_equal = 0
    conflicting_records = 0
    conflicting_coordinates = 0
    for members in coordinate_groups.values():
        if len({record.value for record in members}) > 1:
            conflicting_records += len(members)
            conflicting_coordinates += 1
            continue
        selected.append(
            max(
                members,
                key=lambda record: (
                    record.filed_on,
                    record.available_on,
                    record.accession_number or "",
                    record.record_id,
                ),
            )
        )
        collapsed_equal += len(members) - 1

    records = tuple(selected)
    snapshot = DatasetSnapshot(
        snapshot_id=dataset_snapshot_id(
            dataset_name="real-data-substrate-unit-dealiased",
            as_of_date=AS_OF_DATE,
            records=records,
        ),
        dataset_name="real-data-substrate-unit-dealiased",
        as_of_date=AS_OF_DATE,
        records=records,
    )
    if snapshot.snapshot_id != EXPECTED_UNIT_ID or canonical_sha256(snapshot) != EXPECTED_UNIT_HASH:
        raise SystemExit("Unit Drift selected substrate does not match the frozen identity")
    accounting = {
        "coordinate_groups": len(coordinate_groups),
        "collapsed_equal_value_occurrences": collapsed_equal,
        "conflicting_value_records_excluded": conflicting_records,
        "conflicting_value_coordinates_excluded": conflicting_coordinates,
        "selected_records": len(snapshot.records),
    }
    return snapshot, accounting


def git_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_family(
    *,
    family: str,
    clean: DatasetSnapshot,
    detector: Callable[..., Any],
    injector: Callable[..., Any],
    scorer: Callable[..., Any],
    config_factory: Callable[[int], Any],
    detector_config: object | None = None,
) -> dict[str, object]:
    clean_audit = sanitize_for_audit(clean)
    control_report = (
        detector(clean_audit, detector_config)
        if detector_config is not None
        else detector(clean_audit)
    )
    write_canonical(OUTPUT_ROOT / "public" / family / "clean_control_report.json", control_report)
    case_rows: list[dict[str, object]] = []
    selected_ids_by_seed: dict[str, list[str]] = {}

    for seed in SEEDS:
        config = config_factory(seed)
        corrupted, manifest = injector(clean, config)
        audit_input = sanitize_for_audit(corrupted)
        report = (
            detector(audit_input, detector_config)
            if detector_config is not None
            else detector(audit_input)
        )
        score = scorer(report, manifest)
        case_id = f"seed-{seed}"
        public_root = OUTPUT_ROOT / "public" / family / case_id
        private_root = OUTPUT_ROOT / "private" / family / case_id
        write_canonical(public_root / "injection_config.json", config)
        write_canonical(public_root / "audit_input.json", audit_input)
        write_canonical(public_root / "audit_report.json", report)
        write_canonical(public_root / "score_report.json", score)
        write_canonical(private_root / "manifest.json", manifest)
        selected_ids_by_seed[str(seed)] = sorted(
            entry.eligibility_unit_id for entry in manifest.entries
        )
        case_rows.append(
            {
                "seed": seed,
                "manifest_id": manifest.manifest_id,
                "eligible_record_count": manifest.eligible_record_count,
                "target_count": manifest.target_count,
                "audit_report_id": report.audit_report_id,
                "score_report_id": score.score_report_id,
                "metrics": score.metrics,
                "f1": score.f1,
                "unmatched_finding_count": len(score.unmatched_finding_ids),
                "missed_fault_count": len(score.missed_fault_ids),
                "ambiguous_finding_count": len(score.ambiguous_finding_ids),
                "ambiguous_fault_count": len(score.ambiguous_fault_ids),
            }
        )

    target_sets = [set(ids) for ids in selected_ids_by_seed.values()]
    overlap = {
        "unique_target_record_count_across_seeds": len(set().union(*target_sets)),
        "target_record_count_repeated_across_seeds": sum(
            sum(record_id in target_set for target_set in target_sets) > 1
            for record_id in set().union(*target_sets)
        ),
    }
    return {
        "family": family,
        "clean_snapshot_id": clean.snapshot_id,
        "clean_snapshot_hash": canonical_sha256(clean),
        "clean_control_audit_report_id": control_report.audit_report_id,
        "clean_control_finding_count": len(control_report.findings),
        "cases": case_rows,
        "target_selection_by_seed": selected_ids_by_seed,
        "target_overlap": overlap,
    }


def main() -> None:
    if OUTPUT_ROOT.exists():
        raise SystemExit(f"refusing to overwrite completed study root: {OUTPUT_ROOT}")
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    if freeze["seeds"] != list(SEEDS):
        raise SystemExit("protocol freeze does not match runner seeds")

    sources = load_sources()
    full = build_full_snapshot(sources)
    unit, unit_accounting = build_unit_snapshot(full)

    lookahead_probe = LookAheadInjectionConfig(
        severity="medium",
        seed=SEEDS[0],
        research_as_of_date=RESEARCH_AS_OF_DATE,
        max_targets=100,
    )
    lookahead_eligible = sum(
        is_eligible_lookahead_target(record, lookahead_probe) for record in full.records
    )
    unit_eligible = len(build_comparable_observations(unit.records, as_of_date=unit.as_of_date))
    if (lookahead_eligible, unit_eligible) != (73, 239):
        raise SystemExit("structural eligibility no longer matches the frozen protocol")

    unit_detector_config = UnitDriftDetectorConfig()
    families = [
        run_family(
            family="lookahead_timestamp",
            clean=full,
            detector=detect_lookahead,
            injector=inject_lookahead,
            scorer=score_lookahead,
            config_factory=lambda seed: LookAheadInjectionConfig(
                severity="medium",
                seed=seed,
                research_as_of_date=RESEARCH_AS_OF_DATE,
                max_targets=100,
            ),
        ),
        run_family(
            family="duplicate_observation",
            clean=full,
            detector=detect_duplicate_observations,
            injector=inject_duplicate_observations,
            scorer=score_duplicate_observations,
            config_factory=lambda seed: DuplicateInjectionConfig(
                severity="medium", seed=seed, max_targets=100
            ),
        ),
        run_family(
            family="unit_drift",
            clean=unit,
            detector=detect_unit_drift,
            injector=inject_unit_drift,
            scorer=score_unit_drift,
            config_factory=lambda seed: UnitDriftInjectionConfig(
                severity="medium", seed=seed, max_targets=100
            ),
            detector_config=unit_detector_config,
        ),
    ]
    write_canonical(
        OUTPUT_ROOT / "study_run.json",
        {
            "study": "quantcheck-real-data-substrate-adversarial/v1",
            "completed_at_utc": datetime.now(UTC).replace(microsecond=0),
            "git_revision": git_revision(),
            "protocol_sha256": sha256_file(PROTOCOL),
            "protocol_freeze_sha256": sha256_file(FREEZE),
            "runner_sha256": sha256_file(Path(__file__)),
            "source_snapshot_ids": [snapshot.snapshot_id for snapshot in sources],
            "full_substrate": {
                "snapshot_id": full.snapshot_id,
                "snapshot_hash": canonical_sha256(full),
                "record_count": len(full.records),
            },
            "unit_substrate": {
                "snapshot_id": unit.snapshot_id,
                "snapshot_hash": canonical_sha256(unit),
                "record_count": len(unit.records),
                "selection_accounting": unit_accounting,
            },
            "seeds": SEEDS,
            "revision_overwrite": {
                "status": "NOT_APPLICABLE",
                "eligible_opportunity_count": 0,
                "reason": "SEC adapter does not declare revision lineage",
            },
            "families": families,
        },
    )


if __name__ == "__main__":
    main()
