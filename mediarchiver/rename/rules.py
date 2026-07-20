import logging
import os
import re
from typing import Optional, Union

from mediarchiver.common.tool import (
    FILE_EXT_LIST,
    apply_time_offset_to_date,
    is_sony_xml,
)
from mediarchiver.rename import fingerprint
from mediarchiver.rename import tags as tag_rules
from mediarchiver.rename.brand_rules import apple as apple_brand_rules
from mediarchiver.rename.brand_rules import filter_image_tech_tags, format_device_unit
from mediarchiver.rename.brand_rules import sony as sony_brand_rules
from mediarchiver.rename.metadata import (
    FileMetadataContext,
    build_file_metadata_context,
)
from mediarchiver.rename.options import RenameOptions

_live_photo_image_lookup = apple_brand_rules._live_photo_image_lookup
_live_photo_mov_lookup = apple_brand_rules._live_photo_mov_lookup
live_photo_match_image = apple_brand_rules.live_photo_match_image
live_photo_match_mov = apple_brand_rules.live_photo_match_mov
_sony_xml_lookup_by_video_stem = sony_brand_rules._sony_xml_lookup_by_video_stem
sony_xml_match_xmls = sony_brand_rules.sony_xml_match_xmls

FINGERPRINT_SAMPLE_BYTES = fingerprint.FINGERPRINT_SAMPLE_BYTES
FINGERPRINT_SMALL_FILE_THRESHOLD = fingerprint.FINGERPRINT_SMALL_FILE_THRESHOLD
clear_fingerprint_cache = fingerprint.clear_fingerprint_cache
content_fingerprint_id = fingerprint.content_fingerprint_id
get_content_fingerprint = fingerprint.get_content_fingerprint
get_file_md5 = fingerprint.get_file_md5
get_md5 = get_file_md5
clear_md5_cache = clear_fingerprint_cache

MAKE_MODEL_TAG_RULES = tag_rules.MAKE_MODEL_TAG_RULES
FF_ENCODER_TAG_RULES = tag_rules.FF_ENCODER_TAG_RULES
FF_LOG_TAG_RULES = tag_rules.FF_LOG_TAG_RULES
RESOLUTION_TAGS = tag_rules.RESOLUTION_TAGS
calculate_resolution = tag_rules.calculate_resolution
contains_keywords = tag_rules.contains_keywords
deal_with_m = tag_rules.deal_with_m
match_keyword_rules = tag_rules.match_keyword_rules
remove_exponent = tag_rules.remove_exponent
tag_c = tag_rules.tag_c
tag_ff_encoder = tag_rules.tag_ff_encoder
tag_ff_frame_rate = tag_rules.tag_ff_frame_rate
tag_ff_log = tag_rules.tag_ff_log
tag_ff_resolution = tag_rules.tag_ff_resolution
tag_l = tag_rules.tag_l
tag_m = tag_rules.tag_m


def is_formatted_file_name(filename):
    if filename is None:
        return False
    return bool(re.match(r"^\d{8}-\d{6}_.*_\d{4}", filename))


def generated_original_id(file_name):
    return original_id_details(file_name)["value"]


def original_id_details(file_name):
    original_id = file_number(file_name)
    if original_id is not None:
        return {"value": original_id, "source": "filename"}
    return {"value": content_fingerprint_id(file_name), "source": "content_fingerprint"}


def file_number(file_name, try_hash=False):
    filename_nopath = os.path.basename(file_name)
    filename_noext, _ = os.path.splitext(filename_nopath)
    rm = re.search(r"\d{8}[-_]\d{6}", filename_noext)
    file_name_rm = filename_noext
    if rm:
        file_name_rm = filename_noext.replace(rm.group(), "").strip()
    match = re.search(r"\d{4}(?=\D*$)", file_name_rm)
    if match:
        num_str = match.group()
        return num_str if len(num_str) == 4 else None
    if try_hash is False:
        return None
    return content_fingerprint_id(file_name)


