import logging

from src.common.external import ExternalToolError, run_json_command


def get_metadata_ff(file_path):
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
        return run_json_command(cmd, "ffprobe")
    except ExternalToolError as exc:
        logging.error(f"{file_path} {exc}")
        return None


def get_video_metadate_ff(metadata):
    streams = metadata.get("streams", None)
    if streams is None:
        return None
    v_ss = [stream for stream in streams if stream.get("codec_type") == "video"]
    if len(v_ss) == 0:
        return None
    return v_ss[0]
