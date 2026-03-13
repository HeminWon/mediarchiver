import json
import logging
import os
import re

from mediarchiver.common.external import (
    CommandLoadResult,
    ExternalToolError,
    build_command_load_error,
    map_external_tool_error_code,
    run_json_command,
)

VIDEO_EXT_LIST = ["mp4", "m4v", "avi", "mov"]
IMAGE_EXT_LIST = ["jpg", "png", "mpg", "bmp", "jpeg", "heic", "dng", "arw", "gif"]
FILE_EXT_LIST = VIDEO_EXT_LIST + IMAGE_EXT_LIST


def is_valid_date(text):
    if not isinstance(text, str) or len(text) == 0:
        return False
    pattern = r"\b\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2})?\b"
    match = re.fullmatch(pattern, text)
    return bool(match)


def is_IMG(filename):
    f, e = os.path.splitext(filename)
    ext = e[1:]
    return ext.lower() in IMAGE_EXT_LIST


def is_VID(filename):
    f, e = os.path.splitext(filename)
    ext = e[1:]
    return ext.lower() in VIDEO_EXT_LIST


def is_live_photo_VID(filename):
    """
    Determining if it is a livephoto through exif.
    """
    metadata = get_metadata(filename)
    return is_live_photo_video_from_metadata(filename, metadata)


def is_live_photo_video_from_metadata(filename, metadata):
    if metadata is None:
        return None
    liveP = metadata.get(
        "LivePhotoVitalityScore",
        metadata.get("LivePhotoVitalityScoringVersion", metadata.get("ContentIdentifier", None)),
    )
    if liveP is None:
        return False
    f, e = os.path.splitext(filename)
    ext = e[1:]
    return liveP is not None and ext.lower() in ["mov"]


def get_metadata(file_path):
    return load_metadata_result(file_path).data


def load_metadata_result(file_path):
    try:
        cmd = ["exiftool", "-j", file_path]
        output = run_json_command(cmd, "exiftool")
        if not output:
            raise ExternalToolError("exiftool", "Command returned empty JSON payload.")
        metadata = output[0]
    except (ExternalToolError, IndexError, TypeError, json.JSONDecodeError) as e:
        logging.error(f"{file_path} {e}")
        error_code = map_external_tool_error_code(e)
        if error_code == "tool_error":
            error_code = "invalid_output"
        return build_command_load_error("exiftool", error_code, str(e))
    return CommandLoadResult(tool_name="exiftool", data=metadata)


def get_media_date(filename):
    metadata = get_metadata(filename)
    return get_media_date_from_metadata(metadata)


def get_media_date_from_metadata(metadata):
    if metadata is None:
        return None
    date = metadata.get(
        "DateTimeOriginal",
        metadata.get(
            "CreateDate",
            metadata.get(
                "CreationDate",
                metadata.get(
                    "MediaCreateDate",
                    metadata.get("DateCreated", metadata.get("FileInodeChangeDate", None)),
                ),
            ),
        ),
    )
    return date if is_valid_date(date) else None
