import logging
import os

from tqdm import tqdm

from mediarchiver.common.reporting import OperationLogger
from mediarchiver.common.workers import map_with_workers, resolve_worker_count
from mediarchiver.rename.metadata import build_file_metadata_context, get_context_load_error
from mediarchiver.rename.options import RenameOptions
from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem
from mediarchiver.rename.rules import (
    file_number,
    generate_new_filename,
    is_formatted_file_name,
    live_photo_match_mov,
    need_ignore_file,
    sony_xml_match_xmls,
)
from mediarchiver.common.tool import FILE_EXT_LIST, is_sony_xml, sony_xml_video_stem

MAX_CONTEXT_PREFETCH_WORKERS = 4


def get_prefetch_workers(item_count, requested_workers=None):
    return resolve_worker_count(
        item_count,
        requested_workers=requested_workers,
        default_max_workers=MAX_CONTEXT_PREFETCH_WORKERS,
    )


def prefetch_file_contexts(file_paths, workers=None):
    return map_with_workers(
        file_paths,
        build_file_metadata_context,
        requested_workers=workers,
        default_max_workers=MAX_CONTEXT_PREFETCH_WORKERS,
        progress_desc="Prefetch metadata",
    )


def _is_prefetch_candidate(folder_path, obj):
    """快速判断是否需要 prefetch metadata，不涉及 is_live_photo_video 检查。"""
    file_path = os.path.join(folder_path, obj)
    if os.path.isdir(file_path):
        return False
    if is_sony_xml(obj):
        return False
    _, ext = os.path.splitext(obj)
    if ext[1:].lower() not in FILE_EXT_LIST:
        return False
    return True


def _append_sidecar_plan_item(items, planned_destinations, planned_sources, source_path, destination_path):
    """Append a sidecar file (XML / Live Photo MOV) plan item, handling conflicts.

    Records the source in *planned_sources* regardless of outcome so the main
    loop skips it when iterating over the directory listing.
    Returns True if the item was appended as ready, False otherwise.
    """
    planned_sources.add(source_path)

    if source_path == destination_path:
        items.append(
            RenamePlanItem(
                source=source_path,
                destination=destination_path,
                action="rename",
                status="skipped",
                reason="already_formatted",
            )
        )
        return False

    if os.path.exists(destination_path):
        logging.warning(
            f"File already exists, can not rename {os.path.basename(source_path)} => {os.path.basename(destination_path)}"
        )
        items.append(
            RenamePlanItem(
                source=source_path,
                destination=destination_path,
                action="rename",
                status="conflict",
                reason="destination_exists",
            )
        )
        return False

    existing_index = planned_destinations.get(destination_path)
    if existing_index is not None:
        existing_item = items[existing_index]
        if existing_item.status == "ready":
            items[existing_index] = RenamePlanItem(
                source=existing_item.source,
                destination=existing_item.destination,
                action=existing_item.action,
                status="conflict",
                reason="destination_duplicated_in_plan",
                details={**existing_item.details, "duplicate_with": source_path},
            )
        items.append(
            RenamePlanItem(
                source=source_path,
                destination=destination_path,
                action="rename",
                status="conflict",
                reason="destination_duplicated_in_plan",
                details={"duplicate_with": existing_item.source},
            )
        )
        return False

    items.append(
        RenamePlanItem(
            source=source_path,
            destination=destination_path,
            action="rename",
            status="ready",
        )
    )
    planned_destinations[destination_path] = len(items) - 1
    return True


