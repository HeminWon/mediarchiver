import os
import re
from dataclasses import dataclass

from tqdm import tqdm

from mediarchiver.archive.executor import apply_archive_item, apply_archive_items
from mediarchiver.archive.metadata import (
    get_archive_metadata_error,
    get_cached_archive_date,
    prefetch_archive_metadata,
)
from mediarchiver.archive.sidecars import find_sidecar_primary, is_sidecar_file
from mediarchiver.archive.summary import (
    build_archive_result,
    summarize_archive_group_files,
    summarize_archive_groups,
    summarize_archive_items,
    summarize_skipped_archive_items,
)
from mediarchiver.common.tool import FILE_EXT_LIST

_COMPAT_EXPORTS = (
    apply_archive_item,
    get_archive_metadata_error,
    summarize_archive_group_files,
    summarize_archive_groups,
    summarize_archive_items,
    summarize_skipped_archive_items,
)

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


def build_archive_items(source_dir, target_dir, by="quarter"):
    if not os.path.isdir(source_dir):
        raise ValueError(f"source directory does not exist: {source_dir}")

    objects = collect_archive_objects(source_dir)
    classified = classify_archive_objects(source_dir, objects)

    metadata_cache = prefetch_archive_metadata(
        collect_metadata_paths(source_dir, classified.media)
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


def archive_files(source_dir, target_dir, apply=False, by="quarter"):
    items = build_archive_items(source_dir, target_dir, by=by)
    if apply:
        items = apply_archive_items(items)
    return build_archive_result(items, apply=apply, by=by)
