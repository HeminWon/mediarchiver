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

### Rule Authoring Metadata Inspection

For rule-driven naming, inspect representative files directly with `exiftool` and `ffprobe` as described in the project rule-authoring skill.

### Rename

List supported rename rules:

```bash
mediarchiver rename --list-rules
```

Preview a mixed-folder rename plan across all supported rules (no files are modified):

```bash
mediarchiver rename <source>
```

Apply renames:

```bash
mediarchiver rename <source> --apply
```

Write a plan to a custom output directory:

```bash
mediarchiver rename <source> --output /tmp/mediarchiver-plan
```

### Archive

Preview or move files into date-based directory structures:

```bash
mediarchiver archive <source>
mediarchiver archive <source> --to <target>
mediarchiver archive <source> --to <target> --by quarter
mediarchiver archive <source> --to <target> --by month
mediarchiver archive <source> --to <target> --by year
mediarchiver archive <source> --to <target> --apply
```

## Output Files

| File | Description |
|---|---|
| `rename.log` | Rename workflow log |
| `rename-plan.json` | Rename plan written into the source directory by default, or into `--output` when specified |
| `rename_operations.jsonl` | Structured rename operation records |
| `rename_conflicts.jsonl` | Rename conflict records |

## Documentation

- [Basic Functionality](docs/basic-functionality.md)
- [Development Guide](docs/development.md)
