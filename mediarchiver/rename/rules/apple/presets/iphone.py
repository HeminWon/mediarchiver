import re
from decimal import Decimal, InvalidOperation

from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.naming import first_formatted_metadata_date
from mediarchiver.rename.original_id import fallback_original_id
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule_builder import RenameRuleError
from mediarchiver.rename.rule_builder import build_media_plan_item as build_standard_media_plan_item


class IPhonePreset:
    id = "iphone"
    label = "Apple iPhone"

    def build_media_item(
        self,
        source_dir: str,
        context: FileMetadataContext,
        match_reasons: tuple[str, ...],
    ) -> RenamePlanItem:
        item = build_media_plan_item(source_dir, context)
        item.details["rule_match"] = list(match_reasons)
        return item


PRESET = IPhonePreset()


def build_media_plan_item(source_dir: str, context: FileMetadataContext) -> RenamePlanItem:
    return build_standard_media_plan_item(source_dir, context, build_new_file_name)


def build_new_file_name(context: FileMetadataContext):
    date, date_source = format_required_date(context)
    device_unit, device_source = device_unit_from_metadata(context)
    original_id, original_id_source = fallback_original_id(context.file_path)
    tech_tags = build_tech_tags(context)
    parts = [date, device_unit]
    if tech_tags:
        parts.append(tech_tags)
    parts.append(original_id)
    return "_".join(parts) + context.extension, {
        "required": {
            "date": date,
            "date_source": date_source,
            "device_unit": device_unit,
            "device_unit_source": device_source,
            "original_id": original_id,
            "original_id_source": original_id_source,
        },
        "optional": {
            "tech_tags": tech_tags,
            "missing": [] if tech_tags else ["tech_tags"],
        },
    }


def format_required_date(context: FileMetadataContext):
    date, date_source = first_formatted_metadata_date(
        context.exif_metadata,
        (
            "SubSecDateTimeOriginal",
            "DateTimeOriginal",
            "CreateDate",
            "DateCreated",
            "CreationDate",
        ),
    )
    if date is not None:
        return date, date_source
    raise RenameRuleError("missing_date", {"file_name": context.file_name})


def device_unit_from_metadata(context: FileMetadataContext):
    metadata = context.exif_metadata or {}
    for field in ("Model", "HostComputer"):
        model = metadata.get(field)
        if not model:
            continue
        device_unit = re.sub(r"[^A-Za-z0-9]+", "", str(model).strip())
        if not device_unit:
            raise RenameRuleError("invalid_device_model", {"model": model})
        return device_unit, f"metadata:{field}"
    if not metadata.get("Model") and not metadata.get("HostComputer"):
        raise RenameRuleError("missing_device_model", {"file_name": context.file_name})
    raise RenameRuleError("invalid_device_model", {"file_name": context.file_name})


def build_tech_tags(context: FileMetadataContext):
    tags = []
    metadata = context.exif_metadata or {}
    if is_selfie(metadata):
        tags.append("Selfie")
    if is_hdr(metadata):
        tags.append("HDR")
    if context.is_live_photo_video or metadata.get("LivePhotoVideoIndex") is not None:
        tags.append("LivePhoto")
    if context.is_video:
        tags.extend(video_tech_tags(context))
    return "-".join(tags) or None


def is_selfie(metadata: dict):
    lens_text = " ".join(
        str(metadata.get(field, ""))
        for field in ("LensModel", "LensID", "LensInfo")
        if metadata.get(field) is not None
    ).lower()
    if "front camera" in lens_text:
        return True
    camera_type = metadata.get("CameraType")
    return camera_type in {6, "6"}


def is_hdr(metadata: dict):
    if metadata.get("HDRGainMapVersion") is not None:
        return True
    if metadata.get("HDRHeadroom") is not None:
        return True
    auxiliary_type = str(metadata.get("AuxiliaryImageType", "")).lower()
    return "hdr" in auxiliary_type


def video_tech_tags(context: FileMetadataContext):
    metadata = context.ffprobe_metadata or {}
    stream = first_video_stream(metadata)
    if stream is None:
        return []
    tags = []
    resolution = resolution_tag(stream)
    if resolution:
        tags.append(resolution)
    fps = fps_tag(stream)
    if fps:
        tags.append(fps)
    codec = codec_tag(stream)
    if codec:
        tags.append(codec)
    return tags


def first_video_stream(metadata: dict):
    for stream in metadata.get("streams") or []:
        if stream.get("codec_type") == "video":
            return stream
    return None


def resolution_tag(video_stream: dict):
    width = video_stream.get("width")
    height = video_stream.get("height")
    if width is None or height is None:
        return None
    return {
        (1920, 1080): "FHD",
        (3840, 2160): "4K",
        (7680, 4320): "8K",
    }.get((width, height), f"{width}x{height}")


def fps_tag(video_stream: dict):
    frame_rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
    if not frame_rate:
        return None
    try:
        numerator, denominator = frame_rate.split("/", 1)
        denominator_int = int(denominator)
        if denominator_int == 0:
            return None
        fps = Decimal(numerator) / Decimal(denominator_int)
    except (ValueError, InvalidOperation):
        return None
    return f"{fps.quantize(Decimal('0.01')).normalize()}FPS"


def codec_tag(video_stream: dict):
    codec_name = str(video_stream.get("codec_name", "")).lower()
    if codec_name in {"hevc", "h265"}:
        return "HEVC"
    if codec_name in {"h264", "avc1"}:
        return "H264"
    return re.sub(r"[^A-Za-z0-9]+", "", codec_name).upper() or None
