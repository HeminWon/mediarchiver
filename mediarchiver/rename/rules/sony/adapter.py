import os
import re

from mediarchiver.common.tool import is_vid
from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.naming import is_formatted_file_name
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule import RuleFileSet
from mediarchiver.rename.rules.sony.presets.a7m4 import PRESET as A7M4_PRESET

SONY_CLIP_PATTERN = re.compile(r"^C\d{4}\.(?:MP4|MOV)$", re.IGNORECASE)
SONY_XML_PATTERN = re.compile(r"^C\d{4}M\d{2}\.XML$", re.IGNORECASE)


class SonyA7M4Rule:
    id = "sony:a7m4"
    label = "Sony A7M4"
    description = "Sony A7M4 XAVC media rename rule"
    priority = 50
    required_tools = ("exiftool", "ffprobe")

    def __init__(self):
        self.preset = A7M4_PRESET

    def collect_files(self, source_dir: str, include_formatted: bool = False) -> RuleFileSet:
        media_paths = []
        sidecar_paths = []
        for name in sorted(os.listdir(source_dir)):
            file_path = os.path.join(source_dir, name)
            if not os.path.isfile(file_path):
                continue
            if not include_formatted and is_formatted_file_name(name):
                continue
            if SONY_XML_PATTERN.match(name):
                sidecar_paths.append(file_path)
                continue
            if is_vid(file_path) and SONY_CLIP_PATTERN.match(name):
                media_paths.append(file_path)
        return RuleFileSet(
            source_dir=source_dir,
            media_paths=media_paths,
            sidecar_paths=sidecar_paths,
        )

    def build_plan_items(
        self,
        source_dir: str,
        contexts: dict[str, FileMetadataContext],
        file_set: RuleFileSet,
    ) -> list[RenamePlanItem]:
        items = []
        primary_items_by_id = {}
        for media_path in file_set.media_paths:
            context = contexts[media_path]
            match_reasons = match_sony_a7m4(context)
            if not match_reasons:
                items.append(
                    RenamePlanItem(
                        source=media_path,
                        destination=None,
                        action="rename",
                        status="skipped",
                        reason="rule_not_matched",
                        details={"rule": self.id},
                    )
                )
                continue
            item = self.preset.build_media_item(source_dir, context, match_reasons)
            items.append(item)
            original_id = self.preset.original_id_from_name(context.file_name)
            if original_id is not None:
                primary_items_by_id[original_id] = item

        for sidecar_path in file_set.sidecar_paths:
            items.append(self.preset.build_xml_item(sidecar_path, primary_items_by_id))
        return items


def match_sony_a7m4(context: FileMetadataContext) -> tuple[str, ...]:
    metadata = context.exif_metadata or {}
    reasons = []
    manufacturer = str(metadata.get("DeviceManufacturer", "")).strip().lower()
    model_name = str(metadata.get("DeviceModelName", "")).strip().lower()
    major_brand = str(metadata.get("MajorBrand", "")).strip().lower()
    if manufacturer == "sony":
        reasons.append("metadata=device_manufacturer_sony")
    if model_name == "ilce-7m4":
        reasons.append("metadata=device_model_ilce_7m4")
    if major_brand == "xavc":
        reasons.append("metadata=major_brand_xavc")
    return tuple(reasons) if "metadata=device_model_ilce_7m4" in reasons else ()


RULE = SonyA7M4Rule()
