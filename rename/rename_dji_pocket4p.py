#!/usr/bin/env python3
# ruff: noqa: E402
import argparse
import logging
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mediarchiver.common.external import (
    DependencyMissingError,
    format_missing_dependency_message,
    preflight_check_commands,
)
from mediarchiver.common.logging_utils import configure_logging
from mediarchiver.common.tool import FILE_EXT_LIST, is_img, is_vid
from mediarchiver.common.workers import positive_int
from mediarchiver.rename.metadata import get_context_load_error
from mediarchiver.rename.plan import (
    RENAME_PLAN_VERSION,
    RenamePlan,
    RenamePlanItem,
    write_rename_plan,
)
from mediarchiver.rename.rules import formatted_date, is_formatted_file_name
from mediarchiver.rename.service import apply_rename_plan, prefetch_file_contexts

DEVICE_TAG = "DJI-Pocket4P"
LRF_EXTENSION = ".lrf"


RESOLUTION_TAGS = {
    (1920, 1080): "FHD",
    (3840, 2160): "4K",
    (7680, 4320): "8K",
}


class RenameRuleError(ValueError):
    def __init__(self, reason, details=None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="rename_dji_pocket4p.py",
        description="Preview or apply DJI Pocket 4P batch renames.",
    )
    parser.add_argument("source", type=str, help="source directory")
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="apply ready renames; default is preview only",
    )
    parser.add_argument(
        "--output-plan",
        type=str,
        default=None,
        help="write a mediarchiver rename plan JSON file",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=None,
        help="metadata prefetch workers (default: auto)",
    )
    parser.add_argument(
        "--include-formatted",
        action="store_true",
        default=False,
        help="include already formatted filenames",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="print skipped and conflict details",
    )
    return parser


def build_plan(source, workers=None, include_formatted=False):
    source_dir = os.path.abspath(source)
    if not os.path.isdir(source_dir):
        raise ValueError(f"source directory does not exist: {source_dir}")

    file_paths = collect_media_files(source_dir, include_formatted=include_formatted)
    lrf_paths = collect_lrf_files(source_dir, include_formatted=include_formatted)
    context_cache = prefetch_file_contexts(file_paths, workers=workers)

    items = []
    primary_items_by_stem = {}
    for file_path in file_paths:
        context = context_cache[file_path]
        item = build_plan_item(source_dir, context)
        items.append(item)
        primary_items_by_stem[Path(file_path).stem] = item

    for file_path in lrf_paths:
        items.append(build_lrf_plan_item(source_dir, file_path, primary_items_by_stem))

    items = mark_destination_conflicts(items)
    return RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=source_dir,
        options={
            "script": "rename_dji_pocket4p.py",
            "device": DEVICE_TAG,
            "workers": workers,
            "include_formatted": include_formatted,
            "include_lrf_sidecars": True,
        },
        items=items,
    )


def collect_media_files(source_dir, include_formatted=False):
    names = sorted(os.listdir(source_dir))
    file_paths = []
    for name in names:
        file_path = os.path.join(source_dir, name)
        if not os.path.isfile(file_path):
            continue
        ext = Path(name).suffix[1:].lower()
        if ext not in FILE_EXT_LIST:
            continue
        if not include_formatted and is_formatted_file_name(name):
            continue
        file_paths.append(file_path)
    return file_paths


def collect_lrf_files(source_dir, include_formatted=False):
    names = sorted(os.listdir(source_dir))
    file_paths = []
    for name in names:
        file_path = os.path.join(source_dir, name)
        if not os.path.isfile(file_path):
            continue
        if Path(name).suffix.lower() != LRF_EXTENSION:
            continue
        if not include_formatted and is_formatted_file_name(name):
            continue
        file_paths.append(file_path)
    return file_paths


def build_plan_item(source_dir, context):
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


def build_lrf_plan_item(source_dir, file_path, primary_items_by_stem):
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


