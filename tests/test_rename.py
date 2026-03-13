import json
from builtins import open as builtin_open

import pytest

from mediarchiver.cli import build_parser as build_root_parser
from mediarchiver.common.external import CommandLoadResult
from mediarchiver.common.tool import is_IMG, is_VID, load_metadata_result
from mediarchiver.rename import (
    RenameOptions,
    apply_rename_plan,
    build_parser,
    build_rename_plan,
    export_rename_plan_shell,
    load_rename_plan,
    render_rename_plan_shell,
    write_rename_plan,
)
from mediarchiver.rename.cli import validate_args
from mediarchiver.rename.metadata import (
    FileMetadataContext,
    build_file_metadata_context,
    load_ffprobe_metadata_result,
)
from mediarchiver.rename.rules import (
    clear_md5_cache,
    deal_with_m,
    file_number,
    generate_new_filename,
    get_md5,
    need_ignore_file,
    tag_ff_encoder,
)


def test_parser_can_be_imported_without_side_effects():
    parser = build_parser()
    args = parser.parse_args(["input-dir"])
    assert args.source == "input-dir"
    assert args.include_formatted is False
    assert args.dry_run is False
    assert args.plan is None
    assert args.apply is False
    assert args.shell is False


def test_root_parser_supports_rename_and_archive_commands():
    parser = build_root_parser()

    rename_args = parser.parse_args(["rename", "input-dir", "--apply", "--dry-run"])
    archive_args = parser.parse_args(["archive", "input-dir", "--dry-run"])

    assert rename_args.command == "rename"
    assert rename_args.source == "input-dir"
    assert rename_args.apply is True
    assert rename_args.dry_run is True
    assert archive_args.command == "archive"
    assert archive_args.source == "input-dir"
    assert archive_args.dry_run is True


def test_parser_supports_all_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--all"])
    assert args.include_formatted is True


def test_parser_supports_dry_run_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--apply", "--dry-run"])
    assert args.dry_run is True


def test_parser_supports_workers_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--workers", "3"])
    assert args.workers == 3


def test_parser_rejects_non_positive_workers():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["input-dir", "--workers", "0"])


def test_parser_supports_plan_flag():
    parser = build_parser()
    args = parser.parse_args(["--plan", "rename-plan.json"])
    assert args.plan == "rename-plan.json"


def test_parser_supports_apply_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--apply"])
    assert args.apply is True


def test_parser_supports_shell_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--shell"])
    assert args.shell is True


def test_parser_rejects_source_with_plan_flag():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--plan", "rename-plan.json"])
    with pytest.raises(SystemExit):
        validate_args(parser, args)


def test_parser_rejects_dry_run_without_apply_or_plan():
    parser = build_parser()
    args = parser.parse_args(["input-dir", "--dry-run"])
    with pytest.raises(SystemExit):
        validate_args(parser, args)


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


def test_mpg_is_classified_as_video_not_image():
    assert is_VID("clip.mpg") is True
    assert is_IMG("clip.mpg") is False


def test_file_number_md5_fallback_uses_cached_digest(tmp_path, monkeypatch):
    media_file = tmp_path / "clip.mov"
    media_file.write_text("demo", encoding="utf-8")
    observed = {"count": 0}

    clear_md5_cache()

    def counting_open(file, *args, **kwargs):
        if str(file) == str(media_file):
            observed["count"] += 1
        return builtin_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)

    first = file_number(str(media_file), try_hash=True)
    second = file_number(str(media_file), try_hash=True)

    assert first == second
    assert observed["count"] == 1


def test_get_md5_cache_invalidates_when_file_changes(tmp_path, monkeypatch):
    media_file = tmp_path / "clip.mov"
    media_file.write_text("demo", encoding="utf-8")
    observed = {"count": 0}

    clear_md5_cache()

    def counting_open(file, *args, **kwargs):
        if str(file) == str(media_file):
            observed["count"] += 1
        return builtin_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)

    first = get_md5(str(media_file))
    media_file.write_text("demo-updated", encoding="utf-8")
    second = get_md5(str(media_file))

    assert first != second
    assert observed["count"] == 2


def test_deal_with_m_maps_known_make_with_table_rules():
    assert deal_with_m("Apple iPhone 15 Pro") == "MiPh"
    assert deal_with_m("SONY ILCE-7M4") == "MSON"
    assert deal_with_m("DJI Osmo Pocket 3") == "MDJI"


def test_deal_with_m_raises_for_unknown_make():
    with pytest.raises(ValueError, match="convert failure"):
        deal_with_m("Unknown Camera Brand")


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


