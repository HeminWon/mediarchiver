from enum import Enum
from pathlib import Path


class SonyMediaKind(Enum):
    VIDEO = "video"
    PHOTO = "photo"


VIDEO_SUFFIXES = {".mp4", ".mov"}
PHOTO_SUFFIXES = {".arw", ".jpg", ".jpeg"}


def media_kind_from_suffix(file_path: str) -> SonyMediaKind | None:
    suffix = Path(file_path).suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        return SonyMediaKind.VIDEO
    if suffix in PHOTO_SUFFIXES:
        return SonyMediaKind.PHOTO
    return None
