import logging
import os
import shutil
from dataclasses import replace


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
