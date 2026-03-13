import argparse
import os

from mediarchiver.common.console import print_plan_summary, print_run_header, print_run_summary
from mediarchiver.common.external import preflight_check_commands
from mediarchiver.common.logging_utils import configure_logging
from mediarchiver.common.workers import positive_int
from mediarchiver.rename.options import RenameOptions
from mediarchiver.rename.plan import export_rename_plan_shell, load_rename_plan, write_rename_plan
from mediarchiver.rename.service import apply_rename_plan, build_rename_plan, scan_dir


def build_parser():
    parser = argparse.ArgumentParser(prog="mediarchiver rename", description="rename material")
    parser.add_argument("source", nargs="?", type=str, help="source file path")
    parser.add_argument(
        "--loose",
        dest="loose",
        action="store_true",
        default=False,
        help="loose exif or ffmpeg tags",
    )
    parser.add_argument(
        "--rename",
        dest="rename",
        action="store_true",
        default=False,
        help="rename file",
    )
    parser.add_argument(
        "--include-formatted",
        "--ignore_formatted",
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
        help="preview rename operations without changing files",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=None,
        help="metadata prefetch worker count (default: auto)",
    )
    parser.add_argument(
        "--build-plan",
        type=str,
        default=None,
        help="write rename plan JSON to path",
    )
    parser.add_argument(
        "--apply-plan",
        type=str,
        default=None,
        help="apply rename plan JSON from path",
    )
    parser.add_argument(
        "--export-shell",
        type=str,
        default=None,
        help="export shell script from rename plan JSON",
    )
    return parser


def validate_args(parser, args):
    if args.apply_plan:
        if args.source is not None:
            parser.error("source is not allowed with --apply-plan")
        if args.build_plan:
            parser.error("--build-plan cannot be used with --apply-plan")
        if args.export_shell:
            parser.error("--export-shell cannot be used with --apply-plan")
        if args.rename:
            parser.error("--rename is not needed with --apply-plan")
        if args.loose or args.include_formatted or args.workers is not None:
            parser.error("plan build options cannot be used with --apply-plan")
        return
    if args.export_shell:
        if args.source is not None:
            parser.error("source is not allowed with --export-shell")
        if not args.build_plan:
            parser.error("--export-shell requires --build-plan")
        if args.rename:
            parser.error("--rename is not needed with --export-shell")
        if args.loose or args.include_formatted or args.workers is not None or args.dry_run:
            parser.error("plan build options cannot be used with --export-shell")
        return
    if args.source is None:
        parser.error("source is required unless --apply-plan or --export-shell is used")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)
    configure_logging("rename.log")
    preflight_check_commands(["exiftool", "ffprobe"])

    options = RenameOptions(
        loose=args.loose,
        rename=args.rename,
        include_formatted=args.include_formatted,
        dry_run=args.dry_run,
    )
    if args.apply_plan:
        plan_path = os.path.abspath(args.apply_plan)
        print_run_header(
            "rename",
            {
                "apply_plan": plan_path,
                "dry_run": args.dry_run,
            },
        )
        plan = load_rename_plan(plan_path)
        summary = apply_rename_plan(plan, dry_run=args.dry_run)
        print_run_summary("rename", summary)
        return

    if args.export_shell:
        plan_path = os.path.abspath(args.build_plan)
        shell_path = os.path.abspath(args.export_shell)
        print_run_header(
            "rename",
            {
                "build_plan": plan_path,
                "export_shell": shell_path,
            },
        )
        plan = load_rename_plan(plan_path)
        export_rename_plan_shell(plan, shell_path)
        print_plan_summary("rename", plan.summary)
        return

    print_run_header(
        "rename",
        {
            "source": args.source,
            "loose": options.loose,
            "rename": options.rename,
            "include_formatted": options.include_formatted,
            "dry_run": options.dry_run,
            "workers": args.workers,
            "build_plan": args.build_plan,
            "export_shell": args.export_shell,
        },
    )
    if args.build_plan:
        plan = build_rename_plan(args.source, options, workers=args.workers)
        write_rename_plan(plan, args.build_plan)
        print_plan_summary("rename", plan.summary)
        return

    summary = scan_dir(args.source, options, workers=args.workers)
    print_run_summary("rename", summary)
