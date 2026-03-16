# mediarchiver

A CLI tool for renaming and archiving media files using Exif metadata.

## Requirements

Before installing, make sure the following system tools are available:

```bash
# macOS
brew install exiftool ffmpeg

# Ubuntu / Debian
sudo apt install libimage-exiftool-perl ffmpeg
```

## Installation

Install the latest version directly from GitHub:

```bash
pipx install "git+https://github.com/heminwon/mediarchiver.git"
```

Install a specific version:

```bash
pipx install "git+https://github.com/heminwon/mediarchiver.git@v0.1.0"
```

Upgrade to the latest version:

```bash
pipx upgrade mediarchiver
```

## Usage

### Rename

Preview rename plan (no files are modified):

```bash
mediarchiver rename <source>
```

Apply renames:

```bash
mediarchiver rename <source> --apply
```

Dry run (execute all logic but skip actual file writes):

```bash
mediarchiver rename <source> --apply --dry-run
```

Include already-formatted files:

```bash
mediarchiver rename <source> --all
```

Control metadata read concurrency:

```bash
mediarchiver rename <source> --workers 2
```

Export rename operations as a shell script:

```bash
mediarchiver rename <source> --shell
```

Work with an existing plan file:

```bash
mediarchiver rename --plan rename-plan.json
mediarchiver rename --plan rename-plan.json --apply
mediarchiver rename --plan rename-plan.json --dry-run
mediarchiver rename --plan rename-plan.json --shell
```

### Archive

Move files into a year/quarter directory structure:

```bash
mediarchiver archive <source> --to <target>
mediarchiver archive <source> --to <target> --dry-run
mediarchiver archive <source> --to <target> --workers 2
```

## Output Files

| File | Description |
|---|---|
| `rename.log` | Rename workflow log |
| `archived.log` | Archive workflow log |
| `rename-plan.json` | Rename plan written into the source directory |
| `rename.sh` | Optional shell script export |
| `rename_operations.jsonl` | Structured rename operation records |
| `rename_conflicts.jsonl` | Rename conflict records |
| `archive_operations.jsonl` | Structured archive operation records |
| `archive_conflicts.jsonl` | Archive conflict records |

## Documentation

- [Basic Functionality](docs/basic-functionality.md)
- [Development Guide](docs/development.md)
