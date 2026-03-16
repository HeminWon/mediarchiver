# mediarchiver

A tool for archiving and renaming media files using Exif metadata.

## Installation

### pipx（推荐）

从 GitHub 安装最新版本：

```bash
pipx install "git+https://github.com/heminwon/mediarchiver.git"
```

或安装指定版本：

```bash
pipx install "git+https://github.com/heminwon/mediarchiver.git@v0.1.0"
```

> 安装前请确保系统已安装 `exiftool` 和 `ffmpeg`：
> ```bash
> brew install exiftool ffmpeg   # macOS
> sudo apt install libimage-exiftool-perl ffmpeg   # Ubuntu/Debian
> ```


## Requirements（开发环境）

```bash
nix develop
```

The Nix shell provides `python`, `pytest`, `ruff`, `exiftool`, and `ffmpeg`.

Create a local virtual environment inside the Nix shell (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python3 -m pip install -e .
```

This prevents `pip` from trying to modify read-only packages in `/nix/store`.

Quick setup (same steps, automated):

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
```

When to run setup again:

- You updated `pyproject.toml` or `requirements.txt`
- You recreated or deleted `.venv`
- You changed `scripts/bootstrap.sh` and want to apply the new setup behavior

## Run

Install the package in editable mode if you want the `mediarchiver` command:

```bash
python3 -m pip install -e .
```

If you created `.venv`, activate it first:

```bash
source .venv/bin/activate
```

Then use the unified CLI:

```bash
mediarchiver rename <source>
mediarchiver rename <source> --apply
mediarchiver rename <source> --apply --dry-run
mediarchiver rename <source> --all
mediarchiver rename <source> --workers 2
mediarchiver rename <source> --shell
mediarchiver rename --plan rename-plan.json
mediarchiver rename --plan rename-plan.json --apply
mediarchiver rename --plan rename-plan.json --dry-run
mediarchiver rename --plan rename-plan.json --shell
mediarchiver archive <source> --to <target>
mediarchiver archive <source> --to <target> --dry-run
mediarchiver archive <source> --to <target> --workers 2
python -m mediarchiver rename <source>
```

## Parallel Metadata Reads

- `--workers` controls only metadata prefetch concurrency for `exiftool` and `ffprobe`
- File rename, file move, and report writes still run sequentially to avoid conflicts
- Default behavior is automatic worker selection based on CPU count and candidate file count
- Recommended values: use `2` for laptops or slow disks, `3-4` for larger local batches
- Start with `--dry-run --workers 2` if you want to verify behavior before applying changes

## Test

```bash
python -m pytest
ruff check .
```

## Outputs

- `rename.log`: rename workflow log
- `archived.log`: archive workflow log
- `rename-plan.json`: default rename plan output written into the source directory
- `rename.sh`: optional shell export generated next to the source directory or plan file
- `rename_operations.jsonl`: structured rename operation report
- `rename_conflicts.jsonl`: rename conflict report
- `archive_operations.jsonl`: structured archive operation report
- `archive_conflicts.jsonl`: archive conflict report
