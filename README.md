# mediarchiver

A tool for archiving and renaming media files using Exif metadata.

## Requirements

```bash
nix develop
```

The Nix shell provides `python`, `pytest`, `ruff`, `exiftool`, and `ffmpeg`.

## Run

Install the package in editable mode if you want the `mediarchiver` command:

```bash
python -m pip install -e .
```

Then use the unified CLI:

```bash
mediarchiver rename <source>
mediarchiver rename <source> --rename
mediarchiver rename <source> --rename --dry-run
mediarchiver rename <source> --include-formatted
mediarchiver rename <source> --workers 2
mediarchiver archive <source> --destination <target>
mediarchiver archive <source> --destination <target> --dry-run
mediarchiver archive <source> --destination <target> --workers 2
mediarchiver rename <source> --build-plan rename-plan.json
mediarchiver rename --build-plan rename-plan.json --export-shell rename.sh
mediarchiver rename --apply-plan rename-plan.json
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
- `rename_info.txt`: applied rename history
- `rename-plan.json`: optional rename plan output
- `rename.sh`: optional shell export generated from a plan
- `rename_operations.jsonl`: structured rename operation report
- `rename_conflicts.jsonl`: rename conflict report
- `archive_operations.jsonl`: structured archive operation report
- `archive_conflicts.jsonl`: archive conflict report
