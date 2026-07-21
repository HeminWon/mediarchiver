import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.naming import formatted_date
from mediarchiver.rename.original_id import fallback_original_id
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule_builder import RenameRuleError
from mediarchiver.rename.rule_builder import build_media_plan_item as build_standard_media_plan_item

DEVICE_UNIT = "Sony-A7M4"


class SonyA7M4Preset:
    id = "a7m4"
    label = "Sony A7M4"
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

    def build_sidecar_item(
        self,
        file_path: str,
        primary_items_by_id: dict[str, RenamePlanItem],
    ) -> RenamePlanItem:
        return build_sidecar_plan_item(file_path, primary_items_by_id)

    def original_id_from_name(self, file_name: str):
        try:
            return extract_original_id(file_name)[0]
        except RenameRuleError:
            return None


PRESET = SonyA7M4Preset()


def build_media_plan_item(source_dir: str, context: FileMetadataContext) -> RenamePlanItem:
    return build_standard_media_plan_item(source_dir, context, build_new_file_name)


def build_sidecar_plan_item(
    file_path: str,
    primary_items_by_id: dict[str, RenamePlanItem],
) -> RenamePlanItem:
    source_path = Path(file_path)
    original_id, sidecar_rule, sidecar_type = extract_sidecar_info(source_path.name)
    details = {
        "sidecar_rule": sidecar_rule,
        "sidecar_type": sidecar_type,
        "original_id": original_id,
        "original_id_source": "filename",
    }
    primary_item = primary_items_by_id.get(original_id)
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
    metadata = context.exif_metadata or {}
    for field in ("CreationDateValue", "CreationDate", "DateTimeOriginal", "CreateDate"):
        formatted = formatted_date(metadata.get(field))
        if formatted is not None:
            return formatted, f"metadata:{field}"
    raise RenameRuleError("missing_date", {"file_name": context.file_name})


def extract_original_id(file_name: str):
    clip_match = re.match(r"C(\d{4})\.(?:MP4|MOV)$", file_name, re.IGNORECASE)
    if clip_match:
        return clip_match.group(1), "filename:sony_clip"
    photo_match = re.match(r"DSC(\d+)\.(?:ARW|JPE?G)$", file_name, re.IGNORECASE)
    if photo_match:
        return photo_match.group(1), "filename:sony_photo"
    raise RenameRuleError("missing_original_id", {"file_name": file_name})


def original_id_from_context(context: FileMetadataContext):
    try:
        return extract_original_id(context.file_name)
    except RenameRuleError:
        return fallback_original_id(context.file_path)


def extract_sidecar_info(file_name: str):
    xml_match = re.match(r"C(\d{4})M\d{2}\.XML$", file_name, re.IGNORECASE)
    if xml_match:
        return xml_match.group(1), "sony_xml", "non_real_time_metadata"
    photo_match = re.match(r"DSC(\d+)\.(XMP|ACR)$", file_name, re.IGNORECASE)
    if photo_match:
        sidecar_ext = photo_match.group(2).lower()
        return photo_match.group(1), f"sony_{sidecar_ext}", f"photo_{sidecar_ext}"
    return None, "sony_sidecar", "unknown"


def build_tech_tags(context: FileMetadataContext):
    metadata = context.ffprobe_metadata or {}
    stream = first_video_stream(metadata)
    if stream is None:
        raise RenameRuleError("missing_video_stream", {"file_name": context.file_name})
    tags = [
        resolution_tag(stream),
        fps_tag(stream),
        codec_tag(stream),
    ]
    bit_depth = bit_depth_tag(stream)
    if bit_depth:
        tags.append(bit_depth)
    chroma = chroma_tag(stream)
    if chroma:
        tags.append(chroma)
    gamma = gamma_tag(context.exif_metadata or {})
    if gamma:
        tags.append(gamma)
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
    return {
        (1920, 1080): "FHD",
        (3840, 2160): "4K",
        (7680, 4320): "8K",
    }.get((width, height), f"{width}x{height}")


def fps_tag(video_stream: dict):
    frame_rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
    if not frame_rate:
        raise RenameRuleError("missing_frame_rate", {"video_stream": video_stream})
    try:
        numerator, denominator = frame_rate.split("/", 1)
        denominator_int = int(denominator)
        if denominator_int == 0:
            raise ZeroDivisionError
        fps = Decimal(numerator) / Decimal(denominator_int)
    except (ValueError, ZeroDivisionError, InvalidOperation) as exc:
        raise RenameRuleError("invalid_frame_rate", {"frame_rate": frame_rate}) from exc
    return f"{fps.quantize(Decimal('0.01')).normalize()}FPS"


def codec_tag(video_stream: dict):
    codec_name = str(video_stream.get("codec_name", "")).lower()
    if codec_name in {"h264", "avc1"}:
        return "H264"
    if codec_name in {"hevc", "h265"}:
        return "HEVC"
    return re.sub(r"[^A-Za-z0-9]+", "", codec_name).upper() or None


def bit_depth_tag(video_stream: dict):
    raw = video_stream.get("bits_per_raw_sample")
    if raw is not None and str(raw).isdigit():
        return f"{raw}Bit"
    pixel_format = str(video_stream.get("pix_fmt", "")).lower()
    match = re.search(r"p(\d+)", pixel_format)
    if match:
        return f"{match.group(1)}Bit"
    return None


def chroma_tag(video_stream: dict):
    pixel_format = str(video_stream.get("pix_fmt", "")).lower()
    if "422" in pixel_format:
        return "422"
    if "420" in pixel_format:
        return "420"
    if "444" in pixel_format:
        return "444"
    return None


def gamma_tag(exif_metadata: dict):
    gamma = exif_metadata.get("AcquisitionRecordGroupItemValue")
    if gamma is None:
        return None
    normalized = str(gamma).strip().lower().replace("-", "").replace("_", "")
    if normalized == "slog3":
        return "SLog3"
    if normalized == "slog2":
        return "SLog2"
    return re.sub(r"[^A-Za-z0-9]+", "", str(gamma).strip()) or None
