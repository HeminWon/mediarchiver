from mediarchiver.rename.inventory import SourceInventory
from mediarchiver.rename.metadata import FileMetadataContext
from mediarchiver.rename.plan import RenamePlanItem
from mediarchiver.rename.rule import RuleFileSet
from mediarchiver.rename.rules.apple.detectors import has_apple_marker, has_screenshot_marker
from mediarchiver.rename.rules.apple.presets.iphone import PRESET as IPHONE_PRESET
from mediarchiver.rename.rules.apple.presets.screenshot import PRESET as SCREENSHOT_PRESET


class BaseAppleRule:
    required_tools = ("exiftool", "ffprobe")
    preset = None

    def collect_files(self, inventory: SourceInventory) -> RuleFileSet:
        return RuleFileSet(
            source_dir=inventory.source_dir,
            media_paths=list(inventory.media_paths),
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
            match_reasons = self.match(context)
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

    def match(self, context: FileMetadataContext) -> tuple[str, ...]:
        raise NotImplementedError


class AppleIPhoneRule(BaseAppleRule):
    id = "apple:iphone"
    label = "Apple iPhone"
    description = "Apple iPhone media rename rule"
    priority = 50
    preset = IPHONE_PRESET

    def match(self, context: FileMetadataContext) -> tuple[str, ...]:
        return match_apple_iphone(context)


class AppleScreenshotRule(BaseAppleRule):
    id = "apple:screenshot"
    label = "Apple Screenshot"
    description = "Apple screenshot PNG rename rule"
    priority = 100
    preset = SCREENSHOT_PRESET

    def match(self, context: FileMetadataContext) -> tuple[str, ...]:
        return match_apple_screenshot(context)


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


def match_apple_screenshot(context: FileMetadataContext) -> tuple[str, ...]:
    if is_apple_screenshot(context):
        return ("metadata=apple_screenshot",)
    return ()


def is_apple_screenshot(context: FileMetadataContext) -> bool:
    metadata = context.exif_metadata or {}
    return context.extension.lower() == ".png" and has_screenshot_marker(
        metadata
    ) and has_apple_marker(metadata)


RULES = (AppleIPhoneRule(), AppleScreenshotRule())
