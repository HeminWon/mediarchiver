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
python -m src.archive.archive <source> --destination <target>
python -m src.archive.archive <source> --destination <target> --dry-run
```

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
