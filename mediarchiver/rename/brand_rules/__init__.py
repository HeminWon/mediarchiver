from dataclasses import replace
from typing import Optional

from mediarchiver.rename.brand_rules.apple import AppleLivePhotoRule
from mediarchiver.rename.brand_rules.base import BrandRule, SidecarRename
from mediarchiver.rename.brand_rules.dji import DjiSidecarRule
from mediarchiver.rename.brand_rules.gopro import GoproSidecarRule
from mediarchiver.rename.brand_rules.sony import SonyXmlSidecarRule
from mediarchiver.rename.metadata import FileMetadataContext

BRAND_RULES: tuple[BrandRule, ...] = (
    SonyXmlSidecarRule(),
    AppleLivePhotoRule(),
    DjiSidecarRule(),
    GoproSidecarRule(),
)
SIDECAR_RULES = BRAND_RULES


def find_sidecar_renames(
    source_dir: str,
    context: FileMetadataContext,
    new_file_name: str,
) -> list[SidecarRename]:
    renames = []
    for rule in BRAND_RULES:
        for sidecar in rule.find_sidecars(source_dir, context, new_file_name):
            renames.append(
                replace(
                    sidecar,
                    rule_name=sidecar.rule_name or rule.name,
                    paired_with=sidecar.paired_with or context.file_path,
                )
            )
    return renames


def format_device_unit(context: FileMetadataContext, device_tag: str) -> Optional[str]:
    formatted = device_tag
    for rule in BRAND_RULES:
        formatter = getattr(rule, "format_device_unit", None)
        if formatter is not None:
            formatted = formatter(context, formatted)
            if formatted is None:
                return None
    return formatted


def filter_image_tech_tags(context: FileMetadataContext, tags: list[str]) -> list[str]:
    filtered = tags
    for rule in BRAND_RULES:
        tag_filter = getattr(rule, "filter_image_tech_tags", None)
        if tag_filter is not None:
            filtered = tag_filter(context, filtered)
    return filtered
