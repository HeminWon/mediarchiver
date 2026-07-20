import glob
import os
import re
from functools import cache
from typing import Optional

from mediarchiver.common.tool import IMAGE_EXT_LIST
from mediarchiver.rename.brand_rules.base import SidecarRename
from mediarchiver.rename.metadata import FileMetadataContext


@cache
def _live_photo_mov_lookup(folder_path):
    """Build a 4-digit-num -> mov_file_path lookup for Live Photo pairing."""
    pattern = re.compile(r"(\d{4})\.mov$", re.IGNORECASE)
    lookup = {}
    for file_name in sorted(glob.glob(os.path.join(folder_path, "*"))):
        match = pattern.search(os.path.basename(file_name))
        if match is None:
            continue
        lookup.setdefault(match.group(1), file_name)
    return lookup


def live_photo_match_mov(folder_path, filter_num):
    """Return the Live Photo MOV path whose 4-digit number matches *filter_num*."""
    return _live_photo_mov_lookup(folder_path).get(filter_num)


@cache
def _live_photo_image_lookup(folder_path):
    pattern_str = rf"(\d{{4}})\.({'|'.join(IMAGE_EXT_LIST)})$".replace(" ", "")
    pattern = re.compile(pattern_str, re.IGNORECASE)
    lookup = {}
    for file_name in sorted(glob.glob(os.path.join(folder_path, "*"))):
        match = pattern.search(file_name)
        if match is None:
            continue
        lookup.setdefault(match.group(1), file_name)
    return lookup


def live_photo_match_image(folder_path, filter_num):
    return _live_photo_image_lookup(folder_path).get(filter_num)


class AppleLivePhotoRule:
    name = "apple_live_photo"

    def format_device_unit(self, context: FileMetadataContext, device_tag: str) -> Optional[str]:
        metadata = context.exif_metadata or {}
        if not _is_apple_media(metadata, device_tag):
            return device_tag
        specific_device = _specific_apple_device(metadata)
        if specific_device is None:
            return None
        device_tag = specific_device
        if _is_screenshot(metadata):
            return f"{device_tag}-Screenshot"
        if _is_front_camera(metadata):
            return f"{device_tag}-Selfie"
        return device_tag

    def filter_image_tech_tags(self, context: FileMetadataContext, tags: list[str]) -> list[str]:
        metadata = context.exif_metadata or {}
        if _is_apple_media(metadata, "") and _is_screenshot(metadata):
            return [tag for tag in tags if tag != "CS"]
        return tags

    def find_sidecars(
        self,
        source_dir: str,
        context: FileMetadataContext,
        new_file_name: str,
    ) -> list[SidecarRename]:
        if not context.is_image:
            return []

        from mediarchiver.rename.rules import file_number

        img_num = file_number(context.file_path)
        if img_num is None:
            return []
        mov_path = live_photo_match_mov(source_dir, img_num)
        if mov_path is None:
            return []

        new_file_name_stem = os.path.splitext(new_file_name)[0]
        new_mov_path = os.path.join(
            source_dir,
            new_file_name_stem + os.path.splitext(mov_path)[1],
        )
        return [SidecarRename(source=mov_path, destination=new_mov_path)]


def _is_apple_media(metadata, device_tag):
    if device_tag in ("MiPh", "MiPad"):
        return True
    return any(
        _contains(value, ["apple", "iphone", "ipad"])
        for value in (
            metadata.get("Make"),
            metadata.get("Model"),
            metadata.get("DeviceModelName"),
        )
    )


def _specific_apple_device(metadata):
    for value in (metadata.get("Model"), metadata.get("DeviceModelName")):
        if not _contains(value, ["iphone", "ipad"]):
            continue
        device = re.sub(r"[^A-Za-z0-9]+", "", str(value))
        if device:
            return device
    return None


def _is_screenshot(metadata):
    return _contains(metadata.get("UserComment"), ["screenshot"])


def _is_front_camera(metadata):
    return any(
        _contains(value, ["front", "true"])
        for value in (
            metadata.get("LensID"),
            metadata.get("LensModel"),
            metadata.get("CameraPosition"),
            metadata.get("SelfieCamera"),
        )
    )


def _contains(text, keywords):
    if text is None:
        return False
    normalized = str(text).lower()
    return any(keyword.lower() in normalized for keyword in keywords)