def formatted_tags(filename, options=None):
    options = options or RenameOptions()
    context = ensure_file_context(filename)
    device = formatted_device_unit(context, options)
    tech = formatted_tech_tags(context, options)
    tags = [tag for tag in (device, tech) if tag is not None]
    return "-".join(tags) if len(tags) > 0 else None


def formatted_device_unit(filename, options=None):
    options = options or RenameOptions()
    context = ensure_file_context(filename)
    metadata = context.exif_metadata
    if metadata is None:
        return None
    device = tag_m(metadata)
    if device is None:
        if options.loose is False:
            logging.error(f"[exiftool] make is invalid: {context.file_path}")
        return None
    return format_device_unit(context, device)


def formatted_tech_tags(filename, options=None):
    options = options or RenameOptions()
    context = ensure_file_context(filename)
    if context.is_image:
        return formatted_tags_img(context)
    if context.is_video:
        return formatted_tags_vid(context, options)
    return None


def filename_field_details(filename, options=None):
    options = options or RenameOptions()
    context = ensure_file_context(filename)
    details = {
        "required": {
            "date": None,
            "device_unit": None,
            "original_id": None,
            "original_id_source": None,
        },
        "optional": {
            "tech_tags": None,
            "missing": [],
        },
        "missing_required": [],
    }

    date = context.media_date
    if date is not None and options.time_offset_minutes is not None:
        date = apply_time_offset_to_date(date, options.time_offset_minutes)
    formatted = formatted_date(date) if date is not None else None
    if formatted is None:
        details["missing_required"].append("date")
    else:
        details["required"]["date"] = formatted

    device = formatted_device_unit(context, options)
    if device is None:
        details["missing_required"].append("device_unit")
    else:
        details["required"]["device_unit"] = device

    original_id = original_id_details(context.file_path)
    if original_id["value"] is None:
        details["missing_required"].append("original_id")
    else:
        details["required"]["original_id"] = original_id["value"]
        details["required"]["original_id_source"] = original_id["source"]

    tech_tags = formatted_tech_tags(context, options)
    details["optional"]["tech_tags"] = tech_tags
    details["optional"]["missing"] = missing_optional_fields(context, tech_tags)
    return details


def missing_optional_fields(filename, tech_tags=None):
    context = ensure_file_context(filename)
    if not context.is_video:
        return []
    if context.ffprobe_metadata is None:
        return ["tech_tags"]

    missing = []
    if tag_ff_resolution(context.ffprobe_metadata) is None:
        missing.append("resolution")
    if tag_ff_frame_rate(context.ffprobe_metadata) is None:
        missing.append("frame_rate")
    if tag_ff_log(context.ffprobe_metadata) is None:
        missing.append("log")
    try:
        encoder = tag_ff_encoder(context.ffprobe_metadata)
    except ValueError:
        encoder = None
    if encoder is None:
        missing.append("codec")
    if tech_tags is None and not missing:
        missing.append("tech_tags")
    return missing


def formatted_tags_vid(file_or_context, options=None):
    options = options or RenameOptions()
    context = ensure_file_context(file_or_context)
    file_path = context.file_path
    metadata_ff = context.ffprobe_metadata
    if metadata_ff is None:
        return None
    metadata = context.exif_metadata
    if metadata is None:
        return None
    tags = []
    resolution = tag_ff_resolution(metadata_ff)
    if resolution is None:
        logging.error(f"[ffmpeg] resolution is invalid: {file_path}")
        return None
    tags.append(resolution)
    fps = tag_ff_frame_rate(metadata_ff)
    if fps is None:
        logging.error(f"[ffmpeg] fps is invalid: {file_path}")
        return None
    tags.append(fps)
    log_tag = tag_ff_log(metadata_ff)
    if log_tag is None:
        logging.warning(f"[ffmpeg] log/raw is invalid: {file_path}")
    else:
        tags.append(log_tag)
    encoder = tag_ff_encoder(metadata_ff)
    if encoder is None:
        if options.loose is False:
            logging.error(f"[ffmpeg] encoder is invalid: {file_path}")
            return None
    else:
        tags.append(encoder)
    return "-".join(tags) if len(tags) > 0 else None


