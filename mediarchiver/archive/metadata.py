from mediarchiver.common.progress_map import map_with_progress
from mediarchiver.common.tool import get_media_date_from_metadata, load_metadata_result


def prefetch_archive_metadata(file_paths):
    return map_with_progress(
        file_paths,
        get_archive_metadata_error,
    )


def get_archive_metadata_error(file_path):
    metadata_result = load_metadata_result(file_path)
    if metadata_result.ok:
        return None, get_media_date_from_metadata(metadata_result.data)
    return {
        "reason": f"exiftool_{metadata_result.error_code}",
        "details": {"message": metadata_result.error_message},
    }, None


def get_cached_archive_date(file_path, metadata_cache=None):
    if metadata_cache is not None and file_path in metadata_cache:
        return metadata_cache[file_path]
    return get_archive_metadata_error(file_path)
