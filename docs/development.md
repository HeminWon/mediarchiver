# Development

## Python

The project is pinned to Python 3.11:

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
just binary
just install-local
```

`just check` runs lint only. There is currently no test suite configured.

## Build

Build Python distribution artifacts:

```bash
uv build
```

Build a local single-file binary:

```bash
just binary
./dist/bin/mediarchiver --help
```

Install the local binary:

```bash
just install-local
mediarchiver --version
```

By default this installs to:

```text
~/.local/bin/mediarchiver
```

Override the install target when needed:

```bash
LOCAL_BIN=/usr/local/bin just install-local
```

## Package Index

The `just` recipes use a local uv cache and a PyPI mirror by default:

```text
UV_CACHE_DIR=.uv-cache
UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
```

Override the package index when needed:

```bash
UV_DEFAULT_INDEX=https://pypi.org/simple just binary
```

## GitHub Actions

CI runs on Python 3.11 for Linux and macOS:

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
