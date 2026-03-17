import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from mediarchiver.common.external import (
    CommandLoadResult,
    ExternalToolError,
    build_command_load_error,
    map_external_tool_error_code,
    run_json_command,
)
from mediarchiver.common.tool import (
    get_media_date_from_metadata,
    is_img,
    is_live_photo_video_from_metadata,
    is_vid,
    load_metadata_result,
)


def load_ffprobe_metadata_result(file_path):
    try:
        cmd = [
            "ffprobe",
            "-loglevel",
            "quiet",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            file_path,
        ]
        return CommandLoadResult(
            tool_name="ffprobe",
            data=run_json_command(cmd, "ffprobe"),
        )
    except ExternalToolError as exc:
        logging.error(f"{file_path} {exc}")
        return build_command_load_error(
            "ffprobe",
            map_external_tool_error_code(exc),
            str(exc),
        )


def get_video_metadata_ff(metadata):
    streams = metadata.get("streams", None)
    if streams is None:
        return None
    v_ss = [stream for stream in streams if stream.get("codec_type") == "video"]
    if len(v_ss) == 0:
        return None
    return v_ss[0]


@dataclass(frozen=True)
class FileMetadataContext:
    file_path: str
    exif_result: CommandLoadResult
    ffprobe_result: Optional[CommandLoadResult]
    exif_metadata: Optional[dict[str, Any]]
    ffprobe_metadata: Optional[dict[str, Any]]
    media_date: Optional[str]
    is_image: bool
    is_video: bool
    is_live_photo_video: bool

    @property
    def file_name(self):
        return Path(self.file_path).name

    @property
    def extension(self):
        return Path(self.file_path).suffix


def build_file_metadata_context(file_path):
    is_image = is_img(file_path)
    is_video = is_vid(file_path)
    ffprobe_result = None
    ffprobe_metadata = None

    exif_result = load_metadata_result(file_path)
    if is_video:
        ffprobe_result = load_ffprobe_metadata_result(file_path)
        ffprobe_metadata = ffprobe_result.data

    exif_metadata = exif_result.data

    return FileMetadataContext(
        file_path=file_path,
        exif_result=exif_result,
        ffprobe_result=ffprobe_result,
        exif_metadata=exif_metadata,
        ffprobe_metadata=ffprobe_metadata,
        media_date=get_media_date_from_metadata(exif_metadata),
        is_image=is_image,
        is_video=is_video,
        is_live_photo_video=is_live_photo_video_from_metadata(file_path, exif_metadata),
    )


def get_context_load_error(context):
    if not context.exif_result.ok:
        return {
            "reason": f"exiftool_{context.exif_result.error_code}",
            "details": {"message": context.exif_result.error_message},
        }
    if context.is_video and context.ffprobe_result is not None and not context.ffprobe_result.ok:
        return {
            "reason": f"ffprobe_{context.ffprobe_result.error_code}",
            "details": {"message": context.ffprobe_result.error_message},
        }
    return None
