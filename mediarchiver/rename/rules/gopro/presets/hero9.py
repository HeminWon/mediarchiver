import os
import re
from pathlib import Path

from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.naming import first_formatted_metadata_date, formatted_fps
from mediarchiver.rename.original_id import trailing_four_digits
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule_builder import RenameRuleError
from mediarchiver.rename.rule_builder import build_media_plan_item as build_standard_media_plan_item

DEVICE_UNIT = "GoPro-HERO9"
RESOLUTION_TAGS = {
    (1920, 1080): "FHD",
    (2704, 1520): "2.7K",
    (3840, 2160): "4K",
    (5312, 2988): "5.3K",
}


class Hero9Preset:
    id = "hero9"
    label = "GoPro HERO9"
    device_unit = DEVICE_UNIT

    def build_media_item(
        self,
        source_dir: str,
        context: FileMetadataContext,
        match_reasons: tuple[str, ...],
    ) -> RenamePlanItem:
        item = build_media_plan_item(source_dir, context)
        item.details["rule_match"] = list(match_reasons)
        return item

    def build_thm_item(
        self,
        file_path: str,
        primary_items_by_stem: dict[str, RenamePlanItem],
    ) -> RenamePlanItem:
        return build_thm_plan_item(file_path, primary_items_by_stem)


PRESET = Hero9Preset()


def build_media_plan_item(source_dir: str, context: FileMetadataContext) -> RenamePlanItem:
    return build_standard_media_plan_item(source_dir, context, build_new_file_name)


def build_thm_plan_item(
    file_path: str,
    primary_items_by_stem: dict[str, RenamePlanItem],
) -> RenamePlanItem:
    source_path = Path(file_path)
    primary_item = primary_items_by_stem.get(source_path.stem)
    details = {
        "sidecar_rule": "gopro_thm",
        "sidecar_type": "thumbnail",
    }
    if primary_item is None:
        return RenamePlanItem(
            source=file_path,
            destination=None,
            action="rename",
            status="skipped",
            reason="missing_primary_media",
            details=details,
        )

    details["paired_with"] = primary_item.source
    if primary_item.status != "ready" or primary_item.destination is None:
        details["primary_status"] = primary_item.status
        details["primary_reason"] = primary_item.reason
        return RenamePlanItem(
            source=file_path,
            destination=None,
            action="rename",
            status="skipped",
            reason="primary_not_ready",
            details=details,
        )

    destination = str(Path(primary_item.destination).with_suffix(source_path.suffix))
    if destination == file_path:
        return RenamePlanItem(
            source=file_path,
            destination=destination,
            action="rename",
            status="skipped",
            reason="already_named",
            details=details,
        )
    if os.path.exists(destination):
        return RenamePlanItem(
            source=file_path,
            destination=destination,
            action="rename",
            status="conflict",
            reason="destination_exists",
            details=details,
        )
    return RenamePlanItem(
        source=file_path,
        destination=destination,
        action="rename",
        status="ready",
        details=details,
    )


def build_new_file_name(context: FileMetadataContext):
    date, date_source = format_required_date(context)
    original_id, original_id_source = original_id_from_context(context)
    tech_tags = build_tech_tags(context) if context.is_video else ""
    parts = [date, DEVICE_UNIT]
    if tech_tags:
        parts.append(tech_tags)
    parts.append(original_id)
    return "_".join(parts) + context.extension, {
        "required": {
            "date": date,
            "date_source": date_source,
            "device_unit": DEVICE_UNIT,
            "device_unit_source": "rule",
            "original_id": original_id,
            "original_id_source": original_id_source,
        },
        "optional": {
            "tech_tags": tech_tags,
            "missing": [] if tech_tags else ["tech_tags"],
        },
    }


def format_required_date(context: FileMetadataContext):
    date, date_source = first_formatted_metadata_date(context.exif_metadata)
    if date is not None:
        return date, date_source
    raise RenameRuleError("missing_date", {"file_name": context.file_name})


def original_id_from_context(context: FileMetadataContext):
    original_id = trailing_four_digits(context.file_path)
    if original_id is None:
        raise RenameRuleError("missing_original_id", {"file_name": context.file_name})
    return original_id, "filename:gopro_sequence"


def build_tech_tags(context: FileMetadataContext):
    metadata = context.ffprobe_metadata
    if metadata is None:
        raise RenameRuleError("missing_ffprobe_metadata", {"file_name": context.file_name})
    video_stream = first_video_stream(metadata)
    if video_stream is None:
        raise RenameRuleError("missing_video_stream", {"file_name": context.file_name})

    tags = [
        resolution_tag(video_stream),
        fps_tag(video_stream),
        codec_tag(video_stream),
    ]
    return "-".join(tag for tag in tags if tag)


def first_video_stream(metadata: dict):
    for stream in metadata.get("streams") or []:
        if stream.get("codec_type") == "video":
            return stream
    return None


def resolution_tag(video_stream: dict):
    width = video_stream.get("width")
    height = video_stream.get("height")
    if width is None or height is None:
        raise RenameRuleError("missing_resolution", {"video_stream": video_stream})
    return RESOLUTION_TAGS.get((width, height), f"{width}x{height}")


def fps_tag(video_stream: dict):
    frame_rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
    fps = formatted_fps(frame_rate)
    if fps is None:
        if not frame_rate:
            raise RenameRuleError("missing_frame_rate", {"video_stream": video_stream})
        raise RenameRuleError("invalid_frame_rate", {"frame_rate": frame_rate})
    return f"{fps}FPS"


def codec_tag(video_stream: dict):
    codec_name = str(video_stream.get("codec_name", "")).lower()
    codec_tag_string = str(video_stream.get("codec_tag_string", "")).lower()
    codec = codec_name or codec_tag_string
    if codec in {"hevc", "h265", "hvc1"} or codec_tag_string == "hvc1":
        return "HEVC"
    if codec in {"h264", "avc1"} or codec_tag_string == "avc1":
        return "H264"
    sanitized = re.sub(r"[^A-Za-z0-9]+", "", codec).upper()
    if not sanitized:
        raise RenameRuleError("missing_codec", {"video_stream": video_stream})
    return sanitized
