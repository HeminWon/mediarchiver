import re
from pathlib import Path

from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.rules.detectors.base import BaseDetector
from mediarchiver.rename.rules.sony.media import SonyMediaKind, media_kind_from_suffix

SONY_XML_PATTERN = re.compile(r"^C\d{4}M\d{2}\.XML$", re.IGNORECASE)
SONY_PHOTO_SIDECAR_PATTERN = re.compile(r"^DSC\d+\.(?:XMP|ACR)$", re.IGNORECASE)


class SonyA7M4Detector(BaseDetector):
    def candidate_sidecar_path(self, file_path: str) -> bool:
        name = Path(file_path).name
        return (
            SONY_XML_PATTERN.match(name) is not None
            or SONY_PHOTO_SIDECAR_PATTERN.match(name) is not None
        )

    def match_media(self, context: FileMetadataContext) -> tuple[str, ...]:
        metadata = context.exif_metadata or {}
        media_kind = media_kind_from_suffix(context.file_path)
        if media_kind == SonyMediaKind.PHOTO:
            return self._match_photo(metadata)
        if media_kind == SonyMediaKind.VIDEO:
            return self._match_video(metadata)
        return ()

    def _match_photo(self, metadata: dict) -> tuple[str, ...]:
        reasons = []
        make = str(metadata.get("Make", "")).strip().lower()
        model = str(metadata.get("Model", "")).strip().lower()
        if make == "sony":
            reasons.append("metadata=make_sony")
        if model == "ilce-7m4":
            reasons.append("metadata=model_ilce_7m4")
        return tuple(reasons) if "metadata=model_ilce_7m4" in reasons else ()

    def _match_video(self, metadata: dict) -> tuple[str, ...]:
        reasons = []
        manufacturer = str(metadata.get("DeviceManufacturer", "")).strip().lower()
        model_name = str(metadata.get("DeviceModelName", "")).strip().lower()
        major_brand = str(metadata.get("MajorBrand", "")).strip().lower()
        if manufacturer == "sony":
            reasons.append("metadata=device_manufacturer_sony")
        if model_name == "ilce-7m4":
            reasons.append("metadata=device_model_ilce_7m4")
        if major_brand == "xavc":
            reasons.append("metadata=major_brand_xavc")
        return tuple(reasons) if "metadata=device_model_ilce_7m4" in reasons else ()
