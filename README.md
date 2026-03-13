# mediarchiver

A tool for archiving and renaming media files using Exif metadata.

## Requirements

```bash
nix develop
```

The Nix shell provides `python`, `pytest`, `ruff`, `exiftool`, and `ffmpeg`.

## Run

```bash
python -m src.rename.rename <source>
python -m src.rename.rename <source> --rename
python -m src.rename.rename <source> --rename --dry-run
python -m src.rename.rename <source> --include-formatted
python -m src.rename.rename <source> --workers 2
python -m src.archive.archive <source> --destination <target>
python -m src.archive.archive <source> --destination <target> --dry-run
python -m src.archive.archive <source> --destination <target> --workers 2
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
- `rename_info.txt`: applied rename history
- `rename_operations.jsonl`: structured rename operation report
- `rename_conflicts.jsonl`: rename conflict report
- `archive_operations.jsonl`: structured archive operation report
- `archive_conflicts.jsonl`: archive conflict report
