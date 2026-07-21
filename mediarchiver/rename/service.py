import logging
import os

from tqdm import tqdm

from mediarchiver.common.reporting import OperationLogger
from mediarchiver.common.workers import map_with_workers, resolve_worker_count
from mediarchiver.rename.metadata import build_file_metadata_context
from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem
from mediarchiver.rename.registry import get_profile, list_profiles
from mediarchiver.rename.rules import is_formatted_file_name

MAX_CONTEXT_PREFETCH_WORKERS = 4
DEFAULT_RENAME_PLAN_FILENAME = "rename-plan.json"


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


def build_rename_plan(
    source,
    profile_id=None,
    workers=None,
    include_formatted=False,
):
    source_dir = os.path.abspath(source)
    if not os.path.isdir(source_dir):
        raise ValueError(f"source directory does not exist: {source_dir}")

    profiles = select_profiles(profile_id)
    file_sets = [
        (profile, profile.collect_files(source_dir, include_formatted=include_formatted))
        for profile in profiles
    ]
    media_paths = sorted(
        {
            media_path
            for _, file_set in file_sets
            for media_path in file_set.media_paths
        }
    )
    contexts = prefetch_file_contexts(media_paths, workers=workers)
    items = []
    for profile, file_set in file_sets:
        profile_items = profile.build_plan_items(source_dir, contexts, file_set)
        for item in profile_items:
            if profile_id is None and item.reason == "profile_not_matched":
                continue
            items.append(with_profile_details(item, profile))
    items.extend(
        build_unmatched_items(
            source_dir,
            items,
            profiles,
            include_formatted=include_formatted,
        )
    )
    items = mark_source_profile_conflicts(items)
    items = mark_destination_conflicts(items)
    return RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=source_dir,
        options={
            "profile": profile_id or "auto",
            "profiles": [profile.id for profile in profiles],
            "workers": workers,
            "include_formatted": include_formatted,
        },
        items=items,
    )


def select_profiles(profile_id=None):
    if profile_id is not None:
        return (get_profile(profile_id),)
    return list_profiles()


def with_profile_details(item, profile):
    details = dict(item.details)
    details.setdefault("profile", profile.id)
    details.setdefault("profile_label", profile.label)
    return RenamePlanItem(
        source=item.source,
        destination=item.destination,
        action=item.action,
        status=item.status,
        reason=item.reason,
        details=details,
    )


def build_unmatched_items(source_dir, items, profiles, include_formatted=False):
    planned_sources = {item.source for item in items}
    profile_ids = [profile.id for profile in profiles]
    unmatched_items = []
    for file_path in collect_source_files(source_dir, include_formatted=include_formatted):
        if file_path in planned_sources:
            continue
        unmatched_items.append(
            RenamePlanItem(
                source=file_path,
                destination=None,
                action="rename",
                status="skipped",
                reason="no_matching_profile",
                details={"profiles": profile_ids},
            )
        )
    return unmatched_items


def collect_source_files(source_dir, include_formatted=False):
    ignored_names = {DEFAULT_RENAME_PLAN_FILENAME, "rename.log", "archived.log"}
    file_paths = []
    for name in sorted(os.listdir(source_dir)):
        file_path = os.path.join(source_dir, name)
        if not os.path.isfile(file_path):
            continue
        if name.startswith(".") or name in ignored_names:
            continue
        if not include_formatted and is_formatted_file_name(name):
            continue
        file_paths.append(file_path)
    return file_paths


def mark_source_profile_conflicts(items):
    ready_by_source = {}
    for index, item in enumerate(items):
        if item.status == "ready":
            ready_by_source.setdefault(item.source, []).append(index)

    updated = list(items)
    for indexes in ready_by_source.values():
        if len(indexes) <= 1:
            continue
        profiles = [updated[index].details.get("profile") for index in indexes]
        for index in indexes:
            item = updated[index]
            details = dict(item.details)
            details["matched_profiles"] = profiles
            updated[index] = RenamePlanItem(
                source=item.source,
                destination=item.destination,
                action=item.action,
                status="conflict",
                reason="source_matched_multiple_profiles",
                details=details,
            )
    return updated


def mark_destination_conflicts(items):
    ready_by_destination = {}
    for index, item in enumerate(items):
        if item.status == "ready" and item.destination is not None:
            ready_by_destination.setdefault(item.destination, []).append(index)

    updated = list(items)
    for indexes in ready_by_destination.values():
        if len(indexes) <= 1:
            continue
        duplicate_sources = [updated[index].source for index in indexes]
        for index in indexes:
            item = updated[index]
            details = dict(item.details)
            details["duplicate_sources"] = duplicate_sources
            updated[index] = RenamePlanItem(
                source=item.source,
                destination=item.destination,
                action=item.action,
                status="conflict",
                reason="destination_duplicated_in_plan",
                details=details,
            )
    return updated


def apply_rename_plan(plan, dry_run=False):
    report_logger = OperationLogger(plan.source_dir, "rename")
    process_items = tqdm(plan.items)
    for item in process_items:
        process_items.set_description("Applying " + os.path.basename(item.source))
        if item.status != "ready":
            report_logger.record(
                "rename",
                item.source,
                destination=item.destination,
                status="conflict" if item.status == "conflict" else "skipped",
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