def build_rename_plan(source, options=None, workers=None):
    options = options or RenameOptions()
    source_dir = os.path.abspath(source)
    if not os.path.isdir(source_dir):
        raise ValueError(f"source directory does not exist: {source_dir}")
    try:
        objects = sorted(os.listdir(source_dir))
    except PermissionError as exc:
        raise PermissionError(f"cannot read source directory: {source_dir}") from exc

    # Prefetch all candidate media files (including MOV) so that
    # is_live_photo_video is available before the main loop runs.
    context_cache = prefetch_file_contexts(
        [
            os.path.join(source_dir, obj)
            for obj in objects
            if _is_prefetch_candidate(source_dir, obj)
        ],
        workers=workers,
    )

    def get_file_context(file_path):
        context = context_cache.get(file_path)
        if context is None:
            context = build_file_metadata_context(file_path)
            context_cache[file_path] = context
        return context

    items = []
    planned_destinations = {}
    planned_sources = set()
    process_objs = tqdm(objects)
    for obj in process_objs:
        process_objs.set_description("Planning " + obj)
        file_path = os.path.join(source_dir, obj)
        cached_context = context_cache.get(file_path)
        if need_ignore_file(source_dir, obj, options, context=cached_context):
            if file_path in planned_sources:
                continue
            items.append(
                RenamePlanItem(
                    source=file_path,
                    destination=None,
                    action="rename",
                    status="skipped",
                    reason="ignored",
                )
            )
            continue

        try:
            file_context = get_file_context(file_path)
            load_error = get_context_load_error(file_context)
            if load_error is not None:
                items.append(
                    RenamePlanItem(
                        source=file_path,
                        destination=None,
                        action="rename",
                        status="skipped",
                        reason=load_error["reason"],
                        details=load_error["details"],
                    )
                )
                continue

            new_file_name = generate_new_filename(
                file_context,
                options=options,
            )
            if new_file_name is None:
                items.append(
                    RenamePlanItem(
                        source=file_path,
                        destination=None,
                        action="rename",
                        status="skipped",
                        reason="rule_rejected",
                    )
                )
                continue
            if is_formatted_file_name(new_file_name) is False:
                logging.error(f"formated file name is error: {obj} => {new_file_name}")
                items.append(
                    RenamePlanItem(
                        source=file_path,
                        destination=None,
                        action="rename",
                        status="invalid",
                        reason="invalid_generated_name",
                        details={"generated_name": new_file_name},
                    )
                )
                continue

            new_file_path = os.path.join(source_dir, new_file_name)
            if new_file_path == file_path:
                # Source and destination are the same: file is already correctly
                # named. Mark as skipped but still process its sidecars below.
                items.append(
                    RenamePlanItem(
                        source=file_path,
                        destination=new_file_path,
                        action="rename",
                        status="skipped",
                        reason="already_formatted",
                    )
                )
            elif os.path.exists(new_file_path):
                logging.warning(f"File already exists, can not rename {obj} => {new_file_name}")
                items.append(
                    RenamePlanItem(
                        source=file_path,
                        destination=new_file_path,
                        action="rename",
                        status="conflict",
                        reason="destination_exists",
                    )
                )
                continue
            else:
                existing_index = planned_destinations.get(new_file_path)
                if existing_index is not None:
                    existing_item = items[existing_index]
                    if existing_item.status == "ready":
                        items[existing_index] = RenamePlanItem(
                            source=existing_item.source,
                            destination=existing_item.destination,
                            action=existing_item.action,
                            status="conflict",
                            reason="destination_duplicated_in_plan",
                            details={
                                **existing_item.details,
                                "duplicate_with": file_path,
                            },
                        )
                    items.append(
                        RenamePlanItem(
                            source=file_path,
                            destination=new_file_path,
                            action="rename",
                            status="conflict",
                            reason="destination_duplicated_in_plan",
                            details={"duplicate_with": existing_item.source},
                        )
                    )
                    continue

                items.append(
                    RenamePlanItem(
                        source=file_path,
                        destination=new_file_path,
                        action="rename",
                        status="ready",
                    )
                )
                planned_destinations[new_file_path] = len(items) - 1

            if file_context.is_video:
                new_file_name_stem = os.path.splitext(new_file_name)[0]
                for xml_path in sony_xml_match_xmls(source_dir, file_path):
                    _, xml_suffix = sony_xml_video_stem(os.path.basename(xml_path))
                    new_xml_path = os.path.join(source_dir, new_file_name_stem + xml_suffix)
                    _append_sidecar_plan_item(
                        items, planned_destinations, planned_sources, xml_path, new_xml_path
                    )

            if file_context.is_image:
                new_file_name_stem = os.path.splitext(new_file_name)[0]
                img_num = file_number(file_path)
                if img_num is not None:
                    mov_path = live_photo_match_mov(source_dir, img_num)
                    if mov_path is not None:
                        new_mov_path = os.path.join(
                            source_dir,
                            new_file_name_stem + os.path.splitext(mov_path)[1],
                        )
                        _append_sidecar_plan_item(
                            items, planned_destinations, planned_sources, mov_path, new_mov_path
                        )
        except Exception as exc:
            logging.exception("build rename plan failed: %s", file_path)
            items.append(
                RenamePlanItem(
                    source=file_path,
                    destination=None,
                    action="rename",
                    status="invalid",
                    reason="rule_error",
                    details={"message": str(exc)},
                )
            )
    process_objs.close()

    return RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=source_dir,
        options={
            "loose": options.loose,
            "include_formatted": options.include_formatted,
            "time_offset_minutes": options.time_offset_minutes,
            "workers": workers,
        },
        items=items,
    )


def apply_rename_plan(plan, dry_run=False):
    report_logger = OperationLogger(plan.source_dir, "rename")
    process_items = tqdm(plan.items)
    for item in process_items:
        process_items.set_description("Applying " + os.path.basename(item.source))
        if item.status != "ready":
            if item.status == "conflict":
                report_logger.record(
                    "rename",
                    item.source,
                    destination=item.destination,
                    status="conflict",
                    reason=item.reason,
                    details=item.details,
                )
            else:
                report_logger.record(
                    "rename",
                    item.source,
                    destination=item.destination,
                    status="skipped",
                    reason=item.reason,
                    details=item.details,
                )
            continue

        if item.destination is None:
            report_logger.record(
                "rename",
                item.source,
                status="skipped",
                reason="missing_destination",
            )
            continue

        if os.path.exists(item.destination):
            report_logger.record(
                "rename",
                item.source,
                destination=item.destination,
                status="conflict",
                reason="destination_exists",
            )
            continue

        if not os.path.exists(item.source):
            report_logger.record(
                "rename",
                item.source,
                destination=item.destination,
                status="skipped",
                reason="source_missing",
            )
            continue

        if dry_run:
            logging.info(
                "preview rename from plan: %s => %s",
                os.path.basename(item.source),
                os.path.basename(item.destination),
            )
            report_logger.record(
                "rename",
                item.source,
                destination=item.destination,
                status="preview",
                reason="dry_run",
            )
            continue

        try:
            logging.info("rename: %s => %s", item.source, item.destination)
            os.rename(item.source, item.destination)
            report_logger.record(
                "rename",
                item.source,
                destination=item.destination,
                status="success",
            )
        except OSError as exc:
            logging.exception("apply rename plan failed: %s", item.source)
            report_logger.record(
                "rename",
                item.source,
                destination=item.destination,
                status="skipped",
                reason="rename_failed",
                details={"message": str(exc)},
            )
    process_items.close()
    return report_logger.summary.as_dict()
