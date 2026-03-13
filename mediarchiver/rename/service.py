import logging
import os
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from mediarchiver.common.reporting import OperationLogger
from mediarchiver.common.workers import resolve_worker_count
from mediarchiver.rename.metadata import build_file_metadata_context, get_context_load_error
from mediarchiver.rename.options import RenameOptions
from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem
from mediarchiver.rename.rules import (
    generate_new_filename,
    get_md5,
    is_formatted_file_name,
    need_ignore_file,
)

MAX_CONTEXT_PREFETCH_WORKERS = 4


def get_prefetch_workers(item_count, requested_workers=None):
    return resolve_worker_count(
        item_count,
        requested_workers=requested_workers,
        default_max_workers=MAX_CONTEXT_PREFETCH_WORKERS,
    )


def prefetch_file_contexts(file_paths, workers=None):
    if not file_paths:
        return {}

    def load_prefetched_context(file_path):
        return build_file_metadata_context(file_path, parallel_reads=False)

    with ThreadPoolExecutor(max_workers=get_prefetch_workers(len(file_paths), workers)) as executor:
        contexts = executor.map(load_prefetched_context, file_paths)
        return dict(zip(file_paths, contexts))


def list_md5(file_path):
    if not os.path.exists(file_path):
        return set()
    md5s = set()
    with open(file_path, "r", encoding="utf-8") as file_obj:
        for line in file_obj:
            items = line.split("<=", -1)
            if items:
                md5s.add(items[0].strip())
    return md5s


def build_rename_plan(source, options=None, workers=None):
    options = options or RenameOptions()
    source_dir = os.path.abspath(source)
    info_file = os.path.join(source_dir, "rename_info.txt")
    md5s = list_md5(info_file)
    objects = os.listdir(source_dir)
    context_cache = prefetch_file_contexts(
        [
            os.path.join(source_dir, obj)
            for obj in objects
            if not need_ignore_file(source_dir, obj, options)
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
    process_objs = tqdm(objects)
    for obj in process_objs:
        process_objs.set_description("Planning " + obj)
        file_path = os.path.join(source_dir, obj)
        if need_ignore_file(source_dir, obj, options):
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
                context_provider=get_file_context,
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
            if os.path.exists(new_file_path):
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

            md5 = get_md5(file_path)
            if options.include_formatted is False and md5 in md5s:
                logging.warning(
                    f"md5 already exists, can not rename {obj} => {new_file_name} => {md5}"
                )
                items.append(
                    RenamePlanItem(
                        source=file_path,
                        destination=new_file_path,
                        action="rename",
                        status="conflict",
                        reason="duplicate_md5",
                        details={"md5": md5},
                    )
                )
                continue

            items.append(
                RenamePlanItem(
                    source=file_path,
                    destination=new_file_path,
                    action="rename",
                    status="ready",
                    details={"md5": md5},
                )
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
            "workers": workers,
        },
        items=items,
    )


def apply_rename_plan(plan, dry_run=False):
    source_dir = plan.source_dir
    info_file = os.path.join(source_dir, "rename_info.txt")
    report_logger = OperationLogger(source_dir, "rename")
    open(info_file, "a", encoding="utf-8").close()

    with open(info_file, "a", encoding="utf-8") as file_txt:
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

            md5 = item.details.get("md5")
            if md5 is None:
                md5 = get_md5(item.source)
            if dry_run:
                logging.info(
                    "preview rename from plan: %s <= %s <= %s",
                    md5,
                    os.path.basename(item.destination),
                    os.path.basename(item.source),
                )
                report_logger.record(
                    "rename",
                    item.source,
                    destination=item.destination,
                    status="preview",
                    reason="dry_run",
                    details={"md5": md5},
                )
                continue

            try:
                logging.info("rename: %s => %s", item.source, item.destination)
                destination_name = os.path.basename(item.destination)
                source_name = os.path.basename(item.source)
                file_txt.write(f"{md5} <= {destination_name} <= {source_name}\n")
                os.rename(item.source, item.destination)
                report_logger.record(
                    "rename",
                    item.source,
                    destination=item.destination,
                    status="success",
                    details={"md5": md5},
                )
            except OSError as exc:
                logging.exception("apply rename plan failed: %s", item.source)
                report_logger.record(
                    "rename",
                    item.source,
                    destination=item.destination,
                    status="skipped",
                    reason="rename_failed",
                    details={"message": str(exc), "md5": md5},
                )
        process_items.close()
    return report_logger.summary.as_dict()
