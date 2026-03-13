import argparse

from src.common.external import ensure_command_available
from src.common.logging_utils import configure_logging
from src.rename.options import RenameOptions
from src.rename.service import scan_dir


def build_parser():
    parser = argparse.ArgumentParser(description="rename material")
    parser.add_argument("source", type=str, help="source file path")
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
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging("rename.log")
    ensure_command_available("exiftool")
    ensure_command_available("ffprobe")

    options = RenameOptions(
        loose=args.loose,
        rename=args.rename,
        include_formatted=args.include_formatted,
        dry_run=args.dry_run,
    )
    print(f"source: {args.source}")
    print(f"--loose: {options.loose}")
    print(f"--rename: {options.rename}")
    print(f"--include-formatted: {options.include_formatted}")
    print(f"--dry-run: {options.dry_run}")
    scan_dir(args.source, options)
