#!/usr/bin/env python3
"""Run the deterministic local execution performance suite."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from quantcheck.benchmark_store import atomic_write_bytes
from quantcheck.external_dataset_performance import run_performance_benchmark
from quantcheck.serialization import canonical_json_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="destination for the canonical performance report JSON",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        help="optional new/empty directory for generated corpus and run artifacts",
    )
    arguments = parser.parse_args()
    if arguments.work_root is not None:
        report = run_performance_benchmark(arguments.work_root)
    else:
        with tempfile.TemporaryDirectory(prefix="quantcheck-performance-") as temporary:
            report = run_performance_benchmark(Path(temporary))
    atomic_write_bytes(arguments.output, canonical_json_bytes(report))
    print(f"wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
