import glob
import hashlib
import logging
import os
import re
from decimal import Decimal
from functools import lru_cache

from mediarchiver.common.tool import (
    FILE_EXT_LIST,
    IMAGE_EXT_LIST,
    VIDEO_EXT_LIST,
    apply_time_offset_to_date,
    is_sony_xml,
    sony_xml_video_stem,
)
from mediarchiver.rename.metadata import (
    FileMetadataContext,
    build_file_metadata_context,
    get_video_metadata_ff,
)
from mediarchiver.rename.options import RenameOptions


@lru_cache(maxsize=1024)
def _get_md5_cached(cache_key):
    filename, _, _, _ = cache_key
    md5 = hashlib.md5()
    with open(filename, "rb") as file_obj:
        while True:
            data = file_obj.read(8192)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()


def _get_md5_cache_key(filename):
    absolute_path = os.path.abspath(filename)
    stat_result = os.stat(absolute_path)
    return (
        absolute_path,
        stat_result.st_ino,
        stat_result.st_size,
        stat_result.st_mtime_ns,
    )


def get_md5(filename):
    return _get_md5_cached(_get_md5_cache_key(filename))


def clear_md5_cache():
    _get_md5_cached.cache_clear()


def is_formatted_file_name(filename):
    if filename is None:
        return False
    return re.match(r"^\d{8}-\d{6}_([a-zA-Z0-9.-]+_)?\d{4}\.[a-zA-Z0-9]+$", filename) is not None


def contains_keywords(text, keywords):
    if text is None:
        return False
    return any(keyword.lower() in text.lower() for keyword in keywords)


def live_photo_match_image(folder_path, filter_num):
    return _live_photo_image_lookup(folder_path).get(filter_num)


@lru_cache(maxsize=None)
def _sony_xml_video_lookup(folder_path):
    """Build a stem -> video_file_path lookup for SONY XML pairing."""
    pattern = re.compile(
        r"^(.+)\.(" + "|".join(VIDEO_EXT_LIST) + r")$", re.IGNORECASE
    )
    lookup = {}
    for file_name in sorted(glob.glob(os.path.join(folder_path, "*"))):
        match = pattern.search(os.path.basename(file_name))
        if match is None:
            continue
        lookup.setdefault(match.group(1).upper(), file_name)
    return lookup


def sony_xml_match_video(folder_path, xml_file):
    result = sony_xml_video_stem(xml_file)
    if result is None:
        return None
    stem, _ = result
    return _sony_xml_video_lookup(folder_path).get(stem.upper())


@lru_cache(maxsize=None)
def _live_photo_image_lookup(folder_path):
    pattern_str = rf"(\d{{4}})\.({'|'.join(IMAGE_EXT_LIST)})$".replace(" ", "")
    pattern = re.compile(pattern_str, re.IGNORECASE)
    lookup = {}
    for file_name in sorted(glob.glob(os.path.join(folder_path, "*"))):
        match = pattern.search(file_name)
        if match is None:
            continue
        lookup.setdefault(match.group(1), file_name)
    return lookup


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
    hex_dig = get_md5(file_name)
    decimal_dig = int(hex_dig, 16)
    str_digits = f"{decimal_dig}"
    last_four_digits_str = str_digits[-4:]
    return last_four_digits_str if len(last_four_digits_str) == 4 else None


MAKE_MODEL_TAG_RULES = [
    (["Apple", "iPhone"], "iPh"),
    (["iPad"], "iPad"),
    (["xiaomi", "mi"], "MI"),
    (["SONY", "ILCE", "ILME", "ZV-E", "ZV-1", "RX"], "SON"),
    (["CANON"], "CAN"),
    (["NIKON"], "NIK"),
    (["casio"], "CAS"),
    (["GoPro", "HERO10", "HERO9"], "GoP"),
    (["ZTE"], "ZTE"),
    (["FUJIFILM"], "FUJ"),
    (["Nokia"], "Nokia"),
    (["HUAWEI"], "HUAWEI"),
    (["Smartisan"], "Smartisan"),
    (["Yiruikecorp"], "Yiruikecorp"),
    (["OnePlus"], "OnePlus"),
    (["vivo"], "vivo"),
    (["DJI"], "DJI"),
    (["Hasselblad"], "Hasselblad"),
    (["nubia"], "Nubia"),
]

