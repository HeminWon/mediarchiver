import logging
import os
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass, replace

from tqdm import tqdm

from mediarchiver.archive.sidecars import find_sidecar_primary, is_sidecar_file
from mediarchiver.common.tool import (
    FILE_EXT_LIST,
    get_media_date_from_metadata,
    load_metadata_result,
)
from mediarchiver.common.workers import map_with_workers, resolve_worker_count

MAX_METADATA_PREFETCH_WORKERS = 4
ARCHIVE_IGNORED_NAMES = {
    ".DS_Store",
    "archived.log",
    "archive_operations.jsonl",
    "archive_conflicts.jsonl",
}


@dataclass(frozen=True)
class ArchiveItem:
    source: str
    destination: str | None
    status: str
    reason: str | None = None
    date: str | None = None
    subfolder: str | None = None
    kind: str = "media"
    paired_with: str | None = None
    details: dict | None = None


@dataclass(frozen=True)
class ArchiveObjects:
    media: list[str]
    sidecars: list[str]
    directories: list[str]
    unsupported: list[str]


def get_prefetch_workers(item_count, requested_workers=None):
    return resolve_worker_count(
        item_count,
        requested_workers=requested_workers,
        default_max_workers=MAX_METADATA_PREFETCH_WORKERS,
    )


def prefetch_archive_metadata(file_paths, workers=None):
    return map_with_workers(
        file_paths,
        get_archive_metadata_error,
        requested_workers=workers,
        default_max_workers=MAX_METADATA_PREFETCH_WORKERS,
    )


def get_archive_metadata_error(file_path):
    metadata_result = load_metadata_result(file_path)
    if metadata_result.ok:
        return None, get_media_date_from_metadata(metadata_result.data)
    return {
        "reason": f"exiftool_{metadata_result.error_code}",
        "details": {"message": metadata_result.error_message},
    }, None


def get_quarter(date):
    if date is None:
        return None
    match = re.search(r"\d{4}[:\-](\d{2})", date)
    if not match:
        return None
    month = int(match.group(1))
    if 1 <= month <= 3:
        return "Q1"
    if 4 <= month <= 6:
        return "Q2"
    if 7 <= month <= 9:
        return "Q3"
    if 10 <= month <= 12:
        return "Q4"
    return None


def get_subfolder(date, mode="quarter"):
    """Return the relative subfolder path for a given date and archive mode."""
    year, month = get_year_month(date)
    if year is None or month is None:
        return None
    if mode == "year":
        return year
    if mode == "month":
        return f"{year}/{month}"
    quarter = get_quarter(date)
    if quarter is None:
        return None
    return f"{year}/{quarter}"


def get_year_month(date):
    if date is None:
        return None, None
    match = re.search(r"(\d{4})[:\-](\d{2})", date)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def collect_archive_objects(source_dir):
    try:
        return [
            obj
            for obj in sorted(os.listdir(source_dir))
            if obj not in ARCHIVE_IGNORED_NAMES
        ]
    except PermissionError as exc:
        raise PermissionError(f"cannot read source directory: {source_dir}") from exc


def collect_metadata_paths(source_dir, objects):
    return [
        os.path.join(source_dir, obj)
        for obj in objects
        if is_supported_media_file(os.path.join(source_dir, obj))
    ]


def classify_archive_objects(source_dir, objects):
    media_objects = []
    sidecar_objects = []
    directory_objects = []
    unsupported_objects = []

    for obj in objects:
        path = os.path.join(source_dir, obj)
        if os.path.isdir(path):
            directory_objects.append(obj)
        elif is_supported_media_file(path):
            media_objects.append(obj)
        elif is_sidecar_file(path):
            sidecar_objects.append(obj)
        else:
            unsupported_objects.append(obj)

    return ArchiveObjects(
        media=media_objects,
        sidecars=sidecar_objects,
        directories=directory_objects,
        unsupported=unsupported_objects,
    )


def is_supported_media_file(file_path):
    if not os.path.isfile(file_path):
        return False
    ext = os.path.splitext(file_path)[1][1:].lower()
    return ext in FILE_EXT_LIST


