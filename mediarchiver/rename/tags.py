from decimal import Decimal

from mediarchiver.rename.metadata import get_video_metadata_ff

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


def contains_keywords(text, keywords):
    if text is None:
        return False
    return any(keyword.lower() in text.lower() for keyword in keywords)


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
    if not side_list:
        return None
    for side_data in side_list:
        data_type = side_data.get("side_data_type", None)
        result = match_keyword_rules(data_type, FF_LOG_TAG_RULES)
        if result is not None:
            return result
    return None


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