def build_new_file_name(context):
    date, date_source = format_required_date(context)
    original_id = extract_original_id(context.file_name)
    tech_tags = build_tech_tags(context)
    parts = [date, DEVICE_TAG]
    if tech_tags:
        parts.append(tech_tags)
    parts.append(original_id)
    return "_".join(parts) + context.extension, {
        "required": {
            "date": date,
            "date_source": date_source,
            "device_unit": DEVICE_TAG,
            "original_id": original_id,
            "original_id_source": "filename",
        },
        "optional": {
            "tech_tags": tech_tags,
            "missing": [],
        },
    }


def format_required_date(context):
    filename_date = date_from_dji_filename(context.file_name)
    if filename_date is not None:
        return filename_date, "filename"

    media_date = context.media_date
    formatted = formatted_date(media_date) if media_date else None
    if formatted is None:
        raise RenameRuleError("missing_date", {"media_date": media_date})
    return formatted, "metadata"


def date_from_dji_filename(file_name):
    match = re.search(r"DJI_(\d{14})_", file_name)
    if not match:
        return None
    raw = match.group(1)
    return f"{raw[:8]}-{raw[8:14]}"


def extract_original_id(file_name):
    match = re.search(r"_(\d{4})_", file_name)
    if not match:
        raise RenameRuleError("missing_original_id", {"file_name": file_name})
    return match.group(1)


def build_tech_tags(context):
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


def first_video_stream(metadata):
    for stream in metadata.get("streams") or []:
        if stream.get("codec_type") == "video":
            return stream
    return None


def resolution_tag(video_stream):
    width = video_stream.get("width")
    height = video_stream.get("height")
    if width is None or height is None:
        raise RenameRuleError("missing_resolution", {"video_stream": video_stream})
    return RESOLUTION_TAGS.get((width, height), f"{width}x{height}")


def fps_tag(video_stream):
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


def gamma_tag(exif_metadata):
    gamma = exif_metadata.get("DjiCameraColorGammaSxS")
    if gamma is None:
        return None
    normalized = str(gamma).strip().lower().replace(" ", "")
    if normalized in {"d-log", "dlog"}:
        return "DLog"
    if normalized in {"d-logm", "dlogm"}:
        return "DLogM"
    return re.sub(r"[^A-Za-z0-9]+", "", str(gamma).strip()) or None


def mark_destination_conflicts(items):
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


def print_preview(plan, verbose=False):
    for item in plan.items:
        if item.status == "ready":
            print(os.path.basename(item.source))
            print(f"  -> {os.path.basename(item.destination)}")
        elif verbose:
            print(os.path.basename(item.source))
            print(f"  [{item.status}] {item.reason}")
    summary = plan.summary
    print()
    print("Summary:")
    print(f"  ready: {summary['ready']}")
    print(f"  skipped: {summary['skipped']}")
    print(f"  conflict: {summary['conflict']}")
    print(f"  invalid: {summary['invalid']}")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        source_dir = os.path.abspath(args.source)
        configure_logging(source_dir, "rename_dji_pocket4p.log")
        commands = ["exiftool"]
        if source_has_video(source_dir):
            commands.append("ffprobe")
        preflight_check_commands(commands)
        plan = build_plan(
            args.source,
            workers=args.workers,
            include_formatted=args.include_formatted,
        )
        if args.output_plan:
            write_rename_plan(plan, args.output_plan)
            print(f"Wrote plan: {args.output_plan}")
        print_preview(plan, verbose=args.verbose)
        if args.apply:
            print()
            print("Applying ready renames...")
            summary = apply_rename_plan(plan, dry_run=False)
            print("Apply summary:")
            for key, value in summary.items():
                print(f"  {key}: {value}")
        else:
            print()
            print("Preview only. No files were renamed. Pass --apply to rename ready items.")
    except DependencyMissingError as exc:
        print(format_missing_dependency_message(exc.tool_name))
        return 1
    except (OSError, ValueError) as exc:
        logging.exception("rename_dji_pocket4p failed")
        print(f"Error: {exc}")
        return 1
    return 0


def source_has_video(source_dir):
    if not os.path.isdir(source_dir):
        return False
    for name in sorted(os.listdir(source_dir)):
        file_path = os.path.join(source_dir, name)
        if os.path.isfile(file_path) and is_vid(file_path):
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
