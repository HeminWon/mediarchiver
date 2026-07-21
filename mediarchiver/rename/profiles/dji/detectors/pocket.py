import os
import re
from dataclasses import dataclass
from pathlib import Path

from mediarchiver.common.tool import is_vid
from mediarchiver.rename.metadata import FileMetadataContext

DJI_FILENAME_PATTERN = re.compile(r"^DJI_\d{14}_\d{4}_.+\.[^.]+$", re.IGNORECASE)
DJI_SIDE_SUFFIXES = {".lrf"}


@dataclass(frozen=True)
class PocketMatch:
    matched: bool
    reasons: tuple[str, ...] = ()


class PocketDetector:
    family = "pocket"

    def candidate_media_path(self, file_path: str) -> bool:
        base = os.path.basename(file_path)
        return is_vid(file_path) and DJI_FILENAME_PATTERN.match(base) is not None

    def candidate_sidecar_path(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in DJI_SIDE_SUFFIXES

    def match_media(self, context: FileMetadataContext) -> PocketMatch:
        reasons = []
        if self.candidate_media_path(context.file_path):
            reasons.append("filename=dji_timestamp_id_pattern")
        metadata = context.exif_metadata or {}
        if metadata_contains_dji(metadata):
            reasons.append("metadata=dji")
        return PocketMatch(bool(reasons), tuple(reasons))


def metadata_contains_dji(metadata: dict) -> bool:
    fields = (
        "Make",
        "Model",
        "Software",
        "DjiCameraColorGammaSxS",
        "DjiCameraColorMode",
    )
    values = [str(metadata.get(field, "")) for field in fields if metadata.get(field) is not None]
    if any("dji" in value.lower() for value in values):
        return True
    return any(field in metadata for field in ("DjiCameraColorGammaSxS", "DjiCameraColorMode"))
