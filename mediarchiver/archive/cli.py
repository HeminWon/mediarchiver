import argparse
import os
import sys

from mediarchiver.archive.service import archive_files
from mediarchiver.common.console import confirm_proceed, print_run_header, print_run_summary
from mediarchiver.common.external import (
    DependencyMissingError,
    format_missing_dependency_message,
    preflight_check_commands,
)

ARCHIVE_MODES = ("quarter", "month", "year")
ARCHIVE_USAGE = "%(prog)s <source> [--to DIR] [--by quarter|month|year] [--apply]"
ARCHIVE_EPILOG = (
    "Examples:\n"
    "  mediarchiver archive <source>\n"
    "  mediarchiver archive <source> --to <target>\n"
    "  mediarchiver archive <source> --to <target> --by month\n"
    "  mediarchiver archive <source> --to <target> --apply"
)


def configure_parser(parser):
    parser.add_argument("source", type=str, help="source directory")
    parser.add_argument(
        "--to",
        type=str,
        help="target directory (default: source directory)",
    )
    parser.add_argument(
        "--by",
        choices=ARCHIVE_MODES,
        default="quarter",
        help="folder grouping: quarter (default), month, or year",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="apply archive moves; default is preview only",
    )
    parser.add_argument(
        "--yes",
        "-y",
        dest="yes",
        action="store_true",
        default=False,
        help="skip confirmation prompt when --apply is used",
    )
    return parser


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mediarchiver archive",
        usage=ARCHIVE_USAGE,
        description="Archive media by date into year/quarter, year/month, or year folders",
        epilog=ARCHIVE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    return configure_parser(parser)


def register_subparser(subparsers):
    parser = subparsers.add_parser(
        "archive",
        usage=ARCHIVE_USAGE,
        help="archive media into date-based folders",
        description="Archive media by date into year/quarter, year/month, or year folders",
        epilog=ARCHIVE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    configure_parser(parser)
    parser.set_defaults(handler=run_with_args)
    return parser


def run_with_args(args):
    source_dir = os.path.abspath(args.source)
    if not os.path.isdir(source_dir):
        raise ValueError(f"source directory does not exist: {source_dir}")
    destination = os.path.abspath(args.to if args.to else args.source)
    by = getattr(args, "by", "quarter")
    preflight_check_commands(["exiftool"])
    print_run_header(
        "archive",
        {
            "source": args.source,
            "destination": destination,
            "by": by,
            "apply": args.apply,
        },
    )
    if args.apply and not getattr(args, "yes", False):
        print(f"[archive] will move files from '{source_dir}' into '{destination}' (by {by})")
        if not confirm_proceed("Proceed with archive?"):
            print("[archive] aborted.")
            return
    result = archive_files(
        source_dir,
        destination,
        apply=args.apply,
        by=by,
    )
    summary = result["summary"]
    print_run_summary("archive", summary)
    print_archive_groups(result["groups"], destination)
    print_skipped_items(result["skipped"])
    if not args.apply:
        print()
        print("Preview only. No files were moved. Pass --apply to archive previewed items.")


def print_archive_groups(groups, destination):
    print()
    print("[archive] preview groups")
    if not groups:
        print("  none")
        return
    for group in groups:
        date_range = format_group_date_range(group)
        print()
        print(f"{group['group']}  ({group['count']} file(s), {date_range})")
        print(f"  -> {os.path.join(destination, group['group'])}")
        if group["files"]:
            for file_item in group["files"]:
                print(f"  {format_archive_group_file(file_item)}")


def format_group_date_range(group):
    date_start = group.get("date_start")
    date_end = group.get("date_end")
    if date_start and date_end and date_start != date_end:
        return f"{date_start} .. {date_end}"
    if date_start:
        return date_start
    return "unknown"


def format_archive_group_file(file_item):
    file_name = file_item["file"]
    if file_item.get("kind") == "sidecar":
        paired_with = file_item.get("paired_with") or "unknown"
        return f"[sidecar] {file_name}  -> {paired_with}"
    return f"[media]   {file_name}"


def print_skipped_items(skipped_items):
    if not skipped_items:
        return
    print()
    print("[archive] skipped")
    for item in skipped_items:
        print(f"  {item['file']}  ({item['reason']})")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run_with_args(args)
    except DependencyMissingError as exc:
        print(format_missing_dependency_message(exc.tool_name))
        sys.exit(1)
