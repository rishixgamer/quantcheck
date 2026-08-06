import subprocess
import sys

import pytest

from quantcheck.cli import main


def test_cli_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "quantcheck" in captured.out


def test_cli_no_args_exits_zero() -> None:
    assert main([]) == 0


def test_installed_console_script_help_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "quantcheck.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "quantcheck" in result.stdout
