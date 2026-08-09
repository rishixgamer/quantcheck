"""Execute the frozen QuantCheck 0.1 held-out release benchmark.

A repository development tool, deliberately outside the wheel and sdist and
outside the CLI. It refuses to run without a saved release freeze record that
still verifies against the current repository byte for byte.

    uv run python scripts/run_release_benchmark.py --output release_evidence/final

Reserved final seeds `1000-1009` execute only here. Every ordinary interface —
``quantcheck benchmark run``, ``quantcheck benchmark smoke``, the saved-stage
commands, and ``run_benchmark`` itself — still rejects them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quantcheck.cli_support import build_runtime_metadata
from quantcheck.release_contract import RELEASE_FREEZE_RECORD_NAME
from quantcheck.release_freeze import ReleaseFreezeError
from quantcheck.release_run import ReleaseRunError, run_release_benchmark

REPO_ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="benchmark output root")
    parser.add_argument(
        "--freeze-record",
        type=Path,
        default=REPO_ROOT / RELEASE_FREEZE_RECORD_NAME,
        help="the saved release freeze record to verify against",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="dispatch every case instead of revalidating and reusing prior successes",
    )
    args = parser.parse_args(argv)

    try:
        result = run_release_benchmark(
            repo_root=REPO_ROOT,
            freeze_record_path=args.freeze_record,
            output_root=args.output,
            runtime=build_runtime_metadata(),
            resume=not args.no_resume,
        )
    except (ReleaseRunError, ReleaseFreezeError) as exc:
        print(f"release run refused: {exc}", file=sys.stderr)
        return 1

    overall = result.benchmark.aggregate.overall
    print(f"release_candidate_id  {result.release_candidate_id}")
    print(f"benchmark_id          {result.benchmark.config.benchmark_id}")
    print(f"aggregate_report_id   {result.benchmark.aggregate.aggregate_report_id}")
    print(f"configured            {overall.configured_case_count}")
    print(f"successful            {overall.successful_case_count}")
    print(f"failed                {overall.failed_case_count}")
    print(f"incomplete            {overall.incomplete_case_count}")
    print(f"dispatched            {len(result.benchmark.dispatched_case_ids)}")
    print(f"reused                {len(result.benchmark.reused_case_ids)}")
    print(f"precision             {overall.precision}")
    print(f"recall                {overall.recall}")
    print(f"f1                    {overall.f1}")
    print(f"false_positive_rate   {overall.false_positive_rate}")
    # A failed or incomplete case is real evidence, not a script error: it is
    # reported here and preserved in the saved matrix rather than retried.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
