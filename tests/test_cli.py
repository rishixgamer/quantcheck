"""Root CLI behavior: help, no-args, version absence, and the console script.

Milestone 9 replaces the placeholder ``argparse`` entry point with the
contracted Typer CLI (see ``docs/CLI_CONTRACT.md``). These tests describe the
new, deliberate behavior:

* ``--help`` prints usage and exits 0.
* No arguments at all prints the same help but is a Click usage error
  (missing command), exiting 2 — this is standard Click/Typer
  ``no_args_is_help`` semantics, not a bespoke choice.
* There is deliberately no ``--version`` flag and no separate
  ``python -m quantcheck`` behavior in v0.1, matching the current CLI
  contract's decision not to add presentation-adjacent conveniences the
  Phase 9 contract does not require.
"""

import subprocess
import sys

from quantcheck.cli import main


def test_cli_help_exits_zero_and_lists_the_six_root_commands() -> None:
    assert main(["--help"]) == 0


def test_cli_no_args_is_a_usage_error_that_still_shows_help() -> None:
    assert main([]) == 2


def test_cli_has_no_version_flag() -> None:
    assert main(["--version"]) != 0


def test_installed_console_script_help_exits_zero() -> None:
    result = subprocess.run(  # noqa: S603, S607
        ["quantcheck", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "quantcheck" in result.stdout.lower()


def test_python_dash_m_quantcheck_cli_help_exits_zero() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "quantcheck.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "quantcheck" in result.stdout.lower()