FF_ENCODER_TAG_RULES = [
    (["h.264", "h264", "avc", "x264", "AVC Coding"], "AVC"),
    (["h.265", "h265", "hevc", "x265", "HEVC Coding"], "HEVC"),
]

FF_LOG_TAG_RULES = [(["DOVI"], "DOVI")]

RESOLUTION_TAGS = {
    (720, 480): "SD",
    (1280, 720): "HD",
    (1920, 1080): "FHD",
    (2048, 1080): "2K",
    (3840, 2160): "4K",
    (7680, 4320): "8K",
}


def match_keyword_rules(value, rules):
    for keywords, normalized_tag in rules:
        if contains_keywords(value, keywords):
            return normalized_tag
    return None


def deal_with_m(make_or_model):
    normalized_tag = match_keyword_rules(make_or_model, MAKE_MODEL_TAG_RULES)
    if normalized_tag is not None:
        return "M" + normalized_tag
    raise ValueError(f"convert failure: {make_or_model}")


def tag_m(metadata):
    make = metadata.get("Make", None)
    if make is not None:
        return deal_with_m(make)
    model = metadata.get("Model", None)
    if model is not None:
        return deal_with_m(model)
    device_model = metadata.get("DeviceModelName", None)
    if device_model is not None:
        return deal_with_m(device_model)
    return None


def tag_c(metadata):
    tag = ""
    comment = metadata.get("UserComment", None)
    if contains_keywords(comment, ["Screenshot"]):
        tag = tag + "S"
    return "C" + tag if len(tag) > 0 else None


def tag_l(metadata):
    lens = metadata.get("LensID", None)
    if lens is None:
        return None
    if contains_keywords(lens, ["front"]):
        lens = "F"
    else:
        return None
    return "L" + lens


def calculate_resolution(width, height):
    if width is None or height is None:
        return None
    return RESOLUTION_TAGS.get((width, height), f"{width}x{height}")


def tag_ff_resolution(metadata):
    video_stream = get_video_metadata_ff(metadata)
    if video_stream is None:
        return None
    return calculate_resolution(video_stream.get("width", None), video_stream.get("height", None))


def remove_exponent(num):
    return num.to_integral() if num == num.to_integral() else num.normalize()


def tag_ff_frame_rate(metadata):
    video_stream = get_video_metadata_ff(metadata)
    if video_stream is None:
        return None
    fps = video_stream.get("avg_frame_rate", None)
    if fps is None:
        return None
    items = fps.split("/")
    if items and len(items) == 2:
        denominator = int(items[0])
        numerator = int(items[1])
        if numerator == 0:
            return None
        result = denominator / numerator
        result = Decimal(f"{result}").quantize(Decimal("0.00"))
        result = remove_exponent(result)
        return f"{result}FPS"
    return None


def tag_ff_log(metadata):
    video_stream = get_video_metadata_ff(metadata)
    if video_stream is None:
        return None
    side_list = video_stream.get("side_data_list", None)
    if side_list is None:
        return None
    side_data = side_list[0] if len(side_list) > 0 else None
    if side_data is None:
        return None
    data_type = side_data.get("side_data_type", None)
    return match_keyword_rules(data_type, FF_LOG_TAG_RULES)


def tag_ff_encoder(metadata):
    video_stream = get_video_metadata_ff(metadata)
    if video_stream is None:
        return None
    tags = video_stream.get("tags", None)
    if tags is None:
        return None
    encoder = tags.get("encoder", None)
    if encoder is None:
        return None
    normalized_tag = match_keyword_rules(encoder, FF_ENCODER_TAG_RULES)
    if normalized_tag is not None:
        return normalized_tag
    formatted_encoder = encoder.strip()
    if len(formatted_encoder) > 0:
        raise ValueError(f"encoder convert failure: {encoder}")
    return None


def formatted_tags(filename, options=None):
    options = options or RenameOptions()
    context = ensure_file_context(filename)
    if context.is_live_photo_video:
        raise ValueError(f"livephoto rename failure: {context.file_path}")
    if context.is_image:
        return formatted_tags_img(context)
    if context.is_video:
        return formatted_tags_vid(context, options)
    return None


