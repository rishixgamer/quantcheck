"""Write or verify the frozen Missing Observations synthetic evaluation evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from quantcheck.missing_observation_evaluation import run_missing_observation_evaluation
from quantcheck.missing_observation_fixture import (
    MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
    evaluation_case_ids,
)
from quantcheck.missing_observation_gate import heldout_missing_observation_cases
from quantcheck.serialization import canonical_json_bytes

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = REPOSITORY_ROOT / "missing_observation_evaluation_v1.json"


def _evidence_bytes() -> bytes:
    with heldout_missing_observation_cases(
        freeze_id=MISSING_OBSERVATION_EVALUATION_FREEZE_ID,
        case_ids=evaluation_case_ids("heldout"),
    ):
        return canonical_json_bytes(run_missing_observation_evaluation())


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
    arguments = parser.parse_args()
    expected = _evidence_bytes()
    destination = arguments.path
    if arguments.check:
        if not destination.is_file() or destination.read_bytes() != expected:
            raise SystemExit("Missing Observations evaluation evidence is missing or stale")
        print(f"{destination.name} is current")
        return 0
    if destination.exists():
        if destination.read_bytes() == expected:
            print(f"{destination.name} already contains the current evidence")
            return 0
        raise SystemExit("refusing to overwrite conflicting evaluation evidence")
    destination.write_bytes(expected)
    print(f"wrote {destination.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
