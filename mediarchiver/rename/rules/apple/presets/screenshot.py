from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.naming import first_formatted_metadata_date
from mediarchiver.rename.original_id import fallback_original_id
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule_builder import RenameRuleError
from mediarchiver.rename.rule_builder import build_media_plan_item as build_standard_media_plan_item

DEVICE_UNIT = "Apple"
TECH_TAGS = "Screenshot"


class AppleScreenshotPreset:
    id = "screenshot"
    label = "Apple Screenshot"
    device_unit = DEVICE_UNIT

    def build_media_item(
        self,
        source_dir: str,
        context: FileMetadataContext,
        match_reasons: tuple[str, ...],
    ) -> RenamePlanItem:
        item = build_media_plan_item(source_dir, context)
        item.details["rule_match"] = list(match_reasons)
        return item


PRESET = AppleScreenshotPreset()


def build_media_plan_item(source_dir: str, context: FileMetadataContext) -> RenamePlanItem:
    return build_standard_media_plan_item(source_dir, context, build_new_file_name)


def build_new_file_name(context: FileMetadataContext):
    date, date_source = format_required_date(context)
    original_id, original_id_source = fallback_original_id(context.file_path)
    file_name = "_".join([date, DEVICE_UNIT, TECH_TAGS, original_id]) + context.extension
    return file_name, {
        "required": {
            "date": date,
            "date_source": date_source,
            "device_unit": DEVICE_UNIT,
            "device_unit_source": "rule",
            "original_id": original_id,
            "original_id_source": original_id_source,
        },
        "optional": {
            "tech_tags": TECH_TAGS,
            "missing": [],
        },
    }


def format_required_date(context: FileMetadataContext):
    date, date_source = first_formatted_metadata_date(
        context.exif_metadata,
        (
            "SubSecDateTimeOriginal",
            "DateTimeOriginal",
            "CreateDate",
            "DateCreated",
            "CreationDate",
        ),
    )
    if date is not None:
        return date, date_source
    raise RenameRuleError("missing_date", {"file_name": context.file_name})
