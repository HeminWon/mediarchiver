import logging
import os

from tqdm import tqdm

from src.common.reporting import OperationLogger
from src.rename.metadata import build_file_metadata_context, get_context_load_error
from src.rename.options import RenameOptions
from src.rename.rules import (
    generate_new_filename,
    get_md5,
    is_formatted_file_name,
    need_ignore_file,
)


def list_md5(file_path):
    if not os.path.exists(file_path):
        return set()
    md5s = set()
    with open(file_path, "r", encoding="utf-8") as file_obj:
        for line in file_obj:
            items = line.split("<=", -1)
            if items:
                md5s.add(items[0].strip())
    return md5s


def scan_dir(source, options=None):
    options = options or RenameOptions()
    info_file = os.path.join(source, "rename_info.txt")
    report_logger = OperationLogger(source, "rename")
    md5s = list_md5(info_file)
    context_cache = {}

    open(info_file, "a", encoding="utf-8").close()

    def get_file_context(file_path):
        context = context_cache.get(file_path)
        if context is None:
            context = build_file_metadata_context(file_path)
            context_cache[file_path] = context
        return context

    with open(info_file, "a", encoding="utf-8") as file_txt:
        process_objs = tqdm(os.listdir(source))
        for obj in process_objs:
            process_objs.set_description("Processing " + obj)
            file_path = os.path.join(source, obj)
            if need_ignore_file(source, obj, options):
                report_logger.record("rename", file_path, status="skipped", reason="ignored")
                continue

            file_context = get_file_context(file_path)
            load_error = get_context_load_error(file_context)
            if load_error is not None:
                report_logger.record(
                    "rename",
                    file_path,
                    status="skipped",
                    reason=load_error["reason"],
                    details=load_error["details"],
                )
                continue
            new_file_name = generate_new_filename(
                file_context,
                options=options,
                context_provider=get_file_context,
            )
            if new_file_name is None:
                report_logger.record("rename", file_path, status="skipped", reason="rule_rejected")
                continue
            if is_formatted_file_name(new_file_name) is False:
                logging.error(f"formated file name is error: {obj} => {new_file_name}")
                report_logger.record(
                    "rename",
                    file_path,
                    status="skipped",
                    reason="invalid_generated_name",
                    details={"generated_name": new_file_name},
                )
                continue

            new_file_path = os.path.join(source, new_file_name)
            if os.path.exists(new_file_path):
                logging.warning(f"File already exists, can not rename {obj} => {new_file_name}")
                report_logger.record(
                    "rename",
                    file_path,
                    destination=new_file_path,
                    status="conflict",
                    reason="destination_exists",
                )
                continue

            md5 = get_md5(file_path)
            if options.include_formatted is False and md5 in md5s:
                logging.warning(
                    f"md5 already exists, can not rename {obj} => {new_file_name} => {md5}"
                )
                report_logger.record(
                    "rename",
                    file_path,
                    destination=new_file_path,
                    status="conflict",
                    reason="duplicate_md5",
                    details={"md5": md5},
                )
                continue

            if options.should_apply_changes is False:
                logging.info(f"preview rename: {md5} <= {new_file_name} <= {obj}")
                report_logger.record(
                    "rename",
                    file_path,
                    destination=new_file_path,
                    status="preview",
                    reason="dry_run" if options.dry_run else "rename_disabled",
                    details={"md5": md5},
                )
                continue

            logging.info("rename: " + file_path + " => " + new_file_path)
            file_txt.write(f"{md5} <= {new_file_name} <= {obj}\n")
            md5s.add(md5)
            os.rename(file_path, new_file_path)
            report_logger.record(
                "rename",
                file_path,
                destination=new_file_path,
                status="success",
                details={"md5": md5},
            )
        process_objs.close()
    return report_logger.summary.as_dict()
