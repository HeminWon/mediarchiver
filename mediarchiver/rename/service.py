import logging
import os
from collections import Counter

from tqdm import tqdm

from mediarchiver.common.reporting import OperationLogger
from mediarchiver.common.workers import map_with_workers, resolve_worker_count
from mediarchiver.rename.inventory import collect_source_inventory
from mediarchiver.rename.metadata import build_file_metadata_context, get_context_load_error
from mediarchiver.rename.plan import RENAME_PLAN_VERSION, RenamePlan, RenamePlanItem
from mediarchiver.rename.registry import get_rule, list_rules
from mediarchiver.rename.rule import RuleFileSet, normalize_rule_plan_item

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


def build_rename_plan(
    source,
    rule_id=None,
    workers=None,
    include_formatted=False,
    observer=None,
):
    source_dir = os.path.abspath(source)
    if not os.path.isdir(source_dir):
        raise ValueError(f"source directory does not exist: {source_dir}")

    rules = select_rules(rule_id)
    inventory = collect_source_inventory(
        source_dir,
        include_formatted=include_formatted,
    )
    file_sets = [
        (rule, rule.collect_files(inventory))
        for rule in rules
    ]
    scan_summary = summarize_scan(inventory, file_sets)
    notify_observer(observer, "scan", scan_summary)
    contexts = prefetch_file_contexts(inventory.media_paths, workers=workers)
    valid_contexts, items = split_context_load_results(contexts)
    metadata_summary = summarize_metadata(contexts, valid_contexts, items)
    notify_observer(observer, "metadata", metadata_summary)
    for rule, file_set in file_sets:
        rule_file_set = filter_file_set_contexts(file_set, valid_contexts)
        rule_items = rule.build_plan_items(source_dir, valid_contexts, rule_file_set)
        for item in rule_items:
            if rule_id is None and item.reason == "rule_not_matched":
                continue
            items.append(normalize_rule_plan_item(item, rule))
    if rule_id is None:
        items = select_highest_priority_same_brand_items(items)
    items.extend(
        build_unmatched_items(
            inventory,
            items,
            rules,
        )
    )
    if not include_formatted:
        items.extend(build_already_formatted_items(inventory, items))
    items = mark_source_rule_conflicts(items)
    items = mark_destination_conflicts(items)
    return RenamePlan(
        version=RENAME_PLAN_VERSION,
        operation="rename",
        source_dir=source_dir,
        options={
            "rule": rule_id or "auto",
            "rules": [rule.id for rule in rules],
            "workers": workers,
            "include_formatted": include_formatted,
            "scan": scan_summary,
            "metadata": metadata_summary,
        },
        items=items,
    )


def select_rules(rule_id=None):
    if rule_id is not None:
        return (get_rule(rule_id),)
    return list_rules()


def notify_observer(observer, event, payload):
    if observer is not None:
        observer(event, payload)


def summarize_scan(inventory, file_sets):
    sidecar_paths = {
        sidecar_path
        for _, file_set in file_sets
        for sidecar_path in file_set.sidecar_paths
    }
    return {
        "files": len(inventory.all_paths),
        "media": len(inventory.media_paths),
        "sidecars": len(sidecar_paths),
        "formatted": len(inventory.formatted_paths),
        "ignored": len(inventory.ignored_paths),
    }


def summarize_metadata(contexts, valid_contexts, error_items):
    failed_reasons = Counter(item.reason or "unknown" for item in error_items)
    return {
        "media": len(contexts),
        "loaded": len(valid_contexts),
        "failed": len(error_items),
        "failed_reasons": dict(sorted(failed_reasons.items())),
    }


def split_context_load_results(contexts):
    valid_contexts = {}
    error_items = []
    for file_path, context in contexts.items():
        load_error = get_context_load_error(context)
        if load_error is None:
            valid_contexts[file_path] = context
            continue
        error_items.append(
            RenamePlanItem(
                source=file_path,
                destination=None,
                action="rename",
                status="skipped",
                reason=load_error["reason"],
                details=load_error.get("details") or {},
            )
        )
    return valid_contexts, error_items


def filter_file_set_contexts(file_set, contexts):
    return RuleFileSet(
        source_dir=file_set.source_dir,
        media_paths=[
            media_path
            for media_path in file_set.media_paths
            if media_path in contexts
        ],
        sidecar_paths=file_set.sidecar_paths,
    )


def build_unmatched_items(inventory, items, rules):
    planned_sources = {item.source for item in items}
    rule_ids = [rule.id for rule in rules]
    unmatched_items = []
    for file_path in inventory.all_paths:
        if file_path in planned_sources:
            continue
        unmatched_items.append(
            RenamePlanItem(
                source=file_path,
                destination=None,
                action="rename",
                status="skipped",
                reason="no_matching_rule",
                details={"rules": rule_ids},
            )
        )
    return unmatched_items


def select_highest_priority_same_brand_items(items):
    ready_by_source_brand = {}
    for index, item in enumerate(items):
        if item.status != "ready":
            continue
        rule_brand = item.details.get("rule_brand")
        if not rule_brand:
            continue
        ready_by_source_brand.setdefault((item.source, rule_brand), []).append(index)

    shadowed_indexes = set()
    for indexes in ready_by_source_brand.values():
        if len(indexes) <= 1:
            continue
        priorities = {
            index: int(items[index].details.get("rule_priority", 0))
            for index in indexes
        }
        highest_priority = max(priorities.values())
        winners = [
            index
            for index, priority in priorities.items()
            if priority == highest_priority
        ]
        if len(winners) != 1:
            continue
        shadowed_indexes.update(index for index in indexes if index not in winners)

    if not shadowed_indexes:
        return items
    return [item for index, item in enumerate(items) if index not in shadowed_indexes]


def build_already_formatted_items(inventory, items):
    planned_sources = {item.source for item in items}
    formatted_items = []
    for file_path in inventory.formatted_paths:
        if file_path in planned_sources:
            continue
        formatted_items.append(
            RenamePlanItem(
                source=file_path,
                destination=file_path,
                action="rename",
                status="skipped",
                reason="already_formatted",
                details={"formatted": True},
            )
        )
    return formatted_items


def mark_source_rule_conflicts(items):
    ready_by_source = {}
    for index, item in enumerate(items):
        if item.status == "ready":
            ready_by_source.setdefault(item.source, []).append(index)

    updated = list(items)
    for indexes in ready_by_source.values():
        if len(indexes) <= 1:
            continue
        rules = [updated[index].details.get("rule") for index in indexes]
        for index in indexes:
            item = updated[index]
            details = dict(item.details)
            details["matched_rules"] = rules
            updated[index] = RenamePlanItem(
                source=item.source,
                destination=item.destination,
                action=item.action,
                status="conflict",
                reason="source_matched_multiple_rules",
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


def apply_rename_plan(plan, dry_run=False, report_dir=None):
    report_dir = report_dir or plan.source_dir
    with OperationLogger(report_dir, "rename") as report_logger:
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
        summary = report_logger.summary.as_dict()
        summary["operation_jsonl"] = str(report_logger.operation_file)
        if report_logger.conflict_file.exists():
            summary["conflict_jsonl"] = str(report_logger.conflict_file)
        return summary