def test_apply_built_plan_dry_run_writes_operation_log_without_renaming(tmp_path, monkeypatch):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    monkeypatch.setattr(
        "mediarchiver.rename.service.generate_new_filename",
        lambda *_args, **_kwargs: "20240102-030405_MiPh_1234.HEIC",
    )

    plan = build_rename_plan(str(tmp_path), RenameOptions())
    apply_rename_plan(plan, dry_run=True)

    assert source_file.exists()
    operations = (
        (tmp_path / "rename_operations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    record = json.loads(operations[-1])
    assert record["status"] == "preview"
    assert record["reason"] == "dry_run"
    assert record["destination"].endswith("20240102-030405_MiPh_1234.HEIC")


def test_build_rename_plan_writes_absolute_paths(tmp_path, monkeypatch):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    monkeypatch.setattr(
        "mediarchiver.rename.service.generate_new_filename",
        lambda *_args, **_kwargs: "20240102-030405_MiPh_1234.HEIC",
    )

    plan = build_rename_plan(str(tmp_path), RenameOptions(), workers=2)

    ready_item = next(item for item in plan.items if item.status == "ready")
    assert ready_item.source == str(source_file)
    assert ready_item.destination == str(tmp_path / "20240102-030405_MiPh_1234.HEIC")
    assert plan.summary["ready"] == 1


def test_write_and_load_rename_plan_round_trip(tmp_path):
    plan_path = tmp_path / "rename-plan.json"

    from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem

    plan = RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=str(tmp_path.resolve()),
        options={"loose": False, "include_formatted": False, "workers": None},
        items=[
            RenamePlanItem(
                source=str((tmp_path / "a.jpg").resolve()),
                destination=str((tmp_path / "b.jpg").resolve()),
                action="rename",
                status="ready",
            )
        ],
    )

    write_rename_plan(plan, plan_path)
    loaded_plan = load_rename_plan(plan_path)

    assert loaded_plan.to_dict() == plan.to_dict()


def test_render_rename_plan_shell_outputs_ready_mv_commands(tmp_path):
    from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem

    plan = RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=str(tmp_path.resolve()),
        options={},
        items=[
            RenamePlanItem(
                source=str((tmp_path / "source file.jpg").resolve()),
                destination=str((tmp_path / "dest file.jpg").resolve()),
                action="rename",
                status="ready",
            ),
            RenamePlanItem(
                source=str((tmp_path / "skip.jpg").resolve()),
                destination=None,
                action="rename",
                status="skipped",
                reason="ignored",
            ),
        ],
    )

    shell_text = render_rename_plan_shell(plan)

    assert shell_text.startswith("#!/usr/bin/env bash\nset -euo pipefail\n")
    assert "mv '" in shell_text
    assert "source file.jpg" in shell_text
    assert "skip.jpg" not in shell_text


def test_export_rename_plan_shell_writes_script(tmp_path):
    shell_path = tmp_path / "rename.sh"

    from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem

    plan = RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=str(tmp_path.resolve()),
        options={},
        items=[
            RenamePlanItem(
                source=str((tmp_path / "a.jpg").resolve()),
                destination=str((tmp_path / "b.jpg").resolve()),
                action="rename",
                status="ready",
            )
        ],
    )

    export_rename_plan_shell(plan, shell_path)

    shell_text = shell_path.read_text(encoding="utf-8")
    assert shell_text.endswith("\n")
    assert "mv " in shell_text


def test_apply_rename_plan_dry_run_previews_ready_items(tmp_path):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem

    plan = RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=str(tmp_path.resolve()),
        options={},
        items=[
            RenamePlanItem(
                source=str(source_file),
                destination=str(tmp_path / "20240102-030405_MiPh_1234.HEIC"),
                action="rename",
                status="ready",
            )
        ],
    )

    summary = apply_rename_plan(plan, dry_run=True)

    assert source_file.exists()
    assert summary["preview"] == 1


def test_apply_rename_plan_renames_ready_items(tmp_path):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem

    plan = RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=str(tmp_path.resolve()),
        options={},
        items=[
            RenamePlanItem(
                source=str(source_file),
                destination=str(tmp_path / "20240102-030405_MiPh_1234.HEIC"),
                action="rename",
                status="ready",
            )
        ],
    )

    summary = apply_rename_plan(plan, dry_run=False)

    assert not source_file.exists()
    assert (tmp_path / "20240102-030405_MiPh_1234.HEIC").exists()
    assert summary["success"] == 1


