import os

from mediarchiver.common.tool import is_img, is_vid
from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.naming import is_formatted_file_name
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule import RuleFileSet
from mediarchiver.rename.rules.apple.presets.iphone import PRESET as IPHONE_PRESET


class AppleIPhoneRule:
    id = "apple:iphone"
    label = "Apple iPhone"
    description = "Apple iPhone media rename rule"
    required_tools = ("exiftool", "ffprobe")

    def __init__(self):
        self.preset = IPHONE_PRESET

    def collect_files(self, source_dir: str, include_formatted: bool = False) -> RuleFileSet:
        media_paths = []
        for name in sorted(os.listdir(source_dir)):
            file_path = os.path.join(source_dir, name)
            if not os.path.isfile(file_path):
                continue
            if not include_formatted and is_formatted_file_name(name):
                continue
            if is_img(file_path) or is_vid(file_path):
                media_paths.append(file_path)
        return RuleFileSet(
            source_dir=source_dir,
            media_paths=media_paths,
            sidecar_paths=[],
        )

    def build_plan_items(
        self,
        source_dir: str,
        contexts: dict[str, FileMetadataContext],
        file_set: RuleFileSet,
    ) -> list[RenamePlanItem]:
        items = []
        for media_path in file_set.media_paths:
            context = contexts[media_path]
            match_reasons = match_apple_iphone(context)
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
            items.append(self.preset.build_media_item(source_dir, context, match_reasons))
        return items


def match_apple_iphone(context: FileMetadataContext) -> tuple[str, ...]:
    metadata = context.exif_metadata or {}
    reasons = []
    make = str(metadata.get("Make", "")).strip().lower()
    model = str(metadata.get("Model", "")).strip().lower()
    host = str(metadata.get("HostComputer", "")).strip().lower()
    if make == "apple":
        reasons.append("make=apple")
    if model.startswith("iphone"):
        reasons.append("model=iphone")
    if host.startswith("iphone"):
        reasons.append("host=iphone")
    return tuple(reasons) if any(reason.endswith("=iphone") for reason in reasons) else ()


RULE = AppleIPhoneRule()
