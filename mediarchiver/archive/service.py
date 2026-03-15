import logging
import os
import shutil

from tqdm import tqdm

from mediarchiver.common.reporting import OperationLogger
from mediarchiver.common.tool import (
    FILE_EXT_LIST,
    get_media_date_from_metadata,
    load_metadata_result,
)
from mediarchiver.common.workers import map_with_workers, resolve_worker_count

MAX_METADATA_PREFETCH_WORKERS = 4


def prefetch_archive_metadata(file_paths, workers=None):
    return map_with_workers(
        file_paths,
        get_archive_metadata_error,
        requested_workers=workers,
        default_max_workers=MAX_METADATA_PREFETCH_WORKERS,
    )


def get_archive_metadata_error(file_path):
    metadata_result = load_metadata_result(file_path)
    if metadata_result.ok:
        return None, get_media_date_from_metadata(metadata_result.data)
    return {
        "reason": f"exiftool_{metadata_result.error_code}",
        "details": {"message": metadata_result.error_message},
    }, None


def get_quarter(date):
    if date is None:
        return None
    month = int(date[5:7])
    if month in [1, 2, 3]:
        return "Q1"
    if month in [4, 5, 6]:
        return "Q2"
    if month in [7, 8, 9]:
        return "Q3"
    if month in [10, 11, 12]:
        return "Q4"
    return None


def archive_obj(
    folder_path, target_path, obj, dry_run=False, report_logger=None, metadata_cache=None
):
    file_path = os.path.join(folder_path, obj)
    if os.path.isdir(file_path):
        if report_logger is not None:
            report_logger.record("archive", file_path, status="skipped", reason="directory")
        return
    ext = os.path.splitext(obj)[1][1:]
    if ext.lower() not in FILE_EXT_LIST:
        if report_logger is not None:
            report_logger.record(
                "archive", file_path, status="skipped", reason="unsupported_extension"
            )
        return

    if metadata_cache is not None and file_path in metadata_cache:
        metadata_error, date = metadata_cache[file_path]
    else:
        metadata_error, date = get_archive_metadata_error(file_path)
    if metadata_error is not None:
        if report_logger is not None:
            report_logger.record(
                "archive",
                file_path,
                status="skipped",
                reason=metadata_error["reason"],
                details=metadata_error["details"],
            )
        return

    if date is None:
        logging.error(f"date is invalid: {obj}")
        if report_logger is not None:
            report_logger.record("archive", file_path, status="skipped", reason="invalid_date")
        return

    year = date[:4]
    quarter = get_quarter(date)
    if quarter is None:
        if report_logger is not None:
            report_logger.record("archive", file_path, status="skipped", reason="invalid_quarter")
        return

    subfolder_path = os.path.join(target_path, year, quarter)
    target_file_path = os.path.join(subfolder_path, obj)

    if os.path.exists(target_file_path):
        logging.warning(
            f"File already exists, can not move {obj} from {file_path} to {target_file_path}"
        )
        if report_logger is not None:
            report_logger.record(
                "archive",
                file_path,
                destination=target_file_path,
                status="conflict",
                reason="destination_exists",
            )
        return

    if dry_run:
        if report_logger is not None:
            report_logger.record(
                "archive",
                file_path,
                destination=target_file_path,
                status="preview",
                reason="dry_run",
            )
        return

    try:
        os.makedirs(subfolder_path, exist_ok=True)
        shutil.move(file_path, subfolder_path)
        logging.info(f"Moved {obj} from {file_path} to {target_file_path}")
        if report_logger is not None:
            report_logger.record(
                "archive", file_path, destination=target_file_path, status="success"
            )
    except OSError as exc:
        logging.exception("archive move failed: %s", file_path)
        if report_logger is not None:
            report_logger.record(
                "archive",
                file_path,
                destination=target_file_path,
                status="skipped",
                reason="move_failed",
                details={"message": str(exc)},
            )


def sort_files(folder_path, target_path, dry_run=False, workers=None):
    report_logger = OperationLogger(folder_path, "archive")
    if not os.path.isdir(folder_path):
        raise ValueError(f"source directory does not exist: {folder_path}")
    try:
        objects = sorted(os.listdir(folder_path))
    except PermissionError as exc:
        raise PermissionError(f"cannot read source directory: {folder_path}") from exc
    metadata_cache = prefetch_archive_metadata(
        [
            os.path.join(folder_path, obj)
            for obj in objects
            if os.path.isfile(os.path.join(folder_path, obj))
            and os.path.splitext(obj)[1][1:].lower() in FILE_EXT_LIST
        ],
        workers=workers,
    )
    process_objs = tqdm(objects)
    for obj in process_objs:
        process_objs.set_description("Processing " + obj)
        archive_obj(
            folder_path,
            target_path,
            obj,
            dry_run=dry_run,
            report_logger=report_logger,
            metadata_cache=metadata_cache,
        )
    process_objs.close()
    return report_logger.summary.as_dict()
