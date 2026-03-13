import subprocess

import pytest

from src.common.external import (
    DependencyMissingError,
    ExternalToolExecutionError,
    ExternalToolTimeoutError,
    _COMMAND_AVAILABILITY_CACHE,
    ensure_command_available,
    run_json_command,
)


def test_run_json_command_raises_dependency_missing(monkeypatch):
    monkeypatch.setattr("src.common.external.shutil.which", lambda _name: None)

    with pytest.raises(DependencyMissingError):
        run_json_command(["exiftool", "-j", "demo.jpg"], "exiftool")


def test_run_json_command_raises_timeout_error(monkeypatch):
    monkeypatch.setattr("src.common.external.shutil.which", lambda _name: "/usr/bin/exiftool")

    def raise_timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["exiftool"], timeout=15)

    monkeypatch.setattr("src.common.external.subprocess.run", raise_timeout)

    with pytest.raises(ExternalToolTimeoutError):
        run_json_command(["exiftool", "-j", "demo.jpg"], "exiftool")


def test_run_json_command_raises_execution_error_for_nonzero_exit(monkeypatch):
    monkeypatch.setattr("src.common.external.shutil.which", lambda _name: "/usr/bin/exiftool")

    def raise_called_process_error(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=["exiftool", "-j", "demo.jpg"],
            stderr="boom",
        )

    monkeypatch.setattr("src.common.external.subprocess.run", raise_called_process_error)

    with pytest.raises(ExternalToolExecutionError):
        run_json_command(["exiftool", "-j", "demo.jpg"], "exiftool")


def test_ensure_command_available_uses_cache(monkeypatch):
    calls = {"count": 0}

    def fake_which(_name):
        calls["count"] += 1
        return "/usr/bin/exiftool"

    _COMMAND_AVAILABILITY_CACHE.clear()
    monkeypatch.setattr("src.common.external.shutil.which", fake_which)

    ensure_command_available("exiftool")
    ensure_command_available("exiftool")

    assert calls["count"] == 1
