import json

from src.rename.rename import (
    RenameOptions,
    build_parser,
    need_ignore_file,
    scan_dir,
    tag_ff_encoder,
)


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
        tag_ff_encoder(
            {"streams": [{"codec_type": "video", "tags": {"encoder": "h264"}}]}
        )
        == "AVC"
    )
    assert (
        tag_ff_encoder(
            {"streams": [{"codec_type": "video", "tags": {"encoder": "avc1"}}]}
        )
        == "AVC"
    )


def test_tag_ff_encoder_maps_h265_and_hevc_to_hevc():
    assert (
        tag_ff_encoder(
            {"streams": [{"codec_type": "video", "tags": {"encoder": "h265"}}]}
        )
        == "HEVC"
    )
    assert (
        tag_ff_encoder(
            {"streams": [{"codec_type": "video", "tags": {"encoder": "hevc"}}]}
        )
        == "HEVC"
    )


def test_tag_ff_encoder_raises_for_unknown_encoder():
    try:
        tag_ff_encoder(
            {"streams": [{"codec_type": "video", "tags": {"encoder": "prores"}}]}
        )
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
    monkeypatch.setattr(
        "src.rename.service.get_md5", lambda *_args, **_kwargs: "abc123"
    )

    scan_dir(str(tmp_path), RenameOptions(rename=True, dry_run=True))

    assert source_file.exists()
    operations = (
        (tmp_path / "rename_operations.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
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
    monkeypatch.setattr(
        "src.rename.service.get_md5", lambda *_args, **_kwargs: "abc123"
    )

    scan_dir(str(tmp_path), RenameOptions(rename=True))

    renamed_file = tmp_path / "20240102-030405_MiPh_1234.HEIC"
    assert renamed_file.exists()
    assert (tmp_path / "rename_info.txt").read_text(encoding="utf-8").strip() == (
        "abc123 <= 20240102-030405_MiPh_1234.HEIC <= IMG_0001.HEIC"
    )
    operations = (
        (tmp_path / "rename_operations.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    record = json.loads(operations[-1])
    assert record["status"] == "success"
