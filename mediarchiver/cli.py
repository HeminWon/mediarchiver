import argparse

from mediarchiver.archive.cli import register_subparser as register_archive_subparser
from mediarchiver.rename.cli import register_subparser as register_rename_subparser


def build_parser():
    parser = argparse.ArgumentParser(prog="mediarchiver", description="Organize media files")
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_rename_subparser(subparsers)
    register_archive_subparser(subparsers)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)