def build_archive_item(source_dir, target_dir, obj, metadata_cache=None, by="quarter"):
    source_path = os.path.join(source_dir, obj)
    if os.path.isdir(source_path):
        return ArchiveItem(source_path, None, "skipped", reason="directory")
    if not is_supported_media_file(source_path):
        return ArchiveItem(source_path, None, "skipped", reason="unsupported_extension")

    metadata_error, date = get_cached_archive_date(source_path, metadata_cache)
    if metadata_error is not None:
        return ArchiveItem(
            source_path,
            None,
            "skipped",
            reason=metadata_error["reason"],
            details=metadata_error["details"],
        )

    subfolder = get_subfolder(date, mode=by)
    if subfolder is None:
        return ArchiveItem(source_path, None, "skipped", reason="invalid_date", date=date)

    destination = os.path.join(target_dir, subfolder, obj)
    if os.path.exists(destination):
        return ArchiveItem(
            source_path,
            destination,
            "conflict",
            reason="destination_exists",
            date=date,
            subfolder=subfolder,
        )

    return ArchiveItem(source_path, destination, "ready", date=date, subfolder=subfolder)


def build_media_archive_items(source_dir, target_dir, objects, metadata_cache, by="quarter"):
    items = []
    process_objs = tqdm(objects, disable=not objects)
    for obj in process_objs:
        process_objs.set_description("Processing " + obj)
        items.append(
            build_archive_item(
                source_dir,
                target_dir,
                obj,
                metadata_cache=metadata_cache,
                by=by,
            )
        )
    process_objs.close()
    return items


def build_sidecar_archive_item(source_dir, target_dir, obj, primary_by_stem):
    source_path = os.path.join(source_dir, obj)
    primary = find_sidecar_primary(obj, primary_by_stem)
    if primary is None:
        return ArchiveItem(
            source_path,
            None,
            "skipped",
            reason="sidecar_primary_not_found",
            kind="sidecar",
        )
    paired_with = os.path.basename(primary.source)
    if primary.status != "ready" or primary.destination is None:
        return ArchiveItem(
            source_path,
            None,
            "skipped",
            reason="sidecar_primary_not_ready",
            date=primary.date,
            subfolder=primary.subfolder,
            kind="sidecar",
            paired_with=paired_with,
        )

    destination = os.path.join(target_dir, primary.subfolder, obj)
    if os.path.exists(destination):
        return ArchiveItem(
            source_path,
            destination,
            "conflict",
            reason="destination_exists",
            date=primary.date,
            subfolder=primary.subfolder,
            kind="sidecar",
            paired_with=paired_with,
        )

    return ArchiveItem(
        source_path,
        destination,
        "ready",
        date=primary.date,
        subfolder=primary.subfolder,
        kind="sidecar",
        paired_with=paired_with,
    )


def build_sidecar_archive_items(source_dir, target_dir, objects, primary_by_stem):
    return [
        build_sidecar_archive_item(source_dir, target_dir, obj, primary_by_stem)
        for obj in objects
    ]


def build_directory_archive_items(source_dir, objects):
    return [
        ArchiveItem(os.path.join(source_dir, obj), None, "skipped", reason="directory")
        for obj in objects
    ]


def build_unsupported_archive_items(source_dir, objects):
    return [
        ArchiveItem(
            os.path.join(source_dir, obj),
            None,
            "skipped",
            reason="unsupported_extension",
        )
        for obj in objects
    ]


def build_primary_index(items):
    return {
        os.path.splitext(os.path.basename(item.source))[0].lower(): item
        for item in items
        if item.kind == "media" and is_supported_media_file(item.source)
    }


def get_cached_archive_date(file_path, metadata_cache=None):
    if metadata_cache is not None and file_path in metadata_cache:
        return metadata_cache[file_path]
    return get_archive_metadata_error(file_path)


