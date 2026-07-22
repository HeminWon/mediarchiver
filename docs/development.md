# Development

## Python

The project is pinned to Python 3.14:

```text
.python-version
pyproject.toml
uv.lock
```

Use `uv` to create and manage the local environment:

```bash
uv sync --extra dev
uv run --no-sync python -V
uv run --no-sync python -m mediarchiver --version
```

## Common Commands

```bash
just setup
just check
just smoke
just install-wheel
just uninstall-wheel
just binary
just install-binary
just uninstall-binary
```

`just check` runs lint only. There is currently no test suite configured.

## Build

Build Python distribution artifacts:

```bash
just build
```

Build the wheel and install it as an isolated uv tool:

```bash
just install-wheel
mediarchiver --version
```

The recipe uses `uv tool install --reinstall --force` so the project's console
scripts are replaced cleanly during local development.

Uninstall the uv tool:

```bash
just uninstall-wheel
```

Build a local single-file binary:

```bash
just binary
./dist/bin/mediarchiver --help
```

Install the local binary:

```bash
just install-binary
mediarchiver --version
```

By default this installs to:

```text
~/.local/bin/mediarchiver
```

Override the install target when needed:

```bash
LOCAL_BIN=/usr/local/bin just install-binary
```

Avoid keeping both the uv tool and copied binary installed long-term unless you
are intentionally testing PATH precedence. `which mediarchiver` shows the one
that will run first.

## Package Index

The `just` recipes use a local uv cache and a PyPI mirror by default:

```text
UV_CACHE_DIR=.uv-cache
UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
```

`just build` uses a temporary uv cache outside the source tree so wheel and
sdist builds do not warn about cache files being inside the distribution root.

Override the package index when needed:

```bash
UV_DEFAULT_INDEX=https://pypi.org/simple just binary
```

## GitHub Actions

CI runs on Python 3.14 for Linux and macOS:

```text
.github/workflows/ci.yml
```

Release builds:

```text
.github/workflows/release.yml
```

The release workflow builds:

- wheel and sdist
- Linux single-file binary
- macOS single-file binary

The wheel is the recommended installation artifact:

```bash
just install-wheel
```

PyInstaller binaries are supplemental release artifacts for users who prefer a
download-and-run executable.

Binary builds use PyInstaller with:

```bash
--exclude-module multiprocessing
```

Keep this flag unless multiprocessing is intentionally reintroduced. It avoids
PyInstaller onefile runtime errors related to temporary `_MEI...` directories.

## Rename Rules

Rename is rule-based. Current rules live under:

```text
mediarchiver/rename/rules/
```

The public command auto-applies all registered rules during preview:

```bash
mediarchiver rename <source>
```

Use this to inspect supported rules:

```bash
mediarchiver rename --list-rules
```

When adding a new rule, keep device-specific logic inside that rule package.
Avoid adding brand or model behavior to the generic rename service.

## Archive

Archive logic lives under:

```text
mediarchiver/archive/
```

Sidecar matching rules live in:

```text
mediarchiver/archive/sidecars.py
```

Archive should remain conservative:

- ignore system files such as `.DS_Store`
- archive only supported media files directly
- archive sidecars only when they can be paired with a supported media file
- default to preview; move files only with `--apply`

## Validation

Before shipping changes:

```bash
just check
just smoke
just binary
./dist/bin/mediarchiver --version
./dist/bin/mediarchiver rename --list-rules
./dist/bin/mediarchiver archive --help
```
