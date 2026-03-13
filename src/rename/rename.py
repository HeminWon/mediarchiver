from src.rename.cli import build_parser, main
from src.rename.metadata import get_metadata_ff, get_video_metadate_ff
from src.rename.options import RenameOptions
from src.rename.rules import (
    calculate_resolution,
    contains_keywords,
    deal_with_m,
    exist_filter_file,
    file_number,
    formated_tags_IMG,
    formated_tags_VID,
    formatted_date,
    formatted_tags,
    generate_new_filename,
    generate_new_filename_prefix,
    get_date,
    get_md5,
    is_formatted_file_name,
    live_photo_match_image,
    need_ignore_file,
    remove_exponent,
    tag_c,
    tag_ff_encoder,
    tag_ff_frame_rate,
    tag_ff_log,
    tag_ff_resolutation,
    tag_l,
    tag_m,
)
from src.rename.service import list_md5, scan_dir

__all__ = [
    "RenameOptions",
    "build_parser",
    "calculate_resolution",
    "contains_keywords",
    "deal_with_m",
    "exist_filter_file",
    "file_number",
    "formated_tags_IMG",
    "formated_tags_VID",
    "formatted_date",
    "formatted_tags",
    "generate_new_filename",
    "generate_new_filename_prefix",
    "get_date",
    "get_md5",
    "get_metadata_ff",
    "get_video_metadate_ff",
    "is_formatted_file_name",
    "list_md5",
    "live_photo_match_image",
    "main",
    "need_ignore_file",
    "remove_exponent",
    "scan_dir",
    "tag_c",
    "tag_ff_encoder",
    "tag_ff_frame_rate",
    "tag_ff_log",
    "tag_ff_resolutation",
    "tag_l",
    "tag_m",
]


if __name__ == "__main__":
    main()
