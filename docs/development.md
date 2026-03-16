# Development Guide

## Prerequisites

This project uses [Nix](https://nixos.org/) to manage the development environment. Nix provides a consistent shell with `python`, `pytest`, `ruff`, `exiftool`, and `ffmpeg`.

Enter the development shell:

```bash
nix develop
```

## Setup

Create a local virtual environment inside the Nix shell (recommended to avoid modifying read-only packages in `/nix/store`):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python3 -m pip install -e .
```

Or use the bootstrap script to run the same steps automatically:

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
```

Re-run setup when:

- `pyproject.toml` or `requirements.txt` is updated
- `.venv` is recreated or deleted
- `scripts/bootstrap.sh` changes

## Running Tests

```bash
python -m pytest
ruff check .
```

## Workers

`--workers` controls only the metadata prefetch concurrency for `exiftool` and `ffprobe`. File rename, move, and report writes always run sequentially to avoid conflicts.

- Default: automatic selection based on CPU count and file count
- Recommended: `2` for laptops or slow disks, `3–4` for larger SSD batches
- Suggested first run: `--dry-run --workers 2`
