import re
from decimal import Decimal, InvalidOperation

RENAME_CAPTURE_DATE_FIELDS = (
    "SubSecDateTimeOriginal",
    "DateTimeOriginal",
    "CreateDate",
    "DateCreated",
    "CreationDate",
    "CreationDateValue",
)


def is_formatted_file_name(filename):
    if filename is None:
        return False
    return bool(re.match(r"^\d{8}-\d{6}_.*_\d{4}", filename))


def formatted_date(date):
    if date is None:
        return None
    match = re.search(r"\d{4}[:\-]\d{2}[:\-]\d{2}[T\s]\d{2}:\d{2}:\d{2}", date)
    if match is None:
        return None
    return match.group().replace(":", "").replace("-", "").replace("T", "-").replace(" ", "-")


def first_formatted_metadata_date(metadata, fields=RENAME_CAPTURE_DATE_FIELDS):
    metadata = metadata or {}
    for field in fields:
        formatted = formatted_date(metadata.get(field))
        if formatted is not None:
            return formatted, f"metadata:{field}"
    return None, None


def formatted_fps(frame_rate):
    if not frame_rate:
        return None
    try:
        numerator, denominator = frame_rate.split("/", 1)
        denominator_int = int(denominator)
        if denominator_int == 0:
            return None
        fps = Decimal(numerator) / Decimal(denominator_int)
    except (ValueError, InvalidOperation):
        return None

    value = fps.quantize(Decimal("0.01")).normalize()
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text
