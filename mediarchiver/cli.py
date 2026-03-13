import argparse
import sys

from mediarchiver.archive.cli import main as archive_main
from mediarchiver.rename.cli import main as rename_main


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mediarchiver", description="Media rename and archive CLI"
    )
    parser.add_argument("command", choices=["rename", "archive"], help="subcommand to run")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="arguments for the subcommand")

    return parser


def main(argv=None):
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(argv)
    if args.command == "rename":
        return rename_main(args.args)
    return archive_main(args.args)
