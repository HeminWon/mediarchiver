import argparse
import os
import sys

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
from mediarchiver.rename.service import apply_rename_plan, build_rename_plan

DEFAULT_PLAN_FILENAME = "rename-plan.json"
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
        help=f"write {DEFAULT_PLAN_FILENAME} into DIR",
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


def default_plan_path(source):
    return os.path.join(os.path.abspath(source), DEFAULT_PLAN_FILENAME)


def print_rules():
    for rule in list_rules():
        print(f"{rule.id}\t{rule.label}\t{rule.description}")


def print_preview(plan):
    for item in plan.items:
        if item.status == "ready":
            print(os.path.basename(item.source))
            print(f"  -> {os.path.basename(item.destination)}")


def run_with_args(args):
    if args.list_rules:
        print_rules()
        return 0

    source_dir = os.path.abspath(args.source)
    if not os.path.isdir(source_dir):
        raise ValueError(f"source directory does not exist: {source_dir}")
    rules = list_rules()
    rule_ids = [rule.id for rule in rules]
    log_path = configure_logging(source_dir, "rename.log")
    required_tools = sorted(
        {tool for rule in rules for tool in rule.required_tools}
    )
    preflight_check_commands(required_tools)
    plan_path = (
        os.path.join(os.path.abspath(args.output), DEFAULT_PLAN_FILENAME)
        if args.output
        else default_plan_path(source_dir)
    )
    print_run_header(
        "rename",
        {
            "source": source_dir,
            "rules": ", ".join(rule_ids),
            "apply": args.apply,
            "plan": plan_path,
            "log": log_path,
        },
    )
    plan = build_rename_plan(
        source_dir,
    )
    write_rename_plan(plan, plan_path)
    print_preview(plan)
    print_plan_summary("rename", plan.summary)

    if not args.apply:
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
        print("[rename] aborted.")
        return 0
    summary = apply_rename_plan(plan, dry_run=False)
    print_run_summary("rename", summary)
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
