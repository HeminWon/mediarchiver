import hashlib
import re
from pathlib import Path

from mediarchiver.rename.rule_builder import RenameRuleError

HASH_SAMPLE_SIZE = 1024 * 1024


def fallback_original_id(file_path: str):
    filename_id = trailing_four_digits(file_path)
    if filename_id is not None:
        return filename_id, "filename:trailing_digits"

    hash_id = sampled_content_hash_id(file_path)
    if hash_id is not None:
        return hash_id, "content_hash:full_or_first_1m"

    raise RenameRuleError("missing_original_id", {"file_name": Path(file_path).name})


def trailing_four_digits(file_path: str):
    stem = Path(file_path).stem
    match = re.search(r"(\d{4})$", stem)
    return match.group(1) if match else None


def sampled_content_hash_id(file_path: str):
    path = Path(file_path)
    if not path.is_file():
        return None

    digest = hashlib.sha256()
    with path.open("rb") as file:
        digest.update(file.read(HASH_SAMPLE_SIZE))
    return f"{int.from_bytes(digest.digest()[:8], 'big') % 10000:04d}"
