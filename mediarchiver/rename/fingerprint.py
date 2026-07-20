import hashlib
import os
from functools import lru_cache

FINGERPRINT_SMALL_FILE_THRESHOLD = 16 * 1024 * 1024
FINGERPRINT_SAMPLE_BYTES = 1024 * 1024


def _file_cache_key(filename):
    absolute_path = os.path.abspath(filename)
    stat_result = os.stat(absolute_path)
    return (
        absolute_path,
        stat_result.st_ino,
        stat_result.st_size,
        stat_result.st_mtime_ns,
    )


@lru_cache(maxsize=1024)
def _get_file_md5_cached(cache_key):
    filename, _, _, _ = cache_key
    md5 = hashlib.md5()
    with open(filename, "rb") as file_obj:
        while True:
            data = file_obj.read(8192)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()


def get_file_md5(filename):
    return _get_file_md5_cached(_file_cache_key(filename))


@lru_cache(maxsize=1024)
def _get_content_fingerprint_cached(cache_key):
    filename, file_size, _, _ = cache_key
    digest = hashlib.blake2b(digest_size=6)
    digest.update(str(file_size).encode("ascii"))
    with open(filename, "rb") as file_obj:
        if file_size <= FINGERPRINT_SMALL_FILE_THRESHOLD:
            while True:
                data = file_obj.read(8192)
                if not data:
                    break
                digest.update(data)
        else:
            digest.update(file_obj.read(FINGERPRINT_SAMPLE_BYTES))
            file_obj.seek(max(file_size - FINGERPRINT_SAMPLE_BYTES, 0))
            digest.update(file_obj.read(FINGERPRINT_SAMPLE_BYTES))
    return digest.hexdigest().upper()


def get_content_fingerprint(filename):
    return _get_content_fingerprint_cached(_file_cache_key(filename))


def content_fingerprint_id(filename):
    fingerprint = get_content_fingerprint(filename)
    return f"{int(fingerprint, 16) % 10000:04d}"


def clear_fingerprint_cache():
    _get_content_fingerprint_cached.cache_clear()
    _get_file_md5_cached.cache_clear()


# Backward-compatible names for callers that still import the old MD5 helpers.
get_md5 = get_file_md5
clear_md5_cache = clear_fingerprint_cache
