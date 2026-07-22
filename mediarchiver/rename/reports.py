import json
import os
from collections import defaultdict
from pathlib import Path

ISSUE_STATUSES = {"skipped", "conflict", "invalid"}
FORMATTED_REASONS = {"already_formatted", "already_named"}


def write_issue_jsonl(plan, output_dir=None):
    issue_items = [
        item
        for item in plan.items
        if item.status in ISSUE_STATUSES and item.reason not in FORMATTED_REASONS
    ]
    if not issue_items:
        return None

    parent_dir = Path(output_dir) if output_dir else Path("/tmp")
    parent_dir.mkdir(parents=True, exist_ok=True)
    log_path = parent_dir / f"mediarchiver-rename-issues-{os.getpid()}.jsonl"
    with log_path.open("w", encoding="utf-8") as file:
        for item in issue_items:
            file.write(json.dumps(issue_item_payload(item), ensure_ascii=False) + "\n")
    return str(log_path)


def print_issue_summary(plan, issue_jsonl_path=None):
    groups = grouped_issue_items(plan)
    if not groups:
        return

    print()
    print("[rename] issues")
    for (status, reason), items in sorted(groups.items()):
        print(f"- {status}/{reason}: {len(items)} file(s)")
    if issue_jsonl_path:
        print(f"- issue jsonl: {issue_jsonl_path}")


def grouped_issue_items(plan):
    groups = defaultdict(list)
    for item in plan.items:
        if item.status not in ISSUE_STATUSES:
            continue
        if item.reason in FORMATTED_REASONS:
            continue
        groups[(item.status, item.reason or "unknown")].append(item)
    return dict(groups)


def issue_item_payload(item):
    return {
        "status": item.status,
        "reason": item.reason,
        "source": item.source,
        "destination": item.destination,
        "details": item.details,
    }
