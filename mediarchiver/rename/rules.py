import re


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