def apply_archive_item(item):
    if item.status != "ready":
        return item
    destination = item.destination
    if destination is None:
        return replace(item, status="skipped", reason="missing_destination")
    if os.path.exists(destination):
        return replace(item, status="conflict", reason="destination_exists")

    try:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(item.source, destination)
        logging.info("Moved %s to %s", item.source, destination)
        return replace(item, status="success")
    except OSError as exc:
        logging.exception("archive move failed: %s", item.source)
        return replace(
            item,
            status="skipped",
            reason="move_failed",
            details={"message": str(exc)},
        )


def apply_archive_items(items):
    applied_by_source = {}
    applied_items = []
    for item in items:
        if item.paired_with is not None:
            primary = applied_by_source.get(
                os.path.join(os.path.dirname(item.source), item.paired_with)
            )
            if primary is None or primary.status != "success":
                item = replace(item, status="skipped", reason="sidecar_primary_not_moved")
                applied_by_source[item.source] = item
                applied_items.append(item)
                continue

        applied_item = apply_archive_item(item)
        applied_by_source[applied_item.source] = applied_item
        applied_items.append(applied_item)
    return applied_items


def build_archive_items(source_dir, target_dir, by="quarter", workers=None):
    if not os.path.isdir(source_dir):
        raise ValueError(f"source directory does not exist: {source_dir}")

    objects = collect_archive_objects(source_dir)
    classified = classify_archive_objects(source_dir, objects)

    metadata_cache = prefetch_archive_metadata(
        collect_metadata_paths(source_dir, classified.media),
        workers=workers,
    )
    items = build_media_archive_items(
        source_dir,
        target_dir,
        classified.media,
        metadata_cache,
        by=by,
    )
    primary_by_stem = build_primary_index(items)
    items.extend(
        build_sidecar_archive_items(
            source_dir,
            target_dir,
            classified.sidecars,
            primary_by_stem,
        )
    )
    items.extend(build_directory_archive_items(source_dir, classified.directories))
    items.extend(build_unsupported_archive_items(source_dir, classified.unsupported))
    return items


def archive_files(source_dir, target_dir, apply=False, by="quarter", workers=None):
    items = build_archive_items(source_dir, target_dir, by=by, workers=workers)
    if apply:
        items = apply_archive_items(items)
    return build_archive_result(items, apply=apply, by=by)


def build_archive_result(items, apply=False, by="quarter"):
    summary = summarize_archive_items(items, apply=apply)
    return {
        "summary": summary,
        "groups": summarize_archive_groups(items, by=by),
        "skipped": summarize_skipped_archive_items(items),
    }


def summarize_archive_items(items, apply=False):
    counters = Counter()
    reasons = Counter()
    for item in items:
        status = item.status
        if status == "ready":
            status = "success" if apply else "preview"
        counters[status] += 1
        if item.reason:
            reasons[item.reason] += 1
    return {
        "total": len(items),
        "success": counters.get("success", 0),
        "preview": counters.get("preview", 0),
        "skipped": counters.get("skipped", 0),
        "conflict": counters.get("conflict", 0),
        "reasons": dict(reasons),
    }


def summarize_archive_groups(items, by="quarter"):
    grouped = defaultdict(list)
    for item in items:
        if item.status in {"ready", "success"} and item.subfolder:
            grouped[item.subfolder].append(item)

    summaries = []
    for subfolder, group_items in sorted(grouped.items()):
        dates = sorted(item.date for item in group_items if item.date)
        summaries.append(
            {
                "group": subfolder,
                "mode": by,
                "count": len(group_items),
                "date_start": dates[0] if dates else None,
                "date_end": dates[-1] if dates else None,
                "files": summarize_archive_group_files(group_items)
                if len(group_items) < 5
                else [],
            }
        )
    return summaries


def summarize_archive_group_files(items):
    return [
        {
            "file": os.path.basename(item.source),
            "kind": item.kind,
            "paired_with": item.paired_with,
        }
        for item in items
    ]


def summarize_skipped_archive_items(items):
    skipped = []
    for item in items:
        if item.status != "skipped":
            continue
        skipped.append(
            {
                "file": os.path.basename(item.source),
                "reason": item.reason or "unknown",
            }
        )
    return skipped
