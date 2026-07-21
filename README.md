# mediarchiver

A CLI tool for renaming and archiving media files using metadata from
exiftool and ffprobe.

## Requirements

Before installing, make sure the following system tools are available:

```bash
# macOS
brew install exiftool ffmpeg

# Ubuntu / Debian
sudo apt install libimage-exiftool-perl ffmpeg
```

## Development

This project uses `uv` for Python environment and dependency management.

```bash
uv sync --extra dev
uv run mediarchiver --help
```

Common development commands are available through `just`:

```bash
just setup
just check
just smoke
just binary
just install-local
```

Build local distribution artifacts:

```bash
uv build
```

Build a local single-file CLI binary for the current platform:

```bash
just binary
./dist/bin/mediarchiver --help
```

Install the binary to your user-local command directory:

```bash
just install-local
mediarchiver --help
```

By default this installs to `~/.local/bin/mediarchiver`. Override the target
directory when needed:

```bash
LOCAL_BIN=/usr/local/bin just install-local
```

The `just` recipes use a local uv cache and a PyPI mirror by default. Override the
package index when needed:

```bash
UV_DEFAULT_INDEX=https://pypi.org/simple just binary
```

## Usage

### Profile Authoring Metadata Inspection

For profile-driven rules, inspect representative files directly with `exiftool` and `ffprobe` as described in the project profile-authoring skill.

### Rename

List supported rename profiles:

```bash
mediarchiver rename --list-profiles
```

Preview a mixed-folder rename plan across all supported profiles (no files are modified):

```bash
mediarchiver rename <source>
```

Apply renames:

```bash
mediarchiver rename <source> --apply
```

Write a plan to a custom path:

```bash
mediarchiver rename <source> --output-plan /tmp/rename-plan.json
```

### Archive

Move files into date-based directory structures:

```bash
mediarchiver archive <source> --to <target>
mediarchiver archive <source> --to <target> --by quarter
mediarchiver archive <source> --to <target> --by month
mediarchiver archive <source> --to <target> --by year
mediarchiver archive <source> --to <target> --dry-run
mediarchiver archive <source> --to <target> --workers 2
```

## Output Files

| File | Description |
|---|---|
| `rename.log` | Rename workflow log |
| `archived.log` | Archive workflow log |
| `rename-plan.json` | Rename plan written into the source directory |
| `rename_operations.jsonl` | Structured rename operation records |
| `rename_conflicts.jsonl` | Rename conflict records |
| `archive_operations.jsonl` | Structured archive operation records |
| `archive_conflicts.jsonl` | Archive conflict records |

## Documentation

- [Basic Functionality](docs/basic-functionality.md)
- [Development Guide](docs/development.md)
