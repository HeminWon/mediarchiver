import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from mediarchiver.common.tool import is_img, is_vid
from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.naming import first_formatted_metadata_date
from mediarchiver.rename.original_id import fallback_original_id
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule_builder import RenameRuleError
from mediarchiver.rename.rule_builder import build_media_plan_item as build_standard_media_plan_item

DEVICE_UNIT = "DJI-Pocket4P"
RESOLUTION_TAGS = {
    (1920, 1080): "FHD",
    (3840, 2160): "4K",
    (7680, 4320): "8K",
}


class Pocket4PPreset:
    id = "pocket4p"
    label = "DJI Pocket 4P"
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

    def build_lrf_item(
        self,
        file_path: str,
        primary_items_by_stem: dict[str, RenamePlanItem],
    ) -> RenamePlanItem:
        return build_lrf_plan_item(file_path, primary_items_by_stem)


PRESET = Pocket4PPreset()


def build_media_plan_item(source_dir: str, context: FileMetadataContext) -> RenamePlanItem:
    return build_standard_media_plan_item(source_dir, context, build_new_file_name)


def build_lrf_plan_item(
    file_path: str,
    primary_items_by_stem: dict[str, RenamePlanItem],
) -> RenamePlanItem:
    source_path = Path(file_path)
    primary_item = primary_items_by_stem.get(source_path.stem)
    details = {
        "sidecar_rule": "dji_lrf",
        "sidecar_type": "low_resolution_proxy",
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
    tech_tags = build_tech_tags(context)
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
            "missing": [],
        },
    }


def format_required_date(context: FileMetadataContext):
    filename_date = date_from_dji_filename(context.file_name)
    if filename_date is not None:
        return filename_date, "filename"

    date, date_source = first_formatted_metadata_date(context.exif_metadata)
    if date is not None:
        return date, date_source
    raise RenameRuleError("missing_date", {"file_name": context.file_name})


def date_from_dji_filename(file_name: str):
    match = re.search(r"DJI_(\d{14})_", file_name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:8]}-{raw[8:14]}"


def extract_original_id(file_name: str):
    match = re.search(r"_(\d{4})_", file_name)
    if not match:
        raise RenameRuleError("missing_original_id", {"file_name": file_name})
    return match.group(1), "filename:dji_underscore"


def original_id_from_context(context: FileMetadataContext):
    try:
        return extract_original_id(context.file_name)
    except RenameRuleError:
        return fallback_original_id(context.file_path)


def build_tech_tags(context: FileMetadataContext):
    if is_img(context.file_path):
        return None
    if not is_vid(context.file_path):
        return None
    metadata = context.ffprobe_metadata
    if metadata is None:
        raise RenameRuleError("missing_ffprobe_metadata", {"file_name": context.file_name})
    video_stream = first_video_stream(metadata)
    if video_stream is None:
        raise RenameRuleError("missing_video_stream", {"file_name": context.file_name})

    tags = [
        resolution_tag(video_stream),
        fps_tag(video_stream),
    ]
    gamma = gamma_tag(context.exif_metadata or {})
    if gamma:
        tags.append(gamma)
    return "-".join(tags)


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


def gamma_tag(exif_metadata: dict):
    gamma = exif_metadata.get("DjiCameraColorGammaSxS")
    if gamma is None:
        return None
    normalized = str(gamma).strip().lower().replace(" ", "")
    if normalized in {"d-log", "dlog"}:
        return "DLog"
    if normalized in {"d-logm", "dlogm"}:
        return "DLogM"
    return re.sub(r"[^A-Za-z0-9]+", "", str(gamma).strip()) or None


def mark_destination_conflicts(items: list[RenamePlanItem]) -> list[RenamePlanItem]:
    ready_by_destination = {}
    for index, item in enumerate(items):
        if item.status == "ready" and item.destination is not None:
            ready_by_destination.setdefault(item.destination, []).append(index)

    updated = list(items)
    for indexes in ready_by_destination.values():
        if len(indexes) <= 1:
            continue
        for index in indexes:
            item = updated[index]
            details = dict(item.details)
            details["duplicate_sources"] = [updated[i].source for i in indexes]
            updated[index] = RenamePlanItem(
                source=item.source,
                destination=item.destination,
                action=item.action,
                status="conflict",
                reason="destination_duplicated_in_plan",
                details=details,
            )
    return updated
