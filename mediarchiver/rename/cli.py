import argparse
import os
import re
import sys
import tempfile

from mediarchiver.common.console import (
    confirm_proceed,
    print_plan_summary,
    print_run_header,
    print_run_summary,
)
from mediarchiver.common.external import (
    DependencyMissingError,
    format_missing_dependency_message,
    preflight_check_commands,
)
from mediarchiver.common.logging_utils import configure_logging
from mediarchiver.rename.plan import write_rename_plan
from mediarchiver.rename.registry import list_rules
from mediarchiver.rename.reports import print_issue_summary, write_issue_jsonl
from mediarchiver.rename.service import apply_rename_plan, build_rename_plan

DEFAULT_PLAN_FILENAME = "rename-plan.json"
PREVIEW_LIMIT = 50
RENAME_USAGE = (
    "%(prog)s <source> [--apply] [--output DIR]\n"
    "       %(prog)s --list-rules"
)
RENAME_EPILOG = (
    "Examples:\n"
    "  mediarchiver rename --list-rules\n"
    "  mediarchiver rename <source>\n"
    "  mediarchiver rename <source> --apply"
)


def configure_parser(parser):
    parser.add_argument(
        "source",
        nargs="?",
        type=str,
        help="source directory; required unless --list-rules is used",
    )
    parser.add_argument(
        "--list-rules",
        dest="list_rules",
        action="store_true",
        default=False,
        help="list supported rename rules",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="apply ready renames; default is preview only",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="DIR",
        help=f"write {DEFAULT_PLAN_FILENAME} and logs into DIR",
    )
    return parser


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mediarchiver rename",
        usage=RENAME_USAGE,
        description="Build or apply rule-based rename plans",
        epilog=RENAME_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    return configure_parser(parser)


def register_subparser(subparsers):
    parser = subparsers.add_parser(
        "rename",
        usage=RENAME_USAGE,
        help="build or apply rule-based rename plans",
        description="Build or apply rule-based rename plans",
        epilog=RENAME_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    configure_parser(parser)
    parser.set_defaults(handler=handle_args, parser=parser)
    return parser


def validate_args(parser, args):
    if args.list_rules:
        return
    if args.source is None:
        parser.error(
            "missing required source directory.\n\n"
            "Preview example: mediarchiver rename <source>\n"
            "List rules:      mediarchiver rename --list-rules"
        )


def default_artifact_dir(source):
    source_name = os.path.basename(os.path.abspath(source)) or "source"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", source_name).strip(".-") or "source"
    parent_dir = os.path.join(tempfile.gettempdir(), "mediarchiver", "rename")
    os.makedirs(parent_dir, exist_ok=True)
    return tempfile.mkdtemp(prefix=f"{safe_name}-", dir=parent_dir)


def print_rules():
    for rule in list_rules():
        print(f"{rule.id}\t{rule.label}\t{rule.description}")


def print_build_event(event, payload):
    if event == "scan":
        print()
        print("[rename] scan", flush=True)
        print(f"- files: {payload.get('files', 0)}", flush=True)
        print(f"- media: {payload.get('media', 0)}", flush=True)
        print(f"- sidecars: {payload.get('sidecars', 0)}", flush=True)
        print(f"- formatted: {payload.get('formatted', 0)}", flush=True)
        print(f"- ignored: {payload.get('ignored', 0)}", flush=True)
        return
    if event == "metadata":
        print()
        print("[rename] metadata", flush=True)
        print(f"- media: {payload.get('media', 0)}", flush=True)
        print(f"- loaded: {payload.get('loaded', 0)}", flush=True)
        print(f"- failed: {payload.get('failed', 0)}", flush=True)
        failed_reasons = payload.get("failed_reasons") or {}
        if failed_reasons:
            reasons = ", ".join(
                f"{reason}={count}"
                for reason, count in failed_reasons.items()
            )
            print(f"- failed reasons: {reasons}", flush=True)


def print_preview(plan, limit=PREVIEW_LIMIT):
    ready_items = [item for item in plan.items if item.status == "ready"]
    if not ready_items:
        return
    print()
    print("[rename] preview", flush=True)
    for item in ready_items[:limit]:
        source_name = os.path.basename(item.source)
        destination_name = os.path.basename(item.destination)
        print(f"- {source_name}", flush=True)
        print(f"  -> {destination_name}", flush=True)
    remaining = len(ready_items) - limit
    if remaining > 0:
        print(f"- ... {remaining} more ready item(s); see plan for full list", flush=True)


def print_artifacts(artifact_dir, artifacts):
    print()
    print("[rename] artifacts", flush=True)
    print(f"- dir: {artifact_dir}", flush=True)
    for label, path in artifacts:
        if path:
            print(f"- {label}: {path}", flush=True)


def run_with_args(args):
    if args.list_rules:
        print_rules()
        return 0

    source_dir = os.path.abspath(args.source)
    if not os.path.isdir(source_dir):
        raise ValueError(f"source directory does not exist: {source_dir}")
    rules = list_rules()
    rule_ids = [rule.id for rule in rules]
    required_tools = sorted(
        {tool for rule in rules for tool in rule.required_tools}
    )
    preflight_check_commands(required_tools)
    artifact_dir = os.path.abspath(args.output) if args.output else default_artifact_dir(source_dir)
    os.makedirs(artifact_dir, exist_ok=True)
    log_path = configure_logging(artifact_dir, "rename.log")
    plan_path = os.path.join(artifact_dir, DEFAULT_PLAN_FILENAME)
    print_run_header(
        "rename",
        {
            "source": source_dir,
            "rules": ", ".join(rule_ids),
            "apply": args.apply,
        },
    )
    plan = build_rename_plan(
        source_dir,
        observer=print_build_event,
    )
    write_rename_plan(plan, plan_path)
    print_preview(plan)
    print()
    print_plan_summary("rename", plan.summary)
    issue_jsonl_path = write_issue_jsonl(plan, artifact_dir)
    artifacts = [
        ("plan", plan_path),
        ("log", log_path),
        ("issues", issue_jsonl_path),
    ]
    print_issue_summary(plan)

    if not args.apply:
        print_artifacts(artifact_dir, artifacts)
        print()
        print("Preview only. No files were renamed. Pass --apply to rename ready items.")
        return 0

    s = plan.summary
    print(
        f"[rename] ready: {s['ready']} file(s), "
        f"formatted: {s['formatted']}, skipped: {s['skipped']}, "
        f"conflict: {s['conflict']}"
    )
    if not confirm_proceed("Apply rename?"):
        print_artifacts(artifact_dir, artifacts)
        print("[rename] aborted.")
        return 0
    summary = apply_rename_plan(plan, dry_run=False, report_dir=artifact_dir)
    print_run_summary("rename", summary)
    artifacts.extend(
        [
            ("operations", summary.get("operation_jsonl")),
            ("conflicts", summary.get("conflict_jsonl")),
        ]
    )
    print_artifacts(artifact_dir, artifacts)
    return 0


def handle_args(args):
    parser = getattr(args, "parser", None) or build_parser()
    validate_args(parser, args)
    return run_with_args(args)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(parser, args)
        return run_with_args(args)
    except DependencyMissingError as exc:
        print(format_missing_dependency_message(exc.tool_name))
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
