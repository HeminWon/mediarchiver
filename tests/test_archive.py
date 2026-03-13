import json

from src.archive.archive import archive_obj, build_parser, get_quarter, sort_files


def test_archive_parser_supports_dry_run_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--dry-run"])
    assert args.dry_run is True


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
        "src.archive.service.get_date", lambda *_args, **_kwargs: "2024:05:02 03:04:05"
    )

    from src.common.reporting import OperationLogger

    archive_obj(
        str(source_dir),
        str(target_dir),
        media_file.name,
        dry_run=True,
        report_logger=OperationLogger(source_dir, "archive"),
    )

    assert media_file.exists()
    operations = (
        (source_dir / "archive_operations.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
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
        "src.archive.service.get_date", lambda *_args, **_kwargs: "2024:05:02 03:04:05"
    )

    sort_files(str(source_dir), str(target_dir), dry_run=False)

    conflicts = (
        (source_dir / "archive_conflicts.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    record = json.loads(conflicts[-1])
    assert record["status"] == "conflict"
    assert record["reason"] == "destination_exists"
