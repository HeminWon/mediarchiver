import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from mediarchiver.rename.metadata import FileMetadataContext, get_context_load_error
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rules import formatted_date


@dataclass(frozen=True)
class RenameRuleError(ValueError):
    reason: str
    details: dict

    def __str__(self):
        return self.reason


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
        item.details["profile_match"] = list(match_reasons)
        return item


PRESET = IPhonePreset()


def build_media_plan_item(source_dir: str, context: FileMetadataContext) -> RenamePlanItem:
    load_error = get_context_load_error(context)
    if load_error is not None:
        return RenamePlanItem(
            source=context.file_path,
            destination=None,
            action="rename",
            status="skipped",
            reason=load_error["reason"],
            details=load_error.get("details") or {},
        )

    try:
        new_file_name, details = build_new_file_name(context)
    except RenameRuleError as exc:
        return RenamePlanItem(
            source=context.file_path,
            destination=None,
            action="rename",
            status="invalid",
            reason=exc.reason,
            details=exc.details,
        )

    destination = os.path.join(source_dir, new_file_name)
    if destination == context.file_path:
        return RenamePlanItem(
            source=context.file_path,
            destination=destination,
            action="rename",
            status="skipped",
            reason="already_named",
            details=details,
        )
    if os.path.exists(destination):
        return RenamePlanItem(
            source=context.file_path,
            destination=destination,
            action="rename",
            status="conflict",
            reason="destination_exists",
            details=details,
        )
    return RenamePlanItem(
        source=context.file_path,
        destination=destination,
        action="rename",
        status="ready",
        details=details,
    )


def build_new_file_name(context: FileMetadataContext):
    date, date_source = format_required_date(context)
    device_unit, device_source = device_unit_from_metadata(context)
    original_id, original_id_source = extract_original_id(context.file_name)
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
    metadata = context.exif_metadata or {}
    for field in (
        "SubSecDateTimeOriginal",
        "DateTimeOriginal",
        "CreateDate",
        "DateCreated",
        "CreationDate",
    ):
        formatted = formatted_date(metadata.get(field))
        if formatted is not None:
            return formatted, f"metadata:{field}"
    raise RenameRuleError("missing_date", {"file_name": context.file_name})


def device_unit_from_metadata(context: FileMetadataContext):
    metadata = context.exif_metadata or {}
    model = metadata.get("Model") or metadata.get("HostComputer")
    if not model:
        raise RenameRuleError("missing_device_model", {"file_name": context.file_name})
    device_unit = re.sub(r"[^A-Za-z0-9]+", "", str(model).strip())
    if not device_unit:
        raise RenameRuleError("invalid_device_model", {"model": model})
    return device_unit, "metadata:Model"


def extract_original_id(file_name: str):
    match = re.search(r"(?:IMG|IMG_E|DSC|DSCF|PXL)[_-]?(\d{4})", file_name, re.IGNORECASE)
    if match:
        return match.group(1), "filename"
    raise RenameRuleError("missing_original_id", {"file_name": file_name})


def build_tech_tags(context: FileMetadataContext):
    tags = []
    metadata = context.exif_metadata or {}
    if is_screenshot(context):
        tags.append("Screenshot")
    if is_selfie(metadata):
        tags.append("Selfie")
    if is_hdr(metadata):
        tags.append("HDR")
    if context.is_live_photo_video or metadata.get("LivePhotoVideoIndex") is not None:
        tags.append("LivePhoto")
    if context.is_video:
        tags.extend(video_tech_tags(context))
    return "-".join(tags) or None


def is_screenshot(context: FileMetadataContext):
    metadata = context.exif_metadata or {}
    file_name = context.file_name.lower()
    user_comment = str(metadata.get("UserComment", "")).lower()
    return file_name.startswith(("screenshot", "screen shot")) or "screenshot" in user_comment


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
