import json
import shutil
import subprocess

DEFAULT_COMMAND_TIMEOUT = 15


class ExternalToolError(RuntimeError):
    def __init__(self, tool_name, message):
        super().__init__(message)
        self.tool_name = tool_name


class DependencyMissingError(ExternalToolError):
    pass


class ExternalToolExecutionError(ExternalToolError):
    pass


class ExternalToolOutputError(ExternalToolError):
    pass


def ensure_command_available(command_name):
    if shutil.which(command_name) is None:
        raise DependencyMissingError(
            command_name,
            f"Required command '{command_name}' is not available in PATH.",
        )


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
        raise ExternalToolExecutionError(
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
