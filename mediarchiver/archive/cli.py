import argparse

from mediarchiver.archive.service import sort_files
from mediarchiver.common.console import print_run_header, print_run_summary
from mediarchiver.common.external import preflight_check_commands
from mediarchiver.common.logging_utils import configure_logging
from mediarchiver.common.workers import positive_int


def configure_parser(parser):
    parser.add_argument("source", type=str, help="source directory")
    parser.add_argument(
        "--to",
        type=str,
        help="target directory (default: source directory)",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=False,
        help="preview moves without changing files",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=None,
        help="metadata prefetch workers (default: auto)",
    )
    return parser


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mediarchiver archive", description="Archive media by year and quarter"
    )
    return configure_parser(parser)


def register_subparser(subparsers):
    parser = subparsers.add_parser("archive", help="archive media into year/quarter folders")
    configure_parser(parser)
    parser.set_defaults(handler=run_with_args)
    return parser


def run_with_args(args):
    destination = args.to if args.to else args.source
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


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return run_with_args(args)
