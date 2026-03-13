import argparse

from mediarchiver.archive.service import sort_files
from mediarchiver.common.console import print_run_header, print_run_summary
from mediarchiver.common.external import preflight_check_commands
from mediarchiver.common.logging_utils import configure_logging
from mediarchiver.common.workers import positive_int


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mediarchiver archive", description="Process some material"
    )
    parser.add_argument("source", type=str, help="source file path")
    parser.add_argument(
        "--destination",
        type=str,
        help="destination file path (default: source file path)",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="preview archive operations without moving files",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=None,
        help="metadata prefetch worker count (default: auto)",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    destination = args.destination if args.destination else args.source
    configure_logging("archived.log")
    preflight_check_commands(["exiftool"])
    print_run_header(
        "archive",
        {
            "source": args.source,
            "destination": destination,
            "dry_run": args.dry_run,
            "workers": args.workers,
        },
    )
    summary = sort_files(args.source, destination, dry_run=args.dry_run, workers=args.workers)
    print_run_summary("archive", summary)
