#!/usr/bin/env python3
"""Run the frozen v0.2 development/validation evidence sequence."""

from __future__ import annotations

import argparse
from pathlib import Path

from quantcheck.benchmark_store import AtomicArtifactStore
from quantcheck.benchmark_v2_evidence import (
    aggregate_v2_from_public_root,
    build_design_partner_beta_matrices,
    run_v2_partition,
    write_v2_validation_freeze,
)
from quantcheck.corpus_freeze import load_corpus_freeze_record
from quantcheck.hashing import sha256_hex_of_bytes
from quantcheck.serialization import canonical_json_bytes

REPO_ROOT = Path(__file__).resolve().parent.parent
SCIENCE_FILES = (
    "corpus_freeze_v0_2.json",
    "pyproject.toml",
    "uv.lock",
    "src/quantcheck/benchmark_v2_case.py",
    "src/quantcheck/benchmark_v2_config.py",
    "src/quantcheck/benchmark_v2_contract.py",
    "src/quantcheck/benchmark_v2_evaluation.py",
    "src/quantcheck/benchmark_v2_evidence.py",
    "src/quantcheck/benchmark_v2_execution.py",
    "src/quantcheck/benchmark_v2_schemas.py",
    "src/quantcheck/benchmark_store.py",
    "src/quantcheck/corpus_eligibility.py",
    "src/quantcheck/corpus_registry.py",
    "src/quantcheck/duplicate_detection.py",
    "src/quantcheck/duplicate_injection.py",
    "src/quantcheck/lookahead_detection.py",
    "src/quantcheck/lookahead_injection.py",
    "src/quantcheck/revision_overwrite_detection.py",
    "src/quantcheck/revision_overwrite_injection.py",
    "src/quantcheck/unit_drift_detection.py",
    "src/quantcheck/unit_drift_injection.py",
    "scripts/run_benchmark_v2_evidence.py",
)


def _source_hashes() -> dict[str, str]:
    return {
        relative: sha256_hex_of_bytes((REPO_ROOT / relative).read_bytes())
        for relative in SCIENCE_FILES
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--partition",
        choices=("development", "validation", "all"),
        default="all",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "benchmark_evidence_v0_2",
    )
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    corpus_freeze = load_corpus_freeze_record(REPO_ROOT / "corpus_freeze_v0_2.json")
    development, validation = build_design_partner_beta_matrices(corpus_freeze)
    development_config, development_matrix = development
    validation_config, validation_matrix = validation
    public = AtomicArtifactStore(args.output / "public")
    for name, artifact in (
        ("development_config.json", development_config),
        ("development_matrix.json", development_matrix),
        ("validation_config.json", validation_config),
        ("validation_matrix.json", validation_matrix),
    ):
        public.write_immutable(name, artifact)

    if args.partition in {"development", "all"}:
        run_v2_partition(
            development_config,
            development_matrix,
            output_root=args.output,
            partition="development",
            resume=not args.no_resume,
        )
    if args.partition == "all":
        write_v2_validation_freeze(
            args.output,
            development_config=development_config,
            development_matrix=development_matrix,
            validation_config=validation_config,
            validation_matrix=validation_matrix,
            source_hashes=_source_hashes(),
        )
    if args.partition in {"validation", "all"}:
        run_v2_partition(
            validation_config,
            validation_matrix,
            output_root=args.output,
            partition="validation",
            resume=not args.no_resume,
        )

    summaries = {
        partition: aggregate_v2_from_public_root(args.output, partition)
        for partition in ("development", "validation")
        if (args.output / "public" / f"{partition}_matrix.json").is_file()
    }
    print(canonical_json_bytes(summaries).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
