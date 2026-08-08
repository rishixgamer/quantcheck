#!/usr/bin/env python3
"""Render the deterministic HTML summary from saved public benchmark artifacts.

A repository development tool, matching the existing ``scripts/`` pattern. It is
deliberately not a ``quantcheck`` CLI command: the contracted root command
surface is fixed at six commands in ``docs/CLI_CONTRACT.md``.

Usage::

    uv run python scripts/render_html_summary.py <artifact-root> --output summary.html

``<artifact-root>`` is a benchmark output root containing ``public/``, or a
copied-out public tree. The private tree may be absent. An existing identical
output is reused; an existing *different* output is reported rather than
overwritten.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from quantcheck.benchmark_store import ArtifactIntegrityError
from quantcheck.html_summary import HtmlSummaryError, write_html_summary
from quantcheck.presentation import build_presentation
from quantcheck.public_artifact_reader import PublicArtifactError, read_public_benchmark


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", help="Artifact root containing public/, or a public tree.")
    parser.add_argument(
        "--output", required=True, help="Destination .html file for the rendered summary."
    )
    arguments = parser.parse_args(argv)

    try:
        artifacts = read_public_benchmark(Path(arguments.artifacts))
    except PublicArtifactError as exc:
        print(f"public artifacts rejected: {exc}", file=sys.stderr)
        return 2

    presentation = build_presentation(artifacts)
    try:
        payload = write_html_summary(presentation, Path(arguments.output))
    except (HtmlSummaryError, ArtifactIntegrityError) as exc:
        print(f"the summary was not written: {exc}", file=sys.stderr)
        return 3

    print(f"rendered {len(payload)} bytes for benchmark {presentation.benchmark_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
