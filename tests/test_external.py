import subprocess

import pytest

from src.common.external import (
    DependencyMissingError,
    ExternalToolExecutionError,
    run_json_command,
)


def test_run_json_command_raises_dependency_missing(monkeypatch):
    monkeypatch.setattr("src.common.external.shutil.which", lambda _name: None)

    with pytest.raises(DependencyMissingError):
        run_json_command(["exiftool", "-j", "demo.jpg"], "exiftool")


def test_run_json_command_raises_timeout_error(monkeypatch):
    monkeypatch.setattr(
        "src.common.external.shutil.which", lambda _name: "/usr/bin/exiftool"
    )

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["exiftool"], timeout=15)

    monkeypatch.setattr("src.common.external.subprocess.run", raise_timeout)

    with pytest.raises(ExternalToolExecutionError):
        run_json_command(["exiftool", "-j", "demo.jpg"], "exiftool")
