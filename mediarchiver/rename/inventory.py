import os
from dataclasses import dataclass

from mediarchiver.common.tool import is_img, is_vid
from mediarchiver.rename.naming import is_formatted_file_name

DEFAULT_RENAME_PLAN_FILENAME = "rename-plan.json"
IGNORED_SOURCE_NAMES = {
    DEFAULT_RENAME_PLAN_FILENAME,
    "rename.log",
    "rename_operations.jsonl",
    "archived.log",
}


@dataclass(frozen=True)
class SourceInventory:
    source_dir: str
    all_paths: list[str]
    media_paths: list[str]
    formatted_paths: list[str]
    ignored_paths: list[str]


def collect_source_inventory(source_dir, include_formatted=False):
    all_paths = []
    media_paths = []
    formatted_paths = []
    ignored_paths = []
    for name in sorted(os.listdir(source_dir)):
        file_path = os.path.join(source_dir, name)
        if not os.path.isfile(file_path):
            continue
        if is_ignored_source_name(name):
            ignored_paths.append(file_path)
            continue
        if is_formatted_file_name(name):
            formatted_paths.append(file_path)
            if not include_formatted:
                continue
        all_paths.append(file_path)
        if is_img(file_path) or is_vid(file_path):
            media_paths.append(file_path)
    return SourceInventory(
        source_dir=source_dir,
        all_paths=all_paths,
        media_paths=media_paths,
        formatted_paths=formatted_paths,
        ignored_paths=ignored_paths,
    )


def collect_source_files(source_dir, include_formatted=False):
    return collect_source_inventory(
        source_dir,
        include_formatted=include_formatted,
    ).all_paths


def collect_formatted_files(source_dir):
    return collect_source_inventory(
        source_dir,
        include_formatted=False,
    ).formatted_paths


def is_ignored_source_name(name):
    return name.startswith(".") or name in IGNORED_SOURCE_NAMES
