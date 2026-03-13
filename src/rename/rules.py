import glob
import hashlib
import logging
import os
import re
from decimal import Decimal

from src.common.tool import (
    FILE_EXT_LIST,
    IMAGE_EXT_LIST,
    get_media_date,
    get_metadata,
    is_IMG,
    is_live_photo_VID,
    is_VID,
)
from src.rename.metadata import get_metadata_ff, get_video_metadate_ff
from src.rename.options import RenameOptions


def get_md5(filename):
    md5 = hashlib.md5()
    with open(filename, "rb") as file_obj:
        while True:
            data = file_obj.read(8192)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()


def is_formatted_file_name(filename):
    if filename is None:
        return False
    return (
        re.match(r"^\d{8}-\d{6}_([a-zA-Z0-9.-]+_)?\d{4}\.[a-zA-Z0-9]+$", filename)
        is not None
    )


def contains_keywords(text, keywords):
    if text is None:
        return False
    return any(keyword.lower() in text.lower() for keyword in keywords)


def live_photo_match_image(folder_path, filter_num):
    pattern_str = rf"{filter_num}\.({'|'.join(IMAGE_EXT_LIST)})$".replace(" ", "")
    pattern = re.compile(pattern_str, re.IGNORECASE)
    image_files = [
        file_name
        for file_name in glob.glob(folder_path + "/*")
        if pattern.search(file_name)
    ]
    return image_files[0] if image_files else None


def exist_filter_file(folder_path, filter_file):
    return len(glob.glob(os.path.join(folder_path, filter_file))) > 0


def file_number(file_name, try_hash=False):
    filename_nopath = os.path.basename(file_name)
    rm = re.search(r"\d{8}[-_]\d{6}", filename_nopath)
    file_name_rm = filename_nopath
    if rm:
        file_name_rm = filename_nopath.replace(rm.group(), "").strip()
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


def deal_with_m(make_or_model):
    if contains_keywords(make_or_model, ["Apple", "iPhone"]):
        make_or_model = "iPh"
    elif contains_keywords(make_or_model, ["iPad"]):
        make_or_model = "iPad"
    elif contains_keywords(make_or_model, ["xiaomi", "mi"]):
        make_or_model = "MI"
    elif contains_keywords(make_or_model, ["SONY"]):
        make_or_model = "SON"
    elif contains_keywords(make_or_model, ["CANON"]):
        make_or_model = "CAN"
    elif contains_keywords(make_or_model, ["NIKON"]):
        make_or_model = "NIK"
    elif contains_keywords(make_or_model, ["casio"]):
        make_or_model = "CAS"
    elif contains_keywords(make_or_model, ["GoPro", "HERO10", "HERO9"]):
        make_or_model = "GoP"
    elif contains_keywords(make_or_model, ["ZTE"]):
        make_or_model = "ZTE"
    elif contains_keywords(make_or_model, ["FUJIFILM"]):
        make_or_model = "FUJ"
    elif contains_keywords(make_or_model, ["Nokia"]):
        make_or_model = "Nokia"
    elif contains_keywords(make_or_model, ["HUAWEI"]):
        make_or_model = "HUAWEI"
    elif contains_keywords(make_or_model, ["Smartisan"]):
        make_or_model = "Smartisan"
    elif contains_keywords(make_or_model, ["Yiruikecorp"]):
        make_or_model = "Yiruikecorp"
    elif contains_keywords(make_or_model, ["OnePlus"]):
        make_or_model = "OnePlus"
    elif contains_keywords(make_or_model, ["vivo"]):
        make_or_model = "vivo"
    elif contains_keywords(make_or_model, ["DJI"]):
        make_or_model = "DJI"
    elif contains_keywords(make_or_model, ["Hasselblad"]):
        make_or_model = "Hasselblad"
    elif contains_keywords(make_or_model, ["nubia"]):
        make_or_model = "Nubia"
    else:
        raise ValueError(f"convert failure: {make_or_model}")
    return "M" + make_or_model


def tag_m(metadata):
    make = metadata.get("Make", None)
    if make is not None:
        return deal_with_m(make)
    model = metadata.get("Model", None)
    if model is not None:
        return deal_with_m(model)
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
    resolutions = {
        (720, 480): "SD",
        (1280, 720): "HD",
        (1920, 1080): "FHD",
        (2048, 1080): "2K",
        (3840, 2160): "4K",
        (7680, 4320): "8K",
    }
    return resolutions.get((width, height), f"{width}x{height}")


def tag_ff_resolutation(metadata):
    video_stream = get_video_metadate_ff(metadata)
    if video_stream is None:
        return None
    return calculate_resolution(
        video_stream.get("width", None), video_stream.get("height", None)
    )


def remove_exponent(num):
    return num.to_integral() if num == num.to_integral() else num.normalize()


def tag_ff_frame_rate(metadata):
    video_stream = get_video_metadate_ff(metadata)
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
    video_stream = get_video_metadate_ff(metadata)
    if video_stream is None:
        return None
    side_list = video_stream.get("side_data_list", None)
    if side_list is None:
        return None
    side_data = side_list[0] if len(side_list) > 0 else None
    if side_data is None:
        return None
    data_type = side_data.get("side_data_type", None)
    if contains_keywords(data_type, ["DOVI"]):
        return "DOVI"
    return None


