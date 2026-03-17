import argparse
import sys

from mediarchiver import __version__
from mediarchiver.archive.cli import register_subparser as register_archive_subparser
from mediarchiver.common.external import DependencyMissingError, format_missing_dependency_message
from mediarchiver.rename.cli import register_subparser as register_rename_subparser


def build_parser():
    parser = argparse.ArgumentParser(prog="mediarchiver", description="Organize media files")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_rename_subparser(subparsers)
    register_archive_subparser(subparsers)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except DependencyMissingError as exc:
        print(format_missing_dependency_message(exc.tool_name))
        sys.exit(1)
