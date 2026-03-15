import logging
import os


def configure_logging(log_file):
    log_path = os.path.abspath(log_file)
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )
    return log_path
