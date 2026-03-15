import json
import logging
import os
import re
from datetime import datetime, timedelta

from mediarchiver.common.external import (
    CommandLoadResult,
    ExternalToolError,
    build_command_load_error,
    map_external_tool_error_code,
    run_json_command,
)

VIDEO_EXT_LIST = ["mp4", "m4v", "avi", "mov", "mpg"]
IMAGE_EXT_LIST = ["jpg", "png", "bmp", "jpeg", "heic", "dng", "arw", "gif"]
FILE_EXT_LIST = VIDEO_EXT_LIST + IMAGE_EXT_LIST

SONY_XML_PATTERN = re.compile(r"^(.+)(M\d+\.XML)$", re.IGNORECASE)


def is_sony_xml(filename):
    """Return True if the file is a SONY sidecar XML (e.g. C0212M01.XML, C0212M02.XML)."""
    return bool(SONY_XML_PATTERN.match(os.path.basename(filename)))


def sony_xml_video_stem(filename):
    """
    Given a SONY XML filename, return (video_stem, suffix) tuple.
    e.g. 'C0212M01.XML' -> ('C0212', 'M01.XML')
         'C0212M02.XML' -> ('C0212', 'M02.XML')
    Returns None if not a SONY XML file.
    """
    name = os.path.basename(filename)
    match = SONY_XML_PATTERN.match(name)
    if match:
        return match.group(1), match.group(2)
    return None


def is_valid_date(text):
    if not isinstance(text, str) or len(text) == 0:
        return False
    pattern = r"\b\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2})?\b"
    match = re.fullmatch(pattern, text)
    return bool(match)


def parse_time_offset(offset_str):
    """
    解析 ±HH:MM 格式的时间偏移字符串，返回总分钟数。
    例如: "+8:00" -> 480, "-5:30" -> -330, "+5:45" -> 345
    """
    if offset_str is None:
        return None
    pattern = r"^([+-])(\d{1,2}):(\d{2})$"
    match = re.fullmatch(pattern, offset_str.strip())
    if not match:
        raise ValueError(
            f"invalid time offset format: '{offset_str}', expected ±HH:MM (e.g. +8:00, -5:30)"
        )
    sign = 1 if match.group(1) == "+" else -1
    hours = int(match.group(2))
    minutes = int(match.group(3))
    if minutes >= 60:
        raise ValueError(f"invalid minutes in time offset: '{offset_str}'")
    return sign * (hours * 60 + minutes)


def apply_time_offset_to_date(date_str, offset_minutes):
    """
    对 EXIF 日期字符串（格式：YYYY:MM:DD HH:MM:SS）应用分钟偏移，
    返回同格式字符串。
    """
    if date_str is None or offset_minutes is None or offset_minutes == 0:
        return date_str
    dt_part = re.match(r"\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2}", date_str)
    if not dt_part:
        return date_str
    try:
        dt = datetime.strptime(dt_part.group(), "%Y:%m:%d %H:%M:%S")
        dt = dt + timedelta(minutes=offset_minutes)
        return dt.strftime("%Y:%m:%d %H:%M:%S")
    except ValueError:
        return date_str


def is_IMG(filename):
    f, e = os.path.splitext(filename)
    ext = e[1:]
    return ext.lower() in IMAGE_EXT_LIST


def is_VID(filename):
    f, e = os.path.splitext(filename)
    ext = e[1:]
    return ext.lower() in VIDEO_EXT_LIST


def is_live_photo_video_from_metadata(filename, metadata):
    if metadata is None:
        return False
    liveP = metadata.get(
        "LivePhotoVitalityScore",
        metadata.get("LivePhotoVitalityScoringVersion", metadata.get("ContentIdentifier", None)),
    )
    if liveP is None:
        return False
    f, e = os.path.splitext(filename)
    ext = e[1:]
    return ext.lower() in ["mov"]


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
