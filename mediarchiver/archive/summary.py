import os
from collections import Counter, defaultdict


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
