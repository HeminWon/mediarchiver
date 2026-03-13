import json

import pytest

from mediarchiver.archive import archive_obj, build_parser, get_quarter, sort_files


def test_archive_parser_supports_dry_run_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--dry-run"])
    assert args.dry_run is True


def test_archive_parser_supports_to_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--to", "target-dir"])
    assert args.to == "target-dir"


def test_archive_parser_supports_workers_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--workers", "2"])
    assert args.workers == 2


def test_archive_parser_rejects_non_positive_workers():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["input-dir", "--workers", "0"])


def test_get_quarter_maps_months_correctly():
    assert get_quarter("2024:01:02 03:04:05") == "Q1"
    assert get_quarter("2024:05:02 03:04:05") == "Q2"
    assert get_quarter("2024:08:02 03:04:05") == "Q3"
    assert get_quarter("2024:11:02 03:04:05") == "Q4"


def test_archive_obj_dry_run_records_preview(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    media_file = source_dir / "IMG_0001.JPG"
    media_file.write_text("demo", encoding="utf-8")

    monkeypatch.setattr(
        "mediarchiver.archive.service.get_archive_metadata_error",
        lambda *_args, **_kwargs: (None, "2024:05:02 03:04:05"),
    )

    from mediarchiver.common.reporting import OperationLogger

    archive_obj(
        str(source_dir),
        str(target_dir),
        media_file.name,
        dry_run=True,
        report_logger=OperationLogger(source_dir, "archive"),
    )

    assert media_file.exists()
    operations = (
        (source_dir / "archive_operations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    record = json.loads(operations[-1])
    assert record["status"] == "preview"
    assert record["destination"].endswith("2024/Q2/IMG_0001.JPG")


def test_sort_files_records_conflict(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target_dir = tmp_path / "target"
    (target_dir / "2024" / "Q2").mkdir(parents=True)
    media_file = source_dir / "IMG_0001.JPG"
    media_file.write_text("demo", encoding="utf-8")
    conflict_target = target_dir / "2024" / "Q2" / "IMG_0001.JPG"
    conflict_target.write_text("existing", encoding="utf-8")

    monkeypatch.setattr(
        "mediarchiver.archive.service.get_archive_metadata_error",
        lambda *_args, **_kwargs: (None, "2024:05:02 03:04:05"),
    )

    summary = sort_files(str(source_dir), str(target_dir), dry_run=False)

    conflicts = (
        (source_dir / "archive_conflicts.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    record = json.loads(conflicts[-1])
    assert record["status"] == "conflict"
    assert record["reason"] == "destination_exists"
    assert summary["conflict"] == 1


def test_archive_obj_records_metadata_load_failure(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    media_file = source_dir / "IMG_0001.JPG"
    media_file.write_text("demo", encoding="utf-8")

    monkeypatch.setattr(
        "mediarchiver.archive.service.get_archive_metadata_error",
        lambda *_args, **_kwargs: (
            {
                "reason": "exiftool_command_failed",
                "details": {"message": "Command failed"},
            },
            None,
        ),
    )

    from mediarchiver.common.reporting import OperationLogger

    archive_obj(
        str(source_dir),
        str(target_dir),
        media_file.name,
        report_logger=OperationLogger(source_dir, "archive"),
    )

    operations = (
        (source_dir / "archive_operations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    record = json.loads(operations[-1])
    assert record["status"] == "skipped"
    assert record["reason"] == "exiftool_command_failed"
    assert record["details"]["message"] == "Command failed"


def test_sort_files_prefetches_metadata_once_per_candidate(tmp_path, monkeypatch):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    media_file = source_dir / "IMG_0001.JPG"
    media_file.write_text("demo", encoding="utf-8")

    calls = []

    def fake_get_archive_metadata_error(file_path):
        calls.append(file_path)
        return None, "2024:05:02 03:04:05"

    monkeypatch.setattr(
        "mediarchiver.archive.service.get_archive_metadata_error", fake_get_archive_metadata_error
    )

    sort_files(str(source_dir), str(target_dir), dry_run=True)

    assert calls == [str(media_file)]


def test_prefetch_archive_metadata_respects_requested_workers(monkeypatch):
    observed = {}

    class DummyExecutor:
        def __init__(self, max_workers):
            observed["max_workers"] = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def map(self, func, items):
            return [func(item) for item in items]

    monkeypatch.setattr("mediarchiver.archive.service.ThreadPoolExecutor", DummyExecutor)
    monkeypatch.setattr(
        "mediarchiver.archive.service.get_archive_metadata_error",
        lambda file_path: (None, f"date:{file_path}"),
    )
    monkeypatch.setattr("mediarchiver.archive.service.os.cpu_count", lambda: 8)

    from mediarchiver.archive.service import prefetch_archive_metadata

    result = prefetch_archive_metadata(["a.jpg", "b.jpg"], workers=2)

    assert observed["max_workers"] == 2
    assert result == {"a.jpg": (None, "date:a.jpg"), "b.jpg": (None, "date:b.jpg")}


def test_archive_prefetch_workers_are_clamped(monkeypatch):
    monkeypatch.setattr("mediarchiver.common.workers.os.cpu_count", lambda: 2)

    from mediarchiver.archive.service import get_prefetch_workers

    assert get_prefetch_workers(1, requested_workers=8) == 1
    assert get_prefetch_workers(5, requested_workers=8) == 2
    assert get_prefetch_workers(5) == 2