def formatted_tags_vid(filename, options=None):
    options = options or RenameOptions()
    context = ensure_file_context(filename)
    file_path = context.file_path
    metadata_ff = context.ffprobe_metadata
    if metadata_ff is None:
        return None
    metadata = context.exif_metadata
    if metadata is None:
        return None
    tags = []
    make = tag_m(metadata)
    if make is None:
        if options.loose is False:
            logging.error(f"[exiftool] make is invalid: {file_path}")
            return None
    else:
        tags.append(make)
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
    file_path = context.file_path
    metadata = context.exif_metadata
    if metadata is None:
        return None
    tags = []
    make = tag_m(metadata)
    if make is not None:
        tags.append(make)
    else:
        logging.warning(f"[exiftool] make is invalid: {file_path}")
    lens = tag_l(metadata)
    if lens is not None:
        tags.append(lens)
    comment = tag_c(metadata)
    if comment is not None:
        tags.append(comment)
    return "-".join(tags) if len(tags) > 0 else None


def formatted_date(date):
    matches = re.search(r"\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2}", date)
    return str(matches.group()).replace(":", "").replace(" ", "-") if matches else None


def need_ignore_file(folder_path, obj, options=None):
    options = options or RenameOptions()
    file_path = os.path.join(folder_path, obj)
    if os.path.isdir(file_path):
        return True
    if is_sony_xml(obj):
        return False
    _, ext = os.path.splitext(obj)
    if ext[1:].lower() not in FILE_EXT_LIST:
        return True
    if options.include_formatted is False and is_formatted_file_name(obj):
        return True
    return False


def ensure_file_context(file_or_context):
    if isinstance(file_or_context, FileMetadataContext):
        return file_or_context
    return build_file_metadata_context(file_or_context)


def generate_new_filename_prefix(folder_path, obj=None, options=None):
    options = options or RenameOptions()
    if isinstance(folder_path, FileMetadataContext):
        context = folder_path
        obj = context.file_name
    else:
        if obj is None:
            raise ValueError("obj is required when folder_path is not a FileMetadataContext")
        context = build_file_metadata_context(os.path.join(folder_path, obj))
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
    tags = formatted_tags(context, options)
    if tags is None:
        if options.loose is False:
            logging.error(f"tags is invalid: {obj}")
            return None
    else:
        items.append(tags)
    number = file_number(context.file_path, True)
    if number is None:
        logging.error(f"number is invalid: {obj}")
        return None
    items.append(number)
    return "_".join(items)


def generate_new_filename(folder_path, obj=None, options=None, context_provider=None):
    options = options or RenameOptions()
    if isinstance(folder_path, FileMetadataContext):
        context = folder_path
        obj = context.file_name
    else:
        if obj is None:
            raise ValueError("obj is required when folder_path is not a FileMetadataContext")
        context = build_file_metadata_context(os.path.join(folder_path, obj))
    ext = context.extension
    if context.is_live_photo_video:
        live_photo_num = file_number(context.file_path)
        if live_photo_num is None:
            logging.error(f"livephoto number is error, file: {obj}")
            return None
        target_file = live_photo_match_image(os.path.dirname(context.file_path), live_photo_num)
        if target_file is None:
            logging.error(f"livephoto not found match image, file: {obj}")
            return None
        provider = context_provider or build_file_metadata_context
        target_prefix = generate_new_filename_prefix(provider(target_file), options=options)
        return target_prefix + ext if target_prefix is not None else None
    if is_sony_xml(context.file_path):
        target_video = sony_xml_match_video(os.path.dirname(context.file_path), context.file_name)
        if target_video is None:
            logging.error(f"sony xml not found match video, file: {obj}")
            return None
        provider = context_provider or build_file_metadata_context
        target_prefix = generate_new_filename_prefix(provider(target_video), options=options)
        if target_prefix is None:
            return None
        _, suffix = sony_xml_video_stem(context.file_name)
        return target_prefix + suffix
    prefix = generate_new_filename_prefix(context, options=options)
    return prefix + ext if prefix is not None else None