def formatted_tags_img(filename):
    context = ensure_file_context(filename)
    metadata = context.exif_metadata
    if metadata is None:
        return None
    tags = []
    comment = tag_c(metadata)
    if comment is not None:
        tags.append(comment)
    tags = filter_image_tech_tags(context, tags)
    return "-".join(tags) if len(tags) > 0 else None


def formatted_date(date):
    matches = re.search(r"\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2}", date)
    return str(matches.group()).replace(":", "").replace(" ", "-") if matches else None


def need_ignore_file(folder_path, obj, options=None, context=None):
    options = options or RenameOptions()
    file_path = os.path.join(folder_path, obj)
    if os.path.isdir(file_path):
        return True
    if is_sony_xml(obj):
        return True
    _, ext = os.path.splitext(obj)
    ext_lower = ext[1:].lower()
    if ext_lower not in FILE_EXT_LIST:
        return True
    if ext_lower == "mov":
        ctx = context if context is not None else build_file_metadata_context(file_path)
        if ctx.is_live_photo_video:
            return True
    if options.include_formatted is False and is_formatted_file_name(obj):
        return True
    return False


def ensure_file_context(file_or_context):
    if isinstance(file_or_context, FileMetadataContext):
        return file_or_context
    return build_file_metadata_context(file_or_context)


def generate_new_filename_prefix(
    folder_path_or_context: "Union[str, FileMetadataContext]",
    obj: "Optional[str]" = None,
    options: "Optional[RenameOptions]" = None,
) -> "Optional[str]":
    """Generate the new filename prefix (without extension) for a media file.

    Args:
        folder_path_or_context: Either a folder path (str) paired with *obj*, or a
            pre-built :class:`FileMetadataContext` (in which case *obj* is ignored).
        obj: Filename within *folder_path_or_context*. Required when
            *folder_path_or_context* is a plain string path.
        options: Rename options; defaults to :class:`RenameOptions` defaults.
    """
    options = options or RenameOptions()
    if isinstance(folder_path_or_context, FileMetadataContext):
        context = folder_path_or_context
        obj = context.file_name
    else:
        if obj is None:
            raise ValueError(
                "obj is required when folder_path_or_context is not a FileMetadataContext"
            )
        context = build_file_metadata_context(os.path.join(folder_path_or_context, obj))
    date = context.media_date
    if date is None:
        logging.error(f"date is invalid: {obj}")
        return None
    if options.time_offset_minutes is not None:
        date = apply_time_offset_to_date(date, options.time_offset_minutes)
    items = []
    formatted = formatted_date(date)
    if formatted is None:
        return None
    items.append(formatted)
    device = formatted_device_unit(context, options)
    if device is None:
        if options.loose is False:
            logging.error(f"device is invalid: {obj}")
            return None
    else:
        items.append(device)
    tech_tags = formatted_tech_tags(context, options)
    if tech_tags is not None:
        items.append(tech_tags)
    number = generated_original_id(context.file_path)
    if number is None:
        logging.error(f"number is invalid: {obj}")
        return None
    items.append(number)
    return "_".join(items)


def generate_new_filename(
    folder_path_or_context: "Union[str, FileMetadataContext]",
    obj: "Optional[str]" = None,
    options: "Optional[RenameOptions]" = None,
) -> "Optional[str]":
    """Generate the full new filename (with extension) for a media file.

    Args:
        folder_path_or_context: Either a folder path (str) paired with *obj*, or a
            pre-built :class:`FileMetadataContext`.
        obj: Filename within *folder_path_or_context*. Required when a plain path is passed.
        options: Rename options; defaults to :class:`RenameOptions` defaults.
    """
    options = options or RenameOptions()
    if isinstance(folder_path_or_context, FileMetadataContext):
        context = folder_path_or_context
        obj = context.file_name
    else:
        if obj is None:
            raise ValueError(
                "obj is required when folder_path_or_context is not a FileMetadataContext"
            )
        context = build_file_metadata_context(os.path.join(folder_path_or_context, obj))
    ext = context.extension
    prefix = generate_new_filename_prefix(context, options=options)
    return prefix + ext if prefix is not None else None
