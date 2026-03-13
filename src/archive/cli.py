import argparse

from src.archive.service import sort_files
from src.common.external import ensure_command_available
from src.common.logging_utils import configure_logging


def build_parser():
    parser = argparse.ArgumentParser(description="Process some material")
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
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    destination = args.destination if args.destination else args.source
    configure_logging("archived.log")
    ensure_command_available("exiftool")
    print("source:" + args.source)
    print("destination:" + destination)
    print(f"--dry-run: {args.dry_run}")
    sort_files(args.source, destination, dry_run=args.dry_run)