def tag_ff_encoder(metadata):
    video_stream = get_video_metadate_ff(metadata)
    if video_stream is None:
        return None
    tags = video_stream.get("tags", None)
    if tags is None:
        return None
    encoder = tags.get("encoder", None)
    if encoder is None:
        return None
    if contains_keywords(encoder, ["h.264", "h264", "avc"]):
        formatted_encoder = "AVC"
    elif contains_keywords(encoder, ["h.265", "h265", "hevc"]):
        formatted_encoder = "HEVC"
    else:
        formatted_encoder = encoder.strip()
        if len(formatted_encoder) > 0:
            raise ValueError(f"encoder convert failure: {encoder}")
    return formatted_encoder if len(formatted_encoder) > 0 else None


def formatted_tags(filename, options=None):
    options = options or RenameOptions()
    if is_live_photo_VID(filename):
        raise ValueError(f"livephoto rename failure: {filename}")
    if is_IMG(filename):
        return formated_tags_IMG(filename)
    if is_VID(filename):
        return formated_tags_VID(filename, options)
    return None


def formated_tags_VID(filename, options=None):
    options = options or RenameOptions()
    metadata_ff = get_metadata_ff(filename)
    if metadata_ff is None:
        return None
    metadata = get_metadata(filename)
    if metadata is None:
        return None
    tags = []
    make = tag_m(metadata)
    if make is None:
        if options.loose is False:
            logging.error(f"[exiftool] make is invalid: {filename}")
            return None
    else:
        tags.append(make)
    resolution = tag_ff_resolutation(metadata_ff)
    if resolution is None:
        logging.error(f"[ffmpeg] resolution is invalid: {filename}")
        return None
    tags.append(resolution)
    fps = tag_ff_frame_rate(metadata_ff)
    if fps is None:
        logging.error(f"[ffmpeg] fps is invalid: {filename}")
        return None
    tags.append(fps)
    log_tag = tag_ff_log(metadata_ff)
    if log_tag is None:
        logging.warning(f"[ffmpeg] log/raw is invalid: {filename}")
    else:
        tags.append(log_tag)
    encoder = tag_ff_encoder(metadata_ff)
    if encoder is None:
        if options.loose is False:
            logging.error(f"[ffmpeg] encoder is invalid: {filename}")
            return None
    else:
        tags.append(encoder)
    return "-".join(tags) if len(tags) > 0 else None


def formated_tags_IMG(filename):
    metadata = get_metadata(filename)
    if metadata is None:
        return None
    tags = []
    make = tag_m(metadata)
    if make is not None:
        tags.append(make)
    else:
        logging.warning(f"[exiftool] make is invalid: {filename}")
    lens = tag_l(metadata)
    if lens is not None:
        tags.append(lens)
    comment = tag_c(metadata)
    if comment is not None:
        tags.append(comment)
    return "-".join(tags) if len(tags) > 0 else None


def get_date(filename):
    return get_media_date(filename)


def formatted_date(date):
    matches = re.search(r"\d{4}:\d{2}:\d{2}\s\d{2}:\d{2}:\d{2}", date)
    return str(matches.group()).replace(":", "").replace(" ", "-") if matches else None


def need_ignore_file(folder_path, obj, options=None):
    options = options or RenameOptions()
    file_path = os.path.join(folder_path, obj)
    if os.path.isdir(file_path):
        return True
    _, ext = os.path.splitext(obj)
    if ext[1:].lower() not in FILE_EXT_LIST:
        return True
    if options.include_formatted is False and is_formatted_file_name(obj):
        return True
    return False


def generate_new_filename_prefix(folder_path, obj, options=None):
    options = options or RenameOptions()
    file_path = os.path.join(folder_path, obj)
    date = get_date(file_path)
    if date is None:
        logging.error(f"date is invalid: {obj}")
        return None
    items = []
    formatted = formatted_date(date)
    if formatted is None:
        return None
    items.append(formatted)
    tags = formatted_tags(file_path, options)
    if tags is None:
        if options.loose is False:
            logging.error(f"tags is invalid: {obj}")
            return None
    else:
        items.append(tags)
    number = file_number(file_path, True)
    if number is None:
        logging.error(f"number is invalid: {obj}")
        return None
    items.append(number)
    return "_".join(items)


def generate_new_filename(folder_path, obj, options=None):
    options = options or RenameOptions()
    file_path = os.path.join(folder_path, obj)
    _, ext = os.path.splitext(obj)
    if is_live_photo_VID(file_path):
        live_photo_num = file_number(file_path)
        if live_photo_num is None:
            logging.error(f"livephoto number is error, file: {obj}")
            return None
        target_file = live_photo_match_image(os.path.dirname(file_path), live_photo_num)
        if target_file is None:
            logging.error(f"livephoto not found match image, file: {obj}")
            return None
        target_prefix = generate_new_filename_prefix(
            os.path.dirname(target_file), os.path.basename(target_file), options
        )
        return target_prefix + ext if target_prefix is not None else None
    prefix = generate_new_filename_prefix(folder_path, obj, options)
    return prefix + ext if prefix is not None else None
