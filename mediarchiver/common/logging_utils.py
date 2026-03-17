import logging
import os


def configure_logging(log_dir, log_file):
    log_path = os.path.join(os.path.abspath(log_dir), log_file)
    root_logger = logging.getLogger()

    # Remove any existing file handlers pointing to a different log file to
    # avoid stale handlers accumulating across consecutive rename/archive runs
    # within the same process, while preserving other handler types (e.g. stream).
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            root_logger.removeHandler(handler)
            handler.close()

    if not root_logger.handlers:
        root_logger.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root_logger.addHandler(file_handler)
    return log_path
