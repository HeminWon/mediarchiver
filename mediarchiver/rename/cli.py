import argparse
import os

from mediarchiver.common.console import print_plan_summary, print_run_header, print_run_summary
from mediarchiver.common.external import preflight_check_commands
from mediarchiver.common.logging_utils import configure_logging
from mediarchiver.common.tool import parse_time_offset
from mediarchiver.common.workers import positive_int
from mediarchiver.rename.options import RenameOptions
from mediarchiver.rename.plan import export_rename_plan_shell, load_rename_plan, write_rename_plan
from mediarchiver.rename.service import apply_rename_plan, build_rename_plan

DEFAULT_PLAN_FILENAME = "rename-plan.json"
DEFAULT_SHELL_FILENAME = "rename.sh"


def configure_parser(parser):
    parser.add_argument("source", nargs="?", type=str, help="source directory")
    parser.add_argument("--plan", type=str, default=None, help="load rename plan from JSON file")
    parser.add_argument(
        "--loose",
        dest="loose",
        action="store_true",
        default=False,
        help="allow partial metadata tags",
    )
    parser.add_argument(
        "--all",
        dest="include_formatted",
        action="store_true",
        default=False,
        help="include already formatted files",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="preview rename actions without changing files",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=None,
        help="metadata prefetch workers (default: auto)",
    )
    parser.add_argument(
        "--time-offset",
        dest="time_offset",
        type=str,
        default=None,
        metavar="±HH:MM",
        help="shift EXIF time by offset, e.g. +8:00, -5:30, +5:45",
    )
    parser.add_argument("--apply", action="store_true", default=False, help="apply rename actions")
    parser.add_argument(
        "--shell",
        action="store_true",
        default=False,
        help="export a shell script for ready actions",
    )
    return parser


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mediarchiver rename",
        description="Build or apply rename plans",
    )
    return configure_parser(parser)


def register_subparser(subparsers):
    parser = subparsers.add_parser("rename", help="build or apply rename plans")
    configure_parser(parser)
    parser.set_defaults(handler=handle_args, parser=parser)
    return parser


def validate_args(parser, args):
    if args.plan and args.source is not None:
        parser.error("source is not allowed with --plan")
    if not args.plan and args.source is None:
        parser.error("source is required unless --plan is used")
    if args.plan and (args.loose or args.include_formatted or args.workers is not None):
        parser.error("scan options cannot be used with --plan")
    if args.dry_run and not (args.apply or args.plan):
        parser.error("--dry-run requires --apply or --plan")
    if getattr(args, "time_offset", None) is not None:
        try:
            parse_time_offset(args.time_offset)
        except ValueError as exc:
            parser.error(str(exc))


def _default_plan_path(source):
    return os.path.join(os.path.abspath(source), DEFAULT_PLAN_FILENAME)


def _default_shell_path(base_path):
    return os.path.join(os.path.dirname(os.path.abspath(base_path)), DEFAULT_SHELL_FILENAME)


def run_with_args(args):
    configure_logging("rename.log")
    preflight_check_commands(["exiftool", "ffprobe"])

    if args.plan:
        plan_path = os.path.abspath(args.plan)
        shell_path = _default_shell_path(plan_path) if args.shell else None
        print_run_header(
            "rename",
            {
                "plan": plan_path,
                "apply": args.apply,
                "dry_run": args.dry_run,
                "shell": shell_path,
            },
        )
        plan = load_rename_plan(plan_path)
        if shell_path is not None:
            export_rename_plan_shell(plan, shell_path)
        if args.apply:
            summary = apply_rename_plan(plan, dry_run=args.dry_run)
            print_run_summary("rename", summary)
            return
        if args.dry_run:
            summary = apply_rename_plan(plan, dry_run=True)
            print_run_summary("rename", summary)
            return
        print_plan_summary("rename", plan.summary)
        return

    options = RenameOptions(
        loose=args.loose,
        include_formatted=args.include_formatted,
        time_offset_minutes=parse_time_offset(getattr(args, "time_offset", None)),
    )
    plan_path = _default_plan_path(args.source)
    shell_path = _default_shell_path(plan_path) if args.shell else None
    print_run_header(
        "rename",
        {
            "source": args.source,
            "loose": options.loose,
            "include_formatted": options.include_formatted,
            "time_offset": getattr(args, "time_offset", None),
            "apply": args.apply,
            "dry_run": args.dry_run,
            "workers": args.workers,
            "plan": plan_path,
            "shell": shell_path,
        },
    )
    plan = build_rename_plan(args.source, options, workers=args.workers)
    if shell_path is not None:
        export_rename_plan_shell(plan, shell_path)
    if args.apply:
        summary = apply_rename_plan(plan, dry_run=args.dry_run)
        print_run_summary("rename", summary)
        return
    write_rename_plan(plan, plan_path)
    print_plan_summary("rename", plan.summary)


def handle_args(args):
    parser = getattr(args, "parser", None) or build_parser()
    validate_args(parser, args)
    return run_with_args(args)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)
    return run_with_args(args)
