import os
from dataclasses import dataclass

from mediarchiver.rename.metadata import FileMetadataContext, get_context_load_error
from mediarchiver.rename.plan import RenamePlanItem


@dataclass(frozen=True)
class RenameRuleError(ValueError):
    reason: str
    details: dict

    def __str__(self):
        return self.reason


def build_media_plan_item(source_dir: str, context: FileMetadataContext, build_name):
    load_error = get_context_load_error(context)
    if load_error is not None:
        return RenamePlanItem(
            source=context.file_path,
            destination=None,
            action="rename",
            status="skipped",
            reason=load_error["reason"],
            details=load_error.get("details") or {},
        )

    try:
        new_file_name, details = build_name(context)
    except RenameRuleError as exc:
        return RenamePlanItem(
            source=context.file_path,
            destination=None,
            action="rename",
            status="invalid",
            reason=exc.reason,
            details=exc.details,
        )

    destination = os.path.join(source_dir, new_file_name)
    if destination == context.file_path:
        return RenamePlanItem(
            source=context.file_path,
            destination=destination,
            action="rename",
            status="skipped",
            reason="already_named",
            details=details,
        )
    if os.path.exists(destination):
        return RenamePlanItem(
            source=context.file_path,
            destination=destination,
            action="rename",
            status="conflict",
            reason="destination_exists",
            details=details,
        )
    return RenamePlanItem(
        source=context.file_path,
        destination=destination,
        action="rename",
        status="ready",
        details=details,
    )
