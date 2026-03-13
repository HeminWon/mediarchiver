import json

from src.rename import (
    RenameOptions,
    build_parser,
    generate_new_filename,
    need_ignore_file,
    scan_dir,
    tag_ff_encoder,
)
from src.common.external import CommandLoadResult
from src.rename.metadata import build_file_metadata_context, load_ffprobe_metadata_result
from src.common.tool import load_metadata_result


def test_parser_can_be_imported_without_side_effects():
    parser = build_parser()
    args = parser.parse_args(["input-dir"])
    assert args.source == "input-dir"
    assert args.include_formatted is False
    assert args.dry_run is False


def test_parser_supports_include_formatted_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--include-formatted"])
    assert args.include_formatted is True


def test_parser_supports_dry_run_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--dry-run"])
    assert args.dry_run is True


def test_need_ignore_file_skips_formatted_name_by_default(tmp_path):
    file_path = tmp_path / "20230226-090511_2348.HEIC"
    file_path.write_text("demo", encoding="utf-8")
    options = RenameOptions()
    assert need_ignore_file(str(tmp_path), file_path.name, options) is True


def test_need_ignore_file_keeps_formatted_name_when_enabled(tmp_path):
    file_path = tmp_path / "20230226-090511_2348.HEIC"
    file_path.write_text("demo", encoding="utf-8")
    options = RenameOptions(include_formatted=True)
    assert need_ignore_file(str(tmp_path), file_path.name, options) is False


def test_tag_ff_encoder_maps_h264_and_avc_to_avc():
    assert (
        tag_ff_encoder({"streams": [{"codec_type": "video", "tags": {"encoder": "h264"}}]}) == "AVC"
    )
    assert (
        tag_ff_encoder({"streams": [{"codec_type": "video", "tags": {"encoder": "avc1"}}]}) == "AVC"
    )


def test_tag_ff_encoder_maps_h265_and_hevc_to_hevc():
    assert (
        tag_ff_encoder({"streams": [{"codec_type": "video", "tags": {"encoder": "h265"}}]})
        == "HEVC"
    )
    assert (
        tag_ff_encoder({"streams": [{"codec_type": "video", "tags": {"encoder": "hevc"}}]})
        == "HEVC"
    )


def test_tag_ff_encoder_raises_for_unknown_encoder():
    try:
        tag_ff_encoder({"streams": [{"codec_type": "video", "tags": {"encoder": "prores"}}]})
    except ValueError as exc:
        assert "encoder convert failure" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown encoder")


def test_scan_dir_dry_run_writes_operation_log_without_renaming(tmp_path, monkeypatch):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    monkeypatch.setattr(
        "src.rename.service.generate_new_filename",
        lambda *_args, **_kwargs: "20240102-030405_MiPh_1234.HEIC",
    )
    monkeypatch.setattr("src.rename.service.get_md5", lambda *_args, **_kwargs: "abc123")

    scan_dir(str(tmp_path), RenameOptions(rename=True, dry_run=True))

    assert source_file.exists()
    operations = (
        (tmp_path / "rename_operations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    record = json.loads(operations[-1])
    assert record["status"] == "preview"
    assert record["reason"] == "dry_run"
    assert record["destination"].endswith("20240102-030405_MiPh_1234.HEIC")


def test_scan_dir_rename_records_success(tmp_path, monkeypatch):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    monkeypatch.setattr(
        "src.rename.service.generate_new_filename",
        lambda *_args, **_kwargs: "20240102-030405_MiPh_1234.HEIC",
    )
    monkeypatch.setattr("src.rename.service.get_md5", lambda *_args, **_kwargs: "abc123")

    summary = scan_dir(str(tmp_path), RenameOptions(rename=True))

    renamed_file = tmp_path / "20240102-030405_MiPh_1234.HEIC"
    assert renamed_file.exists()
    assert (tmp_path / "rename_info.txt").read_text(encoding="utf-8").strip() == (
        "abc123 <= 20240102-030405_MiPh_1234.HEIC <= IMG_0001.HEIC"
    )
    operations = (
        (tmp_path / "rename_operations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    record = json.loads(operations[-1])
    assert record["status"] == "success"
    assert summary["success"] == 1
    assert summary["total"] >= 1


def test_generate_new_filename_reuses_preloaded_metadata(tmp_path, monkeypatch):
    video_file = tmp_path / "clip.mov"
    video_file.write_text("demo", encoding="utf-8")
    calls = {"exif": 0, "ffprobe": 0}

    def fake_load_metadata_result(_file_path):
        calls["exif"] += 1
        return CommandLoadResult(
            tool_name="exiftool",
            data={
                "DateTimeOriginal": "2024:01:02 03:04:05",
                "Make": "Apple",
            },
        )

    def fake_load_ffprobe_metadata_result(_file_path):
        calls["ffprobe"] += 1
        return CommandLoadResult(
            tool_name="ffprobe",
            data={
                "streams": [
                    {
                        "codec_type": "video",
                        "width": 1920,
                        "height": 1080,
                        "avg_frame_rate": "30000/1001",
                        "tags": {"encoder": "h264"},
                    }
                ]
            },
        )

    monkeypatch.setattr("src.rename.metadata.load_metadata_result", fake_load_metadata_result)
    monkeypatch.setattr(
        "src.rename.metadata.load_ffprobe_metadata_result",
        fake_load_ffprobe_metadata_result,
    )

    context = build_file_metadata_context(str(video_file))

    assert generate_new_filename(context, options=RenameOptions()) == (
        "20240102-030405_MiPh-FHD-29.97FPS-AVC_7657.mov"
    )
    assert calls == {"exif": 1, "ffprobe": 1}


def test_load_metadata_result_returns_structured_error(monkeypatch):
    def raise_failure(*_args, **_kwargs):
        raise TypeError("boom")

    monkeypatch.setattr("src.common.tool.run_json_command", raise_failure)

    result = load_metadata_result("demo.jpg")

    assert result.ok is False
    assert result.error_code == "invalid_output"
    assert result.error_message is not None
    assert "boom" in result.error_message


def test_load_ffprobe_metadata_result_returns_structured_error(monkeypatch):
    from src.common.external import ExternalToolExecutionError

    def raise_failure(*_args, **_kwargs):
        raise ExternalToolExecutionError("ffprobe", "ffprobe failed")

    monkeypatch.setattr("src.rename.metadata.run_json_command", raise_failure)

    result = load_ffprobe_metadata_result("clip.mov")

    assert result.ok is False
    assert result.error_code == "command_failed"
    assert result.error_message == "ffprobe failed"


def test_scan_dir_records_metadata_load_failure_reason(tmp_path, monkeypatch):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    from src.common.external import build_command_load_error
    from src.rename.metadata import FileMetadataContext

    def fake_context(_file_path):
        return FileMetadataContext(
            file_path=str(source_file),
            exif_result=build_command_load_error("exiftool", "command_failed", "Command failed"),
            ffprobe_result=None,
            exif_metadata=None,
            ffprobe_metadata=None,
            media_date=None,
            is_image=True,
            is_video=False,
            is_live_photo_video=None,
        )

    monkeypatch.setattr("src.rename.service.build_file_metadata_context", fake_context)

    scan_dir(str(tmp_path), RenameOptions(rename=True))

    operations = (
        (tmp_path / "rename_operations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    record = json.loads(operations[-1])
    assert record["status"] == "skipped"
    assert record["reason"] == "exiftool_command_failed"
    assert record["details"]["message"] == "Command failed"
