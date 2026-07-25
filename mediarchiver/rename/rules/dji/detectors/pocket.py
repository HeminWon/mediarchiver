import os
import re
from dataclasses import dataclass
from pathlib import Path

from mediarchiver.common.tool import is_vid
from mediarchiver.rename.metadata import FileMetadataContext

DJI_FILENAME_PATTERN = re.compile(r"^DJI_\d{14}_\d{4}_.+\.[^.]+$", re.IGNORECASE)
DJI_SIDE_SUFFIXES = {".lrf"}
DJI_METADATA_FIELDS = (
    "Encoder",
    "Category",
    "DjiCameraCameraModel",
    "DjiCameraCameraSerialNumber",
    "DjiCameraSupVersion",
    "DjiCameraLensType",
    "DjiCameraColorGammaSxS",
    "DjiCameraExposureIndexAsa",
    "DjiCameraWhiteBalanceKelvin",
    "DjiCameraWhiteBalanceTintCc",
)
POCKET4P_METADATA_FIELDS = (
    "Encoder",
    "Category",
    "DjiCameraCameraModel",
)
POCKET4P_MARKERS = (
    "osmo pocket 4p",
    "dvtm_osmo_pocket_4",
    "PP-041",
)


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
        if metadata_contains_pocket4p(metadata):
            reasons.append("metadata=pocket4p")
        required_reasons = {
            "metadata=dji",
            "metadata=pocket4p",
        }
        return PocketMatch(required_reasons.issubset(reasons), tuple(reasons))


def metadata_contains_dji(metadata: dict) -> bool:
    values = [
        str(metadata.get(field, ""))
        for field in DJI_METADATA_FIELDS
        if metadata.get(field) is not None
    ]
    if any("dji" in value.lower() for value in values):
        return True
    return any(field in metadata for field in DJI_METADATA_FIELDS if field.startswith("DjiCamera"))


def metadata_contains_pocket4p(metadata: dict) -> bool:
    values = [
        normalize_model_marker(str(metadata.get(field, "")))
        for field in POCKET4P_METADATA_FIELDS
        if metadata.get(field) is not None
    ]
    markers = [normalize_model_marker(marker) for marker in POCKET4P_MARKERS]
    return any(marker in value for value in values for marker in markers)


def normalize_model_marker(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())
