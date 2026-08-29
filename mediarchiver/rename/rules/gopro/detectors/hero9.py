import os
import re
from dataclasses import dataclass
from pathlib import Path

from mediarchiver.common.tool import is_vid
from mediarchiver.rename.metadata import FileMetadataContext

GOPRO_VIDEO_PATTERN = re.compile(r"^GX\d{6}\.MP4$", re.IGNORECASE)
GOPRO_PHOTO_PATTERN = re.compile(r"^GOPR\d{4}\.JPE?G$", re.IGNORECASE)
GOPRO_SIDE_SUFFIXES = {".thm"}


@dataclass(frozen=True)
class Hero9Match:
    matched: bool
    reasons: tuple[str, ...] = ()


class Hero9Detector:
    family = "hero9"

    def candidate_media_path(self, file_path: str) -> bool:
        return self.candidate_video_path(file_path) or self.candidate_photo_path(file_path)

    def candidate_video_path(self, file_path: str) -> bool:
        base = os.path.basename(file_path)
        return is_vid(file_path) and GOPRO_VIDEO_PATTERN.match(base) is not None

    def candidate_photo_path(self, file_path: str) -> bool:
        base = os.path.basename(file_path)
        return GOPRO_PHOTO_PATTERN.match(base) is not None

    def candidate_sidecar_path(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in GOPRO_SIDE_SUFFIXES

    def match_media(self, context: FileMetadataContext) -> Hero9Match:
        reasons = []
        if self.candidate_video_path(context.file_path):
            reasons.append("filename=gopro_gx_sequence")
        if self.candidate_photo_path(context.file_path):
            reasons.append("filename=gopro_gopr_photo_sequence")

        metadata = context.exif_metadata or {}
        if metadata_make_is_gopro(metadata):
            reasons.append("metadata=make_gopro")
        if metadata_model_is_hero9(metadata):
            reasons.append("metadata=model_hero9_black")
        if metadata_firmware_is_hero9(metadata):
            reasons.append("metadata=firmware_hd9")
        if ffprobe_has_gopro_telemetry(context.ffprobe_metadata or {}):
            reasons.append("ffprobe=data_stream_gpmd")

        has_candidate_name = any(
            reason in reasons
            for reason in (
                "filename=gopro_gx_sequence",
                "filename=gopro_gopr_photo_sequence",
            )
        )
        matched = (
            has_candidate_name
            and "metadata=model_hero9_black" in reasons
            and any(
                reason in reasons
                for reason in (
                    "metadata=make_gopro",
                    "metadata=firmware_hd9",
                    "ffprobe=data_stream_gpmd",
                )
            )
        )
        return Hero9Match(matched, tuple(reasons))


def metadata_make_is_gopro(metadata: dict) -> bool:
    return str(metadata.get("Make", "")).strip().lower() == "gopro"


def metadata_model_is_hero9(metadata: dict) -> bool:
    model = normalize_model_marker(str(metadata.get("Model", "")))
    return "hero9" in model


def metadata_firmware_is_hero9(metadata: dict) -> bool:
    firmware = str(metadata.get("FirmwareVersion") or metadata.get("Software") or "")
    return firmware.strip().upper().startswith("HD9.")


def ffprobe_has_gopro_telemetry(metadata: dict) -> bool:
    for stream in metadata.get("streams") or []:
        codec_tag = str(stream.get("codec_tag_string", "")).strip().lower()
        handler = str((stream.get("tags") or {}).get("handler_name", "")).strip().lower()
        if codec_tag == "gpmd" or "gopro met" in handler:
            return True
    return False


def normalize_model_marker(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())
