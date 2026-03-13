import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Optional

DEFAULT_COMMAND_TIMEOUT = 15
_COMMAND_AVAILABILITY_CACHE = {}


class ExternalToolError(RuntimeError):
    def __init__(self, tool_name, message):
        super().__init__(message)
        self.tool_name = tool_name


class DependencyMissingError(ExternalToolError):
    pass


class ExternalToolExecutionError(ExternalToolError):
    pass


class ExternalToolTimeoutError(ExternalToolExecutionError):
    pass


class ExternalToolOutputError(ExternalToolError):
    pass


@dataclass(frozen=True)
class CommandLoadResult:
    tool_name: str
    data: Any = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def ok(self):
        return self.error_code is None


def build_command_load_error(tool_name, error_code, error_message):
    return CommandLoadResult(
        tool_name=tool_name,
        data=None,
        error_code=error_code,
        error_message=error_message,
    )


def map_external_tool_error_code(exc):
    if isinstance(exc, DependencyMissingError):
        return "dependency_missing"
    if isinstance(exc, ExternalToolTimeoutError):
        return "command_timeout"
    if isinstance(exc, ExternalToolOutputError):
        return "invalid_output"
    if isinstance(exc, ExternalToolExecutionError):
        return "command_failed"
    return "tool_error"


def ensure_command_available(command_name):
    cached_path = _COMMAND_AVAILABILITY_CACHE.get(command_name)
    if cached_path:
        return cached_path
    resolved_path = shutil.which(command_name)
    if resolved_path is None:
        raise DependencyMissingError(
            command_name,
            f"Required command '{command_name}' is not available in PATH.",
        )
    _COMMAND_AVAILABILITY_CACHE[command_name] = resolved_path
    return resolved_path


def preflight_check_commands(command_names):
    for command_name in command_names:
        ensure_command_available(command_name)


def run_json_command(cmd, tool_name, timeout=DEFAULT_COMMAND_TIMEOUT):
    ensure_command_available(tool_name)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise DependencyMissingError(
            tool_name,
            f"Required command '{tool_name}' is not available in PATH.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ExternalToolTimeoutError(
            tool_name,
            f"Command timed out after {timeout}s: {' '.join(cmd)}",
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        raise ExternalToolExecutionError(
            tool_name,
            f"Command failed with exit code {exc.returncode}: {' '.join(cmd)} {stderr}".strip(),
        ) from exc

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ExternalToolOutputError(
            tool_name,
            f"Command returned invalid JSON: {' '.join(cmd)}",
        ) from exc