def test_apply_rename_plan_does_not_create_history_file_when_rename_fails(tmp_path, monkeypatch):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem

    plan = RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=str(tmp_path.resolve()),
        options={},
        items=[
            RenamePlanItem(
                source=str(source_file),
                destination=str(tmp_path / "20240102-030405_MiPh_1234.HEIC"),
                action="rename",
                status="ready",
            )
        ],
    )

    def raise_rename(*_args, **_kwargs):
        raise OSError("disk error")

    monkeypatch.setattr("mediarchiver.rename.service.os.rename", raise_rename)

    summary = apply_rename_plan(plan, dry_run=False)

    assert source_file.exists()
    assert not (tmp_path / "rename_info.txt").exists()
    assert summary["skipped"] == 1
    assert summary["reasons"]["rename_failed"] == 1


def test_load_rename_plan_rejects_relative_paths(tmp_path):
    plan_path = tmp_path / "rename-plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "version": 1,
                "operation": "rename",
                "source_dir": "relative/source",
                "options": {},
                "summary": {"total": 1, "ready": 1, "skipped": 0, "conflict": 0, "invalid": 0},
                "items": [
                    {
                        "source": "relative/file.jpg",
                        "destination": "/tmp/out.jpg",
                        "action": "rename",
                        "status": "ready",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_rename_plan(plan_path)


def test_apply_built_plan_records_success(tmp_path, monkeypatch):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    monkeypatch.setattr(
        "mediarchiver.rename.service.generate_new_filename",
        lambda *_args, **_kwargs: "20240102-030405_MiPh_1234.HEIC",
    )

    plan = build_rename_plan(str(tmp_path), RenameOptions())
    summary = apply_rename_plan(plan, dry_run=False)

    renamed_file = tmp_path / "20240102-030405_MiPh_1234.HEIC"
    assert renamed_file.exists()
    assert not (tmp_path / "rename_info.txt").exists()
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

    monkeypatch.setattr(
        "mediarchiver.rename.metadata.load_metadata_result", fake_load_metadata_result
    )
    monkeypatch.setattr(
        "mediarchiver.rename.metadata.load_ffprobe_metadata_result",
        fake_load_ffprobe_metadata_result,
    )

    context = build_file_metadata_context(str(video_file))

    assert generate_new_filename(context, options=RenameOptions()) == (
        "20240102-030405_MiPh-FHD-29.97FPS-AVC_7657.mov"
    )
    assert calls == {"exif": 1, "ffprobe": 1}


def test_build_file_metadata_context_loads_video_metadata_once(tmp_path, monkeypatch):
    video_file = tmp_path / "clip.mov"
    video_file.write_text("demo", encoding="utf-8")
    calls = {"exif": 0, "ffprobe": 0}

    def fake_load_metadata_result(_file_path):
        calls["exif"] += 1
        return CommandLoadResult(
            tool_name="exiftool",
            data={"DateTimeOriginal": "2024:01:02 03:04:05", "Make": "Apple"},
        )

    def fake_load_ffprobe_metadata_result(_file_path):
        calls["ffprobe"] += 1
        return CommandLoadResult(
            tool_name="ffprobe",
            data={"streams": [{"codec_type": "video", "width": 1920, "height": 1080}]},
        )

    monkeypatch.setattr(
        "mediarchiver.rename.metadata.load_metadata_result", fake_load_metadata_result
    )
    monkeypatch.setattr(
        "mediarchiver.rename.metadata.load_ffprobe_metadata_result",
        fake_load_ffprobe_metadata_result,
    )

    context = build_file_metadata_context(str(video_file))

    assert context.exif_metadata is not None
    assert context.ffprobe_metadata is not None
    assert context.exif_metadata["Make"] == "Apple"
    assert context.ffprobe_metadata["streams"][0]["width"] == 1920
    assert calls == {"exif": 1, "ffprobe": 1}


def test_load_metadata_result_returns_structured_error(monkeypatch):
    def raise_failure(*_args, **_kwargs):
        raise TypeError("boom")

    monkeypatch.setattr("mediarchiver.common.tool.run_json_command", raise_failure)

    result = load_metadata_result("demo.jpg")

    assert result.ok is False
    assert result.error_code == "invalid_output"
    assert result.error_message is not None
    assert "boom" in result.error_message


def test_load_ffprobe_metadata_result_returns_structured_error(monkeypatch):
    from mediarchiver.common.external import ExternalToolExecutionError

    def raise_failure(*_args, **_kwargs):
        raise ExternalToolExecutionError("ffprobe", "ffprobe failed")

    monkeypatch.setattr("mediarchiver.rename.metadata.run_json_command", raise_failure)

    result = load_ffprobe_metadata_result("clip.mov")

    assert result.ok is False
    assert result.error_code == "command_failed"
    assert result.error_message == "ffprobe failed"


def test_apply_built_plan_records_metadata_load_failure_reason(tmp_path, monkeypatch):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")

    from mediarchiver.common.external import build_command_load_error
    from mediarchiver.rename.metadata import FileMetadataContext

    def fake_context(_file_path, parallel_reads=True):
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

    monkeypatch.setattr("mediarchiver.rename.service.build_file_metadata_context", fake_context)

    plan = build_rename_plan(str(tmp_path), RenameOptions())
    apply_rename_plan(plan, dry_run=False)

    operations = (
        (tmp_path / "rename_operations.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    record = json.loads(operations[-1])
    assert record["status"] == "skipped"
    assert record["reason"] == "exiftool_command_failed"
    assert record["details"]["message"] == "Command failed"


def test_build_rename_plan_prefetches_contexts_once_per_candidate(tmp_path, monkeypatch):
    source_file = tmp_path / "IMG_0001.HEIC"
    source_file.write_text("demo", encoding="utf-8")
    calls = []

    def fake_context(file_path, parallel_reads=True):
        calls.append(file_path)
        return FileMetadataContext(
            file_path=file_path,
            exif_result=CommandLoadResult(
                tool_name="exiftool",
                data={"DateTimeOriginal": "2024:01:02 03:04:05", "Make": "Apple"},
            ),
            ffprobe_result=None,
            exif_metadata={"DateTimeOriginal": "2024:01:02 03:04:05", "Make": "Apple"},
            ffprobe_metadata=None,
            media_date="2024:01:02 03:04:05",
            is_image=True,
            is_video=False,
            is_live_photo_video=False,
        )

    monkeypatch.setattr("mediarchiver.rename.service.build_file_metadata_context", fake_context)
    monkeypatch.setattr(
        "mediarchiver.rename.service.generate_new_filename",
        lambda *_args, **_kwargs: "20240102-030405_MiPh_1234.HEIC",
    )

    build_rename_plan(str(tmp_path), RenameOptions())

    assert calls == [str(source_file)]


def test_build_rename_plan_marks_duplicate_destinations_as_conflict(tmp_path, monkeypatch):
    source_a = tmp_path / "IMG_0001.HEIC"
    source_b = tmp_path / "IMG_0002.HEIC"
    source_a.write_text("demo-a", encoding="utf-8")
    source_b.write_text("demo-b", encoding="utf-8")

    monkeypatch.setattr(
        "mediarchiver.rename.service.generate_new_filename",
        lambda *_args, **_kwargs: "20240102-030405_MiPh_1234.HEIC",
    )

    plan = build_rename_plan(str(tmp_path), RenameOptions())

    items = [item for item in plan.items if item.source in {str(source_a), str(source_b)}]
    assert len(items) == 2
    assert all(item.status == "conflict" for item in items)
    assert all(item.reason == "destination_duplicated_in_plan" for item in items)


def test_prefetch_file_contexts_respects_requested_workers(monkeypatch):
    observed = {}
    calls = []

    class DummyExecutor:
        def __init__(self, max_workers):
            observed["max_workers"] = max_workers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def map(self, func, items):
            return [func(item) for item in items]

    def fake_context(file_path, parallel_reads=True):
        calls.append((file_path, parallel_reads))
        return FileMetadataContext(
            file_path=file_path,
            exif_result=CommandLoadResult(tool_name="exiftool", data={}),
            ffprobe_result=None,
            exif_metadata={},
            ffprobe_metadata=None,
            media_date=None,
            is_image=True,
            is_video=False,
            is_live_photo_video=False,
        )

    monkeypatch.setattr("mediarchiver.rename.service.ThreadPoolExecutor", DummyExecutor)
    monkeypatch.setattr("mediarchiver.rename.service.build_file_metadata_context", fake_context)
    monkeypatch.setattr("mediarchiver.rename.service.os.cpu_count", lambda: 8)

    from mediarchiver.rename.service import prefetch_file_contexts

    result = prefetch_file_contexts(["a.jpg", "b.jpg", "c.jpg"], workers=2)

    assert observed["max_workers"] == 2
    assert list(result) == ["a.jpg", "b.jpg", "c.jpg"]
    assert calls == [("a.jpg", False), ("b.jpg", False), ("c.jpg", False)]


def test_rename_prefetch_workers_are_clamped(monkeypatch):
    monkeypatch.setattr("mediarchiver.common.workers.os.cpu_count", lambda: 2)

    from mediarchiver.rename.service import get_prefetch_workers

    assert get_prefetch_workers(1, requested_workers=8) == 1
    assert get_prefetch_workers(5, requested_workers=8) == 2
    assert get_prefetch_workers(5) == 2
